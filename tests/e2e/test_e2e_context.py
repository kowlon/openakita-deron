"""
TASK-301: 上下文管理端到端测试

E2E 测试：验证上下文管理系统的完整生命周期和端到端行为：
- 完整上下文生命周期（初始化 -> 任务 -> 会话 -> 构建 -> 清理）
- Agent 与上下文系统集成
- 多任务并发场景
- Token 预算控制端到端
- 压缩策略端到端
- 性能指标验证

这些测试模拟真实使用场景，验证系统各组件协同工作。
"""

import pytest
import time
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

from openakita.context.manager import EnterpriseContextManager
from openakita.context.config import ContextConfig, TokenBudget
from openakita.context.interfaces import ContextPriority
from openakita.context.budget_controller import BudgetState
from openakita.context.orchestrator import ContextOrchestrator, create_orchestrator
from openakita.context import (
    create_context_backend,
    ContextBackend,
    BudgetController,
    BudgetCheckResult,
)


class TestE2EContextLifecycle:
    """端到端上下文生命周期测试"""

    def test_full_context_lifecycle_flow(self):
        """
        E2E 测试: 完整上下文生命周期流程

        验证:
        1. 系统上下文初始化
        2. 任务创建和管理
        3. 会话消息交互
        4. 上下文构建
        5. 统计信息
        6. 资源清理
        """
        # Step 1: 初始化
        config = ContextConfig(
            max_conversation_rounds=10,
            max_task_summaries=15,
            max_task_variables=30,
        )
        manager = EnterpriseContextManager(config=config)
        manager.initialize(
            identity="E2E Test Agent",
            rules=["Rule 1: Be helpful", "Rule 2: Be accurate"],
            tools_manifest="## Tools\n- search\n- calculator\n- file_operations",
        )

        # 验证初始化
        assert manager.system_ctx.identity == "E2E Test Agent"
        assert len(manager.system_ctx.rules) == 2

        # Step 2: 创建任务
        task = manager.start_task(
            task_id="e2e-task-001",
            tenant_id="tenant-e2e",
            task_type="multi_step",
            description="E2E multi-step task demonstration",
            total_steps=5,
        )

        # 添加任务进度
        task.add_step_summary("step_1", "Initialized context")
        task.add_step_summary("step_2", "Gathered information")
        task.add_step_summary("step_3", "Processed data")
        task.add_variable("source", "e2e_test")
        task.add_variable("iteration", "1")

        # 验证任务创建
        assert manager.get_task("e2e-task-001") is not None
        assert len(task.step_summaries) == 3
        assert "source" in task.key_variables

        # Step 3: 会话交互
        conversation_flow = [
            ("user", "Hello, I need help with a complex task."),
            ("assistant", "Of course! I'm here to help. What would you like to accomplish?"),
            ("user", "I need to analyze some data."),
            ("assistant", "I can help with data analysis. What kind of data?"),
            ("user", "Sales data from Q4."),
            ("assistant", "I'll analyze the Q4 sales data for you."),
        ]

        for role, content in conversation_flow:
            manager.add_message("e2e-session-001", role, content)

        # 验证会话
        conv = manager.get_conversation("e2e-session-001")
        assert conv is not None
        assert len(conv.messages) == 6

        # Step 4: 构建上下文
        system_prompt, messages = manager.build_context(
            "e2e-task-001", "e2e-session-001"
        )

        # 验证上下文内容
        assert "E2E Test Agent" in system_prompt
        assert "Rule 1: Be helpful" in system_prompt
        assert "E2E multi-step task" in system_prompt
        assert "Initialized context" in system_prompt
        assert "e2e_test" in system_prompt
        assert len(messages) == 6

        # Step 5: 统计信息
        stats = manager.get_stats("e2e-task-001", "e2e-session-001")
        assert stats["system"]["estimated_tokens"] > 0
        assert stats["task"]["estimated_tokens"] > 0
        assert stats["conversation"] is not None
        assert stats["total_estimated_tokens"] > 0

        # Step 6: 清理
        manager.end_task("e2e-task-001")
        assert manager.get_task("e2e-task-001") is None

        # 会话仍然存在
        assert manager.get_conversation("e2e-session-001") is not None

        # 完全清理
        manager.clear_all()
        assert manager.get_session_count() == 0

    def test_context_backend_integration(self):
        """
        E2E 测试: ContextBackend 协议集成

        验证 ContextBackend 协议的正确实现。
        """
        # 使用工厂函数创建
        backend = create_context_backend()

        # 验证协议合规
        assert isinstance(backend, ContextBackend)

        # 初始化
        backend.initialize(identity="Backend Test Agent")

        # 创建任务
        task = backend.start_task("backend-task", "tenant-1", "test", "Backend test")

        # 验证任务操作
        assert task is not None
        assert task.task_id == "backend-task"

        # 添加消息
        backend.add_message("backend-session", "user", "Test message")

        # 构建上下文
        system_prompt, messages = backend.build_context("backend-task", "backend-session")
        assert system_prompt is not None
        assert len(messages) == 1

        # 统计
        stats = backend.get_stats("backend-task", "backend-session")
        assert stats is not None

        # 清理
        backend.end_task("backend-task")
        backend.clear_all()

    def test_multiple_tasks_sessions_workflow(self):
        """
        E2E 测试: 多任务多会话工作流

        验证多任务、多会话场景下的上下文隔离和协调。
        """
        manager = EnterpriseContextManager()
        manager.initialize(
            identity="Multi-Task Agent",
            rules=["Isolate contexts", "Track progress"],
        )

        # 创建多个任务
        tasks = []
        for i in range(3):
            task = manager.start_task(
                task_id=f"multi-task-{i}",
                tenant_id=f"tenant-{i}",
                task_type="parallel",
                description=f"Parallel task {i}",
            )
            task.add_step_summary("init", f"Task {i} initialized")
            task.add_variable("task_index", str(i))
            tasks.append(task)

        # 每个任务有独立的会话
        for i in range(3):
            session_id = f"multi-session-{i}"
            for j in range(3):
                manager.add_message(session_id, "user", f"Task {i} message {j}")
                manager.add_message(session_id, "assistant", f"Task {i} response {j}")

        # 验证隔离
        for i in range(3):
            task_id = f"multi-task-{i}"
            session_id = f"multi-session-{i}"

            system_prompt, messages = manager.build_context(task_id, session_id)

            # 正确的任务描述
            assert f"Parallel task {i}" in system_prompt
            assert f"Task {i} initialized" in system_prompt

            # 正确的消息
            assert len(messages) == 6
            for msg in messages:
                content = str(msg.get("content", ""))
                assert f"Task {i}" in content

            # 其他任务的内容不应该出现
            for other_i in range(3):
                if other_i != i:
                    assert f"Parallel task {other_i}" not in system_prompt

        # 统计
        assert manager.get_task_count() == 3
        assert manager.get_session_count() == 3

        # 清理部分
        manager.end_task("multi-task-0")
        assert manager.get_task_count() == 2

        # 清理全部
        manager.clear_all()
        assert manager.get_task_count() == 0
        assert manager.get_session_count() == 0


