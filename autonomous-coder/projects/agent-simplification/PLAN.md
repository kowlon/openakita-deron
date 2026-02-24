# Agent.py Simplification Plan

## Context

**Problem**: `src/openakita/core/agent.py` has grown to **4366 lines** with **66 methods** in a single `Agent` class. This is a classic "God Class" anti-pattern that:
- Makes the code hard to navigate and understand
- Creates merge conflicts
- Violates Single Responsibility Principle
- Contains deprecated code that should be removed

**Goal**: Reduce agent.py to ~1500-2000 lines by extracting logical modules and removing deprecated code.

---

## Current Analysis

### File Structure Breakdown (4366 lines total)

| Section | Lines | Description | Action |
|---------|-------|-------------|--------|
| Imports & Constants | 1-155 | Module setup | Keep |
| `__init__` | 206-352 | Initialization | Keep (already delegated) |
| Properties | 397-461 | Backward compat delegates | Keep |
| `_execute_tool_calls_batch` | 462-676 | Tool execution | Already in ToolExecutor |
| `initialize` | 677-748 | Init logic | Keep |
| Scheduler | 754-861 | Task scheduling | Keep |
| **Prompt Building** | 862-1318 | System prompt generation | Extract to `prompt_builder.py` |
| **Legacy Code** | 1318-1433 | Old methods | Delete |
| Session Management | 1434-1757 | Already extracted to `session_helper.py` | Verify usage |
| **Retrospect** | 1850-1941 | Task retrospect | Extract to `retrospect.py` |
| Verification | 1980-2109 | Task completion verify | Keep in ReasoningEngine |
| Cancel/LLM | 2110-2252 | Cancellable LLM calls | Keep |
| **Chat Core** | 2253-3203 | `_chat_with_tools_and_context` | **Contains 800 lines of DEAD CODE** |
| **Interrupt Manager** | 3204-3412 | Cancel/skip/insert | Extract to `interrupt_manager.py` |
| **Deprecated** | 3413-3591 | `_chat_with_tools` | Delete |
| Task Execution | 3593-4189 | `execute_task` | Keep |
| Utilities | 4190-4366 | Helpers | Keep |

---

## Key Extraction Targets

### 1. InterruptManager (~250 lines)

**Location**: Lines 3204-3412

**Methods to extract**:
- `_task_cancelled` (property)
- `_cancel_reason` (property)
- `set_interrupt_enabled()`
- `cancel_current_task()`
- `is_stop_command()`
- `is_skip_command()`
- `classify_interrupt()`
- `skip_current_step()`
- `insert_user_message()`
- `confirm_step()`
- `STOP_COMMANDS` / `SKIP_COMMANDS` constants

**New file**: `src/openakita/core/interrupt_manager.py`

### 2. RetrospectHandler (~100 lines)

**Location**: Lines 1850-1941

**Methods to extract**:
- `_do_task_retrospect()`
- `_do_task_retrospect_background()`
- `_build_chain_summary()`

**New file**: `src/openakita/core/retrospect.py`

### 3. PromptBuilder (~400 lines)

**Location**: Lines 862-1318

**Methods to extract**:
- `_build_system_prompt()`
- `_build_system_prompt_compiled_sync()`
- `_build_system_prompt_compiled()`
- `_generate_tools_text()`
- `_compile_prompt()`
- `_summarize_compiler_output()`
- `_should_compile_prompt()`
- `_get_last_user_request()`
- `PROMPT_COMPILER_SYSTEM` constant

**Note**: Some of this is already in `PromptAssembler`, need to consolidate

**Action**: Extend existing `src/openakita/core/prompt_assembler.py`

### 4. Dead Code Removal (~1000 lines)

**Targets**:
- Lines 2411-3202: Old `_chat_with_tools_and_context` implementation (commented as "旧代码（保留参考，后续完全清理）")
- Lines 3413-3591: `_chat_with_tools()` marked as DEPRECATED

---

## Implementation Plan

### Phase 1: Extract InterruptManager (INT-001 ~ INT-004)
1. Create `src/openakita/core/interrupt_manager.py`
2. Move `STOP_COMMANDS`, `SKIP_COMMANDS` constants
3. Move all interrupt-related methods
4. Create `InterruptManager` class with `agent_state` dependency
5. Update `Agent.__init__` to create `self.interrupt_manager`
6. Add delegation properties/methods in `Agent` for backward compatibility

### Phase 2: Extract RetrospectHandler (RETRO-001 ~ RETRO-003)
1. Create `src/openakita/core/retrospect.py`
2. Move `_do_task_retrospect`, `_do_task_retrospect_background`, `_build_chain_summary`
3. Create `RetrospectManager` class
4. Update `Agent` to use `self.retrospect_manager`

### Phase 3: Consolidate PromptBuilder (PROMPT-001 ~ PROMPT-003)
1. Review existing `prompt_assembler.py`
2. Move remaining prompt methods from `agent.py`
3. Consolidate duplicate logic
4. Keep simple delegation in `Agent`

### Phase 4: Remove Dead Code (DEAD-001 ~ DEAD-003)
1. Delete lines 2411-3202 (old `_chat_with_tools_and_context` implementation)
2. Delete `_chat_with_tools()` method entirely
3. Clean up any unused imports

### Phase 5: Verification (VERIFY-001 ~ VERIFY-003)
1. Run baseline import tests
2. Run existing test suite
3. Manual smoke test

---

## Expected Outcome

| Metric | Before | After |
|--------|--------|-------|
| agent.py lines | 4366 | ~1800 |
| agent.py methods | 66 | ~35 |
| New modules | 0 | 3 |

---

## Files to Modify

- `src/openakita/core/agent.py` - Main simplification target
- `src/openakita/core/__init__.py` - Export new modules

## Files to Create

- `src/openakita/core/interrupt_manager.py` - Interrupt handling
- `src/openakita/core/retrospect.py` - Task retrospect logic
- Extend `src/openakita/core/prompt_assembler.py` - Prompt building

---

## Verification Commands

```bash
# Import tests
python -c 'from openakita.core import Agent, InterruptManager, RetrospectManager; print("OK")'

# Baseline tests
python tests/baseline/test_imports_baseline.py

# Check no circular imports
python -c 'import openakita'
```

---

## Risk Assessment

- **Low Risk**: Extracting InterruptManager (self-contained)
- **Low Risk**: Extracting RetrospectHandler (self-contained)
- **Medium Risk**: PromptBuilder consolidation (may have subtle dependencies)
- **Low Risk**: Dead code removal (already deprecated)

---

## Estimated Effort

- Phase 1 (InterruptManager): 30 min
- Phase 2 (Retrospect): 15 min
- Phase 3 (PromptBuilder): 30 min
- Phase 4 (Dead code): 15 min
- Phase 5 (Verification): 15 min

**Total**: ~2 hours

---

*Created: 2026-02-24*
*Status: ready*
