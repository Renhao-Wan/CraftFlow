"""通用 Prompt 模板模块

存放跨模块可复用的通用 Prompt 模板，包括：
- 输出格式规范（Markdown、JSON）
- 通用角色定义
- 通用约束条件
- 通用指令片段

业务专属的 Prompt 应放在各自模块的 prompts.py 中。
"""

from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate

# ============================================
# 通用角色定义
# ============================================

PROFESSIONAL_WRITER_ROLE = """你是一位资深技术写作专家，具备以下能力：
- 深厚的专业知识储备，能够准确理解复杂的技术概念
- 出色的信息组织能力，擅长将复杂内容结构化呈现
- 清晰流畅的表达风格，能够将专业知识转化为易懂的文字
- 严谨的逻辑思维，确保内容前后连贯、论证充分
- 对读者需求的敏锐洞察，能够把握不同受众的阅读习惯"""

PROFESSIONAL_EDITOR_ROLE = """你是一位经验丰富的主编，具备以下能力：
- 敏锐的内容质量判断力，能够快速识别文章的优缺点
- 全面的评估视角，从结构、逻辑、语言、事实等多维度审查
- 建设性的反馈能力，提出具体可行的改进建议
- 严格的质量标准，确保输出内容达到出版级别
- 对细节的关注，不放过任何可能影响质量的问题"""

CONTENT_STRATEGIST_ROLE = """你是一位专业的内容策划师，具备以下能力：
- 深入的主题分析能力，能够快速把握核心要点
- 系统的结构设计能力，擅长构建清晰的内容框架
- 对受众需求的理解，能够设计符合读者期待的内容路径
- 全局视角，确保各部分内容协调统一
- 创新思维，能够提出独特的内容组织方式"""

# ============================================
# 输出格式规范
# ============================================

MARKDOWN_FORMAT_RULES = """## 输出格式要求

使用 Markdown 格式输出，遵循以下规范：
- 使用 `#` 作为文章标题，`##` 作为章节标题，`###` 作为小节标题，最多四级
- 重要概念使用 **粗体** 标注
- 行内代码使用反引号包裹，代码块使用三个反引号并指定语言
- 段落之间空一行，标题前后各空一行"""

JSON_OUTPUT_RULES = """## JSON 输出规范

当需要输出 JSON 格式时，必须遵循以下规则：

### 基本要求
- 输出必须是合法的 JSON 格式，能够被标准 JSON 解析器解析
- 使用双引号包裹字符串，不使用单引号
- 布尔值使用小写的 true 和 false
- 空值使用 null

### 字段命名
- 使用下划线命名风格（如 section_title）
- 字段名应具有描述性，避免缩写
- 保持字段名的一致性

### 数据类型
- 字符串：使用双引号包裹
- 数字：直接使用数字，不加引号
- 布尔值：使用 true 或 false
- 数组：使用方括号包裹
- 对象：使用花括号包裹

### 格式化
- 使用 2 或 4 个空格缩进
- 每个字段独占一行
- 数组元素较多时，每个元素独占一行"""

# ============================================
# 通用约束条件
# ============================================

ANTI_HALLUCINATION_RULES = """## 准确性约束

- 不要编造具体的数据、日期、人名、引用来源
- 不确定的信息使用"可能"、"据报道"等限定词，不要伪装成确定的事实
- 代码示例必须语法正确、可运行
- 技术术语使用规范名称，避免自创词汇
- 前后陈述不得矛盾，结论必须有论据支撑"""

QUALITY_STANDARDS = """## 质量要求

- 结构清晰，层次分明，开头/正文/结尾衔接自然
- 论点明确，论据充分，使用案例或数据支撑
- 语言自然流畅，句式多样，避免过于口语化或学术化的表达
- 段落长度适中（3-5 句），重点内容突出显示"""

# ============================================
# 通用指令片段
# ============================================

