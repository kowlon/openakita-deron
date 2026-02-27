"""
OpenAkita 自我进化模块
"""

from .analyzer import NeedAnalyzer
from .generator import SkillGenerator
from .installer import AutoInstaller
from .log_analyzer import ErrorPattern, LogAnalyzer, LogEntry
from .self_check import SelfChecker
from .models import (
    ExecutionStatus,
    StepType,
    OutcomeLabel,
    ExecutionStep,
    ExecutionTrace,
    PatternObservation,
    EvolutionProposal,
)

__all__ = [
    "NeedAnalyzer",
    "AutoInstaller",
    "SkillGenerator",
    "SelfChecker",
    "LogAnalyzer",
    "LogEntry",
    "ErrorPattern",
    # 新增模型
    "ExecutionStatus",
    "StepType",
    "OutcomeLabel",
    "ExecutionStep",
    "ExecutionTrace",
    "PatternObservation",
    "EvolutionProposal",
]
