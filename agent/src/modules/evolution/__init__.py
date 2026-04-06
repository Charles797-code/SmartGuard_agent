"""
自适应进化模块
支持智能体知识的实时扩充和自适应学习
"""

from .learner import KnowledgeLearner
from .updater import KnowledgeUpdater

__all__ = [
    "KnowledgeLearner",
    "KnowledgeUpdater",
]
