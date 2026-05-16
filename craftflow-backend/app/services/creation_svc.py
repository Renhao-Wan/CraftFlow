"""Creation 业务服务层

封装 Creation Graph 的业务逻辑，包括：
- 任务创建（发起创作流程）
- 任务状态查询
- 任务恢复（HITL 大纲确认后继续执行）

职责边界：
- 管理 thread_id 与 task_id 的映射
- 管理任务元数据（状态、时间戳）
- 调用 Graph 执行业务逻辑
- 不处理 HTTP 请求解析（由 Controller 层负责）
"""

from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.errors import GraphInterrupt
from langgraph.types import Command

from app.adapters.base import BusinessAdapter
from app.core.exceptions import GraphExecutionError, TaskNotFoundError, ValidationError
from app.core.logger import get_logger
from app.graph.creation.builder import get_creation_graph
from app.schemas.response import TaskResponse, TaskStatusResponse
from app.services.checkpointer import cleanup_checkpoint
from app.services.error_formatter import format_error_message

logger = get_logger(__name__)

# 节点中文标签映射（前端展示用）
NODE_LABELS = {
    "planner": "生成大纲",
    "outline_confirmation": "大纲确认",
    "writer": "撰写章节",
    "reducer": "合并润色",
}


class CreationService:
    """Creation 业务服务

    管理创作任务的完整生命周期：创建 → 中断 → 恢复 → 完成。

    Attributes:
        checkpointer: LangGraph Checkpointer 实例
        _graph: 编译后的 Creation Graph（惰性初始化）
        _tasks: 任务元数据存储
    """

    def __init__(self, checkpointer: BaseCheckpointSaver, adapter: BusinessAdapter) -> None:
        """初始化 Creation Service

        Args:
            checkpointer: LangGraph Checkpointer 实例
            adapter: 业务适配器
        """
        self.checkpointer = checkpointer
        self.adapter = adapter
        self._graph = None
        self._tasks: dict[str, dict[str, Any]] = {}

    def _get_graph(self):
        """获取编译后的 Creation Graph（惰性初始化）"""
        if self._graph is None:
            self._graph = get_creation_graph(checkpointer=self.checkpointer)
        return self._graph

    def _generate_task_id(self) -> str:
        """生成唯一任务 ID"""
        return f"creation_{uuid4().hex[:12]}"

    def _save_task(
        self,
        task_id: str,
        thread_id: str,
        status: str,
        request_data: Optional[dict[str, Any]] = None,
    ) -> None:
        """保存任务元数据"""
        self._tasks[task_id] = {
            "task_id": task_id,
            "thread_id": thread_id,
            "graph_type": "creation",
            "status": status,
            "request": request_data,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }

    def _update_task(self, task_id: str, **kwargs) -> None:
        """更新任务元数据"""
        if task_id not in self._tasks:
            raise TaskNotFoundError(task_id=task_id)
        self._tasks[task_id].update(kwargs)
        self._tasks[task_id]["updated_at"] = datetime.now()

    def _build_config(
        self, thread_id: str, max_concurrency: Optional[int] = None
    ) -> dict:
        """构建 LangGraph 执行配置

        Args:
            thread_id: 线程 ID
            max_concurrency: 最大并发数（控制 Send 扇出的并发度）
        """
        config: dict[str, Any] = {"configurable": {"thread_id": thread_id}}
        if max_concurrency is not None:
            config["max_concurrency"] = max_concurrency
        return config

    async def _ensure_default_llm(self) -> None:
        """检查是否存在默认 LLM Profile 且 API Key 有效，否则抛出 ValidationError"""
        profile = await self.adapter.get_llm_profile()
        if profile is None:
            all_profiles = await self.adapter.get_all_llm_profiles()
            if len(all_profiles) == 0:
                raise ValidationError(
                    message="尚未配置 LLM 模型，请先在设置页面添加至少一个 LLM 配置",
                    field="llm_profile",
                )
            else:
                raise ValidationError(
                    message="未设置默认 LLM 配置，请在设置页面将其中一个配置设为默认",
                    field="llm_profile",
                )

        # 检查 API Key 是否有效
        api_key = profile.get("api_key", "")
        if not api_key or not api_key.strip():
            raise ValidationError(
                message="默认 LLM 配置的 API Key 为空，请在设置页面补充 API Key",
                field="llm_api_key",
            )

    async def _persist_interrupted(self, task_id: str) -> None:
        """将中断状态的任务保存到 SQLite

        与 _persist_and_cleanup 的区别：
        - 不清理 checkpoint（恢复时需要图状态）
        - 不从 _tasks dict 移除（恢复时需要元数据）
        - outline 存储在 Checkpointer 中，不保存到 SQLite
        """
        task = self._tasks.get(task_id, {})
        request = task.get("request", {})

        try:
            await self.adapter.save_task(
                {
                    "task_id": task_id,
                    "graph_type": "creation",
                    "status": "interrupted",
                    "topic": request.get("topic"),
                    "description": request.get("description"),
                    "progress": 30.0,
                    "created_at": str(task.get("created_at", datetime.now())),
                    "updated_at": str(datetime.now()),
                }
            )
            logger.info(f"中断任务已持久化 - task_id: {task_id}")
        except Exception as e:
            logger.error(f"持久化中断任务失败 - task_id: {task_id}, error: {e}", exc_info=True)

    async def _persist_and_cleanup(
        self,
        task_id: str,
        thread_id: str,
        status: str,
        result: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        """将终态任务保存到 SQLite 并释放内存

        Args:
            task_id: 任务 ID
            thread_id: thread_id（等于 task_id）
            status: 终态（completed / failed）
            result: 最终结果文本
            error: 错误信息（failed 时）
        """
        task = self._tasks.get(task_id, {})
        request = task.get("request", {})

        # 保存到 SQLite
        logger.info(
            f"持久化创作任务 - task_id: {task_id}, status: {status}, "
            f"result_len: {len(result) if result else 0}, "
            f"topic: {request.get('topic')}, error: {error}"
        )
        try:
            save_data = {
                "task_id": task_id,
                "graph_type": "creation",
                "status": status,
                "topic": request.get("topic"),
                "description": request.get("description"),
                "result": result or "",
                "error": error,
                "progress": 100.0 if status == "completed" else 0.0,
                "created_at": str(task.get("created_at", datetime.now())),
                "updated_at": str(datetime.now()),
            }
            logger.debug(f"保存数据: {save_data}")
            await self.adapter.save_task(save_data)
            logger.info(f"SQLite 保存成功 - task_id: {task_id}")
        except Exception as e:
            logger.error(f"保存任务到 SQLite 失败 - task_id: {task_id}, error: {e}", exc_info=True)

        # 清理 checkpoint 数据
        await cleanup_checkpoint(thread_id)

        # 从 _tasks dict 移除
        self._tasks.pop(task_id, None)

    async def load_interrupted_tasks(self) -> int:
        """从 TaskStore 加载中断任务到内存

        服务重启后，将持久化的 interrupted 任务恢复到 _tasks dict，
        使用户可以继续恢复这些任务。

        Returns:
            加载的任务数量
        """
        interrupted = await self.adapter.get_interrupted_tasks()
        if not interrupted:
            return 0

        loaded = 0
        for row in interrupted:
            if row["graph_type"] != "creation":
                continue

            task_id = row["task_id"]

            # 避免覆盖内存中已有的任务
            if task_id in self._tasks:
                continue

            created_at = row.get("created_at")
            updated_at = row.get("updated_at")

            self._tasks[task_id] = {
                "task_id": task_id,
                "thread_id": task_id,
                "graph_type": "creation",
                "status": "interrupted",
                "request": {
                    "topic": row.get("topic"),
                    "description": row.get("description"),
                },
                "created_at": created_at if isinstance(created_at, datetime) else datetime.now(),
                "updated_at": updated_at if isinstance(updated_at, datetime) else datetime.now(),
            }
            loaded += 1

        if loaded > 0:
            logger.info(f"CreationService 已加载 {loaded} 个中断任务")
        return loaded

    # ============================================
    # 公开 API
    # ============================================

    async def start_task(
        self,
        topic: str,
        description: Optional[str] = None,
    ) -> TaskResponse:
        """创建并启动创作任务

        调用 Creation Graph，执行 PlannerNode 生成大纲后，
        在 outline_confirmation 中断点暂停，等待用户确认。

        Args:
            topic: 创作主题
            description: 创作描述（可选）

        Returns:
            TaskResponse: 包含 task_id 和初始状态

        Raises:
            GraphExecutionError: 图执行失败时抛出
        """
        # 前置检查：确保有默认 LLM Profile
        await self._ensure_default_llm()

        task_id = self._generate_task_id()
        thread_id = task_id  # 使用 task_id 作为 thread_id

        self._save_task(
            task_id=task_id,
            thread_id=thread_id,
            status="running",
            request_data={"topic": topic, "description": description},
        )

        # 从数据库读取运行时配置
        params = await self.adapter.get_writing_params()
        max_outline_sections = int(params.get("max_outline_sections", 5))
        max_concurrent_writers = int(params.get("max_concurrent_writers", 3))

        initial_state = {
            "topic": topic,
            "description": description,
            "outline": [],
            "sections": [],
            "final_draft": None,
            "messages": [],
            "current_node": None,
            "error": None,
            "max_outline_sections": max_outline_sections,
            "max_concurrent_writers": max_concurrent_writers,
        }

        config = self._build_config(thread_id, max_concurrent_writers)
        graph = self._get_graph()

        try:
            logger.info(f"创作任务启动 - task_id: {task_id}, topic: {topic}")

            result = await graph.ainvoke(initial_state, config)

            # 如果 ainvoke 正常返回（无中断），说明图已执行完成
            graph_state = result or {}

            # 检查图状态中是否有错误
            graph_error = graph_state.get("error")
            final_result = graph_state.get("final_draft", "")

            if graph_error or not final_result:
                error_msg = graph_error or "创作任务未生成有效内容"
                self._update_task(task_id, status="failed", error=error_msg)
                logger.error(f"创作任务结果异常 - task_id: {task_id}, error: {error_msg}")
                await self._persist_and_cleanup(
                    task_id,
                    thread_id,
                    "failed",
                    error=error_msg,
                )
                raise GraphExecutionError(
                    message=error_msg,
                    details={"task_id": task_id, "topic": topic},
                )

            self._update_task(task_id, status="completed")
            created_at = self._tasks[task_id]["created_at"]

            # 持久化到 TaskStore + 清理 checkpoint + 释放内存
            await self._persist_and_cleanup(
                task_id,
                thread_id,
                "completed",
                result=final_result,
            )
            logger.info(f"创作任务已完成 - task_id: {task_id}")

            return TaskResponse(
                task_id=task_id,
                status="completed",
                message="创作任务已完成",
                created_at=created_at,
            )

        except GraphInterrupt:
            # 图在 outline_confirmation 中断点暂停（不清理，等待恢复）
            self._update_task(task_id, status="interrupted")
            await self._persist_interrupted(task_id)
            logger.info(f"创作任务暂停（大纲待确认）- task_id: {task_id}")

            return TaskResponse(
                task_id=task_id,
                status="interrupted",
                message="大纲已生成，请确认后继续",
                created_at=self._tasks[task_id]["created_at"],
            )

        except Exception as e:
            friendly_msg = format_error_message(e)
            self._update_task(task_id, status="failed", error=friendly_msg)
            logger.error(f"创作任务失败 - task_id: {task_id}, error: {str(e)}")

            # 持久化到 TaskStore + 清理 checkpoint + 释放内存
            await self._persist_and_cleanup(
                task_id,
                thread_id,
                "failed",
                error=friendly_msg,
            )

            raise GraphExecutionError(
                message=friendly_msg,
                details={"task_id": task_id, "topic": topic},
            ) from e

    async def resume_task(
        self,
        task_id: str,
        action: str,
        data: Optional[dict[str, Any]] = None,
    ) -> TaskResponse:
        """恢复被中断的创作任务

        在用户确认大纲后，继续执行后续流程（并发写作 → 合并）。

        Args:
            task_id: 任务 ID
            action: 恢复动作（confirm_outline / update_outline）
            data: 附加数据（update_outline 时包含新大纲）

        Returns:
            TaskResponse: 任务执行结果

        Raises:
            TaskNotFoundError: 任务不存在时抛出
            GraphExecutionError: 图执行失败时抛出
        """
        task = self._tasks.get(task_id)
        if task is None:
            raise TaskNotFoundError(task_id=task_id)

        thread_id = task["thread_id"]
        # 从数据库读取当前写作参数（恢复时也需限制并发度）
        params = await self.adapter.get_writing_params()
        max_concurrent_writers = int(params.get("max_concurrent_writers", 3))
        config = self._build_config(thread_id, max_concurrent_writers)
        graph = self._get_graph()

        logger.info(f"恢复创作任务 - task_id: {task_id}, action: {action}")

        try:
            if action == "update_outline" and data and "outline" in data:
                # 先更新大纲，再恢复执行
                await graph.aupdate_state(config, {"outline": data["outline"]})

            result = await graph.ainvoke(Command(resume=True), config)

            # 正常返回表示图已完成
            self._update_task(task_id, status="completed")
            created_at = task["created_at"]
            graph_state = result or {}
            final_result = graph_state.get("final_draft", "")

            # 持久化到 TaskStore + 清理 checkpoint + 释放内存
            await self._persist_and_cleanup(
                task_id,
                thread_id,
                "completed",
                result=final_result,
            )
            logger.info(f"创作任务恢复完成 - task_id: {task_id}")

            return TaskResponse(
                task_id=task_id,
                status="completed",
                message="创作任务已完成",
                created_at=created_at,
            )

        except GraphInterrupt:
            # 可能出现二次中断（当前设计不会，但防御性处理）
            self._update_task(task_id, status="interrupted")
            await self._persist_interrupted(task_id)
            logger.warning(f"创作任务再次中断 - task_id: {task_id}")

            return TaskResponse(
                task_id=task_id,
                status="interrupted",
                message="任务再次中断，请继续处理",
                created_at=task["created_at"],
            )

        except Exception as e:
            self._update_task(task_id, status="failed", error=str(e))
            logger.error(f"创作任务恢复失败 - task_id: {task_id}, error: {str(e)}")

            # 持久化到 TaskStore + 清理 checkpoint + 释放内存
            await self._persist_and_cleanup(
                task_id,
                thread_id,
                "failed",
                error=str(e),
            )

            raise GraphExecutionError(
                message=f"创作任务恢复失败: {str(e)}",
                details={"task_id": task_id, "action": action},
            ) from e

    async def get_task_status(
        self,
        task_id: str,
        include_state: bool = False,
        include_history: bool = False,
    ) -> TaskStatusResponse:
        """查询创作任务状态

        查询顺序：内存 _tasks（running/interrupted）→ TaskStore（completed/failed）
        outline 数据统一从 Checkpointer 读取（已持久化）

        Args:
            task_id: 任务 ID
            include_state: 是否包含完整图状态
            include_history: 是否包含执行历史

        Returns:
            TaskStatusResponse: 任务状态详情

        Raises:
            TaskNotFoundError: 任务不存在时抛出
        """
        # 1. 先查内存（running / interrupted 任务）
        task = self._tasks.get(task_id)

        # 2. 内存未找到，查 TaskStore
        if task is None:
            row = await self.adapter.get_task(task_id)
            if row is None:
                raise TaskNotFoundError(task_id=task_id)

            # 检查 graph_type，如果不是 creation 类型则跳过
            if row.get("graph_type") != "creation":
                raise TaskNotFoundError(task_id=task_id)

            # 从 TaskStore 行构建响应
            data: dict[str, Any] = {}
            # 保留原始参数，用于前端重试
            if row.get("topic"):
                data["topic"] = row["topic"]
            if row.get("description"):
                data["description"] = row["description"]

            # 中断任务的 awaiting 字段
            awaiting = None
            if row["status"] == "interrupted":
                awaiting = "outline_confirmation"

            response = TaskStatusResponse(
                task_id=task_id,
                status=row["status"],
                current_node=None,
                current_node_label=None,
                awaiting=awaiting,
                data=data if data else None,
                result=row.get("result"),
                error=row.get("error"),
                progress=row.get("progress"),
                state=None,
                history=None,
                created_at=row.get("created_at"),
                updated_at=row.get("updated_at"),
            )

            # 中断任务从 Checkpointer 读取 outline
            if row["status"] == "interrupted":
                try:
                    config = self._build_config(task_id)
                    checkpoint = await self.checkpointer.aget(config)
                    if checkpoint and checkpoint.get("channel_values"):
                        channel_values = checkpoint["channel_values"]
                        raw_outline = channel_values.get("outline")
                        if raw_outline:
                            data["outline"] = [
                                {"title": item.get("title", ""), "summary": item.get("summary", "")}
                                for item in raw_outline
                            ]
                            response.data = data
                except Exception as e:
                    logger.warning(f"从 Checkpointer 读取 outline 失败 - task_id: {task_id}, error: {e}")

            return response

        # 3. 内存中找到（running / interrupted），从 checkpoint 读取图状态
        thread_id = task["thread_id"]
        config = self._build_config(thread_id)
        graph = self._get_graph()

        # 从 request 中提取原始参数，用于前端重试
        request = task.get("request", {})
        data: dict[str, Any] = {}
        if request.get("topic"):
            data["topic"] = request["topic"]
        if request.get("description"):
            data["description"] = request["description"]

        response = TaskStatusResponse(
            task_id=task_id,
            status=task["status"],
            current_node=None,
            current_node_label=None,
            awaiting=None,
            data=data if data else None,
            result=None,
            error=task.get("error"),
            progress=None,
            state=None,
            history=None,
            created_at=task["created_at"],
            updated_at=task["updated_at"],
        )

        try:
            snapshot = await graph.aget_state(config)
            graph_state = snapshot.values if snapshot else {}

            current_node = graph_state.get("current_node")
            response.current_node = current_node
            response.current_node_label = NODE_LABELS.get(current_node, current_node)
            response.progress = self._calculate_progress(graph_state, task["status"])

            if task["status"] == "completed":
                response.result = graph_state.get("final_draft")

            if task["status"] == "interrupted":
                response.awaiting = "outline_confirmation"
                # 从图状态中提取大纲数据
                raw_outline = graph_state.get("outline")
                if raw_outline:
                    data["outline"] = [
                        {"title": item.get("title", ""), "summary": item.get("summary", "")}
                        for item in raw_outline
                    ]
                    response.data = data

            if include_state:
                response.state = self._serialize_state(graph_state)

            if include_history:
                response.history = await self._get_history(config)

        except Exception as e:
            logger.warning(f"获取图状态失败 - task_id: {task_id}, error: {str(e)}")

        return response

    # ============================================
    # WebSocket 流式执行方法
    # ============================================

    async def start_task_streaming(
        self,
        topic: str,
        description: Optional[str],
        broadcaster: Any,
        client_id: str,
        request_id: Optional[str] = None,
    ) -> None:
        """流式执行创作任务（WebSocket 推送进度）

        使用 LangGraph astream() 逐节点 yield 状态更新，在关键节点手动推送进度。
        """
        # 前置检查：确保有默认 LLM Profile
        await self._ensure_default_llm()

        task_id = self._generate_task_id()
        thread_id = task_id

        self._save_task(
            task_id=task_id,
            thread_id=thread_id,
            status="running",
            request_data={"topic": topic, "description": description},
        )

        # 自动订阅
        broadcaster.subscribe(client_id, task_id)

        # 通知客户端任务已创建
        await broadcaster.send_to(
            client_id,
            {
                "type": "task_created",
                "requestId": request_id,
                "taskId": task_id,
                "status": "running",
                "createdAt": str(self._tasks[task_id]["created_at"]),
            },
        )

        # 从数据库读取运行时配置
        params = await self.adapter.get_writing_params()
        max_outline_sections = int(params.get("max_outline_sections", 5))
        max_concurrent_writers = int(params.get("max_concurrent_writers", 3))

        initial_state = {
            "topic": topic,
            "description": description,
            "outline": [],
            "sections": [],
            "final_draft": None,
            "messages": [],
            "current_node": None,
            "error": None,
            "max_outline_sections": max_outline_sections,
            "max_concurrent_writers": max_concurrent_writers,
        }

        config = self._build_config(thread_id, max_concurrent_writers)
        graph = self._get_graph()

        try:
            logger.info(f"创作任务流式启动 - task_id: {task_id}, topic: {topic}")

            total_sections = len(initial_state.get("outline", []))
            completed_writers = 0

            async for event in graph.astream_events(initial_state, config, version="v2"):
                kind = event.get("event", "")

                # 事件 1：节点完成（替代原 astream 的 node_output）
                if kind == "on_chain_end":
                    node_name = event.get("name", "")
                    data = event.get("data", {})
                    if not isinstance(data, dict):
                        continue
                    output = data.get("output")
                    if not isinstance(output, dict):
                        continue
                    # 跳过顶层图结束事件
                    if node_name == "LangGraph":
                        continue

                    # 跟踪 writer 完成进度
                    if node_name == "writer" and "sections" in output:
                        completed_writers += 1

                    current_node = output.get("current_node", node_name)
                    label = NODE_LABELS.get(current_node, current_node)
                    progress = self._calculate_writer_progress(
                        current_node,
                        completed_writers,
                        total_sections,
                    )

                    await broadcaster.broadcast_update(
                        task_id,
                        {
                            "status": "running",
                            "currentNode": current_node,
                            "currentNodeLabel": label,
                            "progress": progress,
                        },
                    )

                    logger.debug(f"节点完成 - {node_name} ({label}), progress: {progress}")

                # 事件 2：ReducerNode LLM token 流式输出
                elif kind == "on_chat_model_stream":
                    metadata = event.get("metadata", {})
                    if metadata.get("langgraph_node") == "reducer":
                        chunk = event.get("data", {}).get("chunk")
                        if chunk and hasattr(chunk, "content") and chunk.content:
                            await broadcaster.broadcast_token(task_id, chunk.content)

            # astream_events 遇到 interrupt_before 不会抛异常，而是停止 yield
            # 检查图状态是否有待处理的中断
            snapshot = await graph.aget_state(config)
            has_pending_interrupt = (
                any(task.state is None for task in snapshot.tasks)
                if snapshot and snapshot.tasks
                else False
            )

            if has_pending_interrupt:
                # 图在中断点暂停（大纲待确认）
                self._update_task(task_id, status="interrupted")
                await self._persist_interrupted(task_id)
                logger.info(f"创作任务流式暂停（大纲待确认）- task_id: {task_id}")

                graph_state = snapshot.values if snapshot else {}
                outline_data = None
                raw_outline = graph_state.get("outline")
                if raw_outline:
                    outline_data = [
                        {"title": item.get("title", ""), "summary": item.get("summary", "")}
                        for item in raw_outline
                    ]

                await broadcaster.broadcast_update(
                    task_id,
                    {
                        "status": "interrupted",
                        "currentNode": "outline_confirmation",
                        "currentNodeLabel": NODE_LABELS["outline_confirmation"],
                        "awaiting": "outline_confirmation",
                        "data": {"outline": outline_data} if outline_data else None,
                        "progress": self._calculate_progress(graph_state, "interrupted"),
                    },
                )
            else:
                # 从 checkpoint 读取最终状态（比 astream 的 final_state 更可靠）
                graph_state = snapshot.values if snapshot else {}

                # 检查图状态中是否有错误
                graph_error = graph_state.get("error")
                result = graph_state.get("final_draft", "")

                if graph_error or not result:
                    # 图"完成"但结果异常（节点返回了错误状态或空结果）
                    error_msg = graph_error or "创作任务未生成有效内容"
                    self._update_task(task_id, status="failed", error=error_msg)
                    logger.error(f"创作任务结果异常 - task_id: {task_id}, error: {error_msg}")

                    await self._persist_and_cleanup(
                        task_id,
                        thread_id,
                        "failed",
                        error=error_msg,
                    )
                    await broadcaster.broadcast_error(task_id, error_msg)
                else:
                    # 正常完成
                    self._update_task(task_id, status="completed")
                    logger.info(f"创作任务流式完成 - task_id: {task_id}")

                    created_at = self._tasks[task_id]["created_at"]

                    # 持久化到 SQLite + 释放内存
                    await self._persist_and_cleanup(
                        task_id,
                        thread_id,
                        "completed",
                        result=result or "",
                    )

                    await broadcaster.broadcast_result(task_id, result or "", created_at)

        except GraphInterrupt:
            self._update_task(task_id, status="interrupted")
            await self._persist_interrupted(task_id)
            logger.info(f"创作任务流式暂停（大纲待确认）- task_id: {task_id}")

            # 获取大纲数据用于推送
            snapshot = await graph.aget_state(config)
            graph_state = snapshot.values if snapshot else {}
            outline_data = None
            raw_outline = graph_state.get("outline")
            if raw_outline:
                outline_data = [
                    {"title": item.get("title", ""), "summary": item.get("summary", "")}
                    for item in raw_outline
                ]

            await broadcaster.broadcast_update(
                task_id,
                {
                    "status": "interrupted",
                    "currentNode": "outline_confirmation",
                    "currentNodeLabel": NODE_LABELS["outline_confirmation"],
                    "awaiting": "outline_confirmation",
                    "data": {"outline": outline_data} if outline_data else None,
                    "progress": self._calculate_progress(graph_state, "interrupted"),
                },
            )

        except Exception as e:
            friendly_msg = format_error_message(e)
            self._update_task(task_id, status="failed", error=friendly_msg)
            logger.error(f"创作任务流式失败 - task_id: {task_id}, error: {e}")

            # 持久化到 SQLite + 释放内存
            await self._persist_and_cleanup(
                task_id,
                thread_id,
                "failed",
                error=friendly_msg,
            )

            await broadcaster.broadcast_error(task_id, friendly_msg)

    async def resume_task_streaming(
        self,
        task_id: str,
        action: str,
        data: Optional[dict[str, Any]],
        broadcaster: Any,
        client_id: str,
        request_id: Optional[str] = None,
    ) -> None:
        """流式恢复被中断的创作任务（WebSocket 推送进度）"""
        task = self._tasks.get(task_id)
        if task is None:
            await broadcaster.send_to(
                client_id,
                {
                    "type": "error",
                    "requestId": request_id,
                    "code": "TASK_NOT_FOUND",
                    "message": f"任务不存在: {task_id}",
                },
            )
            return

        thread_id = task["thread_id"]
        # 从数据库读取当前写作参数（恢复时也需限制并发度）
        params = await self.adapter.get_writing_params()
        max_concurrent_writers = int(params.get("max_concurrent_writers", 3))
        config = self._build_config(thread_id, max_concurrent_writers)
        graph = self._get_graph()

        # 自动订阅
        broadcaster.subscribe(client_id, task_id)

        try:
            logger.info(f"恢复创作任务流式执行 - task_id: {task_id}, action: {action}")

            if action == "update_outline" and data and "outline" in data:
                await graph.aupdate_state(config, {"outline": data["outline"]})

            await broadcaster.broadcast_update(
                task_id,
                {
                    "status": "running",
                    "currentNode": "outline_confirmation",
                    "currentNodeLabel": NODE_LABELS["outline_confirmation"],
                    "progress": 30.0,
                },
            )

            # 获取大纲长度用于计算 writer 进度
            pre_snapshot = await graph.aget_state(config)
            pre_state = pre_snapshot.values if pre_snapshot else {}
            total_sections = len(pre_state.get("outline", []))

            completed_writers = 0

            async for event in graph.astream_events(
                Command(resume=True), config, version="v2"
            ):
                kind = event.get("event", "")

                # 事件 1：节点完成
                if kind == "on_chain_end":
                    node_name = event.get("name", "")
                    data = event.get("data", {})
                    if not isinstance(data, dict):
                        continue
                    output = data.get("output")
                    if not isinstance(output, dict):
                        continue
                    if node_name == "LangGraph":
                        continue

                    # 跟踪 writer 完成进度
                    if node_name == "writer" and "sections" in output:
                        completed_writers += 1

                    current_node = output.get("current_node", node_name)
                    label = NODE_LABELS.get(current_node, current_node)
                    progress = self._calculate_writer_progress(
                        current_node,
                        completed_writers,
                        total_sections,
                    )

                    await broadcaster.broadcast_update(
                        task_id,
                        {
                            "status": "running",
                            "currentNode": current_node,
                            "currentNodeLabel": label,
                            "progress": progress,
                        },
                    )

                # 事件 2：ReducerNode LLM token 流式输出
                elif kind == "on_chat_model_stream":
                    metadata = event.get("metadata", {})
                    if metadata.get("langgraph_node") == "reducer":
                        chunk = event.get("data", {}).get("chunk")
                        if chunk and hasattr(chunk, "content") and chunk.content:
                            await broadcaster.broadcast_token(task_id, chunk.content)

            # 检查是否有待处理的中断
            snapshot = await graph.aget_state(config)
            has_pending_interrupt = (
                any(task.state is None for task in snapshot.tasks)
                if snapshot and snapshot.tasks
                else False
            )

            if has_pending_interrupt:
                self._update_task(task_id, status="interrupted")
                await self._persist_interrupted(task_id)
                logger.info(f"创作任务恢复后再次中断 - task_id: {task_id}")
                await broadcaster.broadcast_update(
                    task_id,
                    {
                        "status": "interrupted",
                        "currentNode": "outline_confirmation",
                        "currentNodeLabel": NODE_LABELS["outline_confirmation"],
                        "awaiting": "outline_confirmation",
                    },
                )
            else:
                self._update_task(task_id, status="completed")
                logger.info(f"创作任务恢复流式完成 - task_id: {task_id}")

                # 从 checkpoint 读取最终状态（比 astream 的 final_state 更可靠）
                graph_state = snapshot.values if snapshot else {}

                result = graph_state.get("final_draft", "")
                created_at = task["created_at"]

                # 持久化到 SQLite + 释放内存
                await self._persist_and_cleanup(
                    task_id,
                    thread_id,
                    "completed",
                    result=result or "",
                )

                await broadcaster.broadcast_result(task_id, result or "", created_at)

        except Exception as e:
            friendly_msg = format_error_message(e)
            self._update_task(task_id, status="failed", error=friendly_msg)
            logger.error(f"创作任务恢复流式失败 - task_id: {task_id}, error: {e}")

            # 持久化到 SQLite + 释放内存
            await self._persist_and_cleanup(
                task_id,
                thread_id,
                "failed",
                error=friendly_msg,
            )

            await broadcaster.broadcast_error(task_id, friendly_msg)

    # ============================================
    # 内部辅助方法
    # ============================================

    @staticmethod
    def _calculate_progress(state: dict, status: str) -> float:
        """计算任务进度百分比"""
        if status == "completed":
            return 100.0
        if status == "failed":
            return 0.0

        current_node = state.get("current_node", "")
        progress_map = {
            "planner": 20.0,
            "outline_confirmation": 30.0,
            "writer": 60.0,
            "reducer": 80.0,
        }
        return progress_map.get(current_node, 10.0)

    @staticmethod
    def _calculate_writer_progress(
        current_node: str,
        completed_writers: int,
        total_sections: int,
    ) -> float:
        """计算包含并发 writer 的总体进度

        进度分配：
        - planner: 10%
        - outline_confirmation: 20%
        - writer 阶段: 30% ~ 80%（按完成比例线性增长）
        - reducer: 80% ~ 95%
        - completed: 100%
        """
        if current_node == "planner":
            return 10.0
        if current_node == "outline_confirmation":
            return 20.0
        if current_node == "writer":
            if total_sections <= 0:
                return 55.0
            ratio = min(completed_writers / total_sections, 1.0)
            return 30.0 + ratio * 50.0  # 30% → 80%
        if current_node == "reducer":
            return 90.0
        return 10.0

    @staticmethod
    def _serialize_state(state: dict) -> dict:
        """序列化图状态为可传输格式"""
        serialized = {}
        for key, value in state.items():
            if key == "messages":
                serialized[key] = [
                    {"type": type(m).__name__, "content": getattr(m, "content", str(m))}
                    for m in (value or [])
                ]
            elif key == "outline":
                serialized[key] = [
                    {"title": item.get("title", ""), "summary": item.get("summary", "")}
                    for item in (value or [])
                ]
            elif key == "sections":
                serialized[key] = [
                    {
                        "title": s.get("title", ""),
                        "content": s.get("content", ""),
                        "index": s.get("index", 0),
                    }
                    for s in (value or [])
                ]
            else:
                serialized[key] = value
        return serialized

    async def _get_history(self, config: dict) -> list[dict]:
        """获取图执行历史（checkpoint 列表）"""
        history = []
        try:
            async for checkpoint in self.checkpointer.alist(config):
                history.append(
                    {
                        "checkpoint_id": getattr(checkpoint, "id", None),
                        "ts": getattr(checkpoint, "ts", None),
                    }
                )
        except Exception as e:
            logger.warning(f"获取执行历史失败: {str(e)}")
        return history
