"""
TASK-011: 前端测试 - 多轮对话上下文管理

E2E 测试：通过模拟 API 调用验证多轮对话的上下文管理行为：
- 滑动窗口限制生效
- 重要上下文被保留
- 上下文不会无限增长
"""

import pytest

from openakita.context.manager import EnterpriseContextManager
from openakita.context.config import ContextConfig


class TestMultiRoundConversationContext:
    """多轮对话上下文管理测试"""

    def test_context_does_not_grow_unbounded(self):
        """测试上下文不会无限增长"""
        config = ContextConfig(max_conversation_rounds=10)
        manager = EnterpriseContextManager(config=config)
        manager.initialize(identity="Test Agent")

        # 创建任务
        manager.start_task("task-001", "tenant-1", "chat", "Multi-round conversation")

        # 模拟 20+ 轮对话
        for i in range(25):
            manager.add_message("session-001", "user", f"User message {i}")
            manager.add_message("session-001", "assistant", f"Assistant response {i}")

        # 获取会话上下文
        conv = manager.get_conversation("session-001")

        # 验证消息数量被限制
        # 每轮有 2 条消息（用户+助手），max_rounds=10 应该限制在约 20 条消息
        assert conv._count_rounds() <= 10, f"Rounds should be <= 10, got {conv._count_rounds()}"
        assert len(conv.messages) <= 22, f"Messages should be <= 22, got {len(conv.messages)}"

    def test_recent_messages_preserved(self):
        """测试最近的消息被保留"""
        config = ContextConfig(max_conversation_rounds=5)
        manager = EnterpriseContextManager(config=config)
        manager.initialize(identity="Test Agent")

        manager.start_task("task-001", "tenant-1", "chat", "Test")

        # 添加消息
        for i in range(10):
            manager.add_message("session-001", "user", f"Message {i}")

        conv = manager.get_conversation("session-001")
        messages = conv.to_messages()

        # 最近的消息应该存在
        recent_content = str(messages)
        assert "Message 9" in recent_content, "Most recent message should be preserved"
        assert "Message 8" in recent_content, "Second most recent message should be preserved"

        # 最早的消息应该被裁剪
        assert "Message 0" not in recent_content, "Oldest message should be trimmed"

    def test_important_context_preserved_across_rounds(self):
        """测试重要上下文在多轮对话中被保留"""
        config = ContextConfig(max_conversation_rounds=5)
        manager = EnterpriseContextManager(config=config)
        manager.initialize(
            identity="AI Assistant",
            rules=["Be helpful", "Be accurate"],
        )

        # 创建任务并设置重要变量
        task = manager.start_task("task-001", "tenant-1", "search", "Important task")
        task.add_variable("important_key", "important_value")
        task.add_step_summary("initial_step", "Initialized with important context")

        # 添加多轮对话
        for i in range(10):
            manager.add_message("session-001", "user", f"User query {i}")
            manager.add_message("session-001", "assistant", f"Response {i}")

        # 构建上下文
        system_prompt, messages = manager.build_context("task-001", "session-001")

        # 验证重要上下文被保留
        assert "AI Assistant" in system_prompt, "Identity should be in system prompt"
        assert "Be helpful" in system_prompt, "Rules should be in system prompt"
        assert "important_value" in system_prompt, "Task variables should be preserved"
        assert "Initialized" in system_prompt, "Step summaries should be preserved"

    def test_multiple_sessions_isolation(self):
        """测试多个会话之间的上下文隔离"""
        manager = EnterpriseContextManager()
        manager.initialize(identity="Test Agent")

        # 创建多个会话
        manager.start_task("task-001", "tenant-1", "chat", "Session 1")
        manager.start_task("task-002", "tenant-1", "chat", "Session 2")

        # 在不同会话中添加不同的消息
        for i in range(5):
            manager.add_message("session-001", "user", f"Session 1 message {i}")
            manager.add_message("session-002", "user", f"Session 2 message {i}")

        # 验证会话隔离
        conv1 = manager.get_conversation("session-001")
        conv2 = manager.get_conversation("session-002")

        conv1_messages = str(conv1.to_messages())
        conv2_messages = str(conv2.to_messages())

        assert "Session 1" in conv1_messages, "Session 1 should have its messages"
        assert "Session 2" not in conv1_messages, "Session 1 should not have Session 2 messages"
        assert "Session 2" in conv2_messages, "Session 2 should have its messages"
        assert "Session 1" not in conv2_messages, "Session 2 should not have Session 1 messages"

    def test_token_budget_auto_compression(self):
        """测试 Token 预算触发自动压缩"""
        config = ContextConfig(
            max_conversation_rounds=20,
        )
        manager = EnterpriseContextManager(config=config)
        manager.initialize(identity="Test Agent")

        manager.start_task("task-001", "tenant-1", "chat", "Compression test")

        # 添加大量消息
        for i in range(50):
            manager.add_message("session-001", "user", f"Long message {i} " + "x" * 200)
            manager.add_message("session-001", "assistant", f"Long response {i} " + "y" * 200)

        conv = manager.get_conversation("session-001")

        # 验证消息被压缩到合理范围
        assert len(conv.messages) < 100, f"Messages should be compressed, got {len(conv.messages)}"

    def test_twenty_plus_rounds_stability(self):
        """测试 20+ 轮对话的稳定性"""
        config = ContextConfig(max_conversation_rounds=15)
        manager = EnterpriseContextManager(config=config)
        manager.initialize(
            identity="Stability Test Agent",
            rules=["Rule 1", "Rule 2", "Rule 3"],
        )

        manager.start_task("task-001", "tenant-1", "chat", "Stability test")

        # 执行 25 轮对话
        for i in range(25):
            # 添加用户消息
            manager.add_message("session-001", "user", f"User round {i}: Please help with task {i}")

            # 模拟助手响应
            manager.add_message("session-001", "assistant", f"Assistant round {i}: Here's your help")

            # 每轮验证上下文可构建
            system_prompt, messages = manager.build_context("task-001", "session-001")
            assert system_prompt is not None, f"System prompt should exist at round {i}"
            assert len(messages) > 0, f"Messages should exist at round {i}"

        # 最终验证
        conv = manager.get_conversation("session-001")
        assert conv._count_rounds() <= 15, "Final round count should be within limit"

    def test_task_context_persistence_across_conversation(self):
        """测试任务上下文在对话中的持久性"""
        manager = EnterpriseContextManager()
        manager.initialize(identity="Test Agent")

        task = manager.start_task("task-001", "tenant-1", "workflow", "Complex workflow")

        # 记录初始步骤
        task.add_variable("workflow_id", "WF-12345")
        task.add_step_summary("step_1", "Initialized workflow")

        # 进行多轮对话
        for i in range(10):
            manager.add_message("session-001", "user", f"Query {i}")
            manager.add_message("session-001", "assistant", f"Response {i}")

            # 每隔几轮添加新步骤
            if i % 3 == 0:
                task.add_step_summary(f"step_{i//3 + 2}", f"Progress at round {i}")

        # 构建上下文并验证任务上下文完整性
        system_prompt, _ = manager.build_context("task-001", "session-001")

        assert "WF-12345" in system_prompt, "Workflow ID should persist"
        assert "Initialized workflow" in system_prompt, "Initial step should persist"

    def test_stats_tracking_across_rounds(self):
        """测试统计信息在多轮对话中的跟踪"""
        manager = EnterpriseContextManager()
        manager.initialize(identity="Stats Agent")

        manager.start_task("task-001", "tenant-1", "chat", "Stats test")

        # 添加消息
        for i in range(10):
            manager.add_message("session-001", "user", f"Message {i}")

        # 获取统计
        stats = manager.get_stats("task-001", "session-001")

        assert stats["system"]["estimated_tokens"] > 0, "System tokens should be tracked"
        assert stats["task"]["estimated_tokens"] > 0, "Task tokens should be tracked"
        assert stats["conversation"] is not None, "Conversation stats should exist"
        assert stats["total_estimated_tokens"] > 0, "Total tokens should be tracked"

    def test_context_clearing_between_tasks(self):
        """测试任务之间上下文清理"""
        manager = EnterpriseContextManager()
        manager.initialize(identity="Test Agent")

        # 第一个任务
        manager.start_task("task-001", "tenant-1", "chat", "First task")
        manager.add_message("session-001", "user", "First task message")

        # 结束第一个任务
        manager.end_task("task-001")

        # 第二个任务
        manager.start_task("task-002", "tenant-1", "chat", "Second task")
        manager.add_message("session-002", "user", "Second task message")

        # 验证隔离
        assert manager.get_task("task-001") is None, "First task should be removed"
        assert manager.get_task("task-002") is not None, "Second task should exist"

        # 验证会话仍然独立
        conv1 = manager.get_conversation("session-001")
        conv2 = manager.get_conversation("session-002")

        assert conv1 is not None, "First session should still exist"
        assert conv2 is not None, "Second session should exist"
        assert len(conv1.messages) == 1, "First session should have its message"
        assert len(conv2.messages) == 1, "Second session should have its message"


