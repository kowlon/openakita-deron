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


class TestScenarioConfidence:
    """Test scenario matching confidence calculation"""

    def test_regex_confidence_default(self):
        """Test regex match confidence (default 0.9)"""
        registry = ScenarioRegistry()
        scenario = ScenarioDefinition(
            scenario_id="regex-test",
            name="Regex Test",
            trigger_patterns=[
                TriggerPattern(
                    type=TriggerType.REGEX,
                    pattern=r"test.*pattern",
                    priority=10,  # Default priority
                ),
            ],
        )
        registry.register(scenario)

        match = registry.match_from_dialog("test the pattern")
        assert match is not None
        assert match.confidence == 0.9

    def test_regex_confidence_high_priority(self):
        """Test regex match confidence for high priority (priority < 10)"""
        registry = ScenarioRegistry()
        scenario = ScenarioDefinition(
            scenario_id="high-priority",
            name="High Priority",
            trigger_patterns=[
                TriggerPattern(
                    type=TriggerType.REGEX,
                    pattern=r"urgent",
                    priority=1,  # High priority
                ),
            ],
        )
        registry.register(scenario)

        match = registry.match_from_dialog("urgent task")
        assert match is not None
        assert match.confidence == 1.0  # High priority gets confidence 1.0

    def test_keyword_confidence_single_match(self):
        """Test keyword match confidence with single keyword match"""
        registry = ScenarioRegistry()
        scenario = ScenarioDefinition(
            scenario_id="keyword-test",
            name="Keyword Test",
            trigger_patterns=[
                TriggerPattern(
                    type=TriggerType.KEYWORD,
                    keywords=["test"],
                ),
            ],
        )
        registry.register(scenario)

        match = registry.match_from_dialog("this is a test")
        assert match is not None
        # 0.4 + (1 * 0.2) = 0.6 (use approx for floating point)
        assert match.confidence == pytest.approx(0.6)

    def test_keyword_confidence_multiple_matches(self):
        """Test keyword match confidence with multiple keyword matches"""
        registry = ScenarioRegistry()
        scenario = ScenarioDefinition(
            scenario_id="multi-keyword",
            name="Multi Keyword",
            trigger_patterns=[
                TriggerPattern(
                    type=TriggerType.KEYWORD,
                    keywords=["code", "review", "python"],
                ),
            ],
        )
        registry.register(scenario)

        # Match 2 keywords: 0.4 + (2 * 0.2) = 0.8
        match = registry.match_from_dialog("code review for python")
        assert match is not None
        assert match.confidence == 0.8

    def test_keyword_confidence_cap(self):
        """Test keyword match confidence is capped at 0.8"""
        registry = ScenarioRegistry()
        scenario = ScenarioDefinition(
            scenario_id="capped-keyword",
            name="Capped Keyword",
            trigger_patterns=[
                TriggerPattern(
                    type=TriggerType.KEYWORD,
                    keywords=["a", "b", "c", "d", "e", "f"],  # Many keywords
                ),
            ],
        )
        registry.register(scenario)

        match = registry.match_from_dialog("a b c d e f")
        assert match is not None
        assert match.confidence == 0.8  # Capped at 0.8

    def test_regex_vs_keyword_priority(self):
        """Test that regex match has higher confidence than keyword match"""
        registry = ScenarioRegistry()

        regex_scenario = ScenarioDefinition(
            scenario_id="regex-scenario",
            name="Regex Scenario",
            trigger_patterns=[
                TriggerPattern(
                    type=TriggerType.REGEX,
                    pattern=r"review",
                ),
            ],
        )
        keyword_scenario = ScenarioDefinition(
            scenario_id="keyword-scenario",
            name="Keyword Scenario",
            trigger_patterns=[
                TriggerPattern(
                    type=TriggerType.KEYWORD,
                    keywords=["review"],
                ),
            ],
        )

        registry.register(regex_scenario)
        registry.register(keyword_scenario)

        match = registry.match_from_dialog("please review")
        assert match is not None
        assert match.scenario.scenario_id == "regex-scenario"  # Regex wins


