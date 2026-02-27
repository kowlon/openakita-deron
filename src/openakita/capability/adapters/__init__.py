"""
能力适配器模块

提供统一的能力适配器接口，用于封装不同来源的能力。
"""
from __future__ import annotations

from .base import (
    CapabilityAdapter,
    CapabilityLoadError,
    CapabilityExecutionError,
    ExecutionResult,
)


__all__ = [
    "CapabilityAdapter",
    "CapabilityLoadError",
    "CapabilityExecutionError",
    "ExecutionResult",
]