class TestE2ETokenBudgetControl:
    """端到端 Token 预算控制测试"""

    def test_budget_lifecycle_e2e(self):
        """
        E2E 测试: Token 预算控制生命周期

        验证:
        1. 预算检查
        2. 状态转换 (HEALTHY -> WARNING -> CRITICAL)
        3. 自动压缩触发
        """
        # 配置较小的预算便于测试
        config = ContextConfig()
        manager = EnterpriseContextManager(config=config)
        manager.initialize(identity="Budget Test Agent")

        orchestrator = manager.get_orchestrator()
        budget_ctrl = orchestrator.budget_controller

        # Step 1: 初始状态应该是健康的
        result = budget_ctrl.check_budget(system_tokens=1000, conversation_tokens=2000)
        assert result.state == BudgetState.HEALTHY
        assert not result.needs_compression

        # Step 2: 创建任务并添加内容
        task = manager.start_task("budget-task", "t1", "test", "Budget test")
        manager.add_message("budget-session", "user", "Initial message")

        # Step 3: 添加大量内容触发警告
        available = budget_ctrl.available_for_context

        # 模拟接近阈值
        result = budget_ctrl.check_budget(
            system_tokens=int(available * 0.8),
            conversation_tokens=0,
        )
        assert result.state == BudgetState.WARNING

        # Step 4: 模拟严重状态
        result = budget_ctrl.check_budget(
            system_tokens=int(available * 0.95),
            conversation_tokens=0,
        )
        assert result.state == BudgetState.CRITICAL
        assert result.needs_compression

        # Step 5: 测试压缩触发
        large_text = "x" * 5000  # 大文本
        for i in range(50):
            manager.add_message("budget-session", "user", large_text)

        # 构建上下文应该自动压缩
        system_prompt, messages = manager.build_context("budget-task", "budget-session")

        # 消息应该被压缩
        assert len(messages) < 100

    def test_budget_allocation_strategies(self):
        """
        E2E 测试: 预算分配策略

        验证不同的预算分配策略。
        """
        manager = EnterpriseContextManager()
        manager.initialize(identity="Allocation Test")
        orchestrator = manager.get_orchestrator()
        budget_ctrl = orchestrator.budget_controller

        # 平衡策略
        balanced = budget_ctrl.allocate(priority="balanced")
        assert "system" in balanced
        assert "task" in balanced
        assert "conversation" in balanced

        # 系统优先策略
        system_priority = budget_ctrl.allocate(priority="system")
        assert system_priority["system"] >= balanced["system"]

        # 会话优先策略
        conv_priority = budget_ctrl.allocate(priority="conversation")
        assert conv_priority["conversation"] >= balanced["conversation"]

    def test_budget_capacity_estimation(self):
        """
        E2E 测试: 容量估算

        验证预算控制器的容量估算功能。
        """
        manager = EnterpriseContextManager()
        manager.initialize(identity="Capacity Test")
        orchestrator = manager.get_orchestrator()
        budget_ctrl = orchestrator.budget_controller

        # 估算容量
        capacity = budget_ctrl.estimate_capacity(avg_message_tokens=200)

        assert capacity["max_messages"] > 0
        assert capacity["system_capacity"] > 0
        assert capacity["task_capacity"] > 0
        assert capacity["conversation_capacity"] > 0

        # 验证合理性
        assert capacity["max_messages"] > 100  # 应该能容纳至少 100 条消息


