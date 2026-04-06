"""
对话记忆模块
实现长短期记忆机制，支持用户行为画像构建
"""

import json
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from collections import deque
from datetime import datetime


@dataclass
class Message:
    """消息结构"""
    role: str  # user, assistant, system
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "metadata": self.metadata
        }


@dataclass
class UserProfile:
    """用户画像"""
    user_id: str
    age_group: str = "unknown"  # elderly, adult, minor
    gender: str = "unknown"
    occupation: str = "unknown"
    risk_history_count: int = 0
    risk_preference: str = "normal"  # conservative, normal, aggressive
    guardians: List[Dict] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    conversation_count: int = 0
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'UserProfile':
        return cls(**data)
    
    def update(self, **kwargs):
        """更新画像字段"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.updated_at = time.time()


class ConversationMemory:
    """对话记忆管理器"""
    
    # 短期记忆配置
    SHORT_TERM_MAX_SIZE = 20  # 最近20条对话
    SHORT_TERM_TTL = 3600 * 24  # 24小时过期
    
    # 长期记忆配置
    LONG_TERM_MAX_SIZE = 1000  # 最多保留1000条重要记忆
    SUMMARY_INTERVAL = 10  # 每10条对话生成一次摘要
    
    def __init__(self, user_id: str):
        """初始化记忆管理器"""
        self.user_id = user_id
        self.short_term: deque = deque(maxlen=self.SHORT_TERM_MAX_SIZE)
        self.long_term: List[Dict] = []
        self.summaries: List[Dict] = []
        self.current_session_start = time.time()
        
        # 用户画像
        self.user_profile = UserProfile(user_id=user_id)
    
    def add_message(self, role: str, content: str, 
                   metadata: Optional[Dict] = None) -> Message:
        """添加消息到记忆"""
        message = Message(
            role=role,
            content=content,
            metadata=metadata or {}
        )
        
        self.short_term.append(message)
        
        # 检查是否需要生成摘要
        if len(self.short_term) % self.SUMMARY_INTERVAL == 0:
            self._generate_summary()
        
        # 如果是用户消息，更新对话计数
        if role == "user":
            self.user_profile.conversation_count += 1
        
        return message
    
    def get_recent_messages(self, count: int = 10) -> List[Message]:
        """获取最近的对话"""
        messages = list(self.short_term)[-count:]
        return messages
    
    def get_context_for_llm(self, max_messages: int = 10) -> str:
        """获取用于LLM的上下文"""
        recent = self.get_recent_messages(max_messages)
        
        context_parts = []
        for msg in recent:
            role_name = "用户" if msg.role == "user" else "助手"
            context_parts.append(f"{role_name}: {msg.content}")
        
        # 添加摘要（如果有）
        if self.summaries:
            latest_summary = self.summaries[-1]
            context_parts.insert(0, f"【对话摘要】{latest_summary['summary']}")
        
        return "\n\n".join(context_parts)
    
    def _generate_summary(self):
        """生成对话摘要"""
        if len(self.short_term) < 3:
            return
        
        # 简单实现：提取关键信息
        recent_messages = list(self.short_term)[-self.SUMMARY_INTERVAL:]
        content_summary = " ".join([m.content[:50] for m in recent_messages])
        
        summary = {
            "timestamp": time.time(),
            "message_count": len(recent_messages),
            "summary": content_summary[:200],
            "keywords": self._extract_keywords(content_summary)
        }
        
        self.summaries.append(summary)
        
        # 检查是否有风险信息需要存入长期记忆
        self._check_and_store_risk_memory(recent_messages)
    
    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词"""
        # 简单的关键词提取
        keywords = []
        risk_words = ["转账", "汇款", "投资", "密码", "验证码", "账户"]
        
        for word in risk_words:
            if word in text:
                keywords.append(word)
        
        return keywords[:5]
    
    def _check_and_store_risk_memory(self, messages: List[Message]):
        """检查并存储风险记忆"""
        for msg in messages:
            metadata = msg.metadata
            if metadata.get("risk_level", 0) >= 2:
                risk_memory = {
                    "timestamp": msg.timestamp,
                    "content": msg.content,
                    "risk_level": metadata.get("risk_level"),
                    "risk_type": metadata.get("risk_type"),
                    "action_taken": metadata.get("action_taken")
                }
                
                self.long_term.append(risk_memory)
                
                # 限制长期记忆大小
                if len(self.long_term) > self.LONG_TERM_MAX_SIZE:
                    self.long_term.pop(0)
                
                # 更新用户画像
                self.user_profile.risk_history_count += 1
    
    def get_user_profile_context(self) -> Dict:
        """获取用户画像上下文"""
        return {
            "user_profile": {
                "age_group": self.user_profile.age_group,
                "occupation": self.user_profile.occupation,
                "risk_history_count": self.user_profile.risk_history_count,
                "risk_preference": self.user_profile.risk_preference,
                "conversation_count": self.user_profile.conversation_count
            },
            "recent_risks": self.long_term[-5:] if self.long_term else [],
            "context_summary": self.summaries[-1]["summary"] if self.summaries else ""
        }
    
    def update_profile(self, **kwargs):
        """更新用户画像"""
        self.user_profile.update(**kwargs)
    
    def add_guardian(self, name: str, phone: str, relationship: str):
        """添加监护人"""
        guardian = {
            "name": name,
            "phone": phone,
            "relationship": relationship,
            "added_at": time.time()
        }
        
        # 避免重复添加
        existing_phones = [g["phone"] for g in self.user_profile.guardians]
        if phone not in existing_phones:
            self.user_profile.guardians.append(guardian)
            self.user_profile.updated_at = time.time()
    
    def to_dict(self) -> Dict:
        """序列化为字典"""
        return {
            "user_id": self.user_id,
            "short_term": [m.to_dict() for m in self.short_term],
            "long_term": self.long_term,
            "summaries": self.summaries,
            "user_profile": self.user_profile.to_dict(),
            "session_start": self.current_session_start
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ConversationMemory':
        """从字典恢复"""
        memory = cls(user_id=data["user_id"])
        memory.short_term = deque([
            Message(**m) for m in data.get("short_term", [])
        ], maxlen=cls.SHORT_TERM_MAX_SIZE)
        memory.long_term = data.get("long_term", [])
        memory.summaries = data.get("summaries", [])
        memory.user_profile = UserProfile.from_dict(data.get("user_profile", {}))
        memory.current_session_start = data.get("session_start", time.time())
        return memory
    
    def clear_short_term(self):
        """清除短期记忆（新会话）"""
        self.short_term.clear()
        self.current_session_start = time.time()
