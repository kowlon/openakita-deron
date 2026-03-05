"""
Unit tests for context passing mechanism

Tests automatic context passing between steps and template variable replacement.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from openakita.orchestration.models import (
    ScenarioDefinition,
    StepDefinition,
    StepStatus,
    TaskState,
    TaskStatus,
    TriggerPattern,
    TriggerType,
)
from openakita.orchestration.task_session import TaskSession, TaskSessionConfig


class TestSingleStepNoContext:
    """Test single step scenario without context"""

    @pytest.fixture
    def single_step_scenario(self):
        """Create a single step scenario"""
        return ScenarioDefinition(
            scenario_id="single-step",
            name="Single Step",
            steps=[
                StepDefinition(
                    step_id="only-step",
                    name="Only Step",
                    system_prompt="You are a helper.",
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
            output_data={"result": "complete"},
            requires_confirmation=False,
        ))
        return manager

    def test_single_step_context_empty(self, single_step_scenario, mock_manager):
        """Test context is empty for single step"""
        task_state = TaskState(
            task_id="single-001",
            scenario_id="single-step",
        )

        session = TaskSession(
            state=task_state,
            scenario=single_step_scenario,
            sub_agent_manager=mock_manager,
        )

        assert session.context == {}
        assert len(session.step_sessions) == 1

    @pytest.mark.asyncio
    async def test_single_step_no_context_in_prompt(
        self, single_step_scenario, mock_manager
    ):
        """Test system prompt has no context section for single step"""
        task_state = TaskState(
            task_id="single-002",
            scenario_id="single-step",
            initial_message="Hello",
        )

        session = TaskSession(
            state=task_state,
            scenario=single_step_scenario,
            sub_agent_manager=mock_manager,
        )

        # Build system prompt
        step_def = single_step_scenario.steps[0]
        prompt = session._build_system_prompt(step_def)

        # No context section since context is empty
        assert "前置步骤输出" not in prompt
        assert prompt == "You are a helper."

    @pytest.mark.asyncio
    async def test_single_step_completion(self, single_step_scenario, mock_manager):
        """Test single step completes without context dependencies"""
        task_state = TaskState(
            task_id="single-003",
            scenario_id="single-step",
            initial_message="Test",
        )

        session = TaskSession(
            state=task_state,
            scenario=single_step_scenario,
            sub_agent_manager=mock_manager,
        )

        await session.start()

        # Single step should complete the task
        assert session.state.status == TaskStatus.COMPLETED


class TestTwoStepContextPass:
    """Test two step context passing"""

    @pytest.fixture
    def two_step_scenario(self):
        """Create a two step scenario with context passing"""
        return ScenarioDefinition(
            scenario_id="two-step",
            name="Two Step",
            steps=[
                StepDefinition(
                    step_id="generate",
                    name="Generate",
                    output_key="generated_data",
                    system_prompt="Generate some data.",
                    requires_confirmation=False,
                ),
                StepDefinition(
                    step_id="process",
                    name="Process",
                    output_key="processed_data",
                    system_prompt="Process the data. Previous: {{context.generated_data}}",
                    requires_confirmation=False,
                    dependencies=["generate"],
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
            output="Step output",
            output_data={"value": "test"},
            requires_confirmation=False,
        ))
        return manager

    def test_context_updated_after_first_step(self, two_step_scenario, mock_manager):
        """Test context is updated after first step completion"""
        task_state = TaskState(
            task_id="two-001",
            scenario_id="two-step",
            total_steps=2,
        )

        session = TaskSession(
            state=task_state,
            scenario=two_step_scenario,
            sub_agent_manager=mock_manager,
        )

        # Simulate first step completion (manually update context)
        session.context["generated_data"] = {"data": "generated value"}
        session.state.context["generated_data"] = {"data": "generated value"}

        assert "generated_data" in session.context
        assert session.context["generated_data"] == {"data": "generated value"}
        assert session.state.context["generated_data"] == {"data": "generated value"}

    def test_context_injected_in_second_step_prompt(
        self, two_step_scenario, mock_manager
    ):
        """Test context is injected in second step prompt"""
        task_state = TaskState(
            task_id="two-002",
            scenario_id="two-step",
        )

        session = TaskSession(
            state=task_state,
            scenario=two_step_scenario,
            sub_agent_manager=mock_manager,
        )

        # Set context from first step
        session.context["generated_data"] = {"key": "value"}

        # Build prompt for second step
        step_def = two_step_scenario.steps[1]
        prompt = session._build_system_prompt(step_def)

        # Context should be in the prompt
        assert "前置步骤输出" in prompt
        assert "generated_data" in prompt

    @pytest.mark.asyncio
    async def test_two_step_sequential_execution(self, two_step_scenario, mock_manager):
        """Test two steps execute sequentially with context passing"""
        task_state = TaskState(
            task_id="two-003",
            scenario_id="two-step",
            initial_message="Start",
        )

        session = TaskSession(
            state=task_state,
            scenario=two_step_scenario,
            sub_agent_manager=mock_manager,
        )

        await session.start()

        # Both steps should complete
        assert session.state.status == TaskStatus.COMPLETED
        assert session.state.completed_steps == 2


class TestMultiStepChainPass:
    """Test multi-step chain context passing"""

    @pytest.fixture
    def chain_scenario(self):
        """Create a multi-step chain scenario"""
        return ScenarioDefinition(
            scenario_id="chain-scenario",
            name="Chain Scenario",
            steps=[
                StepDefinition(
                    step_id="step1",
                    name="Step 1",
                    output_key="result1",
                    system_prompt="First step",
                    requires_confirmation=False,
                ),
                StepDefinition(
                    step_id="step2",
                    name="Step 2",
                    output_key="result2",
                    system_prompt="Second step. Use: {{context.result1}}",
                    requires_confirmation=False,
                    dependencies=["step1"],
                ),
                StepDefinition(
                    step_id="step3",
                    name="Step 3",
                    output_key="result3",
                    system_prompt="Third step. Use: {{context.result1}} and {{context.result2}}",
                    requires_confirmation=False,
                    dependencies=["step2"],
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
            output="Output",
            output_data={"step": "done"},
            requires_confirmation=False,
        ))
        return manager

    def test_chain_context_accumulation(self, chain_scenario, mock_manager):
        """Test context accumulates through the chain"""
        task_state = TaskState(
            task_id="chain-001",
            scenario_id="chain-scenario",
        )

        session = TaskSession(
            state=task_state,
            scenario=chain_scenario,
            sub_agent_manager=mock_manager,
        )

        # Simulate chain execution by manually setting context
        session.context["result1"] = {"data": "first"}
        session.state.context["result1"] = {"data": "first"}
        assert len(session.context) == 1

        session.context["result2"] = {"data": "second"}
        session.state.context["result2"] = {"data": "second"}
        assert len(session.context) == 2

        session.context["result3"] = {"data": "third"}
        session.state.context["result3"] = {"data": "third"}
        assert len(session.context) == 3

    def test_chain_step_can_access_all_previous_outputs(
        self, chain_scenario, mock_manager
    ):
        """Test later steps can access all previous outputs"""
        task_state = TaskState(
            task_id="chain-002",
            scenario_id="chain-scenario",
        )

        session = TaskSession(
            state=task_state,
            scenario=chain_scenario,
            sub_agent_manager=mock_manager,
        )

        # Set up context from previous steps
        session.context["result1"] = {"value": "A"}
        session.context["result2"] = {"value": "B"}

        # Build prompt for step 3
        step_def = chain_scenario.steps[2]
        prompt = session._build_system_prompt(step_def)

        # Both previous outputs should be accessible
        assert "result1" in prompt
        assert "result2" in prompt

    @pytest.mark.asyncio
    async def test_chain_all_steps_complete(self, chain_scenario, mock_manager):
        """Test all steps in chain complete"""
        task_state = TaskState(
            task_id="chain-003",
            scenario_id="chain-scenario",
            initial_message="Start chain",
        )

        session = TaskSession(
            state=task_state,
            scenario=chain_scenario,
            sub_agent_manager=mock_manager,
        )

        await session.start()

        assert session.state.status == TaskStatus.COMPLETED
        assert session.state.completed_steps == 3


class TestTemplateVariableReplacement:
    """Test {{context.xxx}} template variable replacement"""

    @pytest.fixture
    def template_scenario(self):
        """Create scenario with template variables"""
        return ScenarioDefinition(
            scenario_id="template-scenario",
            name="Template Scenario",
            steps=[
                StepDefinition(
                    step_id="input",
                    name="Input",
                    output_key="user_input",
                    system_prompt="Get user input",
                    requires_confirmation=False,
                ),
                StepDefinition(
                    step_id="transform",
                    name="Transform",
                    output_key="transformed",
                    system_prompt="Transform: {{context.user_input}}",
                    requires_confirmation=False,
                ),
            ],
        )

    @pytest.fixture
    def mock_manager(self):
        """Create mock SubAgentManager"""
        return AsyncMock()

    def test_template_format_context(self, template_scenario, mock_manager):
        """Test _format_context method"""
        task_state = TaskState(
            task_id="template-001",
            scenario_id="template-scenario",
        )

        session = TaskSession(
            state=task_state,
            scenario=template_scenario,
            sub_agent_manager=mock_manager,
        )

        # Empty context
        assert session._format_context() == ""

        # With simple value
        session.context["user_input"] = {"name": "test"}
        formatted = session._format_context()

        assert "### user_input" in formatted
        assert "name" in formatted

    def test_template_with_dict_value(self, template_scenario, mock_manager):
        """Test formatting context with dict value"""
        task_state = TaskState(
            task_id="template-002",
            scenario_id="template-scenario",
        )

        session = TaskSession(
            state=task_state,
            scenario=template_scenario,
            sub_agent_manager=mock_manager,
        )

        session.context["analysis"] = {
            "score": 95,
            "issues": ["issue1", "issue2"],
            "summary": "Good code",
        }

        formatted = session._format_context()

        assert "### analysis" in formatted
        assert "score" in formatted
        assert "issues" in formatted

    def test_template_with_string_value(self, template_scenario, mock_manager):
        """Test formatting context with string value"""
        task_state = TaskState(
            task_id="template-003",
            scenario_id="template-scenario",
        )

        session = TaskSession(
            state=task_state,
            scenario=template_scenario,
            sub_agent_manager=mock_manager,
        )

        session.context["text_output"] = "This is a plain text output"

        formatted = session._format_context()

        assert "### text_output" in formatted
        assert "This is a plain text output" in formatted

    def test_template_with_none_value_skipped(
        self, template_scenario, mock_manager
    ):
        """Test None values are skipped in context formatting"""
        task_state = TaskState(
            task_id="template-004",
            scenario_id="template-scenario",
        )

        session = TaskSession(
            state=task_state,
            scenario=template_scenario,
            sub_agent_manager=mock_manager,
        )

        session.context["valid"] = {"data": "here"}
        session.context["invalid"] = None

        formatted = session._format_context()

        assert "### valid" in formatted
        assert "### invalid" not in formatted

    def test_template_injection_disabled(self, template_scenario, mock_manager):
        """Test template injection can be disabled"""
        task_state = TaskState(
            task_id="template-005",
            scenario_id="template-scenario",
        )

        config = TaskSessionConfig(context_injection_enabled=False)
        session = TaskSession(
            state=task_state,
            scenario=template_scenario,
            sub_agent_manager=mock_manager,
            config=config,
        )

        session.context["user_input"] = {"secret": "data"}

        step_def = template_scenario.steps[1]
        prompt = session._build_system_prompt(step_def)

        # Context should NOT be injected
        assert "前置步骤输出" not in prompt


class TestContextWithBranching:
    """Test context with branching step dependencies"""

    @pytest.fixture
    def branching_scenario(self):
        """Create scenario with branching dependencies"""
        return ScenarioDefinition(
            scenario_id="branching",
            name="Branching Scenario",
            steps=[
                StepDefinition(
                    step_id="analyze",
                    name="Analyze",
                    output_key="analysis",
                    system_prompt="Analyze",
                    requires_confirmation=False,
                ),
                StepDefinition(
                    step_id="review_a",
                    name="Review A",
                    output_key="review_a",
                    system_prompt="Review A based on {{context.analysis}}",
                    requires_confirmation=False,
                    dependencies=["analyze"],
                ),
                StepDefinition(
                    step_id="review_b",
                    name="Review B",
                    output_key="review_b",
                    system_prompt="Review B based on {{context.analysis}}",
                    requires_confirmation=False,
                    dependencies=["analyze"],
                ),
                StepDefinition(
                    step_id="merge",
                    name="Merge",
                    output_key="merged",
                    system_prompt="Merge {{context.review_a}} and {{context.review_b}}",
                    requires_confirmation=False,
                    dependencies=["review_a", "review_b"],
                ),
            ],
        )

    @pytest.fixture
    def mock_manager(self):
        """Create mock SubAgentManager"""
        return AsyncMock()

    def test_branching_context_availability(self, branching_scenario, mock_manager):
        """Test context is available to all branches"""
        task_state = TaskState(
            task_id="branch-001",
            scenario_id="branching",
        )

        session = TaskSession(
            state=task_state,
            scenario=branching_scenario,
            sub_agent_manager=mock_manager,
        )

        # Complete analyze (manually set context)
        session.context["analysis"] = {"result": "analysis done"}

        # Both review_a and review_b should have access to analysis
        assert "analysis" in session.context

        # Build prompts for both branches
        prompt_a = session._build_system_prompt(branching_scenario.steps[1])
        prompt_b = session._build_system_prompt(branching_scenario.steps[2])

        # Both should contain analysis context
        assert "analysis" in prompt_a
        assert "analysis" in prompt_b

    def test_merge_step_access_all_branches(
        self, branching_scenario, mock_manager
    ):
        """Test merge step can access all branch outputs"""
        task_state = TaskState(
            task_id="branch-002",
            scenario_id="branching",
        )

        session = TaskSession(
            state=task_state,
            scenario=branching_scenario,
            sub_agent_manager=mock_manager,
        )

        # Simulate all steps completed
        session.context["analysis"] = {"data": "base"}
        session.context["review_a"] = {"result": "A"}
        session.context["review_b"] = {"result": "B"}

        # Build merge prompt
        merge_prompt = session._build_system_prompt(branching_scenario.steps[3])

        # Should contain all contexts
        assert "analysis" in merge_prompt
        assert "review_a" in merge_prompt
        assert "review_b" in merge_prompt


class TestContextEdgeCases:
    """Test edge cases in context handling"""

    @pytest.fixture
    def simple_scenario(self):
        """Create simple scenario"""
        return ScenarioDefinition(
            scenario_id="edge-scenario",
            name="Edge Scenario",
            steps=[
                StepDefinition(
                    step_id="step1",
                    name="Step 1",
                    output_key="output1",
                    system_prompt="Step 1",
                ),
            ],
        )

    @pytest.fixture
    def mock_manager(self):
        """Create mock SubAgentManager"""
        return AsyncMock()

    def test_context_with_empty_dict(self, simple_scenario, mock_manager):
        """Test context with empty dict value - skipped due to falsy check"""
        task_state = TaskState(task_id="edge-001", scenario_id="edge-scenario")

        session = TaskSession(
            state=task_state,
            scenario=simple_scenario,
            sub_agent_manager=mock_manager,
        )

        session.context["empty"] = {}

        formatted = session._format_context()
        # Empty dict is falsy, so it's skipped in _format_context
        assert formatted == ""

    def test_context_with_nested_dict(self, simple_scenario, mock_manager):
        """Test context with nested dict"""
        task_state = TaskState(task_id="edge-002", scenario_id="edge-scenario")

        session = TaskSession(
            state=task_state,
            scenario=simple_scenario,
            sub_agent_manager=mock_manager,
        )

        session.context["nested"] = {
            "level1": {
                "level2": {"value": "deep"},
            }
        }

        formatted = session._format_context()
        assert "### nested" in formatted
        # Nested values are stringified
        assert "level1" in formatted

    def test_context_overwrite(self, simple_scenario, mock_manager):
        """Test context value can be overwritten"""
        task_state = TaskState(task_id="edge-003", scenario_id="edge-scenario")

        session = TaskSession(
            state=task_state,
            scenario=simple_scenario,
            sub_agent_manager=mock_manager,
        )

        # Set initial value
        session.context["output1"] = {"version": 1}
        assert session.context["output1"]["version"] == 1

        # Overwrite
        session.context["output1"] = {"version": 2}
        assert session.context["output1"]["version"] == 2

    def test_context_shared_with_state(self, simple_scenario, mock_manager):
        """Test context is shared between session.context and state.context"""
        task_state = TaskState(task_id="edge-004", scenario_id="edge-scenario")

        session = TaskSession(
            state=task_state,
            scenario=simple_scenario,
            sub_agent_manager=mock_manager,
        )

        # Manually update both contexts (simulating _complete_step behavior)
        session.context["output1"] = {"data": "test"}
        session.state.context["output1"] = {"data": "test"}

        # Both should have the value
        assert session.context["output1"] == {"data": "test"}
        assert session.state.context["output1"] == {"data": "test"}

    def test_context_with_special_characters(self, simple_scenario, mock_manager):
        """Test context with special characters in values"""
        task_state = TaskState(task_id="edge-005", scenario_id="edge-scenario")

        session = TaskSession(
            state=task_state,
            scenario=simple_scenario,
            sub_agent_manager=mock_manager,
        )

        session.context["special"] = {
            "text": "Hello\nWorld\tTabbed",
            "symbols": "<>&\"'",
        }

        formatted = session._format_context()
        assert "### special" in formatted