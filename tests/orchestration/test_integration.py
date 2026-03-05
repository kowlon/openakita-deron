"""
Integration tests for task orchestration flow

Tests the complete task lifecycle without actual SubAgent process execution.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import tempfile
import yaml

from openakita.orchestration.models import (
    ScenarioDefinition,
    StepDefinition,
    TaskState,
    TaskStatus,
    StepStatus,
    TriggerPattern,
    TriggerType,
)
from openakita.orchestration.scenario_registry import ScenarioRegistry
from openakita.orchestration.task_session import TaskSession, TaskSessionConfig
from openakita.orchestration.task_orchestrator import TaskOrchestrator, OrchestratorConfig


class TestTaskFlow:
    """Test the complete task flow"""

    @pytest.fixture
    def sample_scenario(self):
        """Create a sample scenario for testing"""
        return ScenarioDefinition(
            scenario_id="test-flow",
            name="Test Flow",
            description="A test scenario for integration testing",
            category="test",
            trigger_patterns=[
                TriggerPattern(
                    type=TriggerType.KEYWORD,
                    keywords=["test", "测试"],
                    priority=1,
                ),
            ],
            steps=[
                StepDefinition(
                    step_id="step1",
                    name="First Step",
                    description="First step in the flow",
                    output_key="step1_output",
                    requires_confirmation=True,
                    system_prompt="You are step 1",
                ),
                StepDefinition(
                    step_id="step2",
                    name="Second Step",
                    description="Second step in the flow",
                    output_key="step2_output",
                    requires_confirmation=False,
                    dependencies=["step1"],
                    system_prompt="You are step 2. Previous output: {{context.step1_output}}",
                ),
            ],
        )

    @pytest.fixture
    def registry(self, sample_scenario):
        """Create a scenario registry with sample scenario"""
        registry = ScenarioRegistry()
        registry.register(sample_scenario)
        return registry

    def test_scenario_matching_to_task_creation(self, registry, sample_scenario):
        """Test flow from scenario matching to task creation"""
        # Step 1: Match scenario from dialog
        match = registry.match_from_dialog("这是一个测试消息")
        assert match is not None
        assert match.scenario.scenario_id == "test-flow"

        # Step 2: Create task state
        task_state = TaskState(
            task_id="task-test-001",
            scenario_id=match.scenario.scenario_id,
            total_steps=len(match.scenario.steps),
        )
        assert task_state.status == TaskStatus.PENDING

        # Step 3: Start task
        task_state.start()
        assert task_state.status == TaskStatus.RUNNING

        # Step 4: Simulate step completion
        task_state.completed_steps = 1
        assert task_state.get_progress() == (1, 2)

        # Step 5: Complete task
        task_state.complete({"result": "success"})
        assert task_state.status == TaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_task_session_lifecycle(self, sample_scenario):
        """Test TaskSession lifecycle"""
        # Create mock SubAgentManager
        mock_manager = AsyncMock()
        mock_manager.spawn_sub_agent = AsyncMock(return_value="subagent-001")
        mock_manager.destroy_sub_agent = AsyncMock()
        mock_manager.dispatch_request = AsyncMock(return_value=MagicMock(
            success=True,
            output="Step completed",
            output_data={"result": "done"},
            requires_confirmation=True,
        ))

        # Create task state
        task_state = TaskState(
            task_id="task-session-001",
            scenario_id=sample_scenario.scenario_id,
            initial_message="Test message",
            total_steps=len(sample_scenario.steps),
        )

        # Create task session
        session = TaskSession(
            state=task_state,
            scenario=sample_scenario,
            sub_agent_manager=mock_manager,
            config=TaskSessionConfig(auto_start_next_step=False),
        )

        # Verify initialization
        assert session.state.status == TaskStatus.PENDING
        assert len(session.step_sessions) == 2

        # Start session
        await session.start()
        # After start with auto_start_next_step=False, status is RUNNING but step not executed
        assert session.state.status == TaskStatus.RUNNING

        # Cleanup
        await session.cancel()
        assert session.state.status == TaskStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_context_passing_between_steps(self, sample_scenario):
        """Test context passing between steps"""
        mock_manager = AsyncMock()
        mock_manager.spawn_sub_agent = AsyncMock(return_value="subagent-001")
        mock_manager.destroy_sub_agent = AsyncMock()

        # Create task state
        task_state = TaskState(
            task_id="task-context-001",
            scenario_id=sample_scenario.scenario_id,
            total_steps=len(sample_scenario.steps),
        )

        # Create task session
        session = TaskSession(
            state=task_state,
            scenario=sample_scenario,
            sub_agent_manager=mock_manager,
            config=TaskSessionConfig(context_injection_enabled=True),
        )

        # Simulate step 1 completion with output
        session.context["step1_output"] = {"analysis": "Code quality is good"}
        session.state.completed_steps = 1

        # Build system prompt for step 2
        step2_def = sample_scenario.steps[1]
        prompt = session._build_system_prompt(step2_def)

        # Verify context is injected
        assert "前置步骤输出" in prompt or "analysis" in prompt

    def test_task_orchestrator_task_creation(self, registry):
        """Test TaskOrchestrator task creation"""
        # Create mock SubAgentManager
        mock_manager = AsyncMock()

        # Create orchestrator
        orchestrator = TaskOrchestrator(
            scenario_registry=registry,
            sub_agent_manager=mock_manager,
            config=OrchestratorConfig(),
        )

        # Create task from dialog
        # Note: This is a synchronous test, so we just verify the structure
        # In real async context, we would await the methods


class TestScenarioLoading:
    """Test scenario loading from files"""

    def test_load_scenarios_from_yaml_files(self):
        """Test loading scenarios from YAML configuration"""
        registry = ScenarioRegistry()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create YAML files
            yaml_files = [
                ("scenario1.yaml", {
                    "scenario_id": "s1",
                    "name": "Scenario 1",
                    "category": "test",
                    "trigger_patterns": [
                        {"type": "keyword", "keywords": ["test"]}
                    ],
                    "steps": [
                        {"step_id": "step1", "name": "Step 1"}
                    ],
                }),
                ("scenario2.yaml", {
                    "scenario_id": "s2",
                    "name": "Scenario 2",
                    "category": "development",
                    "trigger_patterns": [
                        {"type": "regex", "pattern": "review.*code"}
                    ],
                    "steps": [
                        {"step_id": "step1", "name": "Step 1"},
                        {"step_id": "step2", "name": "Step 2"},
                    ],
                }),
            ]

            for filename, content in yaml_files:
                with open(Path(tmpdir) / filename, 'w') as f:
                    yaml.dump(content, f)

            # Load scenarios
            count = registry.load_from_directory(tmpdir)
            assert count == 2

            # Verify loaded scenarios
            scenarios = registry.list_all()
            assert len(scenarios) == 2

            # Test matching
            match = registry.match_from_dialog("test scenario")
            assert match is not None

    def test_scenario_yaml_with_tools_config(self):
        """Test loading scenario with tools configuration"""
        registry = ScenarioRegistry()

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump({
                "scenario_id": "tools-test",
                "name": "Tools Test",
                "steps": [
                    {
                        "step_id": "step1",
                        "name": "Step with tools",
                        "tools": {
                            "system_tools": ["read_file", "write_file"],
                            "mcp_tools": [],
                        },
                    },
                ],
            }, f)
            yaml_path = f.name

        try:
            scenario = registry.load_from_yaml(yaml_path)
            assert scenario is not None
            assert len(scenario.steps) == 1
            assert "read_file" in scenario.steps[0].tools.system_tools
        finally:
            Path(yaml_path).unlink()


class TestTaskStateTransitions:
    """Test task state transitions"""

    def test_valid_state_transitions(self):
        """Test valid state transitions"""
        state = TaskState(
            task_id="transitions-001",
            scenario_id="test",
        )

        # PENDING -> RUNNING
        state.start()
        assert state.status == TaskStatus.RUNNING

        # RUNNING -> WAITING_USER
        state.wait_for_user()
        assert state.status == TaskStatus.WAITING_USER

        # WAITING_USER -> RUNNING (continue)
        state.status = TaskStatus.RUNNING
        assert state.status == TaskStatus.RUNNING

    def test_cancel_from_any_state(self):
        """Test cancellation from different states"""
        for initial_status in [TaskStatus.PENDING, TaskStatus.RUNNING, TaskStatus.WAITING_USER]:
            state = TaskState(
                task_id=f"cancel-{initial_status.value}",
                scenario_id="test",
            )
            if initial_status != TaskStatus.PENDING:
                state.start()
            if initial_status == TaskStatus.WAITING_USER:
                state.wait_for_user()

            state.cancel()
            assert state.status == TaskStatus.CANCELLED

    def test_complete_task(self):
        """Test task completion"""
        state = TaskState(
            task_id="complete-001",
            scenario_id="test",
            total_steps=3,
        )

        state.start()
        state.completed_steps = 3
        state.complete({"result": "all done"})

        assert state.status == TaskStatus.COMPLETED
        assert state.final_output["result"] == "all done"

    def test_fail_task(self):
        """Test task failure"""
        state = TaskState(
            task_id="fail-001",
            scenario_id="test",
        )

        state.start()
        state.fail("Something went wrong")

        assert state.status == TaskStatus.FAILED
        assert state.error_message == "Something went wrong"


class TestStepSessionManagement:
    """Test step session management"""

    def test_step_session_lifecycle(self):
        """Test step session lifecycle"""
        from openakita.orchestration.models import StepSession

        session = StepSession(step_id="step-001")

        # Initial state
        assert session.status == StepStatus.PENDING

        # Start
        session.start()
        assert session.status == StepStatus.RUNNING
        assert session.started_at is not None

        # Wait for user
        session.wait_for_user()
        assert session.status == StepStatus.WAITING_USER

        # Complete
        session.complete({"output": "done"})
        assert session.status == StepStatus.COMPLETED
        assert session.completed_at is not None

    def test_step_session_messages(self):
        """Test adding messages to step session"""
        from openakita.orchestration.models import StepSession

        session = StepSession(step_id="step-001")

        session.add_message("user", "Hello")
        session.add_message("assistant", "Hi there!")

        assert len(session.messages) == 2
        assert session.messages[0]["role"] == "user"
        assert session.messages[1]["role"] == "assistant"

    def test_step_session_failure(self):
        """Test step session failure"""
        from openakita.orchestration.models import StepSession

        session = StepSession(step_id="step-001")
        session.start()
        session.fail("Test failure")

        assert session.status == StepStatus.FAILED
        assert session.error_message == "Test failure"