class TestRegexParameterExtraction:
    """Test regex parameter extraction with named groups"""

    def test_extract_named_groups(self):
        """Test extracting named groups from regex match"""
        registry = ScenarioRegistry()
        scenario = ScenarioDefinition(
            scenario_id="extract-params",
            name="Extract Params",
            trigger_patterns=[
                TriggerPattern(
                    type=TriggerType.REGEX,
                    pattern=r"review\s+(?P<language>\w+)\s+code",
                ),
            ],
        )
        registry.register(scenario)

        match = registry.match_from_dialog("review python code")
        assert match is not None
        assert match.extracted_params == {"language": "python"}

    def test_extract_multiple_named_groups(self):
        """Test extracting multiple named groups"""
        registry = ScenarioRegistry()
        scenario = ScenarioDefinition(
            scenario_id="multi-params",
            name="Multi Params",
            trigger_patterns=[
                TriggerPattern(
                    type=TriggerType.REGEX,
                    pattern=r"(?P<action>create|delete)\s+(?P<resource>\w+)",
                ),
            ],
        )
        registry.register(scenario)

        match = registry.match_from_dialog("create user")
        assert match is not None
        assert match.extracted_params == {"action": "create", "resource": "user"}


class TestScenarioRegistryMethods:
    """Test additional ScenarioRegistry methods"""

    def test_list_categories(self):
        """Test listing all categories"""
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

        categories = registry.list_categories()
        assert set(categories) == {"development", "test"}

    def test_to_dict(self):
        """Test exporting registry to dictionary"""
        registry = ScenarioRegistry()
        registry.register(ScenarioDefinition(
            scenario_id="s1",
            name="Scenario 1",
            category="test",
            steps=[
                StepDefinition(step_id="step1", name="Step 1"),
            ],
        ))

        data = registry.to_dict()
        assert "scenarios" in data
        assert "categories" in data
        assert "s1" in data["scenarios"]
        assert data["scenarios"]["s1"]["name"] == "Scenario 1"
        assert "test" in data["categories"]

    def test_unregister_nonexistent(self):
        """Test unregistering a non-existent scenario"""
        registry = ScenarioRegistry()
        success = registry.unregister("nonexistent")
        assert success is False

    def test_unregister_updates_categories(self):
        """Test that unregistering updates category index"""
        registry = ScenarioRegistry()
        registry.register(ScenarioDefinition(
            scenario_id="s1", name="S1", category="test"
        ))
        registry.register(ScenarioDefinition(
            scenario_id="s2", name="S2", category="test"
        ))

        # Verify category exists with 2 scenarios
        test_scenarios = registry.list_by_category("test")
        assert len(test_scenarios) == 2

        # Unregister one scenario
        registry.unregister("s1")
        test_scenarios = registry.list_by_category("test")
        assert len(test_scenarios) == 1
        assert test_scenarios[0].scenario_id == "s2"


class TestScenarioMatchResult:
    """Test ScenarioMatchResult dataclass"""

    def test_match_result_properties(self):
        """Test ScenarioMatchResult properties"""
        scenario = ScenarioDefinition(
            scenario_id="test",
            name="Test",
        )
        pattern = TriggerPattern(
            type=TriggerType.KEYWORD,
            keywords=["test"],
        )

        result = ScenarioMatchResult(
            scenario=scenario,
            confidence=0.8,
            matched_pattern=pattern,
            extracted_params={"key": "value"},
        )

        assert result.scenario.scenario_id == "test"
        assert result.confidence == 0.8
        assert result.matched_pattern.type == TriggerType.KEYWORD
        assert result.extracted_params == {"key": "value"}

    def test_match_result_defaults(self):
        """Test ScenarioMatchResult default values"""
        scenario = ScenarioDefinition(
            scenario_id="test",
            name="Test",
        )

        result = ScenarioMatchResult(
            scenario=scenario,
            confidence=0.5,
        )

        assert result.matched_pattern is None
        assert result.extracted_params == {}