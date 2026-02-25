"""
Session Helper - 会话管理辅助函数

从 Agent 类中提取的会话管理逻辑，包括：
- 会话上下文准备 (prepare_session_context)
- 会话收尾 (finalize_session)
- 状态清理 (cleanup_session_state)
- 会话 ID 解析 (resolve_conversation_id)
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ...config import settings
from ...context.conversation_context import ConversationContext
from ..task_monitor import TaskMonitor
from ..response_handler import strip_thinking_tags

if TYPE_CHECKING:
    from ..agent import Agent

logger = logging.getLogger(__name__)


def resolve_conversation_id(agent: "Agent", session: Any, session_id: str) -> str:
    """从 session 中解析稳定的 conversation_id。"""
    conversation_id = ""
    try:
        if session and hasattr(session, "session_key"):
            conversation_id = session.session_key
        elif session and hasattr(session, "get_metadata"):
            conversation_id = session.get_metadata("_session_key") or ""
    except Exception:
        conversation_id = ""
    return conversation_id or session_id


async def prepare_session_context(
    agent: "Agent",
    message: str,
    session_messages: list[dict],
    session_id: str,
    session: Any,
    gateway: Any,
    conversation_id: str,
    *,
    attachments: list | None = None,
) -> tuple[list[dict], str, "TaskMonitor", str, Any]:
    """
    会话流水线 - 共享准备阶段。

    chat_with_session() 和 chat_with_session_stream() 共用此方法，
    确保 IM/Desktop 两条路径走完全一致的准备逻辑。

    Args:
        agent: Agent 实例
        message: 用户消息
        session_messages: Session 的对话历史
        session_id: 会话 ID（用于日志）
        session: Session 对象
        gateway: MessageGateway 对象
        conversation_id: 稳定对话线程 ID
        attachments: Desktop Chat 附件列表 (可选)

    Returns:
        (messages, session_type, task_monitor, conversation_id, im_tokens)
    """
    # 1. 对齐 MemoryManager 会话
    try:
        conversation_safe_id = conversation_id.replace(":", "__")
        conversation_safe_id = re.sub(r'[/\\+=%?*<>|"\x00-\x1f]', "_", conversation_safe_id)
        if getattr(agent.memory_manager, "_current_session_id", None) != conversation_safe_id:
            agent.memory_manager.start_session(conversation_safe_id)
    except Exception as e:
        logger.warning(f"[Memory] Failed to align memory session: {e}")

    # 2. IM context setup（协程隔离）
    from ..im_context import set_im_context

    im_tokens = set_im_context(
        session=session if gateway else None,
        gateway=gateway,
    )

    # 3. Agent state / log session
    agent._current_session = session
    agent.agent_state.current_session = session

    from ...logging import get_session_log_buffer
    get_session_log_buffer().set_current_session(conversation_id)

    logger.info(f"[Session:{session_id}] User: {message}")

    # 4. Proactive engine: 记录用户互动时间
    # 5. User turn memory record
    agent.memory_manager.record_turn("user", message)

    # 7. Prompt Compiler (两段式第一阶段)
    compiled_message = message
    compiler_output = ""
    compiler_summary = ""

    if agent._should_compile_prompt(message):
        compiled_message, compiler_output = await agent._compile_prompt(message)
        if compiler_output:
            logger.info(f"[Session:{session_id}] Prompt compiled")
            compiler_summary = agent._summarize_compiler_output(compiler_output)

            # 8. Plan 模式自动检测
            from ...tools.handlers.plan import require_plan_for_session, should_require_plan

            is_compound = (
                "task_type: compound" in compiler_output
                or "task_type:compound" in compiler_output
            )
            has_multi_actions = should_require_plan(message)

            if is_compound or has_multi_actions:
                require_plan_for_session(conversation_id, True)
                logger.info(
                    f"[Session:{session_id}] Multi-step task detected "
                    f"(compound={is_compound}, multi_actions={has_multi_actions}), Plan required"
                )

    # 9. Task definition setup
    agent._current_task_definition = compiler_summary
    agent._current_task_query = compiler_summary or message

    # 10. Message history build
    # session_messages 已包含当前轮用户消息（gateway 调用前 add_message），
    # 当前轮由下方 compiled_message 单独追加，需排除最后一条避免重复。
    history_messages = session_messages
    if history_messages and history_messages[-1].get("role") == "user":
        history_messages = history_messages[:-1]

    messages: list[dict] = []
    for msg in history_messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})

    # 上下文边界标记
    if messages:
        messages.append({
            "role": "user",
            "content": "[上下文结束，以下是用户的最新消息]",
        })
        messages.append({
            "role": "assistant",
            "content": "好的，我已了解之前的对话上下文。请告诉我你现在的需求。",
        })

    # 当前用户消息（支持多模态）
    pending_images = session.get_metadata("pending_images") if session else None
    pending_videos = session.get_metadata("pending_videos") if session else None
    pending_audio = session.get_metadata("pending_audio") if session else None
    pending_files = session.get_metadata("pending_files") if session else None

    # 处理 PDF/文档文件 — 如果 LLM 支持 PDF 则构建 DocumentBlock，否则降级为文本
    document_blocks = []
    if pending_files:
        llm_client_for_pdf = getattr(agent.brain, "_llm_client", None)
        has_pdf_cap = llm_client_for_pdf and llm_client_for_pdf.has_any_endpoint_with_capability("pdf")
        for fdata in pending_files:
            if has_pdf_cap and fdata.get("type") == "document":
                document_blocks.append(fdata)
                logger.info(f"[Session:{session_id}] PDF → native DocumentBlock")
            else:
                # 降级: 提取文本描述
                fname = fdata.get("filename", "unknown")
                compiled_message += f"\n[文档附件: {fname}，该端点不支持 PDF 原生输入]"

    # 三级音频决策：LLM原生audio > 在线STT > 本地Whisper
    audio_blocks = []
    if pending_audio:
        llm_client = getattr(agent.brain, "_llm_client", None)
        has_audio_cap = llm_client and llm_client.has_any_endpoint_with_capability("audio")

        if has_audio_cap:
            # Tier 1: LLM 原生音频输入
            for aud in pending_audio:
                local_path = aud.get("local_path", "")
                if local_path and Path(local_path).exists():
                    try:
                        from ...channels.media.audio_utils import ensure_llm_compatible
                        compat_path = ensure_llm_compatible(local_path)
                        audio_blocks.append({
                            "type": "audio",
                            "source": {
                                "type": "base64",
                                "media_type": aud.get("mime_type", "audio/wav"),
                                "data": base64.b64encode(Path(compat_path).read_bytes()).decode("utf-8"),
                                "format": Path(compat_path).suffix.lstrip(".") or "wav",
                            },
                        })
                        logger.info(f"[Session:{session_id}] Audio → native AudioBlock")
                    except Exception as e:
                        logger.error(f"[Session:{session_id}] Failed to build AudioBlock: {e}")
        else:
            # Tier 2: 在线 STT（如果可用）
            stt_client = None
            im_gateway = gateway or (session.get_metadata("_gateway") if session else None)
            if im_gateway and hasattr(im_gateway, "stt_client"):
                stt_client = im_gateway.stt_client

            if stt_client and stt_client.is_available:
                for aud in pending_audio:
                    local_path = aud.get("local_path", "")
                    existing_transcription = aud.get("transcription")
                    if existing_transcription:
                        continue  # 已有 Whisper 结果，不重复调用
                    if local_path and Path(local_path).exists():
                        try:
                            stt_result = await stt_client.transcribe(local_path)
                            if stt_result:
                                # 用在线 STT 结果替换输入
                                if not compiled_message.strip() or "[语音:" in compiled_message:
                                    compiled_message = stt_result
                                else:
                                    compiled_message = f"{compiled_message}\n\n[语音内容(在线识别): {stt_result}]"
                                logger.info(f"[Session:{session_id}] Audio → online STT: {stt_result[:50]}...")
                        except Exception as e:
                            logger.warning(f"[Session:{session_id}] Online STT failed: {e}")
            # Tier 3: 本地 Whisper（已由 Gateway 处理，transcription 已在 input_text 中）
            # 不需要额外操作

    # Desktop Chat 附件处理（与 IM 的 pending_images 对齐）
    if attachments and not pending_images:
        content_blocks: list[dict] = []
        if compiled_message:
            content_blocks.append({"type": "text", "text": compiled_message})
        for att in attachments:
            att_type = getattr(att, "type", None) or ""
            att_url = getattr(att, "url", None) or ""
            att_name = getattr(att, "name", None) or "file"
            att_mime = getattr(att, "mime_type", None) or att_type
            if att_type == "image" and att_url:
                content_blocks.append({"type": "image_url", "image_url": {"url": att_url}})
            elif att_type == "video" and att_url:
                content_blocks.append({"type": "video_url", "video_url": {"url": att_url}})
            elif att_type == "document" and att_url:
                # PDF 等文档 — 通过 URL 下载后交给后端处理
                content_blocks.append({
                    "type": "text",
                    "text": f"[文档: {att_name} ({att_mime})] URL: {att_url}",
                })
            elif att_url:
                content_blocks.append({
                    "type": "text",
                    "text": f"[附件: {att_name} ({att_mime})] URL: {att_url}",
                })
        if content_blocks:
            messages.append({"role": "user", "content": content_blocks})
        elif compiled_message:
            messages.append({"role": "user", "content": compiled_message})
    elif pending_images or pending_videos or audio_blocks or document_blocks:
        # IM 路径: 多模态（图片 + 视频 + 音频 + 文档）
        content_parts: list[dict] = []
        _text_for_llm = compiled_message.strip()
        # 图片占位符替换
        if pending_images and _text_for_llm and re.fullmatch(r"(\[图片: [^\]]+\]\s*)+", _text_for_llm):
            _text_for_llm = (
                f"用户发送了 {len(pending_images)} 张图片（已附在消息中，请直接查看）。"
                "请描述或回应你所看到的图片内容。"
            )
        # 视频占位符替换
        if pending_videos and _text_for_llm and re.fullmatch(r"(\[视频: [^\]]+\]\s*)+", _text_for_llm):
            _text_for_llm = (
                f"用户发送了 {len(pending_videos)} 个视频（已附在消息中，请直接查看）。"
                "请描述或回应你所看到的视频内容。"
            )
        if _text_for_llm:
            content_parts.append({"type": "text", "text": _text_for_llm})
        if pending_images:
            for img_data in pending_images:
                content_parts.append(img_data)
        if pending_videos:
            for vid_data in pending_videos:
                content_parts.append(vid_data)
        if audio_blocks:
            for aud_data in audio_blocks:
                content_parts.append(aud_data)
        if document_blocks:
            for doc_data in document_blocks:
                content_parts.append(doc_data)
        messages.append({"role": "user", "content": content_parts})
        media_info = []
        if pending_images:
            media_info.append(f"{len(pending_images)} images")
        if pending_videos:
            media_info.append(f"{len(pending_videos)} videos")
        if audio_blocks:
            media_info.append(f"{len(audio_blocks)} audio")
        if document_blocks:
            media_info.append(f"{len(document_blocks)} documents")
        logger.info(f"[Session:{session_id}] Multimodal message with {', '.join(media_info)}")
    else:
        # 普通文本消息
        messages.append({"role": "user", "content": compiled_message})

    # 11. Context compression
    messages = ConversationContext.trim_messages(
        messages,
        max_rounds=agent._max_conversation_rounds,
        max_tokens=agent._max_conversation_tokens,
    )

    # 12. TaskMonitor creation
    task_monitor = TaskMonitor(
        task_id=f"{session_id}_{datetime.now().strftime('%H%M%S')}",
        description=message,
        session_id=session_id,
        timeout_seconds=settings.progress_timeout_seconds,
        hard_timeout_seconds=settings.hard_timeout_seconds,
        retrospect_threshold=60,
        fallback_model=agent.brain.get_fallback_model(session_id),
    )
    task_monitor.start(agent.brain.model)
    agent._current_task_monitor = task_monitor

    # session_type 检测
    session_type = "im" if gateway else "cli"
    if session_type == "cli" and session and getattr(session, "channel", "") != "cli":
        session_type = getattr(session, "channel", "im")

    return messages, session_type, task_monitor, conversation_id, im_tokens


async def finalize_session(
    agent: "Agent",
    response_text: str,
    session: Any,
    session_id: str,
    task_monitor: "TaskMonitor",
) -> None:
    """
    会话流水线 - 共享收尾阶段。

    chat_with_session() 和 chat_with_session_stream() 共用此方法。
    """
    # 1. 思维链摘要 → session metadata
    if session:
        try:
            chain_summary = agent._build_chain_summary(
                agent.reasoning_engine._last_react_trace
            )
            if chain_summary:
                session.set_metadata("_last_chain_summary", chain_summary)
        except Exception as e:
            logger.debug(f"[ChainSummary] Failed to build chain summary: {e}")

    # 2. TaskMonitor complete + retrospect
    metrics = task_monitor.complete(success=True, response=response_text)

    # 记录任务完成日志
    logger.info(
        f"[Session:{session_id}] Task completed: task_id={metrics.task_id}, "
        f"duration={metrics.total_duration_seconds:.1f}s, iterations={metrics.total_iterations}, "
        f"retrospect_needed={metrics.retrospect_needed}"
    )

    if metrics.retrospect_needed:
        # 确保有有效的 session_id（使用 task_id 作为回退）
        effective_session_id = session_id or metrics.task_id or "unknown"
        try:
            asyncio.create_task(
                agent._do_task_retrospect_background(task_monitor, effective_session_id)
            )
            logger.info(
                f"[Session:{effective_session_id}] Retrospect scheduled (background): "
                f"duration={metrics.total_duration_seconds:.1f}s > threshold"
            )
        except Exception as e:
            logger.error(
                f"[Session:{effective_session_id}] Failed to schedule retrospect: {e}",
                exc_info=True
            )

    # 3. Memory: 记录 assistant 响应
    agent.memory_manager.record_turn("assistant", response_text)
    try:
        logger.info(f"[Session:{session_id}] Agent: {response_text}")
    except (UnicodeEncodeError, OSError):
        logger.info(f"[Session:{session_id}] Agent: (response logged, {len(response_text)} chars)")

    # 4. 自动关闭未完成的 Plan
    exit_reason = getattr(agent.reasoning_engine, "_last_exit_reason", "normal")
    if exit_reason != "ask_user":
        conversation_id = getattr(agent, "_current_conversation_id", "") or session_id
        try:
            from ...tools.handlers.plan import auto_close_plan
            if auto_close_plan(conversation_id):
                logger.info(f"[Session:{session_id}] Plan auto-closed at finalize")
        except Exception as e:
            logger.debug(f"[Plan] auto_close_plan failed: {e}")


def cleanup_session_state(agent: "Agent", im_tokens: Any) -> None:
    """
    会话流水线 - 状态清理（总是在 finally 中调用）。
    """
    agent._current_task_definition = ""
    agent._current_task_query = ""
    if im_tokens is not None:
        with contextlib.suppress(Exception):
            from ..im_context import reset_im_context
            reset_im_context(im_tokens)
    agent._current_session = None
    agent.agent_state.current_session = None
    agent._current_task_monitor = None
    # 重置任务状态，避免已取消/已完成的任务泄漏到下一次会话
    _sid = getattr(agent, "_current_session_id", None)
    _task = (
        agent.agent_state.get_task_for_session(_sid) if _sid and agent.agent_state else None
    ) or (agent.agent_state.current_task if agent.agent_state else None)
    if _task and not _task.is_active:
        agent.agent_state.reset_task(session_id=_sid)
