    # === ForceToolCall (Tool Guard) ===
    # Set to 0 to disable forcing tool calls for simple questions
    # This significantly improves response speed for simple chat scenarios
    force_tool_call_max_retries: int = Field(
        default=0,
        description="Force tool call max retries (0=disabled)",
    )

    # === Tool Parallel Execution ===
    # Maximum parallel tool calls per round
    tool_max_parallel: int = Field(
        default=1,
        description="Max parallel tool calls (default 1=serial)",
    )

    allow_parallel_tools_with_interrupt_checks: bool = Field(
        default=False,
        description="Allow parallel tools with interrupt checks (default False)",
    )
