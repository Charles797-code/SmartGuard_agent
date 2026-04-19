"""
对话历史API路由
支持对话持久化、多会话管理
"""

import json
import time
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.services.conversation_service import ConversationService
from src.api.auth import get_current_user, UserInfo

router = APIRouter(prefix="/api/v1/conversations", tags=["对话历史"])


# ==================== 请求/响应模型 ====================

class MessageInput(BaseModel):
    role: str
    content: str
    mode: str = "risk"
    metadata: Optional[dict] = None


class SendMessageRequest(BaseModel):
    role: str
    content: str
    mode: str = "risk"
    metadata: Optional[dict] = None


# ==================== 会话管理 ====================

@router.get("/sessions")
async def get_sessions(
    current_user: UserInfo = Depends(get_current_user),
    limit: int = 10,
    login_session_id: Optional[str] = Query(None, description="登录会话ID，为空则返回所有会话")
):
    """获取用户的会话列表"""
    service = ConversationService(current_user.id, login_session_id)
    sessions = await service.load_sessions(limit=limit, login_session_id=login_session_id)

    # 返回会话摘要（不含消息详情）
    return {
        "sessions": [
            {
                "session_id": s.get("session_id"),
                "mode": s.get("mode", "risk"),
                "message_count": s.get("message_count", 0),
                "created_at": s.get("created_at"),
                "updated_at": s.get("updated_at"),
                "login_session_id": s.get("login_session_id"),
                "keywords": s.get("keywords", "")
            }
            for s in sessions
        ]
    }


@router.post("/sessions")
async def create_session(
    mode: str = "risk",
    login_session_id: Optional[str] = Query(None, description="登录会话ID"),
    current_user: UserInfo = Depends(get_current_user)
):
    """创建新会话"""
    service = ConversationService(current_user.id, login_session_id)
    session_id = await service.create_session(mode=mode)
    return {"session_id": session_id, "mode": mode, "login_session_id": service.login_session_id}


@router.post("/sessions/{session_id}/switch")
async def switch_session(
    session_id: str,
    current_user: UserInfo = Depends(get_current_user)
):
    """切换当前会话"""
    service = ConversationService(current_user.id)
    session = await service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    await service.set_current_session(session_id)
    return {"session_id": session_id, "mode": session.get("mode", "risk")}


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    current_user: UserInfo = Depends(get_current_user)
):
    """删除会话"""
    service = ConversationService(current_user.id)
    # 清空消息（逻辑删除）
    await service.clear_session(session_id)
    return {"success": True, "message": "会话已清空"}


# ==================== 消息读写 ====================

@router.get("/messages")
async def get_messages(
    session_id: Optional[str] = None,
    mode: Optional[str] = None,
    limit: int = 50,
    current_user: UserInfo = Depends(get_current_user)
):
    """获取会话消息"""
    service = ConversationService(current_user.id)
    messages = await service.get_messages(session_id=session_id, mode=mode, limit=limit)
    return {"messages": messages, "count": len(messages)}


@router.post("/messages")
async def add_message(
    msg: SendMessageRequest,
    current_user: UserInfo = Depends(get_current_user)
):
    """添加消息（由后端主动调用，持久化存储）"""
    service = ConversationService(current_user.id)
    message = await service.add_message(
        role=msg.role,
        content=msg.content,
        mode=msg.mode,
        metadata=msg.metadata
    )
    return {
        "success": True,
        "message": message.to_dict()
    }


@router.get("/messages/all-modes")
async def get_all_mode_messages(
    session_id: Optional[str] = None,
    limit_per_mode: int = 5,
    login_session_id: Optional[str] = Query(None, description="登录会话ID"),
    current_user: UserInfo = Depends(get_current_user)
):
    """获取各模式的消息（用于恢复上下文）"""
    service = ConversationService(current_user.id, login_session_id)
    messages = await service.get_all_mode_messages(
        session_id=session_id,
        limit_per_mode=limit_per_mode,
        login_session_id=login_session_id
    )
    return messages


@router.get("/current-session")
async def get_current_session(
    current_user: UserInfo = Depends(get_current_user)
):
    """获取当前会话ID"""
    service = ConversationService(current_user.id)
    session_id = await service.get_or_create_current_session()
    return {"session_id": session_id}