"""
IM 通道处理器

处理 IM 通道相关的系统技能：
- deliver_artifacts: 通过网关交付附件并返回回执（推荐）
- get_voice_file: 获取语音文件
- get_image_file: 获取图片文件
- get_chat_history: 获取聊天历史

通用性设计：
- 通过 gateway/adapter 发送消息，不依赖 Session 类的发送方法
- 各 adapter 实现统一接口，新增 IM 平台只需实现 ChannelAdapter 基类
- 对于平台不支持的功能（如某些平台不支持语音），返回友好提示
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from ...channels.base import ChannelAdapter
    from ...core.agent import Agent

logger = logging.getLogger(__name__)


class IMChannelHandler:
    """
    IM 通道处理器

    通过 gateway 获取对应的 adapter 来发送消息，保持通用性。
    各 IM 平台的 adapter 需要实现 ChannelAdapter 基类的方法：
    - send_text(chat_id, text): 发送文本消息
    - send_file(chat_id, file_path, caption): 发送文件
    - send_image(chat_id, image_path, caption): 发送图片（可选）
    - send_voice(chat_id, voice_path, caption): 发送语音（可选）
    """

    TOOLS = [
        "deliver_artifacts",
        "get_voice_file",
        "get_image_file",
        "get_chat_history",
    ]

    def __init__(self, agent: "Agent"):
        self.agent = agent

    async def handle(self, tool_name: str, params: dict[str, Any]) -> str:
        """处理工具调用"""
        from ...core.im_context import get_im_session

        # deliver_artifacts 支持跨通道发送（target_channel 参数）
        if tool_name == "deliver_artifacts":
            target_channel = (params.get("target_channel") or "").strip()
            if target_channel:
                return await self._deliver_artifacts_cross_channel(params, target_channel)
            if not get_im_session():
                return await self._deliver_artifacts_desktop(params)
            return await self._deliver_artifacts(params)

        if not get_im_session():
            return "❌ 当前不在 IM 会话中，无法使用此工具"

        if tool_name == "get_voice_file":
            return self._get_voice_file(params)
        elif tool_name == "get_image_file":
            return self._get_image_file(params)
        elif tool_name == "get_chat_history":
            return await self._get_chat_history(params)
        else:
            return f"❌ Unknown IM channel tool: {tool_name}"

    def _get_adapter_and_chat_id(
        self,
    ) -> tuple[Optional["ChannelAdapter"], str | None, str | None, str | None, str | None]:
        """
        获取当前 IM 会话的 adapter 和 chat_id

        Returns:
            (adapter, chat_id, channel_name, reply_to, channel_user_id)
            或 (None, None, None, None, None) 如果获取失败
        """
        from ...core.im_context import get_im_session

        session = get_im_session()
        if not session:
            return None, None, None, None, None

        # 从 session metadata 获取 gateway 和当前消息
        gateway = session.get_metadata("_gateway")
        current_message = session.get_metadata("_current_message")

        if not gateway or not current_message:
            logger.warning("Missing gateway or current_message in session metadata")
            return None, None, None, None, None

        # 获取对应的 adapter
        channel = current_message.channel
        # 避免访问私有属性：优先使用公开接口
        adapter = gateway.get_adapter(channel) if hasattr(gateway, "get_adapter") else None
        if adapter is None:
            adapter = getattr(gateway, "_adapters", {}).get(channel)

        if not adapter:
            logger.warning(f"Adapter not found for channel: {channel}")
            return None, None, channel, None, None

        # 提取 reply_to (channel_message_id) 和 channel_user_id（群聊精确路由）
        reply_to = getattr(current_message, "channel_message_id", None)
        channel_user_id = getattr(current_message, "channel_user_id", None)

        return adapter, current_message.chat_id, channel, reply_to, channel_user_id

    # ==================== 跨通道辅助方法 ====================

    def _get_gateway(self):
        """
        获取 MessageGateway 实例（不依赖 IM session 上下文）。

        优先从 agent._task_executor.gateway 获取（始终可用，包括 Desktop 模式），
        回退到 IM 上下文。
        """
        executor = getattr(self.agent, "_task_executor", None)
        if executor and getattr(executor, "gateway", None):
            return executor.gateway

        from ...core.im_context import get_im_gateway
        return get_im_gateway()

    def _resolve_target_channel(
        self, target_channel: str
    ) -> tuple[Optional["ChannelAdapter"], str | None]:
        """
        解析 target_channel 名称为 (adapter, chat_id)。

        策略（逐级回退）:
        1. 检查 gateway 中是否有该通道的适配器且正在运行
        2. 从 session_manager 中找到该通道最近活跃的 session
        3. 从持久化文件 sessions.json 中查找
        4. 从通道注册表 channel_registry.json 查找历史记录

        Returns:
            (adapter, chat_id) 或 (None, None)
        """
        from datetime import datetime

        gateway = self._get_gateway()
        if not gateway:
            logger.warning("[CrossChannel] No gateway available")
            return None, None

        # 1. 检查适配器
        adapters = getattr(gateway, "_adapters", {})
        if target_channel not in adapters:
            logger.warning(f"[CrossChannel] Channel '{target_channel}' not found in adapters")
            return None, None

        adapter = adapters[target_channel]
        if not getattr(adapter, "is_running", False):
            logger.warning(f"[CrossChannel] Channel '{target_channel}' adapter is not running")
            return None, None

        chat_id: str | None = None

        # 2. 从 session_manager 查找活跃 session
        session_manager = getattr(gateway, "session_manager", None)
        if session_manager:
            sessions = session_manager.list_sessions(channel=target_channel)
            if sessions:
                sessions.sort(
                    key=lambda s: getattr(s, "last_active", datetime.min),
                    reverse=True,
                )
                chat_id = sessions[0].chat_id

        # 3. 从持久化文件查找
        if not chat_id and session_manager:
            import json as _json

            sessions_file = getattr(session_manager, "storage_path", None)
            if sessions_file:
                sessions_file = sessions_file / "sessions.json"
                if sessions_file.exists():
                    try:
                        with open(sessions_file, encoding="utf-8") as f:
                            raw = _json.load(f)
                        ch_sessions = [
                            s for s in raw
                            if s.get("channel") == target_channel and s.get("chat_id")
                        ]
                        if ch_sessions:
                            ch_sessions.sort(key=lambda s: s.get("last_active", ""), reverse=True)
                            chat_id = ch_sessions[0]["chat_id"]
                    except Exception as e:
                        logger.error(f"[CrossChannel] Failed to read sessions file: {e}")

        # 4. 从通道注册表查找
        if not chat_id and session_manager and hasattr(session_manager, "get_known_channel_target"):
            known = session_manager.get_known_channel_target(target_channel)
            if known:
                chat_id = known[1]
                logger.info(
                    f"[CrossChannel] Resolved '{target_channel}' from channel registry: "
                    f"chat_id={chat_id}"
                )

        if not chat_id:
            logger.warning(
                f"[CrossChannel] Channel '{target_channel}' is configured but no chat_id found. "
                f"Send at least one message through this channel first."
            )
            return None, None

        return adapter, chat_id

    async def _deliver_artifacts_cross_channel(self, params: dict, target_channel: str) -> str:
        """
        跨通道发送附件：解析 target_channel 获取 adapter+chat_id，
        然后复用 _send_file/_send_image/_send_voice 方法发送。
        """
        import hashlib
        import json
        import re

        adapter, chat_id = self._resolve_target_channel(target_channel)
        if not adapter or not chat_id:
            return json.dumps(
                {
                    "ok": False,
                    "error": f"channel_resolve_failed:{target_channel}",
                    "error_code": "channel_resolve_failed",
                    "hint": (
                        f"无法解析通道 '{target_channel}'。"
                        "请确认该通道已配置、适配器正在运行，且至少有过一次会话。"
                    ),
                    "receipts": [],
                },
                ensure_ascii=False,
            )

        artifacts = params.get("artifacts") or []
        receipts = []

        for idx, art in enumerate(artifacts):
            art_type = (art or {}).get("type", "")
            path = (art or {}).get("path", "")
            caption = (art or {}).get("caption", "") or ""
            name = (art or {}).get("name", "") or ""

            size = None
            sha256 = None
            try:
                p = Path(path)
                if p.exists() and p.is_file():
                    size = p.stat().st_size
                    h = hashlib.sha256()
                    with p.open("rb") as f:
                        for chunk in iter(lambda: f.read(1024 * 1024), b""):
                            h.update(chunk)
                    sha256 = h.hexdigest()
            except Exception:
                pass

            receipt: dict[str, Any] = {
                "index": idx,
                "type": art_type,
                "path": path,
                "status": "failed",
                "error_code": "",
                "name": name,
                "size": size,
                "sha256": sha256,
                "channel": target_channel,
            }

            try:
                if not art_type or not path:
                    receipt["error"] = "missing_type_or_path"
                    receipt["error_code"] = "missing_type_or_path"
                elif art_type == "voice":
                    msg = await self._send_voice(adapter, chat_id, path, caption, target_channel)
                    receipt["status"] = "delivered" if msg.startswith("✅") else "failed"
                    receipt["message"] = msg
                    m = re.search(r"message_id=([^)]+)\)", msg)
                    if m:
                        receipt["message_id"] = m.group(1)
                    if receipt["status"] != "delivered":
                        receipt["error_code"] = "send_failed"
                elif art_type == "image":
                    msg = await self._send_image(
                        adapter, chat_id, path, caption, target_channel,
                    )
                    receipt["status"] = "delivered" if msg.startswith("✅") else "failed"
                    receipt["message"] = msg
                    m = re.search(r"message_id=([^)]+)\)", msg)
                    if m:
                        receipt["message_id"] = m.group(1)
                    if receipt["status"] != "delivered":
                        receipt["error_code"] = "send_failed"
                elif art_type == "file":
                    msg = await self._send_file(adapter, chat_id, path, caption, target_channel)
                    receipt["status"] = "delivered" if msg.startswith("✅") else "failed"
                    receipt["message"] = msg
                    m = re.search(r"message_id=([^)]+)\)", msg)
                    if m:
                        receipt["message_id"] = m.group(1)
                    if receipt["status"] != "delivered":
                        receipt["error_code"] = "send_failed"
                else:
                    receipt["error"] = f"unsupported_type:{art_type}"
                    receipt["error_code"] = "unsupported_type"
            except Exception as e:
                receipt["error"] = str(e)
                receipt["error_code"] = "exception"
                logger.error(f"[CrossChannel] Failed to send artifact to {target_channel}: {e}")

            receipts.append(receipt)

        ok = (
            all(r.get("status") in ("delivered", "skipped") for r in receipts)
            if receipts
            else False
        )
        logger.info(
            f"[CrossChannel] deliver_artifacts to {target_channel}: "
            f"{sum(1 for r in receipts if r.get('status') == 'delivered')}/{len(receipts)} delivered"
        )
        return json.dumps(
            {"ok": ok, "channel": target_channel, "receipts": receipts},
            ensure_ascii=False,
            indent=2,
        )

    async def _deliver_artifacts_desktop(self, params: dict) -> str:
        """
        Desktop mode: instead of sending via IM adapter, return file URLs
        so the desktop frontend can display them inline.

        Optionally archives files to output directory if configured.
        """
        import json
        import shutil
        import urllib.parse

        from ...config import settings

        artifacts = params.get("artifacts") or []
        receipts = []

        # 获取归档配置
        auto_archive = getattr(settings, 'auto_archive_to_output', False)
        output_dir = Path(getattr(settings, 'output_directory', 'data/output'))

        for idx, art in enumerate(artifacts):
            art_type = (art or {}).get("type", "")
            path_str = (art or {}).get("path", "")
            caption = (art or {}).get("caption", "") or ""
            name = (art or {}).get("name", "") or ""

            if not path_str:
                receipts.append({
                    "index": idx,
                    "status": "error",
                    "error": "missing_path",
                })
                continue

            p = Path(path_str)
            if not p.exists() or not p.is_file():
                receipts.append({
                    "index": idx,
                    "status": "error",
                    "error": f"file_not_found: {path_str}",
                })
                continue

            # Build a URL that the desktop frontend can use via /api/files endpoint
            abs_path = str(p.resolve())
            file_url = f"/api/files?path={urllib.parse.quote(abs_path, safe='')}"
            size = p.stat().st_size

            # 可选：归档到 output 目录
            archived_path = None
            if auto_archive:
                try:
                    output_dir.mkdir(parents=True, exist_ok=True)
                    archive_target = output_dir / p.name

                    # 避免重名
                    if archive_target.exists():
                        stem = p.stem
                        suffix = p.suffix
                        counter = 1
                        while archive_target.exists():
                            archive_target = output_dir / f"{stem}_{counter}{suffix}"
                            counter += 1

                    shutil.copy2(p, archive_target)
                    archived_path = str(archive_target)
                    logger.info(f"[DeliverArtifacts] Archived to: {archived_path}")
                except Exception as e:
                    logger.warning(f"[DeliverArtifacts] Archive failed: {e}")

            receipts.append({
                "index": idx,
                "status": "delivered",
                "type": art_type,
                "path": str(p.resolve()),
                "file_url": file_url,
                "archived_path": archived_path,
                "caption": caption,
                "name": name or p.name,
                "size": size,
                "channel": "desktop",
            })

        # 构建返回结果
        result = {
            "ok": all(r.get("status") == "delivered" for r in receipts),
            "channel": "desktop",
            "receipts": receipts,
            "hint": "Desktop mode: files are served via /api/files/ endpoint. "
                    "Frontend should display images inline using the file_url.",
        }

        if auto_archive:
            archived_count = sum(1 for r in receipts if r.get("archived_path"))
            result["archived"] = archived_count
            result["archive_dir"] = str(output_dir)

        return json.dumps(result, ensure_ascii=False, indent=2)

    async def _deliver_artifacts(self, params: dict) -> str:
        """
        统一交付入口：显式 manifest 交付附件，并返回回执 JSON。
        """
        import hashlib
        import json
        import re

        adapter, chat_id, channel, reply_to, channel_user_id = self._get_adapter_and_chat_id()
        if not adapter:
            if channel:
                return json.dumps(
                    {
                        "ok": False,
                        "error": f"adapter_not_found:{channel}",
                        "error_code": "adapter_not_found",
                        "receipts": [],
                    },
                    ensure_ascii=False,
                )
            return json.dumps(
                {
                    "ok": False,
                    "error": "missing_gateway_or_message_context",
                    "error_code": "missing_context",
                    "receipts": [],
                },
                ensure_ascii=False,
            )

        artifacts = params.get("artifacts") or []
        receipts = []

        # 会话内去重（仅运行时有效，不落盘）
        session = getattr(self.agent, "_current_session", None)
        dedupe_set: set[str] = set()
        try:
            if session and hasattr(session, "get_metadata"):
                dedupe_set = set(session.get_metadata("_delivered_dedupe_keys") or [])
        except Exception:
            dedupe_set = set()

        for idx, art in enumerate(artifacts):
            art_type = (art or {}).get("type", "")
            path = (art or {}).get("path", "")
            caption = (art or {}).get("caption", "") or ""
            dedupe_key = (art or {}).get("dedupe_key", "") or ""
            mime = (art or {}).get("mime", "") or ""
            name = (art or {}).get("name", "") or ""

            size = None
            sha256 = None
            try:
                p = Path(path)
                if p.exists() and p.is_file():
                    size = p.stat().st_size
                    h = hashlib.sha256()
                    with p.open("rb") as f:
                        for chunk in iter(lambda: f.read(1024 * 1024), b""):
                            h.update(chunk)
                    sha256 = h.hexdigest()
            except Exception:
                pass

            if not dedupe_key and sha256:
                dedupe_key = f"{art_type}:{sha256}"
            elif not dedupe_key and path:
                dedupe_key = f"{art_type}:{hashlib.sha1((path + '|' + caption).encode('utf-8', errors='ignore')).hexdigest()[:12]}"
            receipt = {
                "index": idx,
                "type": art_type,
                "path": path,
                "status": "failed",
                "error_code": "",
                "name": name,
                "mime": mime,
                "size": size,
                "sha256": sha256,
                "dedupe_key": dedupe_key,
            }
            try:
                if not art_type or not path:
                    receipt["error"] = "missing_type_or_path"
                    receipt["error_code"] = "missing_type_or_path"
                elif dedupe_key and dedupe_key in dedupe_set:
                    receipt["status"] = "skipped"
                    receipt["error"] = "deduped"
                    receipt["error_code"] = "deduped"
                elif art_type == "voice":
                    msg = await self._send_voice(adapter, chat_id, path, caption, channel)
                    receipt["status"] = "delivered" if msg.startswith("✅") else "failed"
                    receipt["message"] = msg
                    m = re.search(r"message_id=([^)]+)\)", msg)
                    if m:
                        receipt["message_id"] = m.group(1)
                    if receipt["status"] != "delivered":
                        receipt["error_code"] = "send_failed"
                elif art_type == "image":
                    msg = await self._send_image(
                        adapter, chat_id, path, caption, channel,
                        reply_to=reply_to, channel_user_id=channel_user_id,
                    )
                    receipt["status"] = "delivered" if msg.startswith("✅") else "failed"
                    receipt["message"] = msg
                    m = re.search(r"message_id=([^)]+)\)", msg)
                    if m:
                        receipt["message_id"] = m.group(1)
                    if receipt["status"] != "delivered":
                        receipt["error_code"] = "send_failed"
                elif art_type == "file":
                    msg = await self._send_file(adapter, chat_id, path, caption, channel)
                    receipt["status"] = "delivered" if msg.startswith("✅") else "failed"
                    receipt["message"] = msg
                    m = re.search(r"message_id=([^)]+)\)", msg)
                    if m:
                        receipt["message_id"] = m.group(1)
                    if receipt["status"] != "delivered":
                        receipt["error_code"] = "send_failed"
                else:
                    receipt["error"] = f"unsupported_type:{art_type}"
                    receipt["error_code"] = "unsupported_type"
            except Exception as e:
                receipt["error"] = str(e)
                receipt["error_code"] = "exception"
            receipts.append(receipt)

            if receipt.get("status") == "delivered" and dedupe_key:
                dedupe_set.add(dedupe_key)

        # 保存回 session metadata（下划线开头：不落盘，仅运行时）
        try:
            if session and hasattr(session, "set_metadata"):
                session.set_metadata("_delivered_dedupe_keys", list(dedupe_set))
        except Exception:
            pass

        ok = (
            all(r.get("status") in ("delivered", "skipped") for r in receipts)
            if receipts
            else False
        )
        result_json = json.dumps({"ok": ok, "receipts": receipts}, ensure_ascii=False, indent=2)

        # 进度事件由网关统一发送（节流/合并）
        try:
            session = getattr(self.agent, "_current_session", None)
            gateway = (
                session.get_metadata("_gateway")
                if session and hasattr(session, "get_metadata")
                else None
            )
            if gateway and hasattr(gateway, "emit_progress_event"):
                delivered = sum(1 for r in receipts if r.get("status") == "delivered")
                total = len(receipts)
                await gateway.emit_progress_event(
                    session, f"📦 附件交付回执：{delivered}/{total} delivered"
                )
        except Exception as e:
            logger.warning(f"Failed to emit deliver progress: {e}")

        return result_json

    def _is_image_file(self, file_path: str) -> bool:
        """检测文件是否是图片"""
        image_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
        return Path(file_path).suffix.lower() in image_extensions

    async def _send_text(
        self, adapter: "ChannelAdapter", chat_id: str, text: str, channel: str
    ) -> str:
        """发送文本消息"""
        message_id = await adapter.send_text(chat_id, text)
        logger.info(f"[IM] Sent text to {channel}:{chat_id}")
        return f"✅ 已发送消息 (message_id={message_id})"

    async def _send_file(
        self, adapter: "ChannelAdapter", chat_id: str, file_path: str, caption: str, channel: str
    ) -> str:
        """发送文件"""
        # 检查文件是否存在
        if not Path(file_path).exists():
            return f"❌ 文件不存在: {file_path}"

        try:
            message_id = await adapter.send_file(chat_id, file_path, caption)
            logger.info(f"[IM] Sent file to {channel}:{chat_id}: {file_path}")
            return f"✅ 已发送文件: {file_path} (message_id={message_id})"
        except NotImplementedError:
            return f"❌ 当前平台 ({channel}) 不支持发送文件"

    async def _send_image(
        self,
        adapter: "ChannelAdapter",
        chat_id: str,
        image_path: str,
        caption: str,
        channel: str,
        reply_to: str | None = None,
        channel_user_id: str | None = None,
    ) -> str:
        """发送图片"""
        # 检查文件是否存在
        if not Path(image_path).exists():
            return f"❌ 图片不存在: {image_path}"

        # 优先使用 send_image，失败则降级到 send_file
        # 将 channel_user_id 通过 metadata 传递，避免直接 kwarg 导致
        # 未重写 send_image 的适配器（飞书/QQ/Telegram）在构造 OutgoingMessage 时报错
        send_kwargs: dict = {"reply_to": reply_to}
        if channel_user_id:
            send_kwargs["metadata"] = {"channel_user_id": channel_user_id}
        try:
            message_id = await adapter.send_image(
                chat_id, image_path, caption,
                **send_kwargs,
            )
            logger.info(f"[IM] Sent image to {channel}:{chat_id}: {image_path}")
            return f"✅ 已发送图片: {image_path} (message_id={message_id})"
        except NotImplementedError:
            pass
        except Exception as e:
            logger.warning(f"[IM] send_image failed for {channel}: {e}")
            # 非 NotImplementedError（如 stream 过期、图片处理失败）→ 降级到 send_file

        # 降级：以文件形式发送图片
        try:
            message_id = await adapter.send_file(chat_id, image_path, caption)
            logger.info(f"[IM] Sent image as file to {channel}:{chat_id}: {image_path}")
            return f"✅ 已发送图片(作为文件): {image_path} (message_id={message_id})"
        except NotImplementedError:
            return f"❌ 当前平台 ({channel}) 不支持发送图片"

    async def _send_voice(
        self, adapter: "ChannelAdapter", chat_id: str, voice_path: str, caption: str, channel: str
    ) -> str:
        """发送语音"""
        # 检查文件是否存在
        if not Path(voice_path).exists():
            return f"❌ 语音文件不存在: {voice_path}"

        # 优先使用 send_voice，失败则降级到 send_file
        try:
            message_id = await adapter.send_voice(chat_id, voice_path, caption)
            logger.info(f"[IM] Sent voice to {channel}:{chat_id}: {voice_path}")
            return f"✅ 已发送语音: {voice_path} (message_id={message_id})"
        except NotImplementedError:
            pass

        # 降级：以文件形式发送语音
        try:
            message_id = await adapter.send_file(chat_id, voice_path, caption)
            logger.info(f"[IM] Sent voice as file to {channel}:{chat_id}: {voice_path}")
            return f"✅ 已发送语音(作为文件): {voice_path} (message_id={message_id})"
        except NotImplementedError:
            return f"❌ 当前平台 ({channel}) 不支持发送语音"

    def _get_voice_file(self, params: dict) -> str:
        """获取语音文件路径"""
        from ...core.im_context import get_im_session

        session = get_im_session()

        # 优先从 pending_voices 获取（转写失败时设置）
        pending_voices = session.get_metadata("pending_voices")
        if pending_voices and len(pending_voices) > 0:
            voice = pending_voices[0]
            local_path = voice.get("local_path")
            if local_path and Path(local_path).exists():
                return f"语音文件路径: {local_path}"

        # 兜底从 pending_audio 获取（转写成功时也会存储原始音频路径）
        pending_audio = session.get_metadata("pending_audio")
        if pending_audio and len(pending_audio) > 0:
            audio = pending_audio[0]
            local_path = audio.get("local_path")
            if local_path and Path(local_path).exists():
                transcription = audio.get("transcription")
                info = f"语音文件路径: {local_path}"
                if transcription:
                    info += f"\n已转写文字: {transcription}"
                return info

        return "❌ 当前消息没有语音文件"

    def _get_image_file(self, params: dict) -> str:
        """获取图片文件路径"""
        from ...core.im_context import get_im_session

        session = get_im_session()

        # 从 session metadata 获取图片信息
        pending_images = session.get_metadata("pending_images")
        if pending_images and len(pending_images) > 0:
            image = pending_images[0]
            local_path = image.get("local_path")
            if local_path and Path(local_path).exists():
                return f"图片文件路径: {local_path}"

        return "❌ 当前消息没有图片文件"

    async def _get_chat_history(self, params: dict) -> str:
        """获取聊天历史"""
        from ...core.im_context import get_im_session

        session = get_im_session()
        limit = params.get("limit", 20)

        # 从 session context 获取消息历史
        messages = session.context.get_messages(limit=limit)

        if not messages:
            return "没有聊天历史"

        output = f"最近 {len(messages)} 条消息:\n\n"
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if isinstance(content, str):
                output += f"[{role}] {content[:1000]}{'...' if len(content) > 1000 else ''}\n"
            else:
                output += f"[{role}] [复杂内容]\n"

        return output


def create_handler(agent: "Agent"):
    """创建 IM 通道处理器"""
    handler = IMChannelHandler(agent)
    return handler.handle
