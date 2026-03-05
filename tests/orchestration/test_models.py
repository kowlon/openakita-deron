"""
Unit tests for orchestration models
"""

import pytest
from datetime import datetime

from openakita.orchestration.models import (
    TaskStatus,
    StepStatus,
    ProcessMode,
    BrainMode,
    TriggerType,
    CapabilitiesConfig,
    RuntimeConfig,
    TriggerPattern,
    ToolsConfig,
    SubAgentConfig,
    StepDefinition,
    ScenarioDefinition,
    StepSession,
    TaskState,
)


class TestEnums:
    """Test enum types"""

    def test_task_status_values(self):
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.RUNNING.value == "running"
        assert TaskStatus.WAITING_USER.value == "waiting_user"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.CANCELLED.value == "cancelled"
        assert TaskStatus.FAILED.value == "failed"

    def test_step_status_values(self):
        assert StepStatus.PENDING.value == "pending"
        assert StepStatus.RUNNING.value == "running"
        assert StepStatus.COMPLETED.value == "completed"
        assert StepStatus.WAITING_USER.value == "waiting_user"

    def test_process_mode_values(self):
        assert ProcessMode.WORKER.value == "worker"
        assert ProcessMode.INLINE.value == "inline"

    def test_brain_mode_values(self):
        assert BrainMode.SHARED_PROXY.value == "shared_proxy"
        assert BrainMode.INDEPENDENT.value == "independent"


class TestCapabilitiesConfig:
    """Test CapabilitiesConfig"""

    def test_default_values(self):
        config = CapabilitiesConfig()
        assert config.allow_shell is False
        assert config.allow_write is False
        assert config.allow_network is True

    def test_custom_values(self):
        config = CapabilitiesConfig(allow_shell=True, allow_write=True)
        assert config.allow_shell is True
        assert config.allow_write is True

    def test_serialization(self):
        config = CapabilitiesConfig(allow_shell=True)
        data = config.to_dict()
        assert data["allow_shell"] is True

        restored = CapabilitiesConfig.from_dict(data)
        assert restored.allow_shell is True


class TestRuntimeConfig:
    """Test RuntimeConfig"""

    def test_default_values(self):
        config = RuntimeConfig()
        assert config.max_iterations == 20
        assert config.session_type == "cli"
        assert config.timeout_seconds == 300

    def test_serialization(self):
        config = RuntimeConfig(max_iterations=50, timeout_seconds=600)
        data = config.to_dict()
        assert data["max_iterations"] == 50
        assert data["timeout_seconds"] == 600

        restored = RuntimeConfig.from_dict(data)
        assert restored.max_iterations == 50


class TestToolsConfig:
    """Test ToolsConfig"""

    def test_default_values(self):
        config = ToolsConfig()
        assert config.system_tools == []
        assert config.mcp_tools == []

    def test_custom_values(self):
        config = ToolsConfig(
            system_tools=["read_file", "write_file"],
            mcp_tools=["mcp_tool_1"]
        )
        assert len(config.system_tools) == 2
        assert "read_file" in config.system_tools


class TestSubAgentConfig:
    """Test SubAgentConfig"""

    def test_create_config(self):
        config = SubAgentConfig(
            subagent_id="test-agent",
            name="Test Agent",
            description="Test description",
            system_prompt="You are a test agent",
            allowed_tools=["read_file", "grep"],
        )
        assert config.subagent_id == "test-agent"
        assert len(config.allowed_tools) == 2

    def test_serialization(self):
        config = SubAgentConfig(
            subagent_id="test",
            name="Test",
            capabilities=CapabilitiesConfig(allow_shell=True),
        )
        data = config.to_dict()
        assert data["subagent_id"] == "test"
        assert data["capabilities"]["allow_shell"] is True

        restored = SubAgentConfig.from_dict(data)
        assert restored.subagent_id == "test"
        assert restored.capabilities.allow_shell is True


class TestStepDefinition:
    """Test StepDefinition"""

    def test_create_step(self):
        step = StepDefinition(
            step_id="step1",
            name="First Step",
            description="Test step",
            output_key="step1_output",
            requires_confirmation=True,
        )
        assert step.step_id == "step1"
        assert step.requires_confirmation is True

    def test_serialization(self):
        step = StepDefinition(
            step_id="step1",
            name="Step 1",
            tools=ToolsConfig(system_tools=["read_file"]),
        )
        data = step.to_dict()
        assert data["step_id"] == "step1"
        assert "read_file" in data["tools"]["system_tools"]

        restored = StepDefinition.from_dict(data)
        assert restored.step_id == "step1"
        assert "read_file" in restored.tools.system_tools