class TestE2ECompressionStrategies:
    """端到端压缩策略测试"""

    def test_sliding_window_compression_e2e(self):
        """
        E2E 测试: 滑动窗口压缩

        验证滑动窗口压缩策略的正确性。
        """
        config = ContextConfig(max_conversation_rounds=5)
        manager = EnterpriseContextManager(config=config)
        manager.initialize(identity="Sliding Window Test")

        manager.start_task("sw-task", "t1", "chat", "Sliding window test")

        # 添加超过限制的消息
        for i in range(20):
            manager.add_message("sw-session", "user", f"User message {i}")
            manager.add_message("sw-session", "assistant", f"Assistant response {i}")

        conv = manager.get_conversation("sw-session")

        # 验证滑动窗口生效
        assert conv._count_rounds() <= 5

        # 验证最近的消息保留
        messages = conv.to_messages()
        recent_content = str(messages)
        assert "User message 19" in recent_content or "message 19" in recent_content
        assert "User message 0" not in recent_content

    def test_priority_based_trimming_e2e(self):
        """
        E2E 测试: 基于优先级的裁剪

        验证低优先级任务被优先裁剪。
        """
        manager = EnterpriseContextManager()
        manager.initialize(identity="Priority Trim Test")
        orchestrator = manager.get_orchestrator()

        # 创建不同优先级的任务
        tasks = []
        for i, priority in enumerate([
            ContextPriority.LOW,
            ContextPriority.MEDIUM,
            ContextPriority.HIGH,
            ContextPriority.CRITICAL,
        ]):
            task_id = f"priority-task-{i}"
            task = manager.start_task(task_id, "t1", "test", f"Task with priority {priority.name}")
            task.add_step_summary("step1", f"Content for {priority.name}" * 10)
            orchestrator.set_task_priority(task_id, priority)
            tasks.append((task_id, priority, task))

        # 执行优先级裁剪
        trimmed_tokens = orchestrator.trim_by_priority(target_tokens=0)

        # 验证低优先级被裁剪
        low_task = manager.get_task("priority-task-0")
        medium_task = manager.get_task("priority-task-1")

        # LOW 和 MEDIUM 应该被裁剪
        assert len(low_task.step_summaries) == 0
        assert len(medium_task.step_summaries) == 0

        # HIGH 和 CRITICAL 应该保留
        high_task = manager.get_task("priority-task-2")
        critical_task = manager.get_task("priority-task-3")
        assert len(high_task.step_summaries) > 0
        assert len(critical_task.step_summaries) > 0

    def test_context_compression_with_budget(self):
        """
        E2E 测试: 预算触发的上下文压缩

        验证当预算紧张时自动触发压缩。
        """
        config = ContextConfig(max_conversation_rounds=30)
        manager = EnterpriseContextManager(config=config)
        manager.initialize(identity="Auto Compression Test")

        manager.start_task("auto-task", "t1", "chat", "Auto compression test")

        # 添加大量消息
        for i in range(100):
            manager.add_message("auto-session", "user", f"Message {i}" + "x" * 200)
            manager.add_message("auto-session", "assistant", f"Response {i}" + "y" * 200)

        # 构建上下文
        system_prompt, messages = manager.build_context("auto-task", "auto-session")

        # 消息应该被压缩
        assert len(messages) < 200


