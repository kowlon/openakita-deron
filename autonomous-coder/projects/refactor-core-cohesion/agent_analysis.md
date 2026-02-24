# Agent.py Analysis

## Public Methods
(Based on grep output)
- `__init__`
- `chat`
- `chat_with_session`
- `chat_with_session_stream`
- `execute_task_from_message`
- `execute_task`
- `self_check`
- `is_initialized`
- `conversation_history`
- `set_scheduler_gateway`
- `shutdown`
- `consolidate_memories`
- `get_memory_stats`
- `set_interrupt_enabled`
- `cancel_current_task`
- `is_stop_command`
- `is_skip_command`
- `classify_interrupt`
- `skip_current_step`
- `insert_user_message`
- `confirm_step`

## Internal Methods Classification

### Tool & Skill Management
- `_init_handlers`
- `_load_installed_skills`
- `_update_shell_tool_description`
- `_update_skill_tools`
- `_install_skill*`
- `_extract_skill_name`
- `_normalize_skill_name`
- `_find_skill_md`
- `_list_skill_candidates`
- `_ensure_skill_structure`
- `_list_installed_files`
- `_format_tree`
- `_load_mcp_servers`
- `_start_builtin_mcp_servers`
- `_register_system_tasks`
- `_generate_tools_text`

### Session Management
- `_prepare_session_context`
- `_finalize_session`
- `_cleanup_session_state`
- `_resolve_conversation_id`

### Prompt Building
- `_build_system_prompt`
- `_build_system_prompt_compiled_sync`
- `_build_system_prompt_compiled`
- `_compile_prompt`
- `_summarize_compiler_output`
- `_should_compile_prompt`
- `_get_last_user_request`

### Execution Loop
- `_cancellable_await`
- `_im_chain_progress`
- `_build_chain_summary`
- `_do_task_retrospect`
- `_do_task_retrospect_background`
- `_verify_task_completion`
- `_cancellable_llm_call`
- `_handle_cancel_farewell`
- `_persist_cancel_to_context`
- `_chat_with_tools_and_context`
- `_chat_with_tools`
- `_execute_tool`
- `_format_task_result`
- `_on_iteration`
- `_on_error`
- `_task_cancelled`
- `_cancel_reason`

## Duplicate Code / Refactoring Candidates

1. **System Prompt Building**:
   - `_build_effective_system_prompt` (inside `_chat_with_tools_and_context`)
   - `_build_effective_system_prompt_cli` (inside `_chat_with_tools`)
   - `_build_effective_system_prompt_task` (inside `execute_task`)
   *Recommendation: Extract to `_build_effective_prompt(mode)`.*

2. **Endpoint Resolution**:
   - `_resolve_endpoint_name` (inside `_chat_with_tools_and_context`)
   - `_resolve_endpoint_name` (inside `execute_task`)
   *Recommendation: Extract to `_resolve_endpoint_name` helper method.*

3. **Tool/Skill Installation**:
   - Large block of methods for skill installation (`_install_skill*`, `_extract_skill_name`, etc.)
   *Recommendation: Move to `skills/installer.py` or `skills/manager.py` (some already moved, check if `agent.py` still has them).*

4. **MCP Management**:
   - `_load_mcp_servers`
   - `_start_builtin_mcp_servers`
   *Recommendation: Move to `tools/mcp/manager.py`.*
