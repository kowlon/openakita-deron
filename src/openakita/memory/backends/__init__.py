"""
Memory Backends Module

This module provides backend adapters for the Memory system:
- LegacyMemoryBackend: Wraps existing Memory class for backward compatibility
"""

from openakita.memory.backends.legacy_adapter import LegacyMemoryBackend

__all__ = [
    "LegacyMemoryBackend",
]
