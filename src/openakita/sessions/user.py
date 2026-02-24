"""
用户管理器

管理用户信息和偏好设置
"""
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class UserManager:
    """
    用户管理器
    """

    def __init__(self, storage_path: Path):
        """
        Args:
            storage_path: 用户数据存储目录
        """
        self.storage_path = storage_path
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._users: dict[str, Any] = {}
