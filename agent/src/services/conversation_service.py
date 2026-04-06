"""
对话历史持久化管理
支持多会话、多模式（risk/chat/learn）的对话历史存储与恢复
按登录会话划分历史记录
"""

import json
import time
import uuid
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from src.data.database import get_database


@dataclass
class PersistedMessage:
    """持久化消息结构"""
    role: str
    content: str
    timestamp: float
    mode: str = "risk"
    metadata: Dict[str, Any] = None

    def to_dict(self) -> Dict:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "mode": self.mode,
            "metadata": self.metadata or {}
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "PersistedMessage":
        return cls(
            role=d.get("role", "user"),
            content=d.get("content", ""),
            timestamp=d.get("timestamp", time.time()),
            mode=d.get("mode", "risk"),
            metadata=d.get("metadata", {})
        )


class ConversationService:
    """
    对话历史持久化服务

    设计原则：
    - 每个用户有多个登录会话（login_session），每次登录产生一个新的 login_session
    - 每个登录会话内有多个对话会话（session），用于不同模式
    - 同一会话内可以切换 risk/chat/learn 模式，消息按 mode 分离
    - 登录后加载该 login_session 的最近会话，恢复对话上下文
    """

    # 保留最近 N 个会话（超过则归档）
    MAX_RETAIN_SESSIONS = 10
    # 每个会话最多保留消息数
    MAX_MESSAGES_PER_SESSION = 100

    def __init__(self, user_id: str, login_session_id: Optional[str] = None):
        self.user_id = user_id
        self.login_session_id = login_session_id or str(uuid.uuid4())[:12]
        self.db = get_database()
        self._current_session_id: Optional[str] = None
        self._sessions_cache: Dict[str, Dict] = {}

    # ==================== 会话管理 ====================

    async def create_session(self, mode: str = "risk") -> str:
        """创建新会话（属于当前登录会话）"""
        session_id = str(uuid.uuid4())[:12]
        now = time.time()

        session_data = {
            "id": session_id,
            "user_id": self.user_id,
            "session_id": session_id,
            "login_session_id": self.login_session_id,
            "mode": mode,
            "messages": "[]",
            "message_count": 0,
            "created_at": now,
            "updated_at": now
        }

        await self.db.insert("conversations", session_data)
        self._current_session_id = session_id
        self._sessions_cache[session_id] = session_data
        return session_id

    async def get_or_create_current_session(self, mode: str = "risk") -> str:
        """获取当前会话，不存在则创建"""
        if self._current_session_id and self._current_session_id in self._sessions_cache:
            return self._current_session_id

        # 先查找当前登录会话中最近的会话
        sessions = await self.db.query(
            "conversations",
            filters={"user_id": self.user_id, "login_session_id": self.login_session_id},
            limit=1
        )
        # 按 updated_at 降序排序
        sessions.sort(key=lambda x: x.get("updated_at", 0), reverse=True)
        if sessions:
            if "id" in sessions[0]:
                session_id = sessions[0]["id"]
                if "session_id" not in sessions[0]:
                    sessions[0]["session_id"] = session_id
                self._current_session_id = session_id
                self._sessions_cache[session_id] = sessions[0]
                return session_id

        return await self.create_session(mode=mode)

    async def load_sessions(self, limit: int = 10, login_session_id: Optional[str] = None) -> List[Dict]:
        """加载用户的会话列表（不含消息详情）"""
        filters = {"user_id": self.user_id}
        sessions = await self.db.query(
            "conversations",
            filters=filters,
            limit=limit * 3  # 多查一些，后面会过滤
        )
        sessions.sort(key=lambda x: x.get("updated_at", 0), reverse=True)
        
        # 加载用户所有历史会话（不限 login_session）
        # 确保每条记录都有 session_id 字段，并提取关键词
        for s in sessions[:limit]:
            if "session_id" not in s and "id" in s:
                s["session_id"] = s["id"]
            if "session_id" in s:
                self._sessions_cache[s["session_id"]] = s
            # 从消息中提取关键词作为摘要
            s["keywords"] = self._extract_keywords(s)

        return sessions[:limit]

    def _extract_keywords(self, session: Dict) -> str:
        """从会话消息中提取关键词作为摘要"""
        try:
            messages_json = session.get("messages", "[]")
            messages = json.loads(messages_json) if isinstance(messages_json, str) else messages_json
            if not messages:
                return "新会话"
            # 获取前几条用户消息
            user_messages = [m.get("content", "").strip()[:30] for m in messages if m.get("role") == "user" and m.get("content", "").strip()][:2]
            if user_messages:
                return " · ".join(user_messages)
            return "新会话"
        except Exception:
            return "会话"

    async def get_session(self, session_id: str) -> Optional[Dict]:
        """获取指定会话"""
        if session_id in self._sessions_cache:
            return self._sessions_cache[session_id]

        # 首先尝试用 id 字段查询
        sessions = await self.db.query(
            "conversations",
            filters={"id": session_id},
            limit=1
        )
        
        # 如果没找到，用 session_id 字段查询
        if not sessions:
            sessions = await self.db.query(
                "conversations",
                filters={"session_id": session_id},
                limit=1
            )
        
        if sessions:
            # 确保有 session_id 字段
            if "session_id" not in sessions[0] and "id" in sessions[0]:
                sessions[0]["session_id"] = sessions[0]["id"]
            self._sessions_cache[session_id] = sessions[0]
            return sessions[0]
        return None

    async def set_current_session(self, session_id: str):
        """切换当前会话"""
        session = await self.get_session(session_id)
        if session:
            self._current_session_id = session_id

    # ==================== 消息读写 ====================

    async def add_message(
        self,
        role: str,
        content: str,
        mode: str = "risk",
        metadata: Optional[Dict] = None
    ) -> PersistedMessage:
        """添加消息到当前会话"""
        session_id = await self.get_or_create_current_session(mode=mode)
        if not session_id or session_id not in self._sessions_cache:
            # 如果没有session，创建一个新的
            session_id = await self.create_session(mode=mode)
        
        session = self._sessions_cache.get(session_id)
        if not session:
            session = {"messages": "[]", "mode": mode}
        
        messages_json = session.get("messages", "[]")
        try:
            msgs: List[Dict] = json.loads(messages_json)
        except Exception:
            msgs = []

        msg = PersistedMessage(
            role=role,
            content=content,
            timestamp=time.time(),
            mode=mode,
            metadata=metadata or {}
        )
        msgs.append(msg.to_dict())

        # 截断超长会话
        if len(msgs) > self.MAX_MESSAGES_PER_SESSION:
            msgs = msgs[-self.MAX_MESSAGES_PER_SESSION:]

        await self._save_messages(session_id, msgs, mode)
        return msg

    async def get_messages(
        self,
        session_id: Optional[str] = None,
        mode: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """获取会话消息"""
        sid = session_id or self._current_session_id
        if not sid:
            return []

        session = await self.get_session(sid)
        if not session:
            return []

        messages_json = session.get("messages", "[]")
        try:
            messages: List[Dict] = json.loads(messages_json)
        except Exception:
            messages = []

        # 确保每条消息都有 content 字段
        for m in messages:
            if "content" not in m:
                if "text" in m:
                    m["content"] = m["text"]
                elif "response" in m:
                    m["content"] = m["response"]
                else:
                    m["content"] = ""

        if mode:
            messages = [m for m in messages if m.get("mode") == mode]

        return messages[-limit:]

    async def get_all_mode_messages(
        self,
        session_id: Optional[str] = None,
        limit_per_mode: int = 10,
        login_session_id: Optional[str] = None
    ) -> Dict[str, List[Dict]]:
        """
        获取各模式的最近消息，用于恢复上下文
        返回 {"risk": [...], "chat": [...], "learn": [...]}
        """
        # 如果指定了 session_id，直接获取该会话的消息
        if session_id:
            sid = session_id
            session = await self.get_session(sid)
            if not session:
                return {"risk": [], "chat": [], "learn": []}

            messages_json = session.get("messages", "[]")
            try:
                all_messages: List[Dict] = json.loads(messages_json)
            except Exception:
                all_messages = []

            result = {}
            for mode in ["risk", "chat", "learn"]:
                mode_msgs = [m for m in all_messages if m.get("mode") == mode]
                result[mode] = mode_msgs[-limit_per_mode:]
            return result

        # 否则获取当前登录会话中所有会话的最新消息
        ls_id = login_session_id or self.login_session_id
        sessions = await self.load_sessions(limit=20, login_session_id=ls_id)

        if not sessions:
            return {"risk": [], "chat": [], "learn": []}

        # 从所有会话中收集各模式的消息（按时间顺序）
        all_mode_messages = {"risk": [], "chat": [], "learn": []}
        
        # 按 updated_at 时间倒序排列会话
        sessions.sort(key=lambda x: x.get("updated_at", 0), reverse=True)

        for session in sessions:
            messages_json = session.get("messages", "[]")
            try:
                msgs: List[Dict] = json.loads(messages_json)
            except Exception:
                msgs = []

            for mode in ["risk", "chat", "learn"]:
                for m in msgs:
                    if m.get("mode") == mode:
                        # 确保消息有 content 字段
                        msg_content = m.get("content", m.get("text", m.get("response", "")))
                        msg_copy = {
                            "role": m.get("role", "user"),
                            "content": msg_content,
                            "timestamp": m.get("timestamp", session.get("updated_at", 0)),
                            "mode": mode
                        }
                        all_mode_messages[mode].append(msg_copy)

        # 对每个模式的消息按时间排序，取最新的 limit_per_mode 条
        result = {"risk": [], "chat": [], "learn": []}
        for mode in ["risk", "chat", "learn"]:
            # 按时间倒序，取最新的
            sorted_msgs = sorted(all_mode_messages[mode], key=lambda x: x.get("timestamp", 0), reverse=True)
            result[mode] = sorted_msgs[:limit_per_mode]
            # 转换回用户期望的格式（不需要额外的 timestamp）
            result[mode] = [{"role": m["role"], "content": m["content"]} for m in result[mode]]

        return result

    async def clear_session(self, session_id: Optional[str] = None):
        """清空会话消息"""
        sid = session_id or self._current_session_id
        if not sid:
            return
        await self._save_messages(sid, [], session.get("mode", "risk") if (session := self._sessions_cache.get(sid)) else "risk")

    # ==================== 内部方法 ====================

    async def _save_messages(self, session_id: str, messages: List[Dict], mode: str):
        """保存消息到数据库"""
        messages_json = json.dumps(messages, ensure_ascii=False)
        
        # 更新缓存
        if session_id in self._sessions_cache:
            self._sessions_cache[session_id]["messages"] = messages_json
            self._sessions_cache[session_id]["message_count"] = len(messages)
            self._sessions_cache[session_id]["mode"] = mode
            self._sessions_cache[session_id]["updated_at"] = time.time()
        else:
            self._sessions_cache[session_id] = {
                "session_id": session_id,
                "id": session_id,
                "messages": messages_json,
                "message_count": len(messages),
                "mode": mode,
                "updated_at": time.time()
            }

        try:
            # 先尝试更新
            updated = await self.db.update(
                "conversations",
                session_id,
                {
                    "messages": messages_json,
                    "message_count": len(messages),
                    "mode": mode,
                    "updated_at": time.time()
                },
                id_field="id"
            )
            if not updated:
                # 更新失败，尝试插入
                try:
                    await self.db.insert("conversations", {
                        "id": session_id,
                        "session_id": session_id,
                        "user_id": self.user_id,
                        "mode": mode,
                        "messages": messages_json,
                        "message_count": len(messages),
                        "created_at": time.time(),
                        "updated_at": time.time()
                    })
                except Exception as e2:
                    print(f"[ConversationService] 插入消息失败: {e2}", flush=True)
        except Exception as e:
            print(f"[ConversationService] 保存消息失败: {e}", flush=True)