SEARCH_TOOL_USAGE_INSTRUCTION = """## 搜索工具使用指南

当你需要获取最新信息、验证事实或补充知识时，应使用搜索工具：

### 何时使用搜索
- 需要最新的数据、新闻、技术动态
- 需要验证具体的事实、数据、引用
- 需要补充专业领域的深度知识
- 需要查找具体的案例、示例

### 搜索策略
- 使用精确的关键词，避免模糊查询
- 优先搜索权威来源（官方文档、学术论文、知名媒体）
- 对比多个来源，确保信息准确性
- 记录搜索来源，便于引用

### 搜索结果处理
- 仔细阅读搜索结果，提取关键信息
- 验证信息的时效性和可靠性
- 整合多个来源的信息，形成全面的理解
- 在输出中引用搜索来源"""

CODE_VALIDATION_INSTRUCTION = """## 代码验证指南

当你生成代码时，应使用代码沙箱工具进行验证：

### 何时验证代码
- 生成完整的代码示例
- 提供可执行的脚本或命令
- 涉及复杂的算法或逻辑

### 验证流程
1. 在沙箱中运行代码
2. 检查是否有语法错误
3. 验证输出是否符合预期
4. 测试边界情况和异常处理

### 验证结果处理
- 如果代码运行成功，直接输出
- 如果有错误，修复后重新验证
- 在输出中说明代码已验证可运行"""

# ============================================
# 通用 Prompt 模板
# ============================================


def create_base_system_prompt(
    role: str,
    task_description: str,
    include_markdown_rules: bool = True,
    include_anti_hallucination: bool = True,
    include_quality_standards: bool = True,
    additional_instructions: str = "",
) -> str:
    """创建基础系统 Prompt

    Args:
        role: 角色定义（如 PROFESSIONAL_WRITER_ROLE）
        task_description: 任务描述
        include_markdown_rules: 是否包含 Markdown 格式规范
        include_anti_hallucination: 是否包含防幻觉规则
        include_quality_standards: 是否包含质量标准
        additional_instructions: 额外的指令

    Returns:
        str: 完整的系统 Prompt
    """
    prompt_parts = [role, "", task_description]

    if include_markdown_rules:
        prompt_parts.extend(["", MARKDOWN_FORMAT_RULES])

    if include_anti_hallucination:
        prompt_parts.extend(["", ANTI_HALLUCINATION_RULES])

    if include_quality_standards:
        prompt_parts.extend(["", QUALITY_STANDARDS])

    if additional_instructions:
        prompt_parts.extend(["", additional_instructions])

    return "\n".join(prompt_parts)


def create_chat_prompt_template(
    system_prompt: str, human_prompt: str
) -> ChatPromptTemplate:
    """创建 ChatPromptTemplate

    Args:
        system_prompt: 系统提示词
        human_prompt: 用户提示词（支持变量占位符）

    Returns:
        ChatPromptTemplate: LangChain ChatPromptTemplate 对象
    """
    return ChatPromptTemplate.from_messages(
        [
            SystemMessagePromptTemplate.from_template(system_prompt),
            ("human", human_prompt),
        ]
    )


# ============================================
# 预定义的通用模板（延迟创建函数）
# ============================================


def get_markdown_output_template() -> ChatPromptTemplate:
    """获取通用的 Markdown 输出模板

    Returns:
        ChatPromptTemplate: Markdown 输出模板
    """
    return create_chat_prompt_template(
        system_prompt=create_base_system_prompt(
            role=PROFESSIONAL_WRITER_ROLE,
            task_description="你的任务是生成高质量的 Markdown 格式内容。",
        ),
        human_prompt="{input}",
    )


def get_json_output_template() -> ChatPromptTemplate:
    """获取通用的 JSON 输出模板

    Returns:
        ChatPromptTemplate: JSON 输出模板
    """
    return create_chat_prompt_template(
        system_prompt=create_base_system_prompt(
            role=PROFESSIONAL_WRITER_ROLE,
            task_description="你的任务是生成符合规范的 JSON 格式输出。",
            include_markdown_rules=False,
            additional_instructions=JSON_OUTPUT_RULES,
        ),
        human_prompt="{input}",
    )
