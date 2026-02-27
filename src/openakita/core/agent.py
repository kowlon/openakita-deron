"""
Agent 主类 - 协调所有模块

这是 OpenAkita 的核心，负责:
- 接收用户输入
- 协调各个模块
- 执行工具调用
- 执行 Ralph 循环
- 管理对话和记忆
- 自我进化（技能搜索、安装、生成）

Skills 系统遵循 Agent Skills 规范 (agentskills.io)
MCP 系统遵循 Model Context Protocol 规范 (modelcontextprotocol.io)
"""
from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import logging
import os
import re
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from ..config import settings
from ..context.conversation_context import ConversationContext

# 记忆系统
from ..memory import MemoryManager

# Prompt 编译管线 (v2)
# 技能系统 (SKILL.md 规范)
from ..skills import SkillManager

# 系统工具目录（渐进式披露）
from ..tools.catalog import ToolCatalog

# 系统工具定义（从 tools/definitions 导入）
from ..tools.definitions import BASE_TOOLS
from ..tools.file import FileTool

# Handler Registry（模块化工具执行）
from ..tools.handlers import SystemHandlerRegistry

# MCP 系统
from ..tools.mcp import mcp_client
from ..tools.mcp_catalog import MCPCatalog
from ..tools.mcp_manager import MCPManager
from ..tools.shell import ShellTool
from ..tools.web import WebTool
from .agent_state import AgentState, TaskState, TaskStatus
from .interrupt_manager import InterruptManager, STOP_COMMANDS, SKIP_COMMANDS
from .retrospect import RetrospectManager
from .prompt_assembler import PROMPT_COMPILER_SYSTEM
from .helpers.tool_helper import init_handlers
from .helpers.capability_helper import setup_capability_system
from .helpers.session_helper import (
    cleanup_session_state,
    finalize_session,
    prepare_session_context,
    resolve_conversation_id,
)
from ..llm.brain import Brain, Context
from .errors import UserCancelledError
from .identity import Identity
from .prompt_assembler import PromptAssembler
from .ralph import RalphLoop, TaskResult
from .reasoning_engine import ReasoningEngine
from .response_handler import (
    ResponseHandler,
    clean_llm_response,
    strip_thinking_tags,
)
from .task_monitor import RETROSPECT_PROMPT, TaskMonitor
from ..infra import (
    TokenTrackingContext,
    init_token_tracking,
    reset_tracking_context,
    set_tracking_context,
)
from ..tools.executor import ToolExecutor

_DESKTOP_AVAILABLE = False
_desktop_tool_handler = None
if sys.platform == "win32":
    try:
        from ..tools.desktop import DESKTOP_TOOLS, DesktopToolHandler

        _DESKTOP_AVAILABLE = True
        _desktop_tool_handler = DesktopToolHandler()
    except ImportError:
        pass

logger = logging.getLogger(__name__)