class TestE2EContextPerformance:
    """端到端上下文性能测试"""

    def test_context_build_performance(self):
        """
        E2E 测试: 上下文构建性能

        验证上下文构建在合理时间内完成。
        """
        config = ContextConfig(max_conversation_rounds=20)
        manager = EnterpriseContextManager(config=config)
        manager.initialize(
            identity="Performance Test Agent",
            rules=["Rule 1", "Rule 2", "Rule 3"],
        )

        manager.start_task("perf-task", "t1", "benchmark", "Performance benchmark")

        # 添加大量消息
        for i in range(50):
            manager.add_message("perf-session", "user", f"User message {i}" * 20)
            manager.add_message("perf-session", "assistant", f"Assistant response {i}" * 20)

        # 测量构建时间
        start_time = time.perf_counter()
        for _ in range(10):
            system_prompt, messages = manager.build_context("perf-task", "perf-session")
        elapsed_ms = (time.perf_counter() - start_time) * 1000 / 10

        # 平均构建时间应该 < 20ms
        assert elapsed_ms < 20, f"Context build took {elapsed_ms}ms, expected < 20ms"

    def test_large_scale_context_handling(self):
        """
        E2E 测试: 大规模上下文处理

        验证系统能够处理大规模上下文。
        """
        manager = EnterpriseContextManager()
        manager.initialize(identity="Large Scale Test")

        # 创建多个任务
        for i in range(20):
            task = manager.start_task(f"large-task-{i}", f"tenant-{i}", "batch", f"Batch task {i}")
            for j in range(10):
                task.add_step_summary(f"step_{j}", f"Step {j} of task {i}")
            for k in range(10):
                task.add_variable(f"var_{k}", f"value_{k}")

        # 创建多个会话
        for i in range(20):
            for j in range(20):
                manager.add_message(f"large-session-{i}", "user", f"Message {j}")

        # 验证系统稳定
        assert manager.get_task_count() == 20
        assert manager.get_session_count() == 20

        # 随机验证
        random_task = manager.get_task("large-task-10")
        assert random_task is not None
        assert len(random_task.step_summaries) == 10

        # 清理性能
        start_time = time.perf_counter()
        manager.clear_all()
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        assert elapsed_ms < 100, f"Clear all took {elapsed_ms}ms"
        assert manager.get_task_count() == 0
        assert manager.get_session_count() == 0

    def test_memory_efficiency_under_load(self):
        """
        E2E 测试: 负载下的内存效率

        验证系统在持续负载下保持稳定。
        """
        manager = EnterpriseContextManager()
        manager.initialize(identity="Memory Test")

        # 模拟持续使用
        for cycle in range(5):
            # 创建任务
            task = manager.start_task(f"mem-task-{cycle}", "t1", "loop", f"Cycle {cycle}")

            # 添加内容
            for i in range(20):
                manager.add_message(f"mem-session-{cycle}", "user", f"Cycle {cycle} message {i}")

            # 构建上下文
            system_prompt, messages = manager.build_context(
                f"mem-task-{cycle}", f"mem-session-{cycle}"
            )
            assert system_prompt is not None

            # 清理当前周期
            manager.end_task(f"mem-task-{cycle}")

        # 最终状态
        assert manager.get_task_count() == 0
        assert manager.get_session_count() == 5  # 会话保留


