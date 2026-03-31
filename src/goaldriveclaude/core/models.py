"""Pydantic 模型 - 数据校验"""

from typing import Any, Optional

from pydantic import BaseModel, Field


class SubGoalModel(BaseModel):
    """子目标模型"""

    id: str = Field(description="子目标唯一标识符，如 sg_001")
    description: str = Field(description="子目标描述")
    verification_criteria: list[str] = Field(
        description="可执行的验证条件列表，必须是具体可验证的"
    )
    depends_on: list[str] = Field(default_factory=list, description="依赖的其他子目标 ID")
    status: str = Field(default="pending", description="状态: pending/in_progress/done/failed/verifying")


class GoalAnalysisResult(BaseModel):
    """目标分析结果"""

    goal_understanding: str = Field(description="对目标的理解")
    subgoals: list[SubGoalModel] = Field(description="分解后的子目标列表")


class ToolCallModel(BaseModel):
    """工具调用模型"""

    tool_name: str = Field(description="工具名称")
    tool_input: dict[str, Any] = Field(description="工具输入参数")
    reasoning: str = Field(description="调用此工具的原因")


class ToolResultModel(BaseModel):
    """工具执行结果模型"""

    success: bool = Field(description="是否成功")
    output: str = Field(default="", description="正常输出")
    error: str = Field(default="", description="错误信息")
    duration_ms: int = Field(default=0, description="执行耗时（毫秒）")


class EvaluationResult(BaseModel):
    """评估结果模型"""

    subgoal_completed: bool = Field(description="当前子目标是否完成")
    next_action: str = Field(description="下一步行动建议")
    reasoning: str = Field(description="评估理由")


class VerificationItem(BaseModel):
    """单项验证结果"""

    criteria: str = Field(description="验证标准描述")
    method: str = Field(description="使用的验证方法/工具")
    passed: bool = Field(description="是否通过")
    evidence: str = Field(description="具体执行结果作为证据")
    fix_suggestion: str = Field(default="", description="如果失败，建议如何修复")


class VerificationResult(BaseModel):
    """验证结果模型"""

    results: list[VerificationItem] = Field(description="各项验证结果")
    overall_passed: bool = Field(description="整体是否通过")
    summary: str = Field(description="整体评估总结")
    gaps: list[dict] = Field(default_factory=list, description="验证差距")


class ErrorRecoverySuggestion(BaseModel):
    """错误恢复建议"""

    can_recover: bool = Field(description="是否可以自动恢复")
    strategy: str = Field(description="恢复策略")
    suggested_action: Optional[ToolCallModel] = Field(default=None, description="建议的修复动作")
    needs_human_help: bool = Field(default=False, description="是否需要人工介入")
    message_to_user: str = Field(default="", description="给用户的消息")


class SessionData(BaseModel):
    """会话数据模型"""

    session_id: str = Field(description="会话 ID")
    created_at: str = Field(description="创建时间")
    updated_at: str = Field(description="更新时间")
    goal: str = Field(description="目标")
    state: dict = Field(description="序列化的状态")


class CommandBlacklist:
    """命令黑名单"""

    BLOCKED_COMMANDS = [
        "rm -rf /",
        "rm -rf /*",
        "rm -rf ~",
        "sudo",
        "chmod -R 777 /",
        "dd if=/dev/zero",
        "mkfs",
        ":(){ :|:& };:",  # fork bomb
    ]

    @classmethod
    def is_blocked(cls, command: str) -> tuple[bool, str]:
        """检查命令是否被阻塞

        Returns:
            (是否被阻塞, 阻塞原因)
        """
        cmd_lower = command.lower().strip()
        for blocked in cls.BLOCKED_COMMANDS:
            if blocked in cmd_lower:
                return True, f"命令包含被禁止的操作: {blocked}"
        return False, ""
