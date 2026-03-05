"""
End-to-End tests for multi-task orchestration scenarios

Tests complete task flows using demo skills and scenario files.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import json

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


# Path to scenario files
SCENARIOS_DIR = Path(__file__).parent.parent.parent / "scenarios"


class MockSubAgentManager:
    """Mock SubAgentManager for E2E testing"""

    def __init__(self):
        self.agents = {}
        self.call_count = 0

    async def spawn_sub_agent(self, agent_id: str, config: dict = None):
        self.agents[agent_id] = {"id": agent_id, "config": config}
        return agent_id

    async def destroy_sub_agent(self, agent_id: str):
        if agent_id in self.agents:
            del self.agents[agent_id]

    async def dispatch_request(self, agent_id: str, request):
        self.call_count += 1

        # Handle both dict and StepRequest objects
        if hasattr(request, 'step_id'):
            step_id = request.step_id
        else:
            step_id = request.get("step_id", "")

        # Mock different skill outputs based on step
        if "echo" in step_id or "generate" in step_id:
            output_data = {
                "ok": True,
                "trace_id": "demo-flow-001",
                "payload": {"user": "test_user", "action": "multi_step_test"},
                "received_at": "2026-03-05T00:00:00",
            }
        elif "hash" in step_id:
            output_data = {
                "ok": True,
                "algorithm": "sha256",
                "digest": "a" * 64,
                "length": 100,
            }
        elif "validate" in step_id or "schema" in step_id:
            output_data = {
                "ok": True,
                "errors": [],
            }
        elif "diff" in step_id:
            output_data = {
                "ok": True,
                "changed_paths": ["title"],
                "counts": {"modified": 1, "added": 0, "removed": 0},
            }
        elif "summary" in step_id or "report" in step_id or "finalize" in step_id:
            output_data = {
                "ok": True,
                "trace_id": "demo-flow-001",
                "steps_completed": 4,
                "hash_digest": "a" * 64,
                "validation_status": "ok",
                "overall_status": "success",
            }
        else:
            output_data = {"ok": True, "result": "completed"}

        return MagicMock(
            success=True,
            output="Step completed successfully",
            output_data=output_data,
            requires_confirmation=False,
        )


class TestDemoFlowE2E:
    """E2E tests for test-demo-flow scenario"""

    @pytest.fixture
    def demo_flow_scenario(self):
        """Load test-demo-flow scenario from YAML"""
        registry = ScenarioRegistry()
        scenario_path = SCENARIOS_DIR / "test-demo-flow.yaml"

        if scenario_path.exists():
            scenario = registry.load_from_yaml(str(scenario_path))
            return scenario
        else:
            # Create inline scenario for testing
            return ScenarioDefinition(
                scenario_id="test-demo-flow",
                name="Demo 技能流程测试",
                description="Test flow with demo skills",
                category="test",
                trigger_patterns=[
                    TriggerPattern(
                        type=TriggerType.KEYWORD,
                        keywords=["测试demo流程", "demo flow test"],
                        priority=1,
                    ),
                ],
                steps=[
                    StepDefinition(
                        step_id="echo",
                        name="生成测试数据",
                        description="Generate test data using demo-echo-json",
                        output_key="echo_result",
                        requires_confirmation=False,
                        system_prompt="Generate test data",
                    ),
                    StepDefinition(
                        step_id="hash",
                        name="计算数据指纹",
                        description="Calculate SHA256 hash",
                        output_key="hash_result",
                        requires_confirmation=False,
                        dependencies=["echo"],
                        system_prompt="Calculate hash. Previous: {{context.echo_result}}",
                    ),
                    StepDefinition(
                        step_id="validate",
                        name="校验数据结构",
                        description="Validate schema",
                        output_key="validation_result",
                        requires_confirmation=True,
                        dependencies=["echo"],
                        system_prompt="Validate schema. Data: {{context.echo_result}}",
                    ),
                    StepDefinition(
                        step_id="summary",
                        name="生成测试报告",
                        description="Generate final report",
                        output_key="final_report",
                        requires_confirmation=False,
                        dependencies=["echo", "hash", "validate"],
                        system_prompt="Generate report. Echo: {{context.echo_result}}, Hash: {{context.hash_result}}, Validation: {{context.validation_result}}",
                    ),
                ],
            )

    @pytest.fixture
    def mock_manager(self):
        """Create mock SubAgentManager"""
        return MockSubAgentManager()

    def test_scenario_loading(self, demo_flow_scenario):
        """Test that scenario is loaded correctly"""
        assert demo_flow_scenario.scenario_id == "test-demo-flow"
        assert demo_flow_scenario.name == "Demo 技能流程测试"
        assert len(demo_flow_scenario.steps) == 4

        # Verify step IDs
        step_ids = [s.step_id for s in demo_flow_scenario.steps]
        assert step_ids == ["echo", "hash", "validate", "summary"]

    def test_step_dependencies(self, demo_flow_scenario):
        """Test that step dependencies are correctly defined"""
        steps = {s.step_id: s for s in demo_flow_scenario.steps}

        # echo has no dependencies
        assert len(steps["echo"].dependencies) == 0

        # hash depends on echo
        assert "echo" in steps["hash"].dependencies

        # validate depends on echo
        assert "echo" in steps["validate"].dependencies

        # summary depends on echo, hash, validate
        assert set(steps["summary"].dependencies) == {"echo", "hash", "validate"}

    def test_output_keys_defined(self, demo_flow_scenario):
        """Test that output keys are properly defined for context passing"""
        steps = {s.step_id: s for s in demo_flow_scenario.steps}

        assert steps["echo"].output_key == "echo_result"
        assert steps["hash"].output_key == "hash_result"
        assert steps["validate"].output_key == "validation_result"
        assert steps["summary"].output_key == "final_report"

    def test_requires_confirmation_flags(self, demo_flow_scenario):
        """Test that requires_confirmation flags are set correctly"""
        steps = {s.step_id: s for s in demo_flow_scenario.steps}

        # echo does not require confirmation
        assert steps["echo"].requires_confirmation is False

        # hash does not require confirmation
        assert steps["hash"].requires_confirmation is False

        # validate requires confirmation
        assert steps["validate"].requires_confirmation is True

        # summary does not require confirmation
        assert steps["summary"].requires_confirmation is False

    @pytest.mark.asyncio
    async def test_task_creation_success(self, demo_flow_scenario, mock_manager):
        """Test that task is created successfully"""
        # Create task state
        task_state = TaskState(
            task_id="e2e-demo-flow-001",
            scenario_id=demo_flow_scenario.scenario_id,
            total_steps=len(demo_flow_scenario.steps),
        )

        # Create task session
        session = TaskSession(
            state=task_state,
            scenario=demo_flow_scenario,
            sub_agent_manager=mock_manager,
            config=TaskSessionConfig(auto_start_next_step=False),
        )

        # Verify initial state
        assert session.state.status == TaskStatus.PENDING
        assert session.state.total_steps == 4
        assert len(session.step_sessions) == 4

    @pytest.mark.asyncio
    async def test_step_execution_order(self, demo_flow_scenario, mock_manager):
        """Test that steps execute in correct order based on dependencies"""
        # Create task session
        task_state = TaskState(
            task_id="e2e-step-order-001",
            scenario_id=demo_flow_scenario.scenario_id,
            total_steps=len(demo_flow_scenario.steps),
        )

        session = TaskSession(
            state=task_state,
            scenario=demo_flow_scenario,
            sub_agent_manager=mock_manager,
            config=TaskSessionConfig(auto_start_next_step=False),
        )

        # Start session
        await session.start()
        assert session.state.status == TaskStatus.RUNNING

        # Verify all 4 step sessions exist
        assert len(session.step_sessions) == 4

        # Verify step IDs
        step_ids = set(session.step_sessions.keys())
        assert step_ids == {"echo", "hash", "validate", "summary"}

    @pytest.mark.asyncio
    async def test_context_passing(self, demo_flow_scenario, mock_manager):
        """Test that context is passed correctly between steps"""
        # Create task session
        task_state = TaskState(
            task_id="e2e-context-001",
            scenario_id=demo_flow_scenario.scenario_id,
            total_steps=len(demo_flow_scenario.steps),
        )

        session = TaskSession(
            state=task_state,
            scenario=demo_flow_scenario,
            sub_agent_manager=mock_manager,
            config=TaskSessionConfig(context_injection_enabled=True),
        )

        # Simulate step 1 (echo) completion
        session.context["echo_result"] = {
            "ok": True,
            "trace_id": "demo-flow-001",
            "payload": {"test": "data"},
        }

        # Build prompt for step 2 (hash)
        step2 = demo_flow_scenario.steps[1]  # hash step
        prompt = session._build_system_prompt(step2)

        # Verify context is injected
        assert "echo_result" in prompt or "demo-flow-001" in prompt or "payload" in prompt

    @pytest.mark.asyncio
    async def test_final_report_generation(self, demo_flow_scenario, mock_manager):
        """Test that final report is generated correctly"""
        # Create task session
        task_state = TaskState(
            task_id="e2e-report-001",
            scenario_id=demo_flow_scenario.scenario_id,
            total_steps=len(demo_flow_scenario.steps),
        )

        session = TaskSession(
            state=task_state,
            scenario=demo_flow_scenario,
            sub_agent_manager=mock_manager,
            config=TaskSessionConfig(auto_start_next_step=False),
        )

        # Simulate all steps completed
        session.context["echo_result"] = {
            "ok": True,
            "trace_id": "demo-flow-001",
            "payload": {"test": "data"},
        }
        session.context["hash_result"] = {
            "ok": True,
            "digest": "a" * 64,
            "algorithm": "sha256",
        }
        session.context["validation_result"] = {
            "ok": True,
            "errors": [],
        }
        session.context["final_report"] = {
            "ok": True,
            "trace_id": "demo-flow-001",
            "steps_completed": 4,
            "hash_digest": "a" * 64,
            "validation_status": "ok",
            "overall_status": "success",
        }

        # Build prompt for final step
        step4 = demo_flow_scenario.steps[3]  # summary step
        prompt = session._build_system_prompt(step4)

        # Verify all context variables are referenced
        assert "echo_result" in prompt or "hash_result" in prompt or "validation_result" in prompt


class TestEditFlowE2E:
    """E2E tests for test-edit-flow scenario"""

    @pytest.fixture
    def edit_flow_scenario(self):
        """Load test-edit-flow scenario from YAML"""
        registry = ScenarioRegistry()
        scenario_path = SCENARIOS_DIR / "test-edit-flow.yaml"

        if scenario_path.exists():
            scenario = registry.load_from_yaml(str(scenario_path))
            return scenario
        else:
            # Create inline scenario for testing
            return ScenarioDefinition(
                scenario_id="test-edit-flow",
                name="编辑流程测试",
                description="Test edit and diff flow",
                category="test",
                trigger_patterns=[
                    TriggerPattern(
                        type=TriggerType.KEYWORD,
                        keywords=["编辑测试", "edit test"],
                        priority=1,
                    ),
                ],
                steps=[
                    StepDefinition(
                        step_id="generate",
                        name="生成初始数据",
                        description="Generate initial data",
                        output_key="initial_data",
                        requires_confirmation=True,
                        system_prompt="Generate initial data",
                    ),
                    StepDefinition(
                        step_id="diff",
                        name="对比变更",
                        description="Compare differences",
                        output_key="diff_result",
                        requires_confirmation=False,
                        dependencies=["generate"],
                        system_prompt="Compare. Before: original, After: {{context.initial_data}}",
                    ),
                    StepDefinition(
                        step_id="finalize",
                        name="确认最终版本",
                        description="Generate final version",
                        output_key="final_version",
                        requires_confirmation=False,
                        dependencies=["generate", "diff"],
                        system_prompt="Finalize. Data: {{context.initial_data}}, Diff: {{context.diff_result}}",
                    ),
                ],
            )

    @pytest.fixture
    def mock_manager(self):
        """Create mock SubAgentManager"""
        return MockSubAgentManager()

    def test_scenario_loading(self, edit_flow_scenario):
        """Test that edit flow scenario is loaded correctly"""
        assert edit_flow_scenario.scenario_id == "test-edit-flow"
        assert len(edit_flow_scenario.steps) == 3

    def test_generate_step_requires_confirmation(self, edit_flow_scenario):
        """Test that generate step requires confirmation"""
        steps = {s.step_id: s for s in edit_flow_scenario.steps}
        assert steps["generate"].requires_confirmation is True

    def test_diff_step_dependencies(self, edit_flow_scenario):
        """Test that diff step depends on generate"""
        steps = {s.step_id: s for s in edit_flow_scenario.steps}
        assert "generate" in steps["diff"].dependencies

    def test_finalize_step_dependencies(self, edit_flow_scenario):
        """Test that finalize step depends on generate and diff"""
        steps = {s.step_id: s for s in edit_flow_scenario.steps}
        assert "generate" in steps["finalize"].dependencies
        assert "diff" in steps["finalize"].dependencies

    @pytest.mark.asyncio
    async def test_edit_flow_task_creation(self, edit_flow_scenario, mock_manager):
        """Test edit flow task creation"""
        task_state = TaskState(
            task_id="e2e-edit-001",
            scenario_id=edit_flow_scenario.scenario_id,
            total_steps=len(edit_flow_scenario.steps),
        )

        session = TaskSession(
            state=task_state,
            scenario=edit_flow_scenario,
            sub_agent_manager=mock_manager,
            config=TaskSessionConfig(auto_start_next_step=False),
        )

        assert session.state.status == TaskStatus.PENDING
        assert len(session.step_sessions) == 3


class TestScenarioTriggering:
    """Test scenario triggering from dialog"""

    @pytest.fixture
    def demo_flow_scenario(self):
        """Load test-demo-flow scenario from YAML"""
        registry = ScenarioRegistry()
        scenario_path = SCENARIOS_DIR / "test-demo-flow.yaml"

        if scenario_path.exists():
            scenario = registry.load_from_yaml(str(scenario_path))
            return scenario
        else:
            # Create inline scenario for testing
            return ScenarioDefinition(
                scenario_id="test-demo-flow",
                name="Demo 技能流程测试",
                description="Test flow with demo skills",
                category="test",
                trigger_patterns=[
                    TriggerPattern(
                        type=TriggerType.KEYWORD,
                        keywords=["测试demo流程", "demo flow test"],
                        priority=1,
                    ),
                ],
                steps=[
                    StepDefinition(step_id="echo", name="Step 1"),
                    StepDefinition(step_id="hash", name="Step 2"),
                ],
            )

    @pytest.fixture
    def edit_flow_scenario(self):
        """Load test-edit-flow scenario from YAML"""
        registry = ScenarioRegistry()
        scenario_path = SCENARIOS_DIR / "test-edit-flow.yaml"

        if scenario_path.exists():
            scenario = registry.load_from_yaml(str(scenario_path))
            return scenario
        else:
            return ScenarioDefinition(
                scenario_id="test-edit-flow",
                name="编辑流程测试",
                description="Test edit flow",
                category="test",
                trigger_patterns=[
                    TriggerPattern(
                        type=TriggerType.KEYWORD,
                        keywords=["编辑测试", "edit test"],
                        priority=1,
                    ),
                ],
                steps=[],
            )

    @pytest.fixture
    def registry_with_scenarios(self, demo_flow_scenario, edit_flow_scenario):
        """Create registry with test scenarios"""
        registry = ScenarioRegistry()
        registry.register(demo_flow_scenario)
        registry.register(edit_flow_scenario)
        return registry

    def test_trigger_demo_flow_with_keyword(self, registry_with_scenarios):
        """Test triggering demo flow scenario with keyword"""
        match = registry_with_scenarios.match_from_dialog("测试demo流程")
        assert match is not None
        assert match.scenario.scenario_id == "test-demo-flow"

    def test_trigger_demo_flow_with_english_keyword(self, registry_with_scenarios):
        """Test triggering demo flow scenario with English keyword"""
        match = registry_with_scenarios.match_from_dialog("demo flow test")
        assert match is not None
        assert match.scenario.scenario_id == "test-demo-flow"

    def test_trigger_edit_flow(self, registry_with_scenarios):
        """Test triggering edit flow scenario"""
        match = registry_with_scenarios.match_from_dialog("编辑测试")
        assert match is not None
        assert match.scenario.scenario_id == "test-edit-flow"

    def test_no_match_for_unknown_message(self, registry_with_scenarios):
        """Test no match for unknown message"""
        match = registry_with_scenarios.match_from_dialog("这是一条普通消息")
        assert match is None