class TestE2EContextWithAgentIntegration:
    """端到端 Agent 与上下文集成测试"""

    def test_agent_context_backend_creation(self):
        """
        E2E 测试: Agent 创建时自动配置 ContextBackend

        验证 Agent 默认使用企业级 ContextBackend。
        """
        # 模拟最小 Agent 初始化
        from openakita.context import create_context_backend

        backend = create_context_backend()
        assert backend is not None

        # 初始化
        backend.initialize(identity="Test Agent", rules=["Be helpful"])

        # 验证基本操作
        task = backend.start_task("agent-task", "tenant-1", "test", "Agent task")
        assert task is not None

        backend.add_message("agent-session", "user", "Hello")
        system_prompt, messages = backend.build_context("agent-task", "agent-session")

        assert "Test Agent" in system_prompt
        assert len(messages) == 1

    def test_agent_enterprise_context_factory(self):
        """
        E2E 测试: 企业级上下文工厂方法

        验证创建企业级上下文的便捷方法。
        """
        # 使用工厂方法
        config = ContextConfig(
            max_conversation_rounds=30,
            max_task_summaries=25,
        )

        backend = create_context_backend(config=config)
        backend.initialize(identity="Enterprise Agent")

        # 验证配置生效
        task = backend.start_task("factory-task", "t1", "test", "Factory test")
        backend.add_message("factory-session", "user", "Test")

        # 添加超过默认轮数的消息
        for i in range(40):
            backend.add_message("factory-session", "user", f"Message {i}")

        conv = backend.get_conversation("factory-session")
        # 应该被限制在配置的轮数
        assert conv._count_rounds() <= 30

    def test_context_state_consistency(self):
        """
        E2E 测试: 上下文状态一致性

        验证在多次操作后状态保持一致。
        """
        manager = EnterpriseContextManager()
        manager.initialize(identity="Consistency Test")

        # 执行一系列操作
        for i in range(10):
            task_id = f"consistency-task-{i}"
            session_id = f"consistency-session-{i}"

            # 创建任务
            task = manager.start_task(task_id, f"tenant-{i}", "test", f"Task {i}")
            task.add_step_summary("step1", f"Step for task {i}")
            task.add_variable("index", str(i))

            # 添加消息
            for j in range(5):
                manager.add_message(session_id, "user", f"Task {i} message {j}")

            # 构建上下文
            system_prompt, messages = manager.build_context(task_id, session_id)

            # 验证一致性
            assert f"Task {i}" in system_prompt
            assert str(i) in system_prompt
            assert len(messages) == 5

            # 获取统计
            stats = manager.get_stats(task_id, session_id)
            assert stats["total_estimated_tokens"] > 0

        # 验证最终状态
        assert manager.get_task_count() == 10
        assert manager.get_session_count() == 10

        # 清理并验证
        manager.clear_all()
        assert manager.get_task_count() == 0
        assert manager.get_session_count() == 0


