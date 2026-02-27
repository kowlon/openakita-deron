"""
能力模块

该模块为 Agent 系统提供统一的能力管理框架：

- CapabilityType: 能力类型枚举
- CapabilityMeta: 能力元数据
- CapabilityRegistry: 能力注册表
- CapabilityAdapter: 能力适配器基类
- CapabilityExecutor: 统一执行器

使用方式：
    from openakita.capability import (
        CapabilityType,
        CapabilityMeta,
        CapabilityRegistry,
        CapabilityAdapter,
    )
"""
from __future__ import annotations

from .types import (
    CapabilityCategory,
    CapabilityMeta,
    CapabilityStatus,
    CapabilityType,
)


__all__ = [
    # Types
    "CapabilityType",
    "CapabilityStatus",
    "CapabilityMeta",
    "CapabilityCategory",
    # Registry (will be added later)
    # Adapters (will be added later)
]