class Agent:
    """
    OpenAkita 主类

    一个全能自进化AI助手，基于 Ralph Wiggum 模式永不放弃。
    """

    # 基础工具定义 (Claude API tool use format)
    # BASE_TOOLS 已移至 tools/definitions/ 目录
    # 通过 from ..tools.definitions import BASE_TOOLS 导入

    # 说明：历史上这里用类变量保存 IM 上下文，存在并发串台风险。
    # 现在改为使用 `openakita.core.im_context` 中的 contextvars（协程隔离）。
    _current_im_session = None  # legacy: 保留字段避免外部引用崩溃（不再使用）
    _current_im_gateway = None  # legacy: 保留字段避免外部引用崩溃（不再使用）

    # 向后兼容：常量现在从 InterruptManager 导入
    STOP_COMMANDS = STOP_COMMANDS
    SKIP_COMMANDS = SKIP_COMMANDS

    def __init__(
        self,
        name: str | None = None,
        api_key: str | None = None,
        context_backend: Any | None = None,
    ):
        self.name = name or settings.agent_name

        # 初始化核心组件
        self.identity = Identity()
        self.brain = Brain(api_key=api_key)
        self.ralph = RalphLoop(
            max_iterations=settings.max_iterations,
            on_iteration=self._on_iteration,
            on_error=self._on_error,
        )

        # 初始化基础工具
        self.shell_tool = ShellTool()
        self.file_tool = FileTool()
        self.web_tool = WebTool()

        # 技能管理器（委托自 _install_skill / _load_installed_skills 等）
        self.skill_manager = SkillManager(
            brain=self.brain,
            shell_tool=self.shell_tool,
        )

        # MCP 系统
        self.mcp_client = mcp_client
        self.mcp_catalog = MCPCatalog()
        self.mcp_manager = MCPManager(self.mcp_client, self.mcp_catalog)

        # 系统工具目录（渐进式披露）
        _all_tools = list(BASE_TOOLS)
        if _DESKTOP_AVAILABLE:
            _all_tools.extend(DESKTOP_TOOLS)
        self.tool_catalog = ToolCatalog(_all_tools)

        # 定时任务调度器
        self.task_scheduler = None  # 在 initialize() 中启动

        # 记忆系统
        self.memory_manager = MemoryManager(
            data_dir=settings.project_root / "data" / "memory",
            memory_md_path=settings.memory_path,
            brain=self.brain,
            embedding_model=settings.embedding_model,
            embedding_device=settings.embedding_device,
            model_download_source=settings.model_download_source,
        )

        # 动态工具列表（基础工具 + 技能工具）
        self._tools = list(BASE_TOOLS)

        # Add desktop tools on Windows
        if _DESKTOP_AVAILABLE:
            self._tools.extend(DESKTOP_TOOLS)
            logger.info(f"Desktop automation tools enabled ({len(DESKTOP_TOOLS)} tools)")

        self.skill_manager.update_shell_tool_description(self._tools)

        # 对话上下文
        self._context = Context()
        self._conversation_history: list[dict] = []

        # 消息中断机制
        self._current_session = None  # 当前会话引用
        self._interrupt_enabled = True  # 是否启用中断检查

        # 任务取消机制 — 统一使用 TaskState.cancelled / agent_state.is_task_cancelled
        # (旧 self._task_cancelled 已废弃，取消状态绑定到 TaskState 实例，避免全局竞态)

        # 当前任务监控器（仅在 IM 任务执行期间设置；供 system 工具动态调整超时策略）
        self._current_task_monitor = None

        # 状态
        self._initialized = False
        self._running = False

        # Handler Registry（模块化工具执行）
        self.handler_registry = SystemHandlerRegistry()
        init_handlers(self)

        # === 工具并行执行基础设施（默认不开启并行，tool_max_parallel=1）===
        # 并行执行只影响“同一轮模型返回多个 tool_use/tool_calls”的工具批处理阶段。
        # 注意：browser/desktop/mcp 等状态型工具默认互斥，避免并发踩踏状态。
        self._tool_semaphore = asyncio.Semaphore(max(1, settings.tool_max_parallel))
        self._tool_handler_locks: dict[str, asyncio.Lock] = {}
        for hn in ("browser", "desktop", "mcp"):
            self._tool_handler_locks[hn] = asyncio.Lock()
        self._task_monitor_lock = asyncio.Lock()

        # ==================== Phase 2: 新增子模块 ====================
        # 结构化状态管理
        self.agent_state = AgentState()

        # 中断管理器（委托中断相关方法）
        self.interrupt_manager = InterruptManager(
            agent_state=self.agent_state,
            get_current_session_id=lambda: getattr(self, "_current_session_id", None),
        )

        # 复盘管理器（委托复盘相关方法）
        self.retrospect_manager = RetrospectManager(
            brain=self.brain,
            memory_manager=self.memory_manager,
        )

        # 工具执行引擎（委托自 _execute_tool / _execute_tool_calls_batch）
        self.tool_executor = ToolExecutor(
            handler_registry=self.handler_registry,
            max_parallel=max(1, settings.tool_max_parallel),
        )

        # 上下文管理器（企业版后端）
        # 企业版默认：若未注入，则创建企业级 ContextBackend
        self._context_backend = context_backend
        if context_backend is None:
            from ..config import create_context_backend

            self._context_backend = create_context_backend()

        self.context_manager = self._context_backend
        logger.info("Agent using enterprise ContextBackend")

        # 能力系统（Phase 2 新增）
        # 初始化为 None，在 initialize() 中设置
        self.capability_registry = None
        self.capability_executor = None

        # 响应处理器（委托自 _verify_task_completion 等）
        self.response_handler = ResponseHandler(
            brain=self.brain,
            memory_manager=self.memory_manager,
        )

        # 提示词组装器（委托自 _build_system_prompt 等）
        self.prompt_assembler = PromptAssembler(
            tool_catalog=self.tool_catalog,
            skill_catalog=self.skill_catalog,
            mcp_catalog=self.mcp_catalog,
            memory_manager=self.memory_manager,
            brain=self.brain,
        )

        context_config = getattr(self._context_backend, "config", None)
        max_conversation_rounds = getattr(context_config, "max_conversation_rounds", 20)
        max_conversation_tokens = getattr(context_config, "max_conversation_tokens", 8000)

        self._max_conversation_rounds = max_conversation_rounds
        self._max_conversation_tokens = max_conversation_tokens

        # 推理引擎（替代 _chat_with_tools_and_context）
        self.reasoning_engine = ReasoningEngine(
            brain=self.brain,
            tool_executor=self.tool_executor,
            max_conversation_rounds=max_conversation_rounds,
            max_conversation_tokens=max_conversation_tokens,
            response_handler=self.response_handler,
            agent_state=self.agent_state,
        )

        logger.info(f"Agent '{self.name}' created (with refactored sub-modules)")

    @classmethod
    def create_with_enterprise_context(
        cls,
        name: str | None = None,
        api_key: str | None = None,
        max_conversation_rounds: int = 20,
        max_task_summaries: int = 20,
        max_task_variables: int = 50,
    ) -> "Agent":
        """
        创建使用企业级 ContextBackend 的 Agent 实例。

        企业级 ContextBackend 使用滑动窗口替代 LLM 压缩，
        将上下文构建延迟从 2-5s 降到 <10ms。

        Args:
            name: Agent 名称
            api_key: API Key
            max_conversation_rounds: 对话滑动窗口大小
            max_task_summaries: 任务摘要最大数量
            max_task_variables: 任务变量最大数量

        Returns:
            使用企业级 ContextBackend 的 Agent 实例

        Example:
            agent = Agent.create_with_enterprise_context(
                name="EnterpriseBot",
                max_conversation_rounds=30
            )
        """
        from ..config import ContextBackendConfig, create_context_backend

        config = ContextBackendConfig(
            max_conversation_rounds=max_conversation_rounds,
            max_task_summaries=max_task_summaries,
            max_task_variables=max_task_variables,
        )

        context_backend = create_context_backend(config)
        return cls(name=name, api_key=api_key, context_backend=context_backend)

    @property
    def context_backend_type(self) -> str:
        """获取当前使用的 ContextBackend 类型。"""
        if self._context_backend is not None:
            backend_type = type(self._context_backend).__name__
            if "Enterprise" in backend_type:
                return "enterprise"
            elif "Legacy" in backend_type:
                return "legacy"
            return f"custom({backend_type})"
        return "enterprise(default)"

    @property
    def skill_registry(self):
        """[Backward Compatibility] Delegate to skill_manager.registry"""
        return self.skill_manager.registry

    @property
    def skill_loader(self):
        """[Backward Compatibility] Delegate to skill_manager.loader"""
        return self.skill_manager.loader

    @property
    def skill_catalog(self):
        """[Backward Compatibility] Delegate to skill_manager.catalog"""
        return self.skill_manager.catalog

    @property
    def skill_generator(self):
        """[Backward Compatibility] Delegate to skill_manager.generator"""
        return self.skill_manager.generator

    @property
    def browser_mcp(self):
        """[Backward Compatibility] Delegate to mcp_manager.browser_mcp"""
        return self.mcp_manager.browser_mcp

    @browser_mcp.setter
    def browser_mcp(self, value):
        self.mcp_manager.browser_mcp = value

    @property
    def _builtin_mcp_count(self):
        """[Backward Compatibility] Delegate to mcp_manager.builtin_count"""
        return self.mcp_manager.builtin_count

    @_builtin_mcp_count.setter
    def _builtin_mcp_count(self, value):
        self.mcp_manager._builtin_mcp_count = value

    @property
    def _mcp_catalog_text(self):
        """[Backward Compatibility] Delegate to mcp_manager.catalog_text"""
        return self.mcp_manager.catalog_text

    @_mcp_catalog_text.setter
    def _mcp_catalog_text(self, value):
        self.mcp_manager.catalog_text = value

    def _get_tool_handler_name(self, tool_name: str) -> str | None:
        """获取工具对应的 handler 名称（用于互斥/并发策略）"""
        try:
            return self.handler_registry.get_handler_name_for_tool(tool_name)
        except Exception:
            return None

    async def _execute_tool_calls_batch(
        self,
        tool_calls: list[dict],
        *,
        task_monitor=None,
        allow_interrupt_checks: bool = True,
        capture_delivery_receipts: bool = False,
    ) -> tuple[list[dict], list[str], list | None]:
        """
        执行一批工具调用，并返回 tool_results（顺序与 tool_calls 一致）。

        并行策略：
        - 默认串行（settings.tool_max_parallel=1 或启用中断检查时）
        - 当 tool_max_parallel>1 且不需要“工具间中断检查”时，允许并行执行
        - browser/desktop/mcp handler 默认互斥锁（即使并行也不会并发执行同 handler）
        """
        executed_tool_names: list[str] = []
        delivery_receipts: list | None = None

        if not tool_calls:
            return [], executed_tool_names, delivery_receipts

        # 并行执行会降低“工具间中断检查”的插入粒度（并行时没有天然的工具间隙）
        # 默认：启用中断检查 => 串行；可通过配置显式允许并行。
        allow_parallel_with_interrupts = bool(
            getattr(settings, "allow_parallel_tools_with_interrupt_checks", False)
        )
        parallel_enabled = settings.tool_max_parallel > 1 and (
            (not allow_interrupt_checks) or allow_parallel_with_interrupts
        )

        # 获取 cancel_event / skip_event 用于工具执行竞速取消/跳过
        _tool_cancel_event = (
            self.agent_state.current_task.cancel_event
            if self.agent_state and self.agent_state.current_task
            else asyncio.Event()
        )
        _tool_skip_event = (
            self.agent_state.current_task.skip_event
            if self.agent_state and self.agent_state.current_task
            else asyncio.Event()
        )

        async def _run_one(tc: dict, idx: int) -> tuple[int, dict, str | None, list | None]:
            tool_name = tc.get("name", "")
            tool_input = tc.get("input") or {}
            tool_use_id = tc.get("id", "")

            if self._task_cancelled:
                return (
                    idx,
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": "[任务已被用户停止]",
                        "is_error": True,
                    },
                    None,
                    None,
                )

            handler_name = self._get_tool_handler_name(tool_name)
            handler_lock = self._tool_handler_locks.get(handler_name) if handler_name else None

            t0 = time.time()
            success = True
            result_str = ""
            receipts: list | None = None

            use_parallel_safe_monitor = parallel_enabled and task_monitor is not None and hasattr(
                task_monitor, "record_tool_call"
            )
            if (not parallel_enabled) and task_monitor:
                task_monitor.begin_tool_call(tool_name, tool_input)

            try:
                async def _do_exec():
                    async with self._tool_semaphore:
                        if handler_lock:
                            async with handler_lock:
                                return await self._execute_tool(tool_name, tool_input)
                        else:
                            return await self._execute_tool(tool_name, tool_input)

                # 将工具执行与 cancel_event / skip_event 三路竞速
                # 注意: 不在此处 clear_skip()，让已到达的 skip 信号自然被竞速消费
                tool_task = asyncio.create_task(_do_exec())
                cancel_waiter = asyncio.create_task(_tool_cancel_event.wait())
                skip_waiter = asyncio.create_task(_tool_skip_event.wait())

                done_set, pending_set = await asyncio.wait(
                    {tool_task, cancel_waiter, skip_waiter},
                    return_when=asyncio.FIRST_COMPLETED,
                )

                for t in pending_set:
                    t.cancel()
                    try:
                        await t
                    except (asyncio.CancelledError, Exception):
                        pass

                if cancel_waiter in done_set and tool_task not in done_set:
                    # cancel_event 先触发，工具被中断（终止整个任务）
                    logger.info(f"[StopTask] Tool {tool_name} interrupted by user cancel")
                    success = False
                    result_str = f"[工具 {tool_name} 被用户中断]"
                    return (
                        idx,
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_use_id,
                            "content": result_str,
                            "is_error": True,
                        },
                        None,
                        None,
                    )

                if skip_waiter in done_set and tool_task not in done_set:
                    # skip_event 先触发，仅跳过当前工具（不终止任务）
                    _skip_reason = (
                        self.agent_state.current_task.skip_reason
                        if self.agent_state and self.agent_state.current_task
                        else "用户请求跳过"
                    )
                    if self.agent_state and self.agent_state.current_task:
                        self.agent_state.current_task.clear_skip()
                    logger.info(f"[SkipStep] Tool {tool_name} skipped by user: {_skip_reason}")
                    success = True
                    result_str = f"[用户跳过了此步骤: {_skip_reason}]"
                    return (
                        idx,
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_use_id,
                            "content": result_str,
                            "is_error": False,
                        },
                        tool_name,
                        None,
                    )

                result = tool_task.result()
                result_str = str(result) if result is not None else "操作已完成"

                _preview = result_str if len(result_str) <= 800 else result_str[:800] + "\n... (已截断)"
                logger.info(f"[Tool] {tool_name} → {_preview}")

                if capture_delivery_receipts and tool_name == "deliver_artifacts" and result_str:
                    try:
                        import json as _json

                        parsed = _json.loads(result_str)
                        rs = parsed.get("receipts") if isinstance(parsed, dict) else None
                        if isinstance(rs, list):
                            receipts = rs
                    except Exception:
                        receipts = None

                out = {
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": result_str,
                }
                return idx, out, tool_name, receipts
            except Exception as e:
                success = False
                result_str = str(e)
                logger.info(f"[Tool] {tool_name} ❌ 错误: {result_str}")
                out = {
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": f"工具执行错误: {result_str}",
                    "is_error": True,
                }
                return idx, out, None, None
            finally:
                dt_ms = int((time.time() - t0) * 1000)
                if task_monitor:
                    if use_parallel_safe_monitor:
                        async with self._task_monitor_lock:
                            task_monitor.record_tool_call(
                                tool_name,
                                tool_input,
                                result_str,
                                success=success,
                                duration_ms=dt_ms,
                            )
                    else:
                        task_monitor.end_tool_call(result_str, success=success)

        if not parallel_enabled:
            tool_results: list[dict] = []
            for tc in tool_calls:
                idx = len(tool_results)
                _, out, executed_name, receipts = await _run_one(tc, idx)
                tool_results.append(out)
                if executed_name:
                    executed_tool_names.append(executed_name)
                if receipts:
                    delivery_receipts = receipts
            return tool_results, executed_tool_names, delivery_receipts

        tasks = [_run_one(tc, idx) for idx, tc in enumerate(tool_calls)]
        done = await asyncio.gather(*tasks, return_exceptions=False)
        done.sort(key=lambda x: x[0])
        tool_results = [out for _, out, _, _ in done]
        for _, _, executed_name, receipts in done:
            if executed_name:
                executed_tool_names.append(executed_name)
            if receipts:
                delivery_receipts = receipts
        return tool_results, executed_tool_names, delivery_receipts

    async def initialize(self, start_scheduler: bool = True) -> None:
        """
        初始化 Agent

        Args:
            start_scheduler: 是否启动定时任务调度器（定时任务执行时应设为 False）
        """
        if self._initialized:
            return

        # 初始化 token 用量追踪
        init_token_tracking(str(settings.db_full_path))

        # 加载身份文档
        self.identity.load()

        # 加载已安装的技能
        await self.skill_manager.load_installed_skills()
        # 更新工具描述
        self.skill_manager.update_shell_tool_description(self._tools)

        # 加载 MCP 配置
        await self.mcp_manager.load_servers()

        # === 能力系统初始化 ===
        # 统一能力系统：整合 Tools / Skills / MCP 到统一执行入口
        try:
            setup_capability_system(self)
            logger.info(
                f"[CapabilitySystem] Initialized with "
                f"{len(self.capability_executor.list_adapters())} adapters"
            )
        except Exception as e:
            logger.warning(f"[CapabilitySystem] Initialization failed: {e}")

        # 启动记忆会话
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + str(uuid.uuid4())[:8]
        self.memory_manager.start_session(session_id)
        self._current_session_id = session_id

        # 启动定时任务调度器（定时任务执行时跳过，避免重复）
        if start_scheduler:
            await self._start_scheduler()

        # 设置系统提示词 (包含技能清单、MCP 清单和相关记忆)
        base_prompt = self.identity.get_system_prompt()
        self._context.system = self._build_system_prompt(base_prompt, use_compiled=True)

        # === 启动预热（把昂贵但可复用的初始化提前到启动阶段）===
        # 目标：避免首条用户消息才加载 embedding/向量库、生成清单等，导致 IM 首响应显著变慢。
        try:
            # 1) 预热清单缓存（避免每次 build_system_prompt 都重新生成）
            # 注意：这些方法内部已有缓存；这里调用一次确保缓存命中。
            with contextlib.suppress(Exception):
                self.tool_catalog.get_catalog()
            with contextlib.suppress(Exception):
                self.skill_catalog.get_catalog()
            with contextlib.suppress(Exception):
                self.mcp_catalog.get_catalog()

            # 2) 预热向量库（embedding 模型 + ChromaDB）
            # 放到线程中执行，避免阻塞事件循环；初始化完成后后续搜索会明显更快。
            await asyncio.to_thread(lambda: bool(self.memory_manager.vector_store.enabled))
        except Exception as e:
            # 预热失败不应影响启动（例如 chromadb 未安装时会自动禁用）
            logger.debug(f"[Prewarm] skipped/failed: {e}")

        # === browser_task 依赖的 LLM 配置注入 ===
        # browser_task（browser-use）需要一个 OpenAI-compatible LLM。
        # 这里将 LLMClient 传递给 MCPManager 进行配置注入。
        try:
            self.mcp_manager.inject_llm_config(getattr(self.brain, "_llm_client", None))
        except Exception as e:
            logger.debug(f"[BrowserMCP] LLM config injection skipped/failed: {e}")

        self._initialized = True
        total_mcp = self.mcp_catalog.server_count + self._builtin_mcp_count
        logger.info(
            f"Agent '{self.name}' initialized with "
            f"{self.skill_registry.count} skills, "
            f"{total_mcp} MCP servers"
            f"{f' (builtin: {self._builtin_mcp_count})' if self._builtin_mcp_count else ''}"
        )





    async def _start_scheduler(self) -> None:
        """启动定时任务调度器"""
        try:
            from ..scheduler import TaskScheduler
            from ..scheduler.executor import TaskExecutor

            # 创建执行器（gateway 稍后通过 set_scheduler_gateway 设置）
            self._task_executor = TaskExecutor(timeout_seconds=settings.scheduler_task_timeout)
            # 预设 memory 引用，供系统任务使用
            self._task_executor.memory_manager = getattr(self, "memory_manager", None)

            # 创建调度器
            self.task_scheduler = TaskScheduler(
                storage_path=settings.project_root / "data" / "scheduler",
                executor=self._task_executor.execute,
            )

            # 启动调度器
            await self.task_scheduler.start()

            # 注册内置系统任务（每日记忆整理 + 每日自检）
            await self._register_system_tasks()

            stats = self.task_scheduler.get_stats()
            logger.info(f"TaskScheduler started with {stats['total_tasks']} tasks")

        except Exception as e:
            logger.warning(f"Failed to start scheduler: {e}")
            self.task_scheduler = None

    async def _register_system_tasks(self) -> None:
        """
        注册内置系统任务

        包括:
        - 每日记忆整理（凌晨 3:00）
        - 每日系统自检（凌晨 4:00）
        """
        from ..scheduler import ScheduledTask, TriggerType
        from ..scheduler.task import TaskType

        if not self.task_scheduler:
            return

        # 检查是否已存在（避免重复注册）
        existing_tasks = self.task_scheduler.list_tasks()
        existing_ids = {t.id for t in existing_tasks}

        # 任务 1: 每日记忆整理（凌晨 3:00）
        if "system_daily_memory" not in existing_ids:
            memory_task = ScheduledTask(
                id="system_daily_memory",
                name="每日记忆整理",
                trigger_type=TriggerType.CRON,
                trigger_config={"cron": "0 3 * * *"},
                action="system:daily_memory",
                prompt="执行每日记忆整理：整理当天对话历史，提取精华记忆，刷新 MEMORY.md",
                description="整理当天对话，提取记忆，刷新 MEMORY.md",
                task_type=TaskType.TASK,
                enabled=True,
                deletable=False,  # 系统任务不允许删除
            )
            await self.task_scheduler.add_task(memory_task)
            logger.info("Registered system task: daily_memory (03:00)")
        else:
            # 兼容迁移：历史版本可能漏存 action，导致不会走 _execute_system_task
            existing_task = self.task_scheduler.get_task("system_daily_memory")
            if existing_task:
                changed = False
                if existing_task.deletable:
                    existing_task.deletable = False
                    changed = True
                if not getattr(existing_task, "action", None):
                    existing_task.action = "system:daily_memory"
                    changed = True
                if changed:
                    self.task_scheduler._save_tasks()

        # 任务 2: 每日系统自检（凌晨 4:00）
        if "system_daily_selfcheck" not in existing_ids:
            selfcheck_task = ScheduledTask(
                id="system_daily_selfcheck",
                name="每日系统自检",
                trigger_type=TriggerType.CRON,
                trigger_config={"cron": "0 4 * * *"},
                action="system:daily_selfcheck",
                prompt="执行每日系统自检：分析 ERROR 日志，尝试修复工具问题，生成报告",
                description="分析 ERROR 日志、尝试修复工具问题、生成报告",
                task_type=TaskType.TASK,
                enabled=True,
                deletable=False,  # 系统任务不允许删除
            )
            await self.task_scheduler.add_task(selfcheck_task)
            logger.info("Registered system task: daily_selfcheck (04:00)")
        else:
            # 兼容迁移：历史版本可能漏存 action，导致不会走 _execute_system_task
            existing_task = self.task_scheduler.get_task("system_daily_selfcheck")
            if existing_task:
                changed = False
                if existing_task.deletable:
                    existing_task.deletable = False
                    changed = True
                if not getattr(existing_task, "action", None):
                    existing_task.action = "system:daily_selfcheck"
                    changed = True
                if changed:
                    self.task_scheduler._save_tasks()

    def _build_system_prompt(
        self, base_prompt: str, task_description: str = "", use_compiled: bool = False,
        session_type: str = "cli",
    ) -> str:
        """
        构建系统提示词 (动态生成，包含技能清单、MCP 清单和相关记忆)

        遵循规范的渐进式披露:
        - Agent Skills: name + description 在系统提示中
        - MCP: server + tool name + description 在系统提示中
        - Memory: 相关记忆按需注入
        - Tools: 从 BASE_TOOLS 动态生成
        - User Profile: 首次引导或日常询问

        Args:
            base_prompt: 基础提示词 (身份信息，use_compiled=True 时忽略)
            task_description: 任务描述 (用于检索相关记忆)
            use_compiled: 是否使用编译管线 (v2)，降低约 55% token 消耗

        Returns:
            完整的系统提示词
        """
        # 使用编译管线 (v2) - 降低 token 消耗（同步版本，启动时使用）
        if use_compiled:
            return self._build_system_prompt_compiled_sync(task_description, session_type=session_type)

        # 技能清单 (Agent Skills 规范) - 每次动态生成，确保新创建的技能被包含
        skill_catalog = self.skill_catalog.generate_catalog()

        # MCP 清单 (Model Context Protocol 规范)
        mcp_catalog = getattr(self, "_mcp_catalog_text", "")

        # 相关记忆 (按任务相关性注入)
        memory_context = self.memory_manager.get_injection_context(task_description)

        # 动态生成工具列表
        tools_text = self._generate_tools_text()

        # 系统环境信息
        import os
        import platform

        system_info = f"""## 运行环境

- **操作系统**: {platform.system()} {platform.release()}
- **当前工作目录**: {os.getcwd()}
- **临时目录**:
  - Windows: 使用当前目录下的 `data/temp/` 或 `%TEMP%`
  - Linux/macOS: 使用当前目录下的 `data/temp/` 或 `/tmp`
- **建议**: 创建临时文件时优先使用 `data/temp/` 目录（相对于当前工作目录）

## ⚠️ 重要：运行时状态不持久化

**服务重启后以下状态会丢失，不能依赖会话历史记录判断当前状态：**

| 状态 | 重启后 | 正确做法 |
|------|--------|----------|
| 浏览器 | **已关闭** | 必须先调用 `browser_open` 确认状态，不能假设已打开 |
| 变量/内存数据 | **已清空** | 通过工具重新获取，不能依赖历史 |
| 临时文件 | **可能清除** | 重新检查文件是否存在 |
| 网络连接 | **已断开** | 需要重新建立连接 |

**⚠️ 会话历史中的"成功打开浏览器"等记录只是历史，不代表当前状态！每次执行任务必须通过工具调用获取实时状态。**
"""

        # 工具使用指南
        tools_guide = """
## 工具体系说明

你有三类工具可以使用，**它们都是工具，都可以调用**：

### 1. 系统工具（渐进式披露）

系统内置的核心工具，采用渐进式披露：

| 步骤 | 操作 | 说明 |
|-----|-----|-----|
| 1 | 查看上方 "Available System Tools" 清单 | 了解有哪些工具可用 |
| 2 | `get_tool_info(tool_name)` | 获取工具的完整参数定义 |
| 3 | 直接调用工具 | 如 `read_file(path="...")` |

**工具类别**：文件系统、浏览器、记忆、定时任务、用户档案等

### 2. Skills 技能（渐进式披露）

可扩展的能力模块，采用渐进式披露：

| 步骤 | 操作 | 说明 |
|-----|-----|-----|
| 1 | 查看上方 "Available Skills" 清单 | 了解有哪些技能可用 |
| 2 | `get_skill_info(skill_name)` | 获取技能的详细使用说明 |
| 3 | `run_skill_script(skill_name, script_name)` | 执行技能提供的脚本 |

**特点**：
- `install_skill` - 从 URL/Git 安装新技能
- `load_skill` - 加载新创建的技能（用于 skill-creator 创建后）
- `reload_skill` - 重新加载已修改的技能
- 缺少工具时，使用 `skill-creator` 技能创建新技能

### 3. MCP 外部服务（全量暴露）

MCP (Model Context Protocol) 连接外部服务，**工具定义已全量展示**：

| 步骤 | 操作 | 说明 |
|-----|-----|-----|
| 1 | 查看上方 "MCP Servers" 清单 | 包含完整的工具定义和参数 |
| 2 | `call_mcp_tool(server, tool_name, arguments)` | 直接调用 |

**特点**：连接数据库、API 等外部服务

### 工具选择原则

1. **系统工具**：文件操作、命令执行、浏览器、记忆等基础能力
2. **Skills**：复杂任务、特定领域能力、可复用的工作流
3. **MCP**：外部服务集成（数据库、第三方 API）
4. **找不到工具？使用 `skill-creator` 技能创建一个！**

**记住：这三类都是工具，都可以调用，不要说"我没有这个能力"！**
"""

        return f"""{base_prompt}

{system_info}
{skill_catalog}
{mcp_catalog}
{memory_context}

{tools_text}

{tools_guide}

## 核心原则 (最高优先级!!!)

### 第一铁律：任务型请求必须使用工具

**⚠️ 先判断请求类型，再决定是否调用工具！**

| 请求类型 | 示例 | 处理方式 |
|---------|------|----------|
| **任务型** | "打开百度"、"提醒我开会"、"查天气" | ✅ **必须调用工具** |
| **对话型** | "你好"、"什么是机器学习"、"谢谢" | ✅ 可直接回复 |

**任务型请求的正确做法**：
| 场景 | ❌ 错误 | ✅ 正确 |
|------|--------|--------|
| 用户要提醒 | "好的我会提醒你" | 调用 schedule_task |
| 用户要查信息 | 凭记忆回答 | 调用 web_search |
| 用户要操作文件 | 描述怎么操作 | 调用 write_file/read_file |

**对话型请求**：直接回复即可，不需要调用工具。

### 第二铁律：没有工具就创造工具

**绝不说"我没有这个能力"！立即行动：**

**方式一：临时脚本（一次性任务）**
```
# 根据运行环境信息中的当前工作目录和临时目录建议
write_file("data/temp/task.py", "脚本内容")
run_shell("python data/temp/task.py")
```

**方式二：搜索安装（有现成的）**
```
search_github → install_skill → 使用
```

**方式三：创建技能（需要复用）**
```
使用 skill-creator 技能 → 创建 SKILL.md → 保存到 skills/<name>/ → 调用 load_skill 加载 → 使用
```

**方式四：修改已有技能**
```
修改 skills/<name>/SKILL.md → 调用 reload_skill 重新加载 → 修改立即生效
```

**从"不会"到"会"只需要几分钟！**

### 第三铁律：问题自己解决

**遇到问题，默认自己解决，不要甩给用户：**

- 报错了？自己读日志、分析、修复
- 缺信息？自己用工具查找
- 不确定？先尝试，失败了再换方法
- **只有完全无法解决才询问用户**

### 第四铁律：永不放弃

- 第一次失败？换个方法再试
- 第二次失败？再换一个
- 工具不够用？创建新工具
- 信息不完整？主动去查找

**禁止说"我做不到"、"这超出了我的能力"、"请你自己..."！**
**正确做法：分析问题 → 搜索方案 → 获取工具 → 执行任务 → 验证结果**

---

## 重要提示

### 深度思考模式 (Thinking Mode)

**默认启用 thinking 模式**，这样可以保证回答质量。

如果遇到非常简单的任务（如：简单问候、快速提醒），可以调用 `enable_thinking(enabled=false)` 临时关闭以加快响应。
大多数情况下保持默认启用即可，不需要主动管理。

### Plan 模式（复杂任务必须使用！）

**当任务需要超过 2 步完成时，先调用 create_plan 创建计划：**

**触发条件**：
- 用户请求中有"然后"、"接着"、"之后"等词
- 涉及多个工具协作（如：打开网页 + 搜索 + 截图 + 发送）
- 需要依次完成多个操作

**执行流程**：
1. `create_plan` → 创建计划，通知用户
2. 执行步骤 → `update_plan_step` 更新状态
3. 重复 2 直到所有步骤完成
4. `complete_plan` → 生成总结

**示例**：
用户："打开百度搜索天气并截图发我"
→ create_plan → browser_task("打开百度搜索天气并截图") + update_plan_step → deliver_artifacts + complete_plan

### 工具调用
- 工具直接使用工具名调用，不需要任何前缀
- **提醒/定时任务必须使用 schedule_task 工具**，不要只是回复"好的"
- 当用户说"X分钟后提醒我"时，立即调用 schedule_task 创建任务

### 主动沟通

- 对话型请求：直接回答即可，不需要固定的“收到/开始处理”确认语。
- 任务型请求：在关键节点给出简短进度与结果（避免刷屏）。
- 如涉及附件交付：使用 `deliver_artifacts` 并以回执为证据（不要空口宣称“已发送/已交付”）。

### 定时任务/提醒 (极其重要!!!)

**当用户请求设置提醒、定时任务时，你必须立即调用 schedule_task 工具！**
**禁止只回复"好的，我会提醒你"这样的文字！那样任务不会被创建！**
**只有调用了 schedule_task 工具，任务才会真正被调度执行！**

**⚠️ 任务类型判断 (task_type) - 这是最重要的决策！**

**默认使用 reminder！除非明确需要AI执行操作才用 task！**

✅ **reminder** (90%的情况都是这个!):
- 只需要到时间发一条消息提醒用户
- 例子: "提醒我喝水"、"叫我起床"、"站立提醒"、"开会提醒"、"午睡提醒"
- 特点: 用户说"提醒我xxx"、"叫我xxx"、"通知我xxx"

❌ **task** (仅10%的特殊情况):
- 需要AI在触发时执行查询、操作、截图等
- 例子: "查天气告诉我"、"截图发给我"、"执行脚本"、"帮我发消息给别人"
- 特点: 用户说"帮我做xxx"、"执行xxx"、"查询xxx"

**创建任务后，必须明确告知用户**:
- reminder: "好的，到时间我会提醒你：[提醒内容]" (只发一条消息)
- task: "好的，到时间我会自动执行：[任务内容]" (AI会运行并汇报结果)

调用 schedule_task 时的参数:

1. **简单提醒** (task_type="reminder"):
   - name: "喝水提醒"
   - description: "提醒用户喝水"
   - task_type: "reminder"
   - trigger_type: "once"
   - trigger_config: {{"run_at": "2026-02-01 10:00"}}
   - reminder_message: "⏰ 该喝水啦！记得保持水分摄入哦~"

2. **复杂任务** (task_type="task"):
   - name: "每日天气查询"
   - description: "查询今日天气并告知用户"
   - task_type: "task"
   - trigger_type: "cron"
   - trigger_config: {{"cron": "0 8 * * *"}}
   - prompt: "查询今天的天气，并以友好的方式告诉用户"

**触发类型**:
- once: 一次性，trigger_config 包含 run_at
- interval: 间隔执行，trigger_config 包含 interval_minutes
- cron: 定时执行，trigger_config 包含 cron 表达式

**再次强调：收到提醒请求时，第一反应就是调用 schedule_task 工具！**

### 系统已内置功能 (不需要自己实现!)

以下功能**系统已经内置**，当用户提到时，不要尝试"开发"或"实现"，而是直接使用：

1. **语音转文字** - 系统**已自动处理**语音识别！
   - 用户发送的语音消息会被系统**自动**转写为文字（通过本地 Whisper medium 模型）
   - 你收到的消息中，语音内容已经被转写为文字了
   - 如果看到 `[语音: X秒]` 但没有文字内容，说明自动识别失败
   - **只有**在自动识别失败时（如看到"语音识别失败"提示），才需要手动处理语音文件
   - ⚠️ **重要**：不要每次收到语音消息都调用语音识别工具！系统已经自动处理了！

2. **图片理解** - 用户发送的图片会自动传递给你进行多模态理解
   - 你可以直接"看到"用户发送的图片并描述或分析

3. **Telegram 配对** - 已内置配对验证机制

**当用户说"帮我实现语音转文字"时**：
- ❌ 不要开始写代码、安装 whisper、配置 ffmpeg
- ❌ 不要调用语音识别技能或工具去处理
- ✅ 告诉用户"语音转文字已内置并自动运行，请发送语音测试"

**语音消息处理流程**：
1. 用户发送语音 → 2. 系统自动下载并用 Whisper 转文字 → 3. 你收到的是转写后的文字
4. 只有当你看到"[语音识别失败]"或"自动识别失败"时，才需要用 get_voice_file 工具获取文件路径并手动处理

### 记忆管理 (非常重要!)
**主动使用记忆功能**，在以下情况必须调用 add_memory:
- 学到新东西时 → 记录为 FACT
- 发现用户偏好时 → 记录为 PREFERENCE
- 找到有效解决方案时 → 记录为 SKILL
- 遇到错误教训时 → 记录为 ERROR
- 发现重要规则时 → 记录为 RULE

**记忆时机**:
1. 任务完成后，回顾学到了什么
2. 用户明确表达偏好时
3. 解决了一个难题时
4. 犯错后找到正确方法时

### 记忆使用原则 (重要!)
**上下文优先**：当前对话内容永远优先于记忆中的信息。

**不要让记忆主导对话**：
- ❌ 错误：用户说"你好" → 回复"你好！关于之前 Moltbook 技能的事情，你想怎么处理？"
- ✅ 正确：用户说"你好" → 回复"你好！有什么可以帮你的？"（记忆中的事情等用户主动提起或真正相关时再说）

**记忆提及方式**：
- 如果记忆与当前话题高度相关，可以**简短**提一句，但不要作为回复的主体
- 不要让用户感觉你在"接着上次说"——每次对话都是新鲜的开始
- 例如：处理完用户当前请求后，可以在结尾轻轻带一句"对了，之前xxx的事情需要我继续处理吗？"

### 诚实原则 (极其重要!!!)
**绝对禁止编造不存在的功能或进度！**

❌ **严禁以下行为**：
- 声称"正在运行"、"已完成"但实际没有创建任何文件/脚本
- 在回复中贴一段代码假装在执行，但实际没有调用任何工具
- 声称"每X秒监控"但没有创建对应的定时任务
- 承诺"5分钟内完成"但根本没有开始执行

✅ **正确做法**：
- 如果需要创建脚本，必须调用 write_file 工具实际写入
- 如果需要定时任务，必须调用 schedule_task 工具实际创建
- 如果做不到，诚实告知"这个功能我目前无法实现，原因是..."
- 如果需要时间开发，先实际开发完成，再告诉用户结果

**用户信任比看起来厉害更重要！宁可说"我做不到"也不要骗人！**
"""

    def _build_system_prompt_compiled_sync(self, task_description: str = "", session_type: str = "cli") -> str:
        """同步版本：启动时构建初始系统提示词（此时事件循环可能未就绪）"""
        # 委托给 PromptAssembler
        return self.prompt_assembler._build_compiled_sync(
            task_description, session_type=session_type
        )

    async def _build_system_prompt_compiled(self, task_description: str = "", session_type: str = "cli") -> str:
        """
        使用编译管线构建系统提示词 (v2)

        Token 消耗降低约 55%，从 ~6300 降到 ~2800。
        异步版本：预先异步执行向量搜索，避免阻塞事件循环。

        Args:
            task_description: 任务描述 (用于检索相关记忆)
            session_type: 会话类型 "cli" 或 "im"

        Returns:
            编译后的系统提示词
        """
        # 委托给 PromptAssembler
        return await self.prompt_assembler.build_system_prompt_compiled(
            task_description, session_type=session_type
        )

    def _generate_tools_text(self) -> str:
        """
        从 BASE_TOOLS 动态生成工具列表文本

        按类别分组显示，包含重要参数说明
        """
        # 工具分类
        categories = {
            "File System": ["run_shell", "write_file", "read_file", "list_directory"],
            "Skills Management": [
                "list_skills",
                "get_skill_info",
                "run_skill_script",
                "get_skill_reference",
                "install_skill",
                "load_skill",
                "reload_skill",
            ],
            "Memory Management": ["add_memory", "search_memory", "get_memory_stats"],
            "Browser Automation": [
                "browser_task",
                "browser_open",
                "browser_navigate",
                "browser_get_content",
                "browser_screenshot",
                "browser_close",
            ],
            "Scheduled Tasks": [
                "schedule_task",
                "list_scheduled_tasks",
                "cancel_scheduled_task",
                "trigger_scheduled_task",
            ],
        }

        # 构建工具名到完整定义的映射
        tool_map = {t["name"]: t for t in self._tools}

        lines = ["## Available Tools"]

        for category, tool_names in categories.items():
            # 过滤出存在的工具
            existing_tools = [(name, tool_map[name]) for name in tool_names if name in tool_map]

            if existing_tools:
                lines.append(f"\n### {category}")
                for name, tool_def in existing_tools:
                    desc = tool_def.get("description", "")
                    # 不再截断描述，完整显示
                    lines.append(f"- **{name}**: {desc}")

                    # 显示重要参数（可选）
                    schema = tool_def.get("input_schema", {})
                    schema.get("properties", {})
                    schema.get("required", [])

                    # 注意：工具的完整参数定义通过 tools=self._tools 传递给 LLM API
                    # 这里只在 system prompt 中简要列出，避免过长

        # 添加未分类的工具
        categorized = set()
        for names in categories.values():
            categorized.update(names)

        uncategorized = [(t["name"], t) for t in self._tools if t["name"] not in categorized]
        if uncategorized:
            lines.append("\n### Other Tools")
            for name, tool_def in uncategorized:
                desc = tool_def.get("description", "")
                lines.append(f"- **{name}**: {desc}")

        return "\n".join(lines)

    async def _cancellable_await(self, coro, cancel_event: asyncio.Event | None = None):
        """将任意协程包装为可被 cancel_event 立即中断的操作。

        如果 cancel_event 先于 coro 完成，抛出 UserCancelledError。
        如果 cancel_event 为 None 或任务无活跃 task，直接 await coro。
        """
        if cancel_event is None:
            if self.agent_state and self.agent_state.current_task:
                cancel_event = self.agent_state.current_task.cancel_event
            else:
                return await coro

        task = asyncio.create_task(coro) if not isinstance(coro, asyncio.Task) else coro
        cancel_waiter = asyncio.create_task(cancel_event.wait())

        done, pending = await asyncio.wait(
            {task, cancel_waiter},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for t in pending:
            t.cancel()
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass

        if task in done:
            return task.result()
        raise UserCancelledError(
            reason=self._cancel_reason or "用户请求停止",
            source="cancellable_await",
        )

    async def chat(self, message: str, session_id: str | None = None) -> str:
        """
        对话接口 - 委托给 chat_with_session() 复用完整处理链路

        内部创建/复用一个持久的 CLI Session，使 CLI 获得与 IM 通道一致的能力：
        Prompt Compiler、高级循环检测、Task Monitor、记忆检索、上下文压缩等。

        Args:
            message: 用户消息
            session_id: 可选的会话标识（用于日志）

        Returns:
            Agent 响应
        """
        if not self._initialized:
            await self.initialize()

        # 懒初始化 CLI Session（在 Agent 生命周期内持久存在）
        if not hasattr(self, '_cli_session') or self._cli_session is None:
            from ..sessions.session import Session
            self._cli_session = Session.create(
                channel="cli", chat_id="cli", user_id="user"
            )

        # 模拟 Gateway 的消息管理流程：先记录用户消息到 Session
        self._cli_session.add_message("user", message)
        session_messages = self._cli_session.context.get_messages()

        # 委托给统一的 chat_with_session
        response = await self.chat_with_session(
            message=message,
            session_messages=session_messages,
            session_id=session_id or self._cli_session.id,
            session=self._cli_session,
            gateway=None,  # CLI 无 Gateway
        )

        # 记录 Assistant 响应到 Session
        self._cli_session.add_message("assistant", response)

        # 同步更新旧属性（保持向后兼容：conversation_history 属性、/status 命令等依赖）
        self._conversation_history.append(
            {"role": "user", "content": message, "timestamp": datetime.now().isoformat()}
        )
        self._conversation_history.append(
            {"role": "assistant", "content": response, "timestamp": datetime.now().isoformat()}
        )

        return response

    # ==================== 会话流水线: 共享准备 / 收尾 / 入口 ====================

    async def _prepare_session_context(
        self,
        message: str,
        session_messages: list[dict],
        session_id: str,
        session: Any,
        gateway: Any,
        conversation_id: str,
        *,
        attachments: list | None = None,
    ) -> tuple[list[dict], str, "TaskMonitor", str, Any]:
        return await prepare_session_context(
            self,
            message,
            session_messages,
            session_id,
            session,
            gateway,
            conversation_id,
            attachments=attachments,
        )

    async def _finalize_session(
        self,
        response_text: str,
        session: Any,
        session_id: str,
        task_monitor: "TaskMonitor",
    ) -> None:
        await finalize_session(self, response_text, session, session_id, task_monitor)

    def _cleanup_session_state(self, im_tokens: Any) -> None:
        cleanup_session_state(self, im_tokens)

    async def chat_with_session(
        self,
        message: str,
        session_messages: list[dict],
        session_id: str = "",
        session: Any = None,
        gateway: Any = None,
        *,
        thinking_mode: str | None = None,
        thinking_depth: str | None = None,
    ) -> str:
        """
        使用外部 Session 历史进行对话（用于 IM / CLI 通道）。

        走完整的 Agent 流水线：Prompt Compiler → 上下文构建 → ReasoningEngine.run()。
        与 chat_with_session_stream() 共享 _prepare_session_context / _finalize_session。

        Args:
            message: 用户消息
            session_messages: Session 的对话历史
            session_id: 会话 ID
            session: Session 对象
            gateway: MessageGateway 对象
            thinking_mode: 思考模式覆盖 ('auto'/'on'/'off'/None)
            thinking_depth: 思考深度 ('low'/'medium'/'high'/None)

        Returns:
            Agent 响应
        """
        # === 性能追踪：开始请求 ===
        from ..infra.performance import get_performance_tracker
        perf = get_performance_tracker()
        perf.start_request(message)

        if not self._initialized:
            await self.initialize()

        # === 停止指令检测 ===
        message_lower = message.strip().lower()
        if message_lower in self.STOP_COMMANDS or message.strip() in self.STOP_COMMANDS:
            self.cancel_current_task(f"用户发送停止指令: {message}", session_id=session_id)
            logger.info(f"[StopTask] User requested to stop (session={session_id}): {message}")
            return "✅ 好的，已停止当前任务。有什么其他需要帮助的吗？"

        # 清理上一轮残留的任务状态（按 session 隔离）
        _prev_task = (
            self.agent_state.get_task_for_session(session_id) if session_id and self.agent_state else None
        ) or (self.agent_state.current_task if self.agent_state else None)
        if _prev_task:
            if _prev_task.cancelled or not _prev_task.is_active:
                logger.info(
                    f"[Session:{session_id}] Resetting stale task "
                    f"(cancelled={_prev_task.cancelled}, status={_prev_task.status.value})"
                )
                self.agent_state.reset_task(session_id=session_id)
            else:
                _prev_task.clear_skip()
                await _prev_task.drain_user_inserts()

        self._current_session_id = session_id
        conversation_id = self._resolve_conversation_id(session, session_id)
        self._current_conversation_id = conversation_id

        im_tokens = None
        try:
            # === 共享准备 ===
            messages, session_type, task_monitor, conversation_id, im_tokens = (
                await self._prepare_session_context(
                    message=message,
                    session_messages=session_messages,
                    session_id=session_id,
                    session=session,
                    gateway=gateway,
                    conversation_id=conversation_id,
                )
            )

            # === 从 session metadata 读取 thinking 偏好（IM 通道使用） ===
            _thinking_mode = thinking_mode
            _thinking_depth = thinking_depth
            if session and (_thinking_mode is None or _thinking_depth is None):
                try:
                    if _thinking_mode is None:
                        _thinking_mode = session.get_metadata("thinking_mode")
                    if _thinking_depth is None:
                        _thinking_depth = session.get_metadata("thinking_depth")
                except Exception:
                    pass

            # === 构建 IM 思维链进度回调 ===
            _progress_cb = None
            if gateway and session:
                async def _im_chain_progress(text: str) -> None:
                    try:
                        await gateway.emit_progress_event(session, text)
                    except Exception:
                        pass
                _progress_cb = _im_chain_progress

            # === 核心推理 (同步返回) ===
            response_text = await self._chat_with_tools_and_context(
                messages, task_monitor=task_monitor, session_type=session_type,
                thinking_mode=_thinking_mode, thinking_depth=_thinking_depth,
                progress_callback=_progress_cb,
            )

            # === flush 残留的 IM 进度消息，确保思维链先于回答到达 ===
            if gateway and session:
                try:
                    await gateway.flush_progress(session)
                except Exception:
                    pass

            # === 共享收尾 ===
            await self._finalize_session(
                response_text=response_text,
                session=session,
                session_id=session_id,
                task_monitor=task_monitor,
            )

            # === 性能追踪：结束请求 ===
            perf.end_request()
            perf.log_summary()

            return response_text
        finally:
            self._cleanup_session_state(im_tokens)

    async def chat_with_session_stream(
        self,
        message: str,
        session_messages: list[dict],
        session_id: str = "",
        session: Any = None,
        gateway: Any = None,
        *,
        plan_mode: bool = False,
        edit_mode: bool = False,
        endpoint_override: str | None = None,
        attachments: list | None = None,
        thinking_mode: str | None = None,
        thinking_depth: str | None = None,
    ):
        """
        流式版 chat_with_session，yield SSE 事件字典。

        走与 chat_with_session() 完全一致的 Agent 流水线（共享准备/收尾），
        中间推理部分使用 reasoning_engine.reason_stream() 实现流式输出。

        用于 Desktop Chat API (/api/chat) 的 SSE 通道。

        Args:
            message: 用户消息
            session_messages: Session 的对话历史
            session_id: 会话 ID
            session: Session 对象
            gateway: MessageGateway 对象
            plan_mode: 是否启用 Plan 模式
            edit_mode: 是否启用 Edit 模式（步骤暂停等待用户确认）
            endpoint_override: 端点覆盖
            attachments: Desktop Chat 附件列表
            thinking_mode: 思考模式覆盖 ('auto'/'on'/'off'/None)
            thinking_depth: 思考深度 ('low'/'medium'/'high'/None)

        Yields:
            SSE 事件字典 {"type": "...", ...}
        """
        if not self._initialized:
            await self.initialize()

        # === 停止指令检测 ===
        message_lower = message.strip().lower()
        if message_lower in self.STOP_COMMANDS or message.strip() in self.STOP_COMMANDS:
            self.cancel_current_task(f"用户发送停止指令: {message}", session_id=session_id)
            logger.info(f"[StopTask] User requested to stop (session={session_id}): {message}")
            yield {"type": "plan_cancelled"}
            yield {"type": "text_delta", "content": "✅ 好的，已停止当前任务。有什么其他需要帮助的吗？"}
            yield {"type": "done"}
            return

        # 清理上一轮残留的任务状态（按 session 隔离）
        _prev_task = (
            self.agent_state.get_task_for_session(session_id) if session_id and self.agent_state else None
        ) or (self.agent_state.current_task if self.agent_state else None)
        if _prev_task:
            if _prev_task.cancelled or not _prev_task.is_active:
                logger.info(
                    f"[Session:{session_id}] Resetting stale task "
                    f"(cancelled={_prev_task.cancelled}, status={_prev_task.status.value})"
                )
                self.agent_state.reset_task(session_id=session_id)
            else:
                _prev_task.clear_skip()
                await _prev_task.drain_user_inserts()

        # 解析 conversation_id
        self._current_session_id = session_id
        conversation_id = self._resolve_conversation_id(session, session_id)
        self._current_conversation_id = conversation_id

        im_tokens = None
        _reply_text = ""
        try:
            # === 共享准备 ===
            messages, session_type, task_monitor, conversation_id, im_tokens = (
                await self._prepare_session_context(
                    message=message,
                    session_messages=session_messages,
                    session_id=session_id,
                    session=session,
                    gateway=gateway,
                    conversation_id=conversation_id,
                    attachments=attachments,
                )
            )

            # === 构建 System Prompt（与 _chat_with_tools_and_context 一致） ===
            task_description = (getattr(self, "_current_task_query", "") or "").strip()
            if not task_description:
                task_description = self._get_last_user_request(messages).strip()

            system_prompt = await self._build_system_prompt_compiled(
                task_description=task_description,
                session_type=session_type,
            )

            # 注入 TaskDefinition
            task_def = (getattr(self, "_current_task_definition", "") or "").strip()
            if task_def:
                system_prompt += f"\n\n## Developer: TaskDefinition\n{task_def}\n"

            base_system_prompt = system_prompt

            # === 从 session metadata 读取 thinking 偏好（IM 通道使用） ===
            _thinking_mode = thinking_mode
            _thinking_depth = thinking_depth
            if session and (_thinking_mode is None or _thinking_depth is None):
                try:
                    if _thinking_mode is None:
                        _thinking_mode = session.get_metadata("thinking_mode")
                    if _thinking_depth is None:
                        _thinking_depth = session.get_metadata("thinking_depth")
                except Exception:
                    pass

            # === 适配 TaskMonitor 为 Callbacks (解耦准备) ===
            def _on_model_switch(old_model: str, new_model: str) -> None:
                if task_monitor:
                    task_monitor.record_model_switch(old_model, new_model)

            def _on_llm_error(error: Exception) -> str | tuple[str, str] | None:
                if task_monitor:
                    return task_monitor.record_llm_error(error)
                return None

            def _check_model_switch() -> str | None:
                if task_monitor and hasattr(task_monitor, "check_model_switch_needed"):
                    return task_monitor.check_model_switch_needed()
                return None

            def _on_iteration_start(iteration: int, model: str) -> None:
                if task_monitor:
                    task_monitor.begin_iteration(iteration, model)

            def _on_iteration_end(result_text: str) -> None:
                if task_monitor:
                    task_monitor.end_iteration(result_text)

            def _on_retry_reset() -> None:
                if task_monitor:
                    task_monitor.reset_retry_count()

            def _on_tool_start(tool_name: str, tool_input: dict) -> None:
                if task_monitor:
                    task_monitor.begin_tool_call(tool_name, tool_input)

            def _on_tool_complete(tool_name: str, tool_input: dict, result: str, success: bool, duration_ms: int) -> None:
                if task_monitor:
                    task_monitor.record_tool_call(tool_name, tool_input, result, success=success, duration_ms=duration_ms)

            # === 核心推理 (流式) ===
            async for event in self.reasoning_engine.reason_stream(
                messages=messages,
                tools=self._tools,
                system_prompt=system_prompt,
                base_system_prompt=base_system_prompt,
                task_description=task_description,
                task_monitor=None,  # 显式传递 None，强制使用 callbacks
                session_type=session_type,
                plan_mode=plan_mode,
                edit_mode=edit_mode,
                endpoint_override=endpoint_override,
                conversation_id=conversation_id,
                thinking_mode=_thinking_mode,
                thinking_depth=_thinking_depth,
                # Callbacks
                on_model_switch=_on_model_switch,
                on_llm_error=_on_llm_error,
                check_model_switch=_check_model_switch,
                on_iteration_start=_on_iteration_start,
                on_iteration_end=_on_iteration_end,
                on_retry_reset=_on_retry_reset,
                on_tool_start=_on_tool_start,
                on_tool_complete=_on_tool_complete,
            ):
                # 收集回复文本（用于 session 保存 & memory）
                if event.get("type") == "text_delta":
                    _reply_text += event.get("content", "")
                yield event

            # === 共享收尾 ===
            if _reply_text:
                await self._finalize_session(
                    response_text=_reply_text,
                    session=session,
                    session_id=session_id,
                    task_monitor=task_monitor,
                )

        except Exception as e:
            logger.error(f"chat_with_session_stream error: {e}", exc_info=True)
            yield {"type": "error", "message": str(e)[:500]}
            yield {"type": "done"}
        finally:
            self._cleanup_session_state(im_tokens)

    def _resolve_conversation_id(self, session: Any, session_id: str) -> str:
        return resolve_conversation_id(self, session, session_id)

    def _build_chain_summary(self, react_trace: list[dict]) -> list[dict] | None:
        """从 ReAct trace 构建思维链摘要（委托到 RetrospectManager）"""
        return self.retrospect_manager.build_chain_summary(react_trace)

    async def _compile_prompt(self, user_message: str) -> tuple[str, str]:
        """两段式 Prompt 第一阶段（委托到 PromptAssembler）"""
        return await self.prompt_assembler.compile_prompt(user_message)

    def _summarize_compiler_output(self, compiler_output: str, max_chars: int = 600) -> str:
        """将 Compiler 输出压缩为短摘要（委托到 PromptAssembler）"""
        return self.prompt_assembler.summarize_compiler_output(compiler_output, max_chars)

    async def _do_task_retrospect(self, task_monitor: TaskMonitor) -> str:
        """执行任务复盘分析（委托到 RetrospectManager）"""
        return await self.retrospect_manager.do_task_retrospect(task_monitor)

    async def _do_task_retrospect_background(
        self, task_monitor: TaskMonitor, session_id: str
    ) -> None:
        """后台执行任务复盘分析（委托到 RetrospectManager）"""
        await self.retrospect_manager.do_task_retrospect_background(task_monitor, session_id)

    def _should_compile_prompt(self, message: str) -> bool:
        """判断是否需要编译 Prompt（委托到 PromptAssembler）"""
        return self.prompt_assembler.should_compile_prompt(message)

    def _get_last_user_request(self, messages: list[dict]) -> str:
        """获取最后一条用户请求（委托到 PromptAssembler）"""
        return self.prompt_assembler.get_last_user_request(messages)

    async def _verify_task_completion(
        self,
        user_request: str,
        assistant_response: str,
        executed_tools: list[str],
        delivery_receipts: list[dict] | None = None,
    ) -> bool:
        """
        任务完成度复核

        让 LLM 判断当前响应是否真正完成了用户的意图，
        而不是仅仅返回了中间状态的文本。

        Args:
            user_request: 用户原始请求
            assistant_response: 助手当前响应
            executed_tools: 已执行的工具列表

        Returns:
            True 如果任务已完成，False 如果需要继续执行
        """
        delivery_receipts = delivery_receipts or []

        # === Quick completion check (evidence-based) ===
        # 交付型任务：必须以 deliver_artifacts 的成功回执作为“已交付”证据，而不是仅凭工具名。
        if "deliver_artifacts" in (executed_tools or []):
            delivered = [r for r in delivery_receipts if r.get("status") == "delivered"]
            if delivered:
                logger.info(
                    f"[TaskVerify] deliver_artifacts delivered={len(delivered)}, marking as completed"
                )
                return True

        # Plan 明确完成：允许快速完成（避免卡在 verify）
        if "complete_plan" in (executed_tools or []):
            logger.info("[TaskVerify] complete_plan executed, marking as completed")
            return True

        # 如果响应宣称“已发送/已交付”，但没有任何交付证据，默认判定未完成（避免空口刷屏）
        if any(
            k in (assistant_response or "") for k in ("已发送", "已交付", "已发给你", "已发给您")
        ) and not delivery_receipts and "deliver_artifacts" not in (executed_tools or []):
            logger.info(
                "[TaskVerify] delivery claim without receipts/tools, marking as INCOMPLETE"
            )
            return False

        # === Plan 步骤检查：如果有活跃 Plan 且有未完成步骤，强制继续执行 ===
        from ..tools.handlers.plan import get_plan_handler_for_session, has_active_plan

        conversation_id = getattr(self, "_current_conversation_id", None) or getattr(
            self, "_current_session_id", None
        )
        if conversation_id and has_active_plan(conversation_id):
            handler = get_plan_handler_for_session(conversation_id)
            plan = handler.get_plan_for(conversation_id) if handler else None
            if plan:
                steps = plan.get("steps", [])
                pending = [s for s in steps if s.get("status") in ("pending", "in_progress")]

                if pending:
                    pending_ids = [s.get("id", "?") for s in pending[:3]]
                    logger.info(
                        f"[TaskVerify] Plan has {len(pending)} pending steps: {pending_ids}, forcing continue"
                    )
                    return False

                if plan.get("status") != "completed":
                    logger.info(
                        "[TaskVerify] All plan steps done but plan not formally completed, proceeding to LLM verification"
                    )
                    # 继续执行 LLM 验证，不强制返回 False

        # 依赖 LLM 进行判断
        verify_prompt = f"""请判断以下交互是否已经**完成**用户的意图。

## 用户消息
{user_request[:2000]}

## 助手响应
{assistant_response[:4000]}

## 已执行的工具
{", ".join(executed_tools) if executed_tools else "无"}

## 附件交付回执（如有）
{delivery_receipts if delivery_receipts else "无"}

## 判断标准

### 非任务类消息（直接判 COMPLETED）
- 如果用户消息是**闲聊/问候**（如"在吗""你好""在不在""嗨""干嘛呢"），助手已礼貌回复 → **COMPLETED**
- 如果用户消息是**简单确认/反馈**（如"好的""收到""嗯""哦"），助手已简短回应 → **COMPLETED**
- 如果用户消息是**简单问答**（如"几点了""天气怎么样"），助手已给出回答 → **COMPLETED**

### 任务类消息
- 如果已执行 write_file 工具，说明文件已保存，保存任务完成
- 如果已执行 browser_task/browser_navigate 等浏览器工具，说明浏览器操作已执行
- 工具执行成功即表示该操作完成，不要求响应文本中包含文件内容
- 如果响应只是说"现在开始..."、"让我..."且没有工具执行，说明任务还在进行中
- 如果响应包含明确的操作确认（如"已完成"、"已发送"、"已保存"），任务完成

## 回答要求
请用以下格式回答：
STATUS: COMPLETED 或 INCOMPLETE
EVIDENCE: 完成的证据（如有）
MISSING: 缺失的内容（如有）
NEXT: 建议的下一步（如有）"""

        try:
            response = await self.brain.think(
                prompt=verify_prompt,
                system="你是一个任务完成度判断助手。请分析任务是否完成，并说明证据和缺失项。",
            )

            result = response.content.strip().upper() if response.content else ""
            # 建议 33: 改进的完成度判断
            is_completed = "STATUS: COMPLETED" in result or (
                "COMPLETED" in result and "INCOMPLETE" not in result
            )

            logger.info(
                f"[TaskVerify] user_request={user_request[:50]}... response={assistant_response[:50]}... result={result} -> {is_completed}"
            )
            return is_completed

        except Exception as e:
            logger.warning(f"[TaskVerify] Failed to verify: {e}, assuming INCOMPLETE")
            return False  # 验证失败时不要默认完成，交由上层计数器做兜底退出

    async def _cancellable_llm_call(self, cancel_event: asyncio.Event, **kwargs) -> Any:
        """将 LLM 调用包装为可取消的 asyncio.Task，配合 cancel_event 竞速。

        当 cancel_event 先于 LLM 返回被 set() 时，抛出 UserCancelledError。
        """
        logger.info(f"[CancellableLLM] 发起可取消 LLM 调用, cancel_event.is_set={cancel_event.is_set()}")
        _tt = set_tracking_context(TokenTrackingContext(
            operation_type="chat",
            session_id=kwargs.get("conversation_id", ""),
            channel="cli",
        ))
        try:
            llm_task = asyncio.create_task(
                self.brain.messages_create_async(**kwargs)
            )
            cancel_waiter = asyncio.create_task(cancel_event.wait())

            done, pending = await asyncio.wait(
                {llm_task, cancel_waiter},
                return_when=asyncio.FIRST_COMPLETED,
            )

            for t in pending:
                t.cancel()
                try:
                    await t
                except (asyncio.CancelledError, Exception):
                    pass

            if llm_task in done:
                logger.info("[CancellableLLM] LLM 调用先完成，正常返回")
                return llm_task.result()
            else:
                reason = self._cancel_reason or "用户请求停止"
                logger.info(f"[CancellableLLM] cancel_event 先触发，抛出 UserCancelledError: {reason!r}")
                raise UserCancelledError(
                    reason=reason,
                    source="llm_call",
                )
        finally:
            reset_tracking_context(_tt)

    async def _handle_cancel_farewell(
        self,
        working_messages: list[dict],
        system_prompt: str,
        current_model: str,
    ) -> str:
        """取消后注入中断上下文，发起轻量 LLM 调用让模型自然收尾。

        将「用户中断」作为特殊消息注入上下文，让 LLM 知晓并做出合理收尾，
        而不是粗暴返回固定文本。LLM 的收尾回复和中断事件都会被记录到持久上下文中。

        Args:
            working_messages: 当前的工作消息列表（会被修改）
            system_prompt: 当前的系统提示词
            current_model: 当前使用的模型

        Returns:
            LLM 生成的收尾文本，或超时后的默认文本
        """
        cancel_reason = self._cancel_reason or "用户请求停止"
        default_farewell = "✅ 好的，已停止当前任务。"

        logger.info(
            f"[StopTask][CancelFarewell] 进入收尾流程: cancel_reason={cancel_reason!r}, "
            f"model={current_model}, msg_count={len(working_messages)}"
        )

        cancel_msg = (
            f"[系统通知] 用户发送了停止指令「{cancel_reason}」，"
            "请立即停止当前操作，简要告知用户已停止以及当前进度（1~2 句话即可）。"
            "不要调用任何工具。"
        )
        working_messages.append({"role": "user", "content": cancel_msg})

        farewell_text = default_farewell
        logger.info(
            f"[StopTask][CancelFarewell] 发起 LLM 收尾调用 (timeout=5s), "
            f"working_messages count={len(working_messages)}"
        )
        _tt = set_tracking_context(TokenTrackingContext(
            operation_type="farewell", channel="api",
        ))
        try:
            response = await asyncio.wait_for(
                self.brain.messages_create_async(
                    model=current_model,
                    max_tokens=200,
                    system=system_prompt,
                    tools=[],
                    messages=working_messages,
                ),
                timeout=5.0,
            )
            logger.info(
                f"[StopTask][CancelFarewell] LLM 调用返回, "
                f"content_blocks={len(response.content)}, "
                f"stop_reason={getattr(response, 'stop_reason', 'N/A')}"
            )
            for block in response.content:
                logger.debug(
                    f"[StopTask][CancelFarewell] block type={block.type}, "
                    f"text={getattr(block, 'text', '')[:80]!r}"
                )
                if block.type == "text" and block.text.strip():
                    farewell_text = block.text.strip()
                    break
            logger.info(f"[StopTask][CancelFarewell] LLM farewell 成功: {farewell_text[:120]}")
        except TimeoutError:
            logger.warning("[StopTask][CancelFarewell] LLM farewell 超时 (5s)，使用默认文本")
        except Exception as e:
            logger.error(
                f"[StopTask][CancelFarewell] LLM farewell 失败: "
                f"{type(e).__name__}: {e}，使用默认文本",
                exc_info=True,
            )
        finally:
            reset_tracking_context(_tt)

        self._persist_cancel_to_context(cancel_reason, farewell_text)
        return farewell_text

    def _persist_cancel_to_context(self, cancel_reason: str, farewell_text: str) -> None:
        """将中断事件持久化到 _context.messages 对话历史。

        确保后续对话中 LLM 能看到之前的中断历史。
        """
        try:
            ctx = getattr(self, "_context", None)
            if ctx and hasattr(ctx, "messages"):
                ctx.messages.append({
                    "role": "user",
                    "content": f"[用户中断了上一个任务: {cancel_reason}]",
                })
                ctx.messages.append({
                    "role": "assistant",
                    "content": farewell_text,
                })
                logger.debug(f"[StopTask] Cancel event persisted to context (reason={cancel_reason})")
        except Exception as e:
            logger.warning(f"[StopTask] Failed to persist cancel to context: {e}")

    async def _chat_with_tools_and_context(
        self,
        messages: list[dict],
        use_session_prompt: bool = True,
        task_monitor: TaskMonitor | None = None,
        session_type: str = "cli",
        thinking_mode: str | None = None,
        thinking_depth: str | None = None,
        progress_callback: Any = None,
    ) -> str:
        """
        使用指定的消息上下文进行对话（委托给 ReasoningEngine）

        Phase 2 重构: 保留 system prompt / task_description 的构建逻辑，
        将核心推理循环委托给 self.reasoning_engine.run()。

        Args:
            messages: 对话消息列表
            use_session_prompt: 是否使用 Session 专用的 System Prompt
            task_monitor: 任务监控器
            session_type: 会话类型 ("cli" 或 "im")
            thinking_mode: 思考模式覆盖 ('auto'/'on'/'off'/None)
            thinking_depth: 思考深度 ('low'/'medium'/'high'/None)
            progress_callback: 进度回调 async fn(str) -> None，IM 实时思维链

        Returns:
            最终响应文本
        """
        # === 构建 System Prompt ===
        task_description = (getattr(self, "_current_task_query", "") or "").strip()
        if not task_description:
            task_description = self._get_last_user_request(messages).strip()

        if use_session_prompt:
            system_prompt = await self._build_system_prompt_compiled(
                task_description=task_description,
                session_type=session_type,
            )
        else:
            system_prompt = self._context.system

        # 注入 TaskDefinition
        task_def = (getattr(self, "_current_task_definition", "") or "").strip()
        if task_def:
            system_prompt += f"\n\n## Developer: TaskDefinition\n{task_def}\n"

        base_system_prompt = system_prompt
        conversation_id = getattr(self, "_current_conversation_id", None) or getattr(
            self, "_current_session_id", None
        )

        # === 委托给 RalphLoop ===
        # 1. 准备任务状态
        state = self.reasoning_engine.prepare_task(
            messages,
            task_description=task_description,
            session_type=session_type,
            conversation_id=conversation_id,
        )

        # 2. 配置执行函数
        if session_type == "im":
            base_force_retries = 0
        else:
            base_force_retries = max(0, int(getattr(settings, "force_tool_call_max_retries", 1)))

        async def execute_step(task: TaskState) -> str | None:
            # 动态注入 Plan
            effective_base_prompt = base_system_prompt or system_prompt
            try:
                from ..tools.handlers.plan import get_active_plan_prompt
                if conversation_id:
                    plan_section = get_active_plan_prompt(conversation_id)
                    if plan_section:
                        effective_base_prompt += f"\n\n{plan_section}\n"
            except Exception:
                pass

            # 构造回调适配器 (CORE-008 Decouple TaskMonitor)
            on_model_switch = None
            on_llm_error = None
            check_model_switch = None
            on_iteration_start = None
            on_iteration_end = None
            on_retry_reset = None
            on_tool_start = None
            on_tool_complete = None

            if task_monitor:
                # 1. 模型切换
                def _on_model_switch(new_model: str, reason: str):
                    task_monitor.switch_model(new_model, reason, reset_context=True)
                on_model_switch = _on_model_switch

                # 2. 错误处理
                def _on_llm_error(error: Exception) -> str | tuple[str, str] | None:
                    should_retry = task_monitor.record_error(str(error))
                    if should_retry:
                        return "retry"
                    
                    # 重试耗尽，检查 fallback
                    fallback = getattr(task_monitor, "fallback_model", None)
                    if fallback:
                        return ("switch", fallback)
                    return None
                on_llm_error = _on_llm_error

                # 3. 检查切换
                if hasattr(task_monitor, "check_model_switch_needed"):
                    check_model_switch = task_monitor.check_model_switch_needed

                # 4. 迭代生命周期
                on_iteration_start = task_monitor.begin_iteration
                on_iteration_end = task_monitor.end_iteration
                on_retry_reset = task_monitor.reset_retry_count

                # 5. 工具监控
                if hasattr(task_monitor, "begin_tool_call"):
                    on_tool_start = task_monitor.begin_tool_call
                
                if hasattr(task_monitor, "record_tool_call"):
                    def _on_tool_complete(name: str, input_data: dict, result: str, success: bool, duration: int):
                        task_monitor.record_tool_call(
                            name, input_data, result, success=success, duration_ms=duration
                        )
                    on_tool_complete = _on_tool_complete

            return await self.reasoning_engine.step(
                task,
                tools=self._tools,
                system_prompt=effective_base_prompt,
                task_monitor=task_monitor,
                conversation_id=conversation_id,
                session_type=session_type,
                thinking_mode=thinking_mode,
                thinking_depth=thinking_depth,
                progress_callback=progress_callback,
                iteration=task.iteration,
                base_force_retries=base_force_retries,
                # 注入回调
                on_model_switch=on_model_switch,
                on_llm_error=on_llm_error,
                check_model_switch=check_model_switch,
                on_iteration_start=on_iteration_start,
                on_iteration_end=on_iteration_end,
                on_retry_reset=on_retry_reset,
                on_tool_start=on_tool_start,
                on_tool_complete=on_tool_complete,
            )

        # 3. 运行 Ralph 循环
        result = await self.ralph.run(state, execute_step)
        
        if result.success:
            return result.data
        else:
            return result.error or "Task failed"
    # ==================== 取消状态代理属性（委托到 InterruptManager）====================

    @property
    def _task_cancelled(self) -> bool:
        """统一的取消状态查询（委托到 InterruptManager）"""
        return self.interrupt_manager._task_cancelled

    @property
    def _cancel_reason(self) -> str:
        """统一的取消原因查询（委托到 InterruptManager）"""
        return self.interrupt_manager._cancel_reason

    def set_interrupt_enabled(self, enabled: bool) -> None:
        """设置是否启用中断检查（委托到 InterruptManager）"""
        self._interrupt_enabled = enabled
        self.interrupt_manager.set_interrupt_enabled(enabled)

    def cancel_current_task(self, reason: str = "用户请求停止", session_id: str | None = None) -> None:
        """取消正在执行的任务（委托到 InterruptManager）"""
        self.interrupt_manager.cancel_current_task(reason, session_id)

    def is_stop_command(self, message: str) -> bool:
        """检查消息是否为停止指令（委托到 InterruptManager）"""
        return self.interrupt_manager.is_stop_command(message)

    def is_skip_command(self, message: str) -> bool:
        """检查消息是否为跳过当前步骤指令（委托到 InterruptManager）"""
        return self.interrupt_manager.is_skip_command(message)

    def classify_interrupt(self, message: str) -> str:
        """分类中断消息类型（委托到 InterruptManager）"""
        return self.interrupt_manager.classify_interrupt(message)

    def skip_current_step(self, reason: str = "用户请求跳过当前步骤", session_id: str | None = None) -> bool:
        """跳过当前正在执行的工具/步骤（委托到 InterruptManager）"""
        return self.interrupt_manager.skip_current_step(reason, session_id)

    async def insert_user_message(self, text: str, session_id: str | None = None) -> bool:
        """向当前任务注入用户消息（委托到 InterruptManager）"""
        return await self.interrupt_manager.insert_user_message(text, session_id)

    def confirm_step(
        self,
        step_id: str,
        conversation_id: str | None = None,
        edited_results: list[dict] | None = None,
        action: str = "confirm",
    ) -> bool:
        """确认暂停的步骤（委托到 InterruptManager）"""
        return self.interrupt_manager.confirm_step(step_id, conversation_id, edited_results, action)

    async def execute_task_from_message(self, message: str) -> TaskResult:
        """从消息创建并执行任务"""
        task = Task(
            id=str(uuid.uuid4())[:8],
            description=message,
            session_id=getattr(self, "_current_session_id", None),  # 关联当前会话
            priority=1,
        )
        return await self.execute_task(task)

    async def _execute_tool(self, tool_name: str, tool_input: dict) -> str:
        """
        执行工具调用

        优先使用 handler_registry 执行，不支持的工具使用旧的 if-elif 兜底
        执行后自动附加 WARNING/ERROR 日志到返回结果

        Args:
            tool_name: 工具名称
            tool_input: 工具输入参数

        Returns:
            工具执行结果（包含执行期间的警告/错误日志）
        """
        logger.info(f"Executing tool: {tool_name} with {tool_input}")

        # ============================================
        # Plan 模式强制检查
        # ============================================
        # 如果当前 session 被标记为需要 Plan（compound 任务），
        # 但还没有创建 Plan，则拒绝执行其他工具
        if tool_name != "create_plan":
            from ..tools.handlers.plan import has_active_plan, is_plan_required

            session_id = getattr(self, "_current_session_id", None)
            if session_id and is_plan_required(session_id) and not has_active_plan(session_id):
                return (
                    "⚠️ **这是一个多步骤任务，必须先创建计划！**\n\n"
                    "请先调用 `create_plan` 工具创建任务计划，然后再执行具体操作。\n\n"
                    "示例：\n"
                    "```\n"
                    "create_plan(\n"
                    "  task_summary='写脚本获取时间并显示',\n"
                    "  steps=[\n"
                    "    {id: 'step1', description: '创建Python脚本', tool: 'write_file'},\n"
                    "    {id: 'step2', description: '执行脚本', tool: 'run_shell'},\n"
                    "    {id: 'step3', description: '读取结果', tool: 'read_file'}\n"
                    "  ]\n"
                    ")\n"
                    "```"
                )

        # 导入日志缓存
        from ..logging import get_session_log_buffer

        log_buffer = get_session_log_buffer()

        # 记录执行前的日志数量
        logs_before = log_buffer.get_logs(count=500)
        logs_before_count = len(logs_before)

        try:
            # 优先使用 handler_registry 执行
            if self.handler_registry.has_tool(tool_name):
                result = await self.handler_registry.execute_by_tool(tool_name, tool_input)
            else:
                # 未注册的工具
                return f"❌ 未知工具: {tool_name}。请检查工具名称是否正确。"

            # 获取执行期间产生的新日志（WARNING/ERROR/CRITICAL）
            all_logs = log_buffer.get_logs(count=500)
            new_logs = [
                log
                for log in all_logs[logs_before_count:]
                if log["level"] in ("WARNING", "ERROR", "CRITICAL")
            ]

            # 如果有警告/错误日志，附加到结果
            if new_logs:
                result += "\n\n[执行日志]:\n"
                for log in new_logs[-10:]:  # 最多显示 10 条
                    result += f"[{log['level']}] {log['module']}: {log['message']}\n"

            # ★ 通用截断守卫（与 ToolExecutor._guard_truncate 逻辑一致）
            result = ToolExecutor._guard_truncate(tool_name, result)

            return result

        except Exception as e:
            logger.error(f"Tool execution error: {e}", exc_info=True)
            return f"工具执行错误: {str(e)}"

    async def execute_task(self, task: TaskState) -> TaskResult:
        """
        执行任务（带工具调用）

        安全模型切换策略：
        1. 超时或错误时先重试 3 次
        2. 重试次数用尽后才切换到备用模型
        3. 切换时废弃已有的工具调用历史，从任务原始描述开始重新处理

        Args:
            task: 任务对象

        Returns:
            TaskResult
        """
        import time

        start_time = time.time()

        if not self._initialized:
            await self.initialize()

        logger.info(f"Executing task: {task.description}")

        # === 创建任务监控器 ===
        task_monitor = TaskMonitor(
            task_id=task.id,
            description=task.description,
            session_id=task.session_id,
            timeout_seconds=settings.progress_timeout_seconds,
            hard_timeout_seconds=settings.hard_timeout_seconds,
            retrospect_threshold=60,  # 复盘阈值：60秒
            fallback_model=self.brain.get_fallback_model(task.session_id),  # 动态获取备用模型
            retry_before_switch=3,  # 切换前重试 3 次
        )
        task_monitor.start(self.brain.model)

        # 使用已构建的系统提示词 (包含技能清单)
        # 技能清单已在初始化时注入到 _context.system 中
        system_prompt = (
            self._context.system
            + """

## Task Execution Strategy

请使用工具来实际执行任务:

1. **Check skill catalog above** - 技能清单已在上方，根据描述判断是否有匹配的技能
2. **If skill matches**: Use `get_skill_info(skill_name)` to load full instructions
3. **Run script**: Use `run_skill_script(skill_name, script_name, args)`
4. **If no skill matches**: Use `skill-creator` skill to create one, then `load_skill` to load it

永不放弃，直到任务完成！"""
        )

        # === Plan 持久化：保存不含 Plan 的基础提示词，循环内动态追加 ===
        _base_system_prompt_task = system_prompt
        _task_conversation_id = task.session_id or f"task:{task.id}"

        def _build_effective_system_prompt_task() -> str:
            """在基础提示词上动态追加活跃 Plan 段落（Task 路径）"""
            from ..tools.handlers.plan import get_active_plan_prompt

            prompt = _base_system_prompt_task
            plan_section = get_active_plan_prompt(_task_conversation_id)
            if plan_section:
                prompt += f"\n\n{plan_section}\n"
            return prompt

        # === 关键：保存原始任务描述，用于模型切换时重置上下文 ===
        original_task_message = {"role": "user", "content": task.description}
        messages = [original_task_message.copy()]

        # === 工具按需加载：根据任务内容过滤工具 ===
        from ..tools.filter import get_tools_for_message
        filtered_tools = get_tools_for_message(self._tools, task.description, "desktop")
        logger.info(f"[ToolFilter] Task tools: {len(self._tools)} → {len(filtered_tools)}")

        max_tool_iterations = settings.max_iterations  # Ralph Wiggum 模式：永不放弃
        iteration = 0
        final_response = ""
        current_model = self.brain.model
        conversation_id = task.session_id or f"task:{task.id}"

        def _resolve_endpoint_name(model_or_endpoint: str) -> str | None:
            """将 'endpoint_name' 或 'model' 解析为 endpoint_name（任务循环专用，最小兼容）。"""
            try:
                llm_client = getattr(self.brain, "_llm_client", None)
                if not llm_client:
                    return None
                available = [m.name for m in llm_client.list_available_models()]
                if model_or_endpoint in available:
                    return model_or_endpoint
                for m in llm_client.list_available_models():
                    if m.model == model_or_endpoint:
                        return m.name
                return None
            except Exception:
                return None

        # 防止循环检测
        recent_tool_calls: list[str] = []  # 记录最近的工具调用
        max_repeated_calls = 3  # 连续相同调用超过此次数则强制结束

        # 模型切换熔断：与 ReasoningEngine.MAX_MODEL_SWITCHES 对齐
        # 防止并行任务路径因所有模型不可用而无限循环切换
        MAX_TASK_MODEL_SWITCHES = 5
        _task_switch_count = 0

        # 追问计数器：当 LLM 没有调用工具时，最多追问几次
        no_tool_call_count = 0
        max_no_tool_retries = max(0, int(getattr(settings, "force_tool_call_max_retries", 1)))

        # 获取 cancel_event（用于 LLM 调用竞速取消）
        _cancel_event = (
            self.agent_state.current_task.cancel_event
            if self.agent_state and self.agent_state.current_task
            else asyncio.Event()
        )

        try:
            while iteration < max_tool_iterations:
                # C8: 每轮迭代开始时检查任务是否被取消
                if self._task_cancelled:
                    logger.info(
                        f"[StopTask] Task cancelled in execute_task: {self._cancel_reason}"
                    )
                    return "✅ 任务已停止。"

                iteration += 1
                logger.info(f"Task iteration {iteration}")

                # 任务监控：开始迭代
                task_monitor.begin_iteration(iteration, current_model)

                # === 安全模型切换检查 ===
                # 检查是否超时且重试次数已用尽
                if task_monitor.should_switch_model:
                    # 熔断检查：防止无限模型切换循环
                    _task_switch_count += 1
                    if _task_switch_count > MAX_TASK_MODEL_SWITCHES:
                        logger.error(
                            f"[Task:{task.id}] Exceeded max model switches "
                            f"({MAX_TASK_MODEL_SWITCHES}), aborting task"
                        )
                        return (
                            f"❌ 任务失败：已尝试切换 {MAX_TASK_MODEL_SWITCHES} 次模型，所有模型均不可用。\n"
                            "💡 建议：请检查 API Key 是否正确、账户余额是否充足、网络连接是否正常。"
                            "如果是配额耗尽，充值后即可恢复。"
                        )

                    new_model = task_monitor.fallback_model
                    task_monitor.switch_model(
                        new_model,
                        f"任务执行超过 {task_monitor.timeout_seconds} 秒，重试 {task_monitor.retry_count} 次后切换",
                        reset_context=True,
                    )

                    endpoint_name = _resolve_endpoint_name(new_model)
                    if endpoint_name:
                        ok, msg = self.brain.switch_model(
                            endpoint_name=endpoint_name,
                            hours=0.05,
                            reason=f"task_timeout:{task.id}",
                            conversation_id=conversation_id,
                        )
                        if not ok:
                            logger.error(
                                f"[ModelSwitch] switch_model failed: {msg}. "
                                f"Aborting task (no healthy endpoint)."
                            )
                            return (
                                f"❌ 任务失败：模型切换失败（{msg}），无法继续执行。\n"
                                "💡 建议：请检查网络连接，或在设置中心确认至少有一个模型配置正确。"
                            )
                    else:
                        logger.warning(f"[ModelSwitch] Cannot resolve endpoint for '{new_model}'")

                    current_model = new_model

                    # === 关键：重置上下文，废弃工具调用历史 ===
                    logger.warning(
                        f"[ModelSwitch] Task {task.id}: Switching to {new_model}, resetting context. "
                        f"Discarding {len(messages) - 1} tool-related messages"
                    )
                    messages = [original_task_message.copy()]

                    # 添加模型切换说明 + tool-state revalidation barrier
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                "[系统提示] 发生模型切换：之前的 tool_use/tool_result 历史已清除。现在所有工具状态一律视为未知。\n"
                                "在执行任何状态型工具前，必须先做状态复核：浏览器先 browser_open；MCP 先 list_mcp_servers；桌面先 desktop_window/desktop_inspect。\n"
                                "请从头开始处理上面的任务请求。"
                            ),
                        }
                    )

                    # 重置循环检测
                    recent_tool_calls.clear()

                try:
                    # 检查并压缩上下文（任务执行可能产生大量工具输出）
                    if iteration > 1:
                        messages = ConversationContext.trim_messages(
                            messages,
                            max_rounds=self._max_conversation_rounds,
                            max_tokens=self._max_conversation_tokens,
                        )

                    # 调用 Brain（可被 cancel_event 中断）
                    response = await self._cancellable_llm_call(
                        _cancel_event,
                        max_tokens=self.brain.max_tokens,
                        system=_build_effective_system_prompt_task(),
                        tools=filtered_tools,
                        messages=messages,
                        conversation_id=conversation_id,
                    )

                    # 成功调用，重置重试计数
                    task_monitor.reset_retry_count()

                except UserCancelledError:
                    logger.info(f"[StopTask] LLM call interrupted by user cancel in execute_task {task.id}")
                    return await self._handle_cancel_farewell(
                        messages, _build_effective_system_prompt_task(), current_model
                    )

                except Exception as e:
                    logger.error(f"[LLM] Brain call failed in task {task.id}: {e}")

                    # 记录错误并判断是否应该重试
                    should_retry = task_monitor.record_error(str(e))

                    if should_retry:
                        logger.info(
                            f"[LLM] Will retry (attempt {task_monitor.retry_count}/{task_monitor.retry_before_switch})"
                        )
                        try:
                            await self._cancellable_await(asyncio.sleep(2), _cancel_event)
                        except UserCancelledError:
                            return await self._handle_cancel_farewell(
                                messages, _build_effective_system_prompt_task(), current_model
                            )
                        continue
                    else:
                        # 重试次数用尽，切换模型（per-conversation override）
                        # 熔断检查：防止无限模型切换循环
                        _task_switch_count += 1
                        if _task_switch_count > MAX_TASK_MODEL_SWITCHES:
                            logger.error(
                                f"[Task:{task.id}] Exceeded max model switches "
                                f"({MAX_TASK_MODEL_SWITCHES}), aborting task"
                            )
                            return (
                                f"❌ 任务失败：已尝试切换 {MAX_TASK_MODEL_SWITCHES} 次模型，所有模型均不可用。\n"
                                "💡 建议：请检查 API Key 是否正确、账户余额是否充足、网络连接是否正常。"
                                f"如果是配额耗尽，充值后即可恢复。\n最后错误: {e}"
                            )

                        new_model = task_monitor.fallback_model
                        task_monitor.switch_model(
                            new_model,
                            f"LLM 调用失败，重试 {task_monitor.retry_count} 次后切换: {e}",
                            reset_context=True,
                        )
                        endpoint_name = _resolve_endpoint_name(new_model)
                        if endpoint_name:
                            ok, msg = self.brain.switch_model(
                                endpoint_name=endpoint_name,
                                hours=0.05,
                                reason=f"task_error:{task.id}",
                                conversation_id=conversation_id,
                            )
                            if not ok:
                                logger.warning(
                                    f"[ModelSwitch] switch_model failed: {msg}. "
                                    f"Not resetting retry_count."
                                )
                                # switch_model 失败（目标在冷静期），不重置 retry_count
                                # 直接 break，避免无限重试
                                return (
                                    f"❌ 任务失败：模型切换失败（{msg}），无法继续执行。\n"
                                    "💡 建议：请检查网络连接，或在设置中心确认至少有一个模型配置正确。"
                                )
                        else:
                            logger.warning(
                                f"[ModelSwitch] Cannot resolve endpoint for '{new_model}'"
                            )
                        current_model = new_model

                        # 重置上下文 + barrier
                        logger.warning(
                            f"[ModelSwitch] Task {task.id}: Switching to {new_model} due to errors, resetting context"
                        )
                        messages = [original_task_message.copy()]
                        messages.append(
                            {
                                "role": "user",
                                "content": (
                                    "[系统提示] 发生模型切换：之前的 tool_use/tool_result 历史已清除。现在所有工具状态一律视为未知。\n"
                                    "在执行任何状态型工具前，必须先做状态复核：浏览器先 browser_open；MCP 先 list_mcp_servers；桌面先 desktop_window/desktop_inspect。\n"
                                    "请从头开始处理上面的任务请求。"
                                ),
                            }
                        )
                        recent_tool_calls.clear()
                        continue

                # 检测 max_tokens 截断
                _task_stop = getattr(response, "stop_reason", "")
                if str(_task_stop) == "max_tokens":
                    logger.warning(
                        f"[Task:{task.id}] ⚠️ LLM output truncated (stop_reason=max_tokens, limit={self.brain.max_tokens})"
                    )

                # 处理响应
                tool_calls = []
                text_content = ""

                for block in response.content:
                    if block.type == "text":
                        text_content += block.text
                    elif block.type == "tool_use":
                        tool_calls.append(
                            {
                                "id": block.id,
                                "name": block.name,
                                "input": block.input,
                            }
                        )

                # 任务监控：结束迭代
                task_monitor.end_iteration(text_content if text_content else "")

                # 如果有文本响应，保存（过滤 thinking 标签和工具调用模拟文本）
                if text_content:
                    cleaned_text = clean_llm_response(text_content)
                    # 只有在没有工具调用时才保存文本作为最终响应
                    # 如果有工具调用，这个文本可能是 LLM 的思考过程
                    if not tool_calls and cleaned_text:
                        final_response = cleaned_text

                # 如果没有工具调用，检查是否需要强制要求调用工具
                if not tool_calls:
                    no_tool_call_count += 1

                    # 如果还有追问次数，强制要求调用工具
                    if no_tool_call_count <= max_no_tool_retries:
                        logger.warning(
                            f"[ForceToolCall] Task LLM returned text without tool calls (attempt {no_tool_call_count}/{max_no_tool_retries})"
                        )

                        # 将 LLM 的响应加入历史
                        if text_content:
                            messages.append(
                                {
                                    "role": "assistant",
                                    "content": [{"type": "text", "text": text_content}],
                                }
                            )

                        # 追加强制要求调用工具的消息
                        messages.append(
                            {
                                "role": "user",
                                "content": "[系统] 若确实需要工具，请调用相应工具；若不需要工具（纯对话/问答），请直接回答，不要复述系统规则。",
                            }
                        )
                        continue  # 继续循环，让 LLM 调用工具

                    # 追问次数用尽，任务完成
                    break

                # 循环检测：记录工具调用签名
                call_signature = "|".join(
                    [f"{tc['name']}:{sorted(tc['input'].items())}" for tc in tool_calls]
                )
                recent_tool_calls.append(call_signature)

                # 只保留最近的调用记录
                if len(recent_tool_calls) > max_repeated_calls:
                    recent_tool_calls = recent_tool_calls[-max_repeated_calls:]

                # 检测连续重复调用
                if len(recent_tool_calls) >= max_repeated_calls:
                    if len(set(recent_tool_calls)) == 1:
                        logger.warning(
                            f"[Loop Detection] Same tool call repeated {max_repeated_calls} times, forcing task end"
                        )
                        final_response = (
                            "任务执行中检测到重复操作，已自动结束。如需继续，请重新描述任务。"
                        )
                        break

                # 执行工具调用
                # MiniMax M2.1 Interleaved Thinking 支持：
                # 必须完整保留 thinking 块以保持思维链连续性
                assistant_content = []
                for block in response.content:
                    if block.type == "thinking":
                        # 保留 thinking 块（MiniMax M2.1 要求）
                        assistant_content.append(
                            {
                                "type": "thinking",
                                "thinking": block.thinking
                                if hasattr(block, "thinking")
                                else str(block),
                            }
                        )
                    elif block.type == "text":
                        assistant_content.append({"type": "text", "text": block.text})
                    elif block.type == "tool_use":
                        assistant_content.append(
                            {
                                "type": "tool_use",
                                "id": block.id,
                                "name": block.name,
                                "input": block.input,
                            }
                        )

                messages.append({"role": "assistant", "content": assistant_content})

                # 执行每个工具并收集结果
                # execute_task() 场景没有“工具间中断检查”的强需求，可按配置启用并行
                tool_results, executed_names, _ = await self._execute_tool_calls_batch(
                    tool_calls,
                    task_monitor=task_monitor,
                    allow_interrupt_checks=False,
                    capture_delivery_receipts=False,
                )

                messages.append({"role": "user", "content": tool_results})

                # === 统一处理 skip 反思 + 用户插入消息 ===
                if self.agent_state and self.agent_state.current_task:
                    await self.agent_state.current_task.process_post_tool_signals(messages)

                # 注意：不在工具执行后检查 stop_reason，让循环继续获取 LLM 的最终总结
            # 循环结束后，如果 final_response 为空，尝试让 LLM 生成一个总结
            if not final_response or len(final_response.strip()) < 10:
                logger.info("Task completed but no final response, requesting summary...")
                try:
                    # 请求 LLM 生成任务完成总结
                    messages.append(
                        {
                            "role": "user",
                            "content": "任务执行完毕。请简要总结一下执行结果和完成情况。",
                        }
                    )
                    _tt_sum = set_tracking_context(TokenTrackingContext(
                        operation_type="task_summary",
                        session_id=conversation_id or "",
                        channel="scheduler",
                    ))
                    try:
                        summary_response = await self._cancellable_await(
                            asyncio.to_thread(
                                self.brain.messages_create,
                                max_tokens=1000,
                                system=_build_effective_system_prompt_task(),
                                messages=messages,
                                conversation_id=conversation_id,
                            ),
                            _cancel_event,
                        )
                    finally:
                        reset_tracking_context(_tt_sum)
                    for block in summary_response.content:
                        if block.type == "text":
                            final_response = clean_llm_response(block.text)
                            break
                except UserCancelledError:
                    final_response = "✅ 任务已停止。"
                except Exception as e:
                    logger.warning(f"Failed to get summary: {e}")
                    final_response = "任务已执行完成。"
        finally:
            # 清理 per-conversation override，避免影响后续任务/会话
            with contextlib.suppress(Exception):
                self.brain.restore_default_model(conversation_id=conversation_id)

        # === 完成任务监控 ===
        metrics = task_monitor.complete(
            success=True,
            response=final_response,
        )

        # === 后台复盘分析（如果任务耗时过长，不阻塞响应） ===
        if metrics.retrospect_needed:
            # 创建后台任务执行复盘，不等待结果
            asyncio.create_task(
                self._do_task_retrospect_background(task_monitor, task.session_id or task.id)
            )
            logger.info(f"[Task:{task.id}] Retrospect scheduled (background)")

        task.mark_completed(final_response)

        duration = time.time() - start_time

        return TaskResult(
            success=True,
            data=final_response,
            iterations=iteration,
            duration_seconds=duration,
        )

    def _format_task_result(self, result: TaskResult) -> str:
        """格式化任务结果"""
        if result.success:
            return f"""✅ 任务完成

{result.data}

---
迭代次数: {result.iterations}
耗时: {result.duration_seconds:.2f}秒"""
        else:
            return f"""❌ 任务未能完成

错误: {result.error}

---
尝试次数: {result.iterations}
耗时: {result.duration_seconds:.2f}秒

我会继续尝试其他方法..."""

    async def self_check(self) -> dict[str, Any]:
        """
        自检

        Returns:
            自检结果
        """
        logger.info("Running self-check...")

        results = {
            "timestamp": datetime.now().isoformat(),
            "status": "healthy",
            "checks": {},
        }

        # 检查 Brain
        try:
            response = await self.brain.think("你好，这是一个测试。请回复'OK'。")
            results["checks"]["brain"] = {
                "status": "ok"
                if "OK" in response.content or "ok" in response.content.lower()
                else "warning",
                "message": "Brain is responsive",
            }
        except Exception as e:
            results["checks"]["brain"] = {
                "status": "error",
                "message": str(e),
            }
            results["status"] = "unhealthy"

        # 检查 Identity
        try:
            soul = self.identity.soul
            agent = self.identity.agent
            results["checks"]["identity"] = {
                "status": "ok" if soul and agent else "warning",
                "message": f"SOUL.md: {len(soul)} chars, AGENT.md: {len(agent)} chars",
            }
        except Exception as e:
            results["checks"]["identity"] = {
                "status": "error",
                "message": str(e),
            }

        # 检查配置
        results["checks"]["config"] = {
            "status": "ok" if settings.anthropic_api_key else "error",
            "message": "API key configured" if settings.anthropic_api_key else "API key missing",
        }

        # 检查技能系统 (SKILL.md 规范)
        skill_count = self.skill_registry.count
        results["checks"]["skills"] = {
            "status": "ok",
            "message": f"已安装 {skill_count} 个技能 (Agent Skills 规范)",
            "count": skill_count,
            "skills": [s.name for s in self.skill_registry.list_all()],
        }

        # 检查技能目录
        skills_path = settings.skills_path
        results["checks"]["skills_dir"] = {
            "status": "ok" if skills_path.exists() else "warning",
            "message": str(skills_path),
        }

        # 检查 MCP 客户端
        mcp_servers = self.mcp_client.list_servers()
        mcp_connected = self.mcp_client.list_connected()
        results["checks"]["mcp"] = {
            "status": "ok",
            "message": f"配置 {len(mcp_servers)} 个服务器, 已连接 {len(mcp_connected)} 个",
            "servers": mcp_servers,
            "connected": mcp_connected,
        }

        logger.info(f"Self-check complete: {results['status']}")

        return results

    def _on_iteration(self, iteration: int, task: TaskState) -> None:
        """Ralph 循环迭代回调"""
        logger.debug(f"Ralph iteration {iteration} for task {task.task_id}")

    def _on_error(self, error: str, task: TaskState) -> None:
        """Ralph 循环错误回调"""
        logger.warning(f"Ralph error for task {task.task_id}: {error}")

    @property
    def is_initialized(self) -> bool:
        """是否已初始化"""
        return self._initialized

    @property
    def conversation_history(self) -> list[dict]:
        """对话历史"""
        return self._conversation_history.copy()

    # ==================== 记忆系统方法 ====================

    def set_scheduler_gateway(self, gateway: Any) -> None:
        """
        设置定时任务调度器的消息网关

        用于定时任务执行后发送通知到 IM 通道

        Args:
            gateway: MessageGateway 实例
        """
        if hasattr(self, "_task_executor") and self._task_executor:
            self._task_executor.gateway = gateway
            # 同时传递 memory 引用，供系统任务使用
            self._task_executor.memory_manager = getattr(self, "memory_manager", None)
            logger.info("Scheduler gateway configured")

    async def shutdown(
        self, task_description: str = "", success: bool = True, errors: list = None
    ) -> None:
        """
        关闭 Agent 并保存记忆

        Args:
            task_description: 会话的主要任务描述
            success: 任务是否成功
            errors: 遇到的错误列表
        """
        logger.info("Shutting down agent...")

        # 结束记忆会话
        self.memory_manager.end_session(
            task_description=task_description,
            success=success,
            errors=errors or [],
        )

        # MEMORY.md 由 DailyConsolidator 在凌晨刷新，shutdown 时不同步

        self._running = False
        logger.info("Agent shutdown complete")

    async def consolidate_memories(self) -> dict:
        """
        整理记忆 (批量处理未处理的会话)

        适合在空闲时段 (如凌晨) 由 cron job 调用

        Returns:
            整理结果统计
        """
        logger.info("Starting memory consolidation...")
        return await self.memory_manager.consolidate_daily()

    def get_memory_stats(self) -> dict:
        """获取记忆统计"""
        return self.memory_manager.get_stats()