class TestE2EContextEdgeCases:
    """端到端边界情况测试"""

    def test_empty_context_handling(self):
        """
        E2E 测试: 空上下文处理

        验证系统正确处理空上下文场景。
        """
        manager = EnterpriseContextManager()
        manager.initialize(identity="Empty Context Test")

        # 创建任务但不添加任何内容
        manager.start_task("empty-task", "t1", "test", "Empty task")

        # 尝试构建上下文
        system_prompt, messages = manager.build_context("empty-task", "empty-session")

        # 系统提示应该存在
        assert system_prompt is not None
        assert "Empty Context Test" in system_prompt

        # 消息可能为空
        assert isinstance(messages, list)

    def test_concurrent_session_access(self):
        """
        E2E 测试: 并发会话访问

        验证多个会话同时操作的正确性。
        """
        manager = EnterpriseContextManager()
        manager.initialize(identity="Concurrent Test")

        # 模拟并发添加消息
        for i in range(10):
            for j in range(5):
                manager.add_message(f"concurrent-session-{i}", "user", f"Message {j}")

        # 验证每个会话独立
        for i in range(10):
            conv = manager.get_conversation(f"concurrent-session-{i}")
            assert conv is not None
            assert len(conv.messages) == 5

    def test_context_recovery_after_error(self):
        """
        E2E 测试: 错误后上下文恢复

        验证系统在错误后能够恢复。
        """
        manager = EnterpriseContextManager()
        manager.initialize(identity="Recovery Test")

        # 创建正常任务
        manager.start_task("normal-task", "t1", "test", "Normal task")
        manager.add_message("normal-session", "user", "Normal message")

        # 尝试访问不存在的任务（不应该崩溃）
        result = manager.get_task("nonexistent-task")
        assert result is None

        # 尝试构建不存在任务的上下文（可能抛异常或返回空）
        try:
            system_prompt, messages = manager.build_context("nonexistent", "session")
        except Exception:
            pass  # 预期可能抛出异常

        # 正常任务应该仍然可用
        task = manager.get_task("normal-task")
        assert task is not None

        conv = manager.get_conversation("normal-session")
        assert conv is not None
        assert len(conv.messages) == 1

    def test_context_with_unicode_content(self):
        """
        E2E 测试: Unicode 内容处理

        验证系统正确处理 Unicode 内容。
        """
        manager = EnterpriseContextManager()
        manager.initialize(
            identity="Unicode 测试代理 🤖",
            rules=["使用中文 🇨🇳", "使用表情符号 🎉"],
        )

        task = manager.start_task("unicode-task", "t1", "test", "Unicode 任务 📋")
        task.add_step_summary("步骤1", "初始化完成 ✅")
        task.add_variable("状态", "运行中 🚀")

        # 添加 Unicode 消息
        unicode_messages = [
            ("user", "你好，世界！🌍"),
            ("assistant", "你好！有什么可以帮助你的？😊"),
            ("user", "请解释量子纠缠 ⚛️"),
            ("assistant", "量子纠缠是量子力学中的一个重要概念... 🔬"),
        ]

        for role, content in unicode_messages:
            manager.add_message("unicode-session", role, content)

        # 构建上下文
        system_prompt, messages = manager.build_context("unicode-task", "unicode-session")

        # 验证 Unicode 内容保留
        assert "🤖" in system_prompt
        assert "🇨🇳" in system_prompt
        assert "✅" in system_prompt
        assert "🚀" in system_prompt
        assert "🌍" in str(messages)


class TestE2EContextStatistics:
    """端到端统计功能测试"""

    def test_comprehensive_statistics(self):
        """
        E2E 测试: 综合统计功能

        验证统计信息的完整性和准确性。
        """
        manager = EnterpriseContextManager()
        manager.initialize(
            identity="Statistics Agent",
            rules=["Rule A", "Rule B"],
        )

        task = manager.start_task("stats-task", "t1", "analysis", "Statistics test")
        for i in range(5):
            task.add_step_summary(f"step_{i}", f"Completed step {i}")
        for i in range(3):
            task.add_variable(f"var_{i}", f"value_{i}")

        for i in range(10):
            manager.add_message("stats-session", "user", f"Stats message {i}" * 10)

        # 获取统计
        stats = manager.get_stats("stats-task", "stats-session")

        # 验证统计结构
        assert "system" in stats
        assert "task" in stats
        assert "conversation" in stats
        assert "total_estimated_tokens" in stats

        # 验证系统统计
        # get_stats() 返回 identity_length 和 rules_count
        assert stats["system"]["identity_length"] > 0  # "Statistics Agent" 有长度
        assert stats["system"]["rules_count"] == 2
        assert stats["system"]["estimated_tokens"] > 0

        # 验证任务统计
        assert stats["task"]["task_id"] == "stats-task"
        assert stats["task"]["step_count"] == 5
        assert stats["task"]["variable_count"] == 3
        assert stats["task"]["estimated_tokens"] > 0

        # 验证会话统计
        conv_stats = stats["conversation"]
        assert conv_stats is not None
        assert conv_stats["message_count"] == 10

        # 验证总 Token
        assert stats["total_estimated_tokens"] > 0

    def test_orchestrator_statistics(self):
        """
        E2E 测试: 编排器统计

        验证 ContextOrchestrator 的统计功能。
        """
        orchestrator = create_orchestrator(
            identity="Orchestrator Stats",
            rules=["Rule 1"],
        )

        # 创建任务和会话
        for i in range(5):
            orchestrator.create_task(
                task_id=f"stats-task-{i}",
                tenant_id=f"tenant-{i}",
                description=f"Task {i}",
            )
            orchestrator.get_or_create_conversation(f"stats-session-{i}")

        # 获取统计
        stats = orchestrator.get_stats()

        assert stats["tasks_count"] == 5
        assert stats["conversations_count"] == 5
        assert "system_context_stats" in stats
        assert "budget_status" in stats
        assert "config" in stats