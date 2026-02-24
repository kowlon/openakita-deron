from pydantic import Field

# === 强制 Tool 调用（工具守卫） ===
# 设为 0 可在简单问题中禁用强制工具调用
# 这能显著提升简单聊天场景的响应速度
force_tool_call_max_retries: int = Field(
    default=0,
    description="Force tool call max retries (0=disabled)",
)

# === 工具并行执行 ===
# 每轮最大并行工具调用数
tool_max_parallel: int = Field(
    default=1,
    description="Max parallel tool calls (default 1=serial)",
)

allow_parallel_tools_with_interrupt_checks: bool = Field(
    default=False,
    description="Allow parallel tools with interrupt checks (default False)",
)
