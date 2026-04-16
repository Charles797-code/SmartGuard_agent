"""
LLM 模块
基于 DashScope API 的 qwen-plus 调用封装
"""

from .qwen_client import (
    QwenLLM,
    QwenConfig,
    create_qwen_client,
)

__all__ = [
    "QwenLLM",
    "QwenConfig",
    "create_qwen_client",
]
