"""
SmartGuard - 多模态反诈智能助手
基于大语言模型的智能反诈系统
"""

__version__ = "1.0.0"
__author__ = "SmartGuard Team"

from .core.agent import AntiFraudAgent
from .core.prompts import PromptEngine
from .core.memory import ConversationMemory
from .core.decision import RiskDecisionEngine

__all__ = [
    "AntiFraudAgent",
    "PromptEngine",
    "ConversationMemory",
    "RiskDecisionEngine",
]
