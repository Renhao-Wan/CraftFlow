"""
API 请求模型定义

本模块定义所有 API 接口的请求数据传输对象 (DTO)。
使用 Pydantic 进行数据校验和序列化。
"""

from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class CreationRequest(BaseModel):
    """
    创作任务请求模型

    用于 POST /api/v1/creation 接口
    """

    topic: str = Field(
        ..., min_length=1, max_length=500, description="文章主题，必填", examples=["微服务架构演进"]
    )

    description: Optional[str] = Field(
        default="",
        max_length=2000,
        description="补充描述或需求说明，可选",
        examples=["请重点关注容器化部署和服务治理"],
    )

    @field_validator("topic")
    @classmethod
    def validate_topic(cls, v: str) -> str:
        """验证主题不能为空白字符"""
        if not v.strip():
            raise ValueError("主题不能为空白字符")
        return v.strip()

    class Config:
        json_schema_extra = {
            "example": {"topic": "微服务架构演进", "description": "请重点关注容器化部署和服务治理"}
        }


class PolishingRequest(BaseModel):
    """
    润色任务请求模型

    用于 POST /api/v1/polishing 接口
    """

    content: str = Field(
        ...,
        min_length=10,
        description="待润色的文章内容（Markdown 格式）",
        examples=["# 标题\n\n正文内容..."],
    )

    mode: int = Field(
        default=2,
        ge=1,
        le=3,
        description="润色模式：1=极速格式化, 2=专家对抗审查, 3=事实核查",
        examples=[2],
    )

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        """验证内容不能为空白字符"""
        if not v.strip():
            raise ValueError("内容不能为空白字符")
        return v.strip()

    class Config:
        json_schema_extra = {
            "example": {"content": "# 微服务架构演进\n\n微服务架构是一种...", "mode": 2}
        }


class ResumeRequest(BaseModel):
    """
    任务恢复请求模型

    用于 POST /api/v1/tasks/{task_id}/resume 接口
    用于在 interrupt 断点处注入人工修改的数据并恢复图执行
    """

    action: str = Field(
        ..., description="恢复动作类型", examples=["confirm_outline", "update_outline"]
    )

    data: Optional[dict[str, Any]] = Field(
        default=None,
        description="注入的数据（如修改后的大纲）",
        examples=[{"outline": [{"title": "第一章", "summary": "概述"}]}],
    )

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        """验证动作类型"""
        allowed_actions = ["confirm_outline", "update_outline", "approve_draft", "reject_draft"]
        if v not in allowed_actions:
            raise ValueError(f"不支持的动作类型: {v}，允许的值: {allowed_actions}")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "action": "update_outline",
                "data": {
                    "outline": [
                        {"title": "第一章：微服务概述", "summary": "介绍微服务的基本概念"},
                        {"title": "第二章：架构演进", "summary": "从单体到微服务的演进路径"},
                    ]
                },
            }
        }


class LlmProfileRequest(BaseModel):
    """LLM Profile 创建/更新请求模型"""

    name: str = Field(..., min_length=1, max_length=100, description="配置名称")
    api_key: Optional[str] = Field(default=None, min_length=1, description="API Key")
    api_base: str = Field(default="", description="API Base URL")
    model: str = Field(..., min_length=1, max_length=100, description="模型名称")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="温度参数")
    system_prompt: Optional[str] = Field(
        default="", max_length=500, description="自定义系统提示词"
    )
    is_default: bool = Field(default=False, description="是否为默认配置")


class ToolConfigsRequest(BaseModel):
    """外部工具配置更新请求模型"""

    tavily_api_key: Optional[str] = Field(
        default=None, max_length=200, description="Tavily Search API Key"
    )
    e2b_api_key: Optional[str] = Field(
        default=None, max_length=200, description="E2B Code Sandbox API Key"
    )


class WritingParamsRequest(BaseModel):
    """写作参数更新请求模型"""

    max_outline_sections: Optional[int] = Field(
        default=None, ge=1, le=20, description="大纲最大章节数"
    )
    max_concurrent_writers: Optional[int] = Field(
        default=None, ge=1, le=10, description="最大并发写作者数"
    )
    max_debate_iterations: Optional[int] = Field(
        default=None, ge=1, le=10, description="对抗循环最大迭代次数"
    )
    editor_pass_score: Optional[int] = Field(
        default=None, ge=0, le=100, description="主编通过分数阈值"
    )
    task_timeout: Optional[int] = Field(
        default=None, ge=60, le=86400, description="任务超时时间（秒）"
    )
    tool_call_timeout: Optional[int] = Field(
        default=None, ge=5, le=300, description="工具调用超时时间（秒）"
    )
