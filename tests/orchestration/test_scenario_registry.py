"""
Unit tests for ScenarioRegistry
"""

import pytest
from pathlib import Path
import tempfile
import yaml

from openakita.orchestration.models import (
    ScenarioDefinition,
    StepDefinition,
    TriggerPattern,
    TriggerType,
)
from openakita.orchestration.scenario_registry import ScenarioRegistry, ScenarioMatchResult


class TestScenarioRegistry:
    """Test ScenarioRegistry"""

    def test_create_registry(self):
        registry = ScenarioRegistry()
        assert registry.count() == 0

    def test_register_scenario(self):
        registry = ScenarioRegistry()
        scenario = ScenarioDefinition(
            scenario_id="test-scenario",
            name="Test Scenario",
            category="test",
            steps=[
                StepDefinition(step_id="step1", name="Step 1"),
            ],
        )

        success = registry.register(scenario)
        assert success is True
        assert registry.count() == 1

    def test_register_duplicate(self):
        registry = ScenarioRegistry()
        scenario = ScenarioDefinition(
            scenario_id="test-scenario",
            name="Test Scenario",
        )

        registry.register(scenario)
        success = registry.register(scenario)  # Duplicate
        assert success is False
        assert registry.count() == 1

    def test_unregister_scenario(self):
        registry = ScenarioRegistry()
        scenario = ScenarioDefinition(
            scenario_id="test-scenario",
            name="Test Scenario",
        )

        registry.register(scenario)
        assert registry.count() == 1

        success = registry.unregister("test-scenario")
        assert success is True
        assert registry.count() == 0

    def test_get_scenario(self):
        registry = ScenarioRegistry()
        scenario = ScenarioDefinition(
            scenario_id="test-scenario",
            name="Test Scenario",
        )
        registry.register(scenario)

        retrieved = registry.get("test-scenario")
        assert retrieved is not None
        assert retrieved.name == "Test Scenario"

        assert registry.get("nonexistent") is None

    def test_list_all(self):
        registry = ScenarioRegistry()
        registry.register(ScenarioDefinition(scenario_id="s1", name="Scenario 1"))
        registry.register(ScenarioDefinition(scenario_id="s2", name="Scenario 2"))

        all_scenarios = registry.list_all()
        assert len(all_scenarios) == 2

    def test_list_by_category(self):
        registry = ScenarioRegistry()
        registry.register(ScenarioDefinition(
            scenario_id="s1", name="S1", category="development"
        ))
        registry.register(ScenarioDefinition(
            scenario_id="s2", name="S2", category="test"
        ))
        registry.register(ScenarioDefinition(
            scenario_id="s3", name="S3", category="development"
        ))

        dev_scenarios = registry.list_by_category("development")
        assert len(dev_scenarios) == 2

        test_scenarios = registry.list_by_category("test")
        assert len(test_scenarios) == 1


class TestScenarioMatching:
    """Test scenario matching functionality"""

    def test_keyword_match(self):
        registry = ScenarioRegistry()
        scenario = ScenarioDefinition(
            scenario_id="test-scenario",
            name="Test Scenario",
            trigger_patterns=[
                TriggerPattern(
                    type=TriggerType.KEYWORD,
                    keywords=["test", "测试"],
                ),
            ],
        )
        registry.register(scenario)

        # Should match
        match = registry.match_from_dialog("这是一个测试消息")
        assert match is not None
        assert match.scenario.scenario_id == "test-scenario"

        # Should not match
        match = registry.match_from_dialog("hello world")
        assert match is None

    def test_regex_match(self):
        registry = ScenarioRegistry()
        scenario = ScenarioDefinition(
            scenario_id="code-review",
            name="Code Review",
            trigger_patterns=[
                TriggerPattern(
                    type=TriggerType.REGEX,
                    pattern=r"(审查|review).*代码",
                ),
            ],
        )
        registry.register(scenario)

        # Should match
        match = registry.match_from_dialog("请帮我审查这段代码")
        assert match is not None
        assert match.confidence >= 0.9

        # Should not match
        match = registry.match_from_dialog("帮我写代码")
        assert match is None

    def test_match_priority(self):
        registry = ScenarioRegistry()

        # Lower priority number = higher priority
        scenario1 = ScenarioDefinition(
            scenario_id="s1",
            name="Scenario 1",
            trigger_patterns=[
                TriggerPattern(
                    type=TriggerType.KEYWORD,
                    keywords=["test"],
                    priority=1,  # Higher priority
                ),
            ],
        )
        scenario2 = ScenarioDefinition(
            scenario_id="s2",
            name="Scenario 2",
            trigger_patterns=[
                TriggerPattern(
                    type=TriggerType.KEYWORD,
                    keywords=["test"],
                    priority=2,  # Lower priority
                ),
            ],
        )

        registry.register(scenario1)
        registry.register(scenario2)

        match = registry.match_from_dialog("test message")
        assert match is not None
        assert match.scenario.scenario_id == "s1"  # Higher priority wins

    def test_empty_message(self):
        registry = ScenarioRegistry()
        scenario = ScenarioDefinition(
            scenario_id="test",
            name="Test",
            trigger_patterns=[
                TriggerPattern(type=TriggerType.KEYWORD, keywords=["test"]),
            ],
        )
        registry.register(scenario)

        assert registry.match_from_dialog("") is None
        assert registry.match_from_dialog(None) is None


class TestScenarioLoading:
    """Test scenario loading from YAML"""

    def test_load_from_yaml(self):
        registry = ScenarioRegistry()

        # Create temporary YAML file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump({
                'scenario_id': 'test-yaml',
                'name': 'Test YAML Scenario',
                'description': 'Loaded from YAML',
                'category': 'test',
                'trigger_patterns': [
                    {'type': 'keyword', 'keywords': ['yaml', 'test']}
                ],
                'steps': [
                    {'step_id': 'step1', 'name': 'Step 1'},
                    {'step_id': 'step2', 'name': 'Step 2'},
                ],
            }, f)
            yaml_path = f.name

        try:
            scenario = registry.load_from_yaml(yaml_path)
            assert scenario.scenario_id == 'test-yaml'
            assert len(scenario.steps) == 2
            assert registry.count() == 1
        finally:
            Path(yaml_path).unlink()

    def test_load_from_directory(self):
        registry = ScenarioRegistry()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create multiple YAML files
            for i in range(3):
                yaml_path = Path(tmpdir) / f"scenario_{i}.yaml"
                with open(yaml_path, 'w') as f:
                    yaml.dump({
                        'scenario_id': f's{i}',
                        'name': f'Scenario {i}',
                        'steps': [],
                    }, f)

            count = registry.load_from_directory(tmpdir)
            assert count == 3
            assert registry.count() == 3

    def test_clear(self):
        registry = ScenarioRegistry()
        registry.register(ScenarioDefinition(scenario_id="s1", name="S1"))
        registry.register(ScenarioDefinition(scenario_id="s2", name="S2"))

        assert registry.count() == 2
        registry.clear()
        assert registry.count() == 0