class TestScenarioDefinition:
    """Test ScenarioDefinition"""

    def test_create_scenario(self):
        scenario = ScenarioDefinition(
            scenario_id="test-scenario",
            name="Test Scenario",
            description="A test scenario",
            category="test",
            steps=[
                StepDefinition(step_id="step1", name="Step 1"),
                StepDefinition(step_id="step2", name="Step 2"),
            ],
        )
        assert scenario.scenario_id == "test-scenario"
        assert len(scenario.steps) == 2

    def test_get_step(self):
        scenario = ScenarioDefinition(
            scenario_id="test",
            name="Test",
            steps=[
                StepDefinition(step_id="step1", name="Step 1"),
                StepDefinition(step_id="step2", name="Step 2"),
            ],
        )
        step = scenario.get_step("step1")
        assert step is not None
        assert step.name == "Step 1"

        assert scenario.get_step("nonexistent") is None

    def test_get_step_index(self):
        scenario = ScenarioDefinition(
            scenario_id="test",
            name="Test",
            steps=[
                StepDefinition(step_id="step1", name="Step 1"),
                StepDefinition(step_id="step2", name="Step 2"),
            ],
        )
        assert scenario.get_step_index("step1") == 0
        assert scenario.get_step_index("step2") == 1
        assert scenario.get_step_index("nonexistent") == -1


class TestStepSession:
    """Test StepSession"""

    def test_create_session(self):
        session = StepSession(step_id="step1")
        assert session.step_id == "step1"
        assert session.status == StepStatus.PENDING

    def test_start(self):
        session = StepSession(step_id="step1")
        session.start()
        assert session.status == StepStatus.RUNNING
        assert session.started_at is not None

    def test_complete(self):
        session = StepSession(step_id="step1")
        session.start()
        session.complete({"result": "done"})
        assert session.status == StepStatus.COMPLETED
        assert session.output["result"] == "done"

    def test_wait_for_user(self):
        session = StepSession(step_id="step1")
        session.wait_for_user()
        assert session.status == StepStatus.WAITING_USER

    def test_fail(self):
        session = StepSession(step_id="step1")
        session.fail("Test error")
        assert session.status == StepStatus.FAILED
        assert session.error_message == "Test error"

    def test_add_message(self):
        session = StepSession(step_id="step1")
        session.add_message("user", "Hello")
        session.add_message("assistant", "Hi!")
        assert len(session.messages) == 2
        assert session.messages[0]["role"] == "user"


class TestTaskState:
    """Test TaskState"""

    def test_create_state(self):
        state = TaskState(
            task_id="task-001",
            scenario_id="test-scenario",
            total_steps=3,
        )
        assert state.task_id == "task-001"
        assert state.status == TaskStatus.PENDING
        assert state.total_steps == 3

    def test_start(self):
        state = TaskState(
            task_id="task-001",
            scenario_id="test-scenario",
        )
        state.start()
        assert state.status == TaskStatus.RUNNING
        assert state.started_at is not None

    def test_complete(self):
        state = TaskState(
            task_id="task-001",
            scenario_id="test-scenario",
        )
        state.start()
        state.complete({"result": "done"})
        assert state.status == TaskStatus.COMPLETED
        assert state.final_output["result"] == "done"

    def test_cancel(self):
        state = TaskState(
            task_id="task-001",
            scenario_id="test-scenario",
        )
        state.start()
        state.cancel()
        assert state.status == TaskStatus.CANCELLED

    def test_progress(self):
        state = TaskState(
            task_id="task-001",
            scenario_id="test-scenario",
            total_steps=4,
            completed_steps=1,
        )
        progress = state.get_progress()
        assert progress == (1, 4)
        assert state.get_progress_percent() == 25.0

    def test_serialization(self):
        state = TaskState(
            task_id="task-001",
            scenario_id="test-scenario",
            session_id="session-001",
            total_steps=3,
            context={"key": "value"},
        )
        data = state.to_dict()
        assert data["task_id"] == "task-001"
        assert data["context"]["key"] == "value"

        restored = TaskState.from_dict(data)
        assert restored.task_id == "task-001"
        assert restored.context["key"] == "value"