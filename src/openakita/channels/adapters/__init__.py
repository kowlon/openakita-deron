"""
IM 通道适配器（企业级）

保留的平台:
- Telegram
- 飞书
- 企业微信（智能机器人）
- 钉钉

已移除（消费者端）:
- OneBot (通用协议)
- QQ 官方机器人
"""

from .dingtalk import DingTalkAdapter
from .feishu import FeishuAdapter
from .telegram import TelegramAdapter
from .wework_bot import WeWorkBotAdapter

__all__ = [
    "TelegramAdapter",
    "FeishuAdapter",
    "WeWorkBotAdapter",
    "DingTalkAdapter",
]
