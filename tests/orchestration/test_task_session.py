"""
Unit tests for TaskSession

Tests task session lifecycle, step execution, and state transitions.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from openakita.orchestration.models import (
    ScenarioDefinition,
    StepDefinition,
    StepSession,
    StepStatus,
    TaskState,
    TaskStatus,
    ToolsConfig,
    TriggerPattern,
    TriggerType,
)
from openakita.orchestration.task_session import TaskSession, TaskSessionConfig


class TestTaskSessionInit:
    """Test TaskSession initialization"""

    @pytest.fixture
    def simple_scenario(self):
        """Create a simple scenario for testing"""
        return ScenarioDefinition(
            scenario_id="test-scenario",
            name="Test Scenario",
            steps=[
                StepDefinition(step_id="step1", name="Step 1", output_key="output1"),
                StepDefinition(step_id="step2", name="Step 2", output_key="output2"),
            ],
        )

    @pytest.fixture
    def mock_manager(self):
        """Create mock SubAgentManager"""
        manager = AsyncMock()
        manager.spawn_sub_agent = AsyncMock(return_value="subagent-001")
        manager.destroy_sub_agent = AsyncMock()
        return manager

    def test_create_task_session(self, simple_scenario, mock_manager):
        """Test creating a task session"""
        task_state = TaskState(
            task_id="task-001",
            scenario_id="test-scenario",
            total_steps=len(simple_scenario.steps),
        )

        session = TaskSession(
            state=task_state,
            scenario=simple_scenario,
            sub_agent_manager=mock_manager,
        )

        assert session.state.task_id == "task-001"
        assert session.state.status == TaskStatus.PENDING
        assert len(session.step_sessions) == 2
        assert session.state.total_steps == 2

    def test_init_step_sessions(self, simple_scenario, mock_manager):
        """Test step sessions initialization"""
        task_state = TaskState(
            task_id="task-001",
            scenario_id="test-scenario",
        )

        session = TaskSession(
            state=task_state,
            scenario=simple_scenario,
            sub_agent_manager=mock_manager,
        )

        # Verify step sessions created
        assert "step1" in session.step_sessions
        assert "step2" in session.step_sessions
        assert session.step_sessions["step1"].status == StepStatus.PENDING
        assert session.step_sessions["step2"].status == StepStatus.PENDING

    def test_default_config(self, simple_scenario, mock_manager):
        """Test default configuration"""
        task_state = TaskState(task_id="task-001", scenario_id="test-scenario")

        session = TaskSession(
            state=task_state,
            scenario=simple_scenario,
            sub_agent_manager=mock_manager,
        )

        assert session._config.auto_start_next_step is True
        assert session._config.enable_edit_mode is True
        assert session._config.context_injection_enabled is True

    def test_custom_config(self, simple_scenario, mock_manager):
        """Test custom configuration"""
        task_state = TaskState(task_id="task-001", scenario_id="test-scenario")

        config = TaskSessionConfig(
            auto_start_next_step=False,
            enable_edit_mode=False,
            context_injection_enabled=False,
        )

        session = TaskSession(
            state=task_state,
            scenario=simple_scenario,
            sub_agent_manager=mock_manager,
            config=config,
        )

        assert session._config.auto_start_next_step is False
        assert session._config.enable_edit_mode is False
        assert session._config.context_injection_enabled is False


class TestTaskSessionLifecycle:
    """Test TaskSession lifecycle"""

    @pytest.fixture
    def scenario_with_confirmation(self):
        """Create scenario with confirmation steps"""
        return ScenarioDefinition(
            scenario_id="confirm-scenario",
            name="Confirmation Scenario",
            steps=[
                StepDefinition(
                    step_id="step1",
                    name="Step 1",
                    output_key="output1",
                    requires_confirmation=True,
                    system_prompt="You are step 1",
                ),
                StepDefinition(
                    step_id="step2",
                    name="Step 2",
                    output_key="output2",
                    requires_confirmation=False,
                    system_prompt="You are step 2",
                ),
            ],
        )

    @pytest.fixture
    def mock_manager(self):
        """Create mock SubAgentManager with default responses"""
        manager = AsyncMock()
        manager.spawn_sub_agent = AsyncMock(return_value="subagent-001")
        manager.destroy_sub_agent = AsyncMock()
        manager.dispatch_request = AsyncMock(return_value=MagicMock(
            success=True,
            output="Step output",
            output_data={"result": "done"},
            requires_confirmation=False,
        ))
        return manager

    @pytest.mark.asyncio
    async def test_start_task(self, scenario_with_confirmation, mock_manager):
        """Test starting a task"""
        task_state = TaskState(
            task_id="task-start-001",
            scenario_id="confirm-scenario",
            initial_message="Test message",
            total_steps=len(scenario_with_confirmation.steps),
        )

        session = TaskSession(
            state=task_state,
            scenario=scenario_with_confirmation,
            sub_agent_manager=mock_manager,
            config=TaskSessionConfig(auto_start_next_step=False),
        )

        assert session.state.status == TaskStatus.PENDING

        await session.start()

        assert session.state.status == TaskStatus.RUNNING
        assert session.state.current_step_id == "step1"
        mock_manager.spawn_sub_agent.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancel_task(self, scenario_with_confirmation, mock_manager):
        """Test cancelling a task"""
        task_state = TaskState(
            task_id="task-cancel-001",
            scenario_id="confirm-scenario",
            total_steps=len(scenario_with_confirmation.steps),
        )

        session = TaskSession(
            state=task_state,
            scenario=scenario_with_confirmation,
            sub_agent_manager=mock_manager,
        )

        await session.start()
        await session.cancel()

        assert session.state.status == TaskStatus.CANCELLED
        # Verify SubAgent destroyed
        assert mock_manager.destroy_sub_agent.call_count >= 1

    @pytest.mark.asyncio
    async def test_complete_task(self, scenario_with_confirmation, mock_manager):
        """Test completing a task"""
        task_state = TaskState(
            task_id="task-complete-001",
            scenario_id="confirm-scenario",
            total_steps=len(scenario_with_confirmation.steps),
        )

        session = TaskSession(
            state=task_state,
            scenario=scenario_with_confirmation,
            sub_agent_manager=mock_manager,
        )

        await session.complete({"final_result": "success"})

        assert session.state.status == TaskStatus.COMPLETED
        assert session.state.final_output["final_result"] == "success"

    @pytest.mark.asyncio
    async def test_cancel_completed_task_warning(self, scenario_with_confirmation, mock_manager):
        """Test cancelling a completed task logs warning"""
        task_state = TaskState(
            task_id="task-cancel-done-001",
            scenario_id="confirm-scenario",
            total_steps=2,
        )

        session = TaskSession(
            state=task_state,
            scenario=scenario_with_confirmation,
            sub_agent_manager=mock_manager,
        )

        # Complete the task first
        await session.complete({"result": "done"})

        # Try to cancel (should not change state)
        await session.cancel()

        assert session.state.status == TaskStatus.COMPLETED  # Still completed


class TestTaskStateTransitions:
    """Test task state transitions"""

    def test_pending_to_running(self):
        """Test PENDING -> RUNNING transition"""
        state = TaskState(task_id="trans-001", scenario_id="test")
        assert state.status == TaskStatus.PENDING

        state.start()
        assert state.status == TaskStatus.RUNNING
        assert state.started_at is not None

    def test_running_to_waiting_user(self):
        """Test RUNNING -> WAITING_USER transition"""
        state = TaskState(task_id="trans-002", scenario_id="test")
        state.start()

        state.wait_for_user()
        assert state.status == TaskStatus.WAITING_USER

    def test_running_to_completed(self):
        """Test RUNNING -> COMPLETED transition"""
        state = TaskState(task_id="trans-003", scenario_id="test", total_steps=2)
        state.start()
        state.completed_steps = 2

        state.complete({"output": "done"})
        assert state.status == TaskStatus.COMPLETED
        assert state.final_output["output"] == "done"
        assert state.completed_at is not None

    def test_running_to_cancelled(self):
        """Test RUNNING -> CANCELLED transition"""
        state = TaskState(task_id="trans-004", scenario_id="test")
        state.start()

        state.cancel()
        assert state.status == TaskStatus.CANCELLED
        assert state.completed_at is not None

    def test_running_to_failed(self):
        """Test RUNNING -> FAILED transition"""
        state = TaskState(task_id="trans-005", scenario_id="test")
        state.start()

        state.fail("Something went wrong")
        assert state.status == TaskStatus.FAILED
        assert state.error_message == "Something went wrong"

    def test_progress_tracking(self):
        """Test progress tracking"""
        state = TaskState(task_id="progress-001", scenario_id="test", total_steps=5)

        assert state.get_progress() == (0, 5)
        assert state.get_progress_percent() == 0.0

        state.completed_steps = 2
        assert state.get_progress() == (2, 5)
        assert state.get_progress_percent() == 40.0

        state.completed_steps = 5
        assert state.get_progress_percent() == 100.0


class TestContextStorage:
    """Test context storage and retrieval"""

    @pytest.fixture
    def scenario_with_output_keys(self):
        """Create scenario with output keys"""
        return ScenarioDefinition(
            scenario_id="context-scenario",
            name="Context Scenario",
            steps=[
                StepDefinition(
                    step_id="analyze",
                    name="Analyze",
                    output_key="analysis",
                    requires_confirmation=False,
                ),
                StepDefinition(
                    step_id="review",
                    name="Review",
                    output_key="review_result",
                    dependencies=["analyze"],
                    requires_confirmation=False,
                ),
            ],
        )

    @pytest.fixture
    def mock_manager(self):
        """Create mock SubAgentManager"""
        manager = AsyncMock()
        manager.spawn_sub_agent = AsyncMock(return_value="subagent-001")
        manager.destroy_sub_agent = AsyncMock()
        manager.dispatch_request = AsyncMock(return_value=MagicMock(
            success=True,
            output="Done",
            output_data={"data": "test"},
            requires_confirmation=False,
        ))
        return manager

    def test_context_initialization(self, scenario_with_output_keys, mock_manager):
        """Test context is initialized empty"""
        task_state = TaskState(task_id="ctx-001", scenario_id="context-scenario")

        session = TaskSession(
            state=task_state,
            scenario=scenario_with_output_keys,
            sub_agent_manager=mock_manager,
        )

        assert session.context == {}
        assert session.state.context == {}

    @pytest.mark.asyncio
    async def test_context_update_on_step_completion(
        self, scenario_with_output_keys, mock_manager
    ):
        """Test context updated when step completes"""
        task_state = TaskState(
            task_id="ctx-002",
            scenario_id="context-scenario",
            total_steps=len(scenario_with_output_keys.steps),
        )

        session = TaskSession(
            state=task_state,
            scenario=scenario_with_output_keys,
            sub_agent_manager=mock_manager,
        )

        # Simulate step completion
        await session._complete_step("analyze", {"result": "analysis complete"})

        assert session.context["analysis"] == {"result": "analysis complete"}
        assert session.state.context["analysis"] == {"result": "analysis complete"}

    def test_get_step_output(self, scenario_with_output_keys, mock_manager):
        """Test getting step output"""
        task_state = TaskState(task_id="ctx-003", scenario_id="context-scenario")

        session = TaskSession(
            state=task_state,
            scenario=scenario_with_output_keys,
            sub_agent_manager=mock_manager,
        )

        # Set step output
        session.step_sessions["analyze"].output = {"result": "test output"}

        # Get step output
        output = session.get_step_output("analyze")
        assert output == {"result": "test output"}

        # Non-existent step
        assert session.get_step_output("nonexistent") is None

    def test_is_step_completed(self, scenario_with_output_keys, mock_manager):
        """Test checking if step is completed"""
        task_state = TaskState(task_id="ctx-004", scenario_id="context-scenario")

        session = TaskSession(
            state=task_state,
            scenario=scenario_with_output_keys,
            sub_agent_manager=mock_manager,
        )

        assert session.is_step_completed("analyze") is False

        # Mark step as completed
        session.step_sessions["analyze"].status = StepStatus.COMPLETED
        assert session.is_step_completed("analyze") is True

    def test_build_system_prompt_with_context(
        self, scenario_with_output_keys, mock_manager
    ):
        """Test building system prompt with context injection"""
        task_state = TaskState(task_id="ctx-005", scenario_id="context-scenario")

        session = TaskSession(
            state=task_state,
            scenario=scenario_with_output_keys,
            sub_agent_manager=mock_manager,
        )

        # Add context
        session.context["analysis"] = {"result": "code quality is good"}

        # Build prompt for review step
        step_def = scenario_with_output_keys.steps[1]
        prompt = session._build_system_prompt(step_def)

        # Verify context is included
        assert "前置步骤输出" in prompt or "analysis" in prompt.lower()

    def test_context_injection_disabled(self, scenario_with_output_keys, mock_manager):
        """Test context injection can be disabled"""
        task_state = TaskState(task_id="ctx-006", scenario_id="context-scenario")

        config = TaskSessionConfig(context_injection_enabled=False)
        session = TaskSession(
            state=task_state,
            scenario=scenario_with_output_keys,
            sub_agent_manager=mock_manager,
            config=config,
        )

        # Add context
        session.context["analysis"] = {"result": "test"}

        # Build prompt
        step_def = scenario_with_output_keys.steps[1]
        prompt = session._build_system_prompt(step_def)

        # Verify context is NOT included
        assert "前置步骤输出" not in prompt


class TestStepExecution:
    """Test step execution flow"""

    @pytest.fixture
    def scenario(self):
        """Create test scenario"""
        return ScenarioDefinition(
            scenario_id="exec-scenario",
            name="Exec Scenario",
            steps=[
                StepDefinition(
                    step_id="step1",
                    name="Step 1",
                    output_key="output1",
                    requires_confirmation=True,
                    system_prompt="You are step 1",
                ),
            ],
        )

    @pytest.fixture
    def mock_manager(self):
        """Create mock SubAgentManager"""
        manager = AsyncMock()
        manager.spawn_sub_agent = AsyncMock(return_value="subagent-001")
        manager.destroy_sub_agent = AsyncMock()
        manager.get_sub_agent = MagicMock(return_value=None)
        return manager

    @pytest.mark.asyncio
    async def test_dispatch_step(self, scenario, mock_manager):
        """Test dispatching message to step"""
        mock_manager.dispatch_request = AsyncMock(return_value=MagicMock(
            success=True,
            output="Response from step",
            output_data={"result": "done"},
            requires_confirmation=False,
        ))

        task_state = TaskState(
            task_id="dispatch-001",
            scenario_id="exec-scenario",
            total_steps=1,
        )

        session = TaskSession(
            state=task_state,
            scenario=scenario,
            sub_agent_manager=mock_manager,
        )

        await session.start()
        response = await session.dispatch_step("Test message")

        assert response == "Response from step"
        mock_manager.dispatch_request.assert_called()

    @pytest.mark.asyncio
    async def test_dispatch_step_to_specific_step(self, scenario, mock_manager):
        """Test dispatching message to specific step"""
        mock_manager.dispatch_request = AsyncMock(return_value=MagicMock(
            success=True,
            output="Response",
            output_data={},
            requires_confirmation=False,
        ))

        task_state = TaskState(
            task_id="dispatch-002",
            scenario_id="exec-scenario",
            total_steps=1,
        )

        session = TaskSession(
            state=task_state,
            scenario=scenario,
            sub_agent_manager=mock_manager,
        )

        await session.dispatch_step_to("step1", "Direct message")

        mock_manager.dispatch_request.assert_called()

    @pytest.mark.asyncio
    async def test_confirm_step(self, scenario, mock_manager):
        """Test confirming step output"""
        task_state = TaskState(
            task_id="confirm-001",
            scenario_id="exec-scenario",
            total_steps=1,
        )

        session = TaskSession(
            state=task_state,
            scenario=scenario,
            sub_agent_manager=mock_manager,
        )

        # Set step to waiting for confirmation
        session.step_sessions["step1"].status = StepStatus.WAITING_USER
        session.step_sessions["step1"].output = {"original": "output"}

        # Confirm with edited output
        result = await session.confirm_step("step1", {"edited": "output"})

        assert result is True
        assert session.step_sessions["step1"].status == StepStatus.COMPLETED
        assert session.context["output1"] == {"edited": "output"}

    @pytest.mark.asyncio
    async def test_confirm_step_not_waiting(self, scenario, mock_manager):
        """Test confirming step that is not waiting"""
        task_state = TaskState(
            task_id="confirm-002",
            scenario_id="exec-scenario",
            total_steps=1,
        )

        session = TaskSession(
            state=task_state,
            scenario=scenario,
            sub_agent_manager=mock_manager,
        )

        # Step is still PENDING, not WAITING_USER
        result = await session.confirm_step("step1")

        assert result is False

    @pytest.mark.asyncio
    async def test_confirm_nonexistent_step(self, scenario, mock_manager):
        """Test confirming non-existent step"""
        task_state = TaskState(
            task_id="confirm-003",
            scenario_id="exec-scenario",
        )

        session = TaskSession(
            state=task_state,
            scenario=scenario,
            sub_agent_manager=mock_manager,
        )

        result = await session.confirm_step("nonexistent")
        assert result is False


class TestStepSwitching:
    """Test step switching functionality"""

    @pytest.fixture
    def scenario_with_dependencies(self):
        """Create scenario with step dependencies"""
        return ScenarioDefinition(
            scenario_id="switch-scenario",
            name="Switch Scenario",
            steps=[
                StepDefinition(step_id="step1", name="Step 1", output_key="out1"),
                StepDefinition(
                    step_id="step2",
                    name="Step 2",
                    output_key="out2",
                    dependencies=["step1"],
                ),
                StepDefinition(
                    step_id="step3",
                    name="Step 3",
                    output_key="out3",
                    dependencies=["step1", "step2"],
                ),
            ],
        )

    @pytest.fixture
    def mock_manager(self):
        """Create mock SubAgentManager"""
        manager = AsyncMock()
        manager.spawn_sub_agent = AsyncMock(return_value="subagent-001")
        manager.destroy_sub_agent = AsyncMock()
        manager.get_sub_agent = MagicMock(return_value=None)
        return manager

    @pytest.mark.asyncio
    async def test_switch_to_step_dependencies_met(
        self, scenario_with_dependencies, mock_manager
    ):
        """Test switching when dependencies are met"""
        task_state = TaskState(
            task_id="switch-001",
            scenario_id="switch-scenario",
            total_steps=3,
        )

        session = TaskSession(
            state=task_state,
            scenario=scenario_with_dependencies,
            sub_agent_manager=mock_manager,
        )

        # Mark step1 as completed
        session.step_sessions["step1"].status = StepStatus.COMPLETED

        # Switch to step2
        result = await session.switch_to_step("step2")

        assert result is True
        assert session.state.current_step_id == "step2"

    @pytest.mark.asyncio
    async def test_switch_to_step_dependencies_not_met(
        self, scenario_with_dependencies, mock_manager
    ):
        """Test switching when dependencies are not met"""
        task_state = TaskState(
            task_id="switch-002",
            scenario_id="switch-scenario",
            total_steps=3,
        )

        session = TaskSession(
            state=task_state,
            scenario=scenario_with_dependencies,
            sub_agent_manager=mock_manager,
        )

        # step2 depends on step1, but step1 is not completed
        result = await session.switch_to_step("step2")

        assert result is False

    @pytest.mark.asyncio
    async def test_switch_to_nonexistent_step(
        self, scenario_with_dependencies, mock_manager
    ):
        """Test switching to non-existent step"""
        task_state = TaskState(
            task_id="switch-003",
            scenario_id="switch-scenario",
        )

        session = TaskSession(
            state=task_state,
            scenario=scenario_with_dependencies,
            sub_agent_manager=mock_manager,
        )

        result = await session.switch_to_step("nonexistent")
        assert result is False

    def test_check_step_dependencies(self, scenario_with_dependencies, mock_manager):
        """Test checking step dependencies"""
        task_state = TaskState(
            task_id="deps-001",
            scenario_id="switch-scenario",
        )

        session = TaskSession(
            state=task_state,
            scenario=scenario_with_dependencies,
            sub_agent_manager=mock_manager,
        )

        # step1 has no dependencies
        assert session._check_step_dependencies("step1") is True

        # step2 depends on step1 (not completed)
        assert session._check_step_dependencies("step2") is False

        # Complete step1
        session.step_sessions["step1"].status = StepStatus.COMPLETED
        assert session._check_step_dependencies("step2") is True

        # step3 depends on both step1 and step2
        assert session._check_step_dependencies("step3") is False

        # Complete step2
        session.step_sessions["step2"].status = StepStatus.COMPLETED
        assert session._check_step_dependencies("step3") is True


class TestModeSwitching:
    """Test mode switching"""

    @pytest.fixture
    def simple_scenario(self):
        """Create simple scenario"""
        return ScenarioDefinition(
            scenario_id="mode-scenario",
            name="Mode Scenario",
            steps=[StepDefinition(step_id="step1", name="Step 1")],
        )

    @pytest.fixture
    def mock_manager(self):
        """Create mock SubAgentManager"""
        return AsyncMock()

    def test_default_mode_is_step(self, simple_scenario, mock_manager):
        """Test default mode is step mode"""
        task_state = TaskState(task_id="mode-001", scenario_id="mode-scenario")

        session = TaskSession(
            state=task_state,
            scenario=simple_scenario,
            sub_agent_manager=mock_manager,
        )

        assert session.mode == "step"

    def test_switch_to_step_mode(self, simple_scenario, mock_manager):
        """Test switching to step mode"""
        task_state = TaskState(task_id="mode-002", scenario_id="mode-scenario")

        session = TaskSession(
            state=task_state,
            scenario=simple_scenario,
            sub_agent_manager=mock_manager,
        )

        session.mode = "free"
        session.switch_to_step_mode()
        assert session.mode == "step"

    def test_switch_to_free_mode(self, simple_scenario, mock_manager):
        """Test switching to free mode"""
        task_state = TaskState(task_id="mode-003", scenario_id="mode-scenario")

        session = TaskSession(
            state=task_state,
            scenario=simple_scenario,
            sub_agent_manager=mock_manager,
        )

        session.switch_to_free_mode()
        assert session.mode == "free"


class TestTaskSessionQueries:
    """Test TaskSession query methods"""

    @pytest.fixture
    def scenario(self):
        """Create test scenario"""
        return ScenarioDefinition(
            scenario_id="query-scenario",
            name="Query Scenario",
            steps=[
                StepDefinition(step_id="step1", name="Step 1"),
                StepDefinition(step_id="step2", name="Step 2"),
            ],
        )

    @pytest.fixture
    def mock_manager(self):
        """Create mock SubAgentManager"""
        return AsyncMock()

    def test_get_current_step(self, scenario, mock_manager):
        """Test getting current step"""
        task_state = TaskState(task_id="query-001", scenario_id="query-scenario")

        session = TaskSession(
            state=task_state,
            scenario=scenario,
            sub_agent_manager=mock_manager,
        )

        # No current step initially
        assert session.get_current_step() is None

        # Set current step
        session.state.current_step_id = "step1"
        current = session.get_current_step()
        assert current is not None
        assert current.step_id == "step1"

    def test_get_progress(self, scenario, mock_manager):
        """Test getting progress"""
        task_state = TaskState(
            task_id="query-002",
            scenario_id="query-scenario",
            total_steps=2,
        )

        session = TaskSession(
            state=task_state,
            scenario=scenario,
            sub_agent_manager=mock_manager,
        )

        assert session.get_progress() == (0, 2)

        session.state.completed_steps = 1
        assert session.get_progress() == (1, 2)

    def test_get_progress_percent(self, scenario, mock_manager):
        """Test getting progress percent"""
        task_state = TaskState(
            task_id="query-003",
            scenario_id="query-scenario",
        )

        session = TaskSession(
            state=task_state,
            scenario=scenario,
            sub_agent_manager=mock_manager,
        )

        # total_steps is set from scenario (2 steps)
        assert session.get_progress_percent() == 0.0

        session.state.completed_steps = 1
        assert session.get_progress_percent() == 50.0

    def test_to_dict(self, scenario, mock_manager):
        """Test exporting to dictionary"""
        task_state = TaskState(
            task_id="query-004",
            scenario_id="query-scenario",
            total_steps=2,
        )

        session = TaskSession(
            state=task_state,
            scenario=scenario,
            sub_agent_manager=mock_manager,
        )

        data = session.to_dict()

        assert "state" in data
        assert "scenario_id" in data
        assert "mode" in data
        assert "context" in data
        assert "step_sessions" in data
        assert data["scenario_id"] == "query-scenario"
        assert data["mode"] == "step"