class TestContextPerformanceUnderLoad:
    """上下文性能负载测试"""

    def test_large_conversation_performance(self):
        """测试大量对话的性能"""
        import time

        config = ContextConfig(max_conversation_rounds=50)
        manager = EnterpriseContextManager(config=config)
        manager.initialize(identity="Performance Agent")

        manager.start_task("task-001", "tenant-1", "chat", "Performance test")

        # 添加 100 轮对话
        start_time = time.perf_counter()
        for i in range(100):
            manager.add_message("session-001", "user", f"User message {i}" * 10)
            manager.add_message("session-001", "assistant", f"Assistant response {i}" * 10)
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        # 100 轮对话的添加应该在 500ms 内完成
        assert elapsed_ms < 500, f"Adding 100 rounds took {elapsed_ms}ms, expected < 500ms"

        # 构建上下文的性能
        start_time = time.perf_counter()
        system_prompt, messages = manager.build_context("task-001", "session-001")
        build_ms = (time.perf_counter() - start_time) * 1000

        # 上下文构建应该在 50ms 内完成
        assert build_ms < 50, f"Building context took {build_ms}ms, expected < 50ms"

    def test_memory_usage_stability(self):
        """测试内存使用稳定性"""
        manager = EnterpriseContextManager()
        manager.initialize(identity="Memory Test")

        # 创建多个任务和会话
        for i in range(10):
            manager.start_task(f"task-{i}", f"tenant-{i}", "chat", f"Task {i}")
            for j in range(20):
                manager.add_message(f"session-{i}", "user", f"Message {j}" * 50)
                manager.add_message(f"session-{i}", "assistant", f"Response {j}" * 50)

        # 验证系统仍然响应
        assert manager.get_task_count() == 10, "Should have 10 tasks"
        assert manager.get_session_count() == 10, "Should have 10 sessions"

        # 清理后验证
        manager.clear_all()
        assert manager.get_task_count() == 0, "Tasks should be cleared"
        assert manager.get_session_count() == 0, "Sessions should be cleared"


