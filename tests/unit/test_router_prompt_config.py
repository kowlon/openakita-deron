"""
TASK-001: RouterPromptConfig 数据模型单元测试

测试 RouterPromptConfig 数据类的功能：
- 数据类创建和字段验证
- to_dict 序列化
- from_dict 反序列化
- 默认值处理
- 边界情况处理
"""

import pytest

from openakita.orchestration.models import RouterPromptConfig


class TestRouterPromptConfig:
    """RouterPromptConfig 单元测试"""

    def test_create_with_all_fields(self):
        """测试创建包含所有字段的配置"""
        config = RouterPromptConfig(
            router_name="task_router",
            description="Router for task delegation",
            system_prompt="You are a task router. Analyze the user input and route to the appropriate agent.",
            examples=[
                {"input": "帮我写代码", "output": "code_agent"},
                {"input": "分析这个数据", "output": "data_agent"},
            ],
            threshold=0.8,
        )

        assert config.router_name == "task_router"
        assert config.description == "Router for task delegation"
        assert "task router" in config.system_prompt
        assert len(config.examples) == 2
        assert config.threshold == 0.8

    def test_create_with_required_fields_only(self):
        """测试仅使用必需字段创建配置"""
        config = RouterPromptConfig(
            router_name="simple_router",
            description="Simple router",
            system_prompt="Route to best agent.",
        )

        assert config.router_name == "simple_router"
        assert config.description == "Simple router"
        assert config.system_prompt == "Route to best agent."
        assert config.examples == []  # 默认空列表
        assert config.threshold == 0.7  # 默认阈值

    def test_to_dict_serialization(self):
        """测试 to_dict 序列化"""
        config = RouterPromptConfig(
            router_name="test_router",
            description="Test router",
            system_prompt="Test prompt",
            examples=[{"input": "test", "output": "result"}],
            threshold=0.9,
        )

        data = config.to_dict()

        assert isinstance(data, dict)
        assert data["router_name"] == "test_router"
        assert data["description"] == "Test router"
        assert data["system_prompt"] == "Test prompt"
        assert len(data["examples"]) == 1
        assert data["examples"][0]["input"] == "test"
        assert data["threshold"] == 0.9

    def test_from_dict_deserialization(self):
        """测试 from_dict 反序列化"""
        data = {
            "router_name": "agent_router",
            "description": "Agent routing config",
            "system_prompt": "Select the best agent.",
            "examples": [
                {"input": "搜索信息", "output": "search_agent"},
                {"input": "发送邮件", "output": "email_agent"},
            ],
            "threshold": 0.75,
        }

        config = RouterPromptConfig.from_dict(data)

        assert config.router_name == "agent_router"
        assert config.description == "Agent routing config"
        assert config.system_prompt == "Select the best agent."
        assert len(config.examples) == 2
        assert config.examples[0]["input"] == "搜索信息"
        assert config.threshold == 0.75

    def test_from_dict_with_defaults(self):
        """测试 from_dict 使用默认值"""
        data = {
            "router_name": "minimal_router",
            "description": "Minimal config",
            "system_prompt": "Minimal prompt",
        }

        config = RouterPromptConfig.from_dict(data)

        assert config.router_name == "minimal_router"
        assert config.examples == []  # 默认值
        assert config.threshold == 0.7  # 默认值

    def test_round_trip_serialization(self):
        """测试序列化后反序列化的往返一致性"""
        original = RouterPromptConfig(
            router_name="round_trip_router",
            description="Round trip test",
            system_prompt="Test round trip serialization.",
            examples=[
                {"input": "input1", "output": "output1"},
                {"input": "input2", "output": "output2"},
            ],
            threshold=0.85,
        )

        # 序列化
        data = original.to_dict()

        # 反序列化
        restored = RouterPromptConfig.from_dict(data)

        # 验证一致性
        assert restored.router_name == original.router_name
        assert restored.description == original.description
        assert restored.system_prompt == original.system_prompt
        assert restored.examples == original.examples
        assert restored.threshold == original.threshold

    def test_empty_examples(self):
        """测试空示例列表"""
        config = RouterPromptConfig(
            router_name="no_examples_router",
            description="Router without examples",
            system_prompt="Route without examples.",
            examples=[],
        )

        assert config.examples == []
        data = config.to_dict()
        assert data["examples"] == []

    def test_multiple_examples(self):
        """测试多个示例"""
        examples = [
            {"input": f"input_{i}", "output": f"output_{i}"} for i in range(10)
        ]

        config = RouterPromptConfig(
            router_name="multi_example_router",
            description="Router with many examples",
            system_prompt="Route with multiple examples.",
            examples=examples,
        )

        assert len(config.examples) == 10
        assert config.examples[0]["input"] == "input_0"
        assert config.examples[9]["output"] == "output_9"

    def test_threshold_boundary_values(self):
        """测试阈值边界值"""
        # 最小值
        config_min = RouterPromptConfig(
            router_name="min_threshold",
            description="Minimum threshold",
            system_prompt="Test",
            threshold=0.0,
        )
        assert config_min.threshold == 0.0

        # 最大值
        config_max = RouterPromptConfig(
            router_name="max_threshold",
            description="Maximum threshold",
            system_prompt="Test",
            threshold=1.0,
        )
        assert config_max.threshold == 1.0

    def test_unicode_content(self):
        """测试 Unicode 内容处理"""
        config = RouterPromptConfig(
            router_name="unicode_router_路由器",
            description="中文描述 🚀 Unicode test",
            system_prompt="系统提示词：请分析用户输入并进行路由 🤖",
            examples=[
                {"input": "你好世界 🌍", "output": "greeting_agent"},
                {"input": "编写代码 💻", "output": "code_agent"},
            ],
            threshold=0.8,
        )

        assert "路由器" in config.router_name
        assert "🚀" in config.description
        assert "🤖" in config.system_prompt
        assert config.examples[0]["input"] == "你好世界 🌍"

        # 测试序列化保留 Unicode
        data = config.to_dict()
        assert "路由器" in data["router_name"]
        assert "🚀" in data["description"]

    def test_complex_system_prompt(self):
        """测试复杂的系统提示词"""
        complex_prompt = """
        You are an intelligent task router.

        Your responsibilities:
        1. Analyze user input
        2. Determine the best agent
        3. Return the agent name

        Rules:
        - Always respond with just the agent name
        - If unsure, return "default_agent"

        Examples format:
        Input: [user message]
        Output: [agent_name]
        """

        config = RouterPromptConfig(
            router_name="complex_router",
            description="Router with complex prompt",
            system_prompt=complex_prompt,
        )

        assert "intelligent task router" in config.system_prompt
        assert len(config.system_prompt) > 100