class TestContextIntegrationWithAPI:
    """上下文与 API 集成测试（模拟 API 行为）"""

    def test_conversation_id_tracking(self):
        """测试会话 ID 跟踪"""
        manager = EnterpriseContextManager()
        manager.initialize(identity="API Test Agent")

        # 模拟多个不同的 conversation_id
        conversation_ids = [f"conv-{i}" for i in range(5)]

        for conv_id in conversation_ids:
            manager.start_task(f"task-{conv_id}", "tenant-1", "chat", f"Task for {conv_id}")
            manager.add_message(conv_id, "user", f"Message for {conv_id}")

        # 验证每个会话独立
        for conv_id in conversation_ids:
            conv = manager.get_conversation(conv_id)
            assert conv is not None, f"Conversation {conv_id} should exist"
            assert len(conv.messages) == 1, f"Conversation {conv_id} should have 1 message"

    def test_session_message_flow(self):
        """测试会话消息流（模拟 API 流式响应）"""
        manager = EnterpriseContextManager()
        manager.initialize(identity="Stream Test Agent")

        manager.start_task("task-001", "tenant-1", "chat", "Stream test")

        # 模拟流式对话：用户 -> 助手 -> 用户 -> 助手
        conversation_flow = [
            ("user", "Hello, I need help with Python."),
            ("assistant", "Of course! What do you need help with?"),
            ("user", "How do I read a file?"),
            ("assistant", "You can use open() function or Path.read_text()."),
            ("user", "Thanks! What about writing?"),
            ("assistant", "Use open(file, 'w') or Path.write_text()."),
        ]

        for role, content in conversation_flow:
            manager.add_message("session-001", role, content)

        conv = manager.get_conversation("session-001")
        messages = conv.to_messages()

        # 验证对话完整性
        assert len(messages) == 6, "Should have 6 messages"

        # 验证消息顺序
        user_msgs = [m for m in messages if m["role"] == "user"]
        assistant_msgs = [m for m in messages if m["role"] == "assistant"]

        assert len(user_msgs) == 3, "Should have 3 user messages"
        assert len(assistant_msgs) == 3, "Should have 3 assistant messages"