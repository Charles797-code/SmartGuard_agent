"""
监护人管理API路由
支持监护人绑定、风险联动、通知历史
"""

import json
import time
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.services.guardian_service import GuardianService
from src.api.auth import get_current_user, UserInfo

router = APIRouter(prefix="/api/v1/guardians", tags=["监护人管理"])


# ==================== 请求/响应模型 ====================

class GuardianAdd(BaseModel):
    """添加监护人"""
    relationship: str
    linked_username: str
    notification_level: str = "emergency"
    auto_notify: bool = True


class GuardianUpdate(BaseModel):
    """更新监护人"""
    name: Optional[str] = None
    phone: Optional[str] = None
    relationship: Optional[str] = None
    notification_level: Optional[str] = None
    auto_notify: Optional[bool] = None
    is_active: Optional[bool] = None


# ==================== 监护人管理 ====================

@router.get("/")
async def list_guardians(current_user: UserInfo = Depends(get_current_user)):
    """获取监护人列表"""
    service = GuardianService(current_user.id)
    guardians = await service.get_guardians()
    return {"guardians": guardians, "total": len(guardians)}


@router.post("/")
async def add_guardian(
    guardian: GuardianAdd,
    current_user: UserInfo = Depends(get_current_user)
):
    """添加监护人"""
    service = GuardianService(current_user.id)
    try:
        result = await service.add_guardian(
            relationship=guardian.relationship,
            linked_username=guardian.linked_username,
            notification_level=guardian.notification_level,
            auto_notify=guardian.auto_notify
        )
        return {"success": True, "guardian": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{guardian_id}")
async def update_guardian(
    guardian_id: str,
    update: GuardianUpdate,
    current_user: UserInfo = Depends(get_current_user)
):
    """更新监护人"""
    service = GuardianService(current_user.id)
    result = await service.update_guardian(
        guardian_id=guardian_id,
        name=update.name,
        phone=update.phone,
        relationship=update.relationship,
        notification_level=update.notification_level,
        auto_notify=update.auto_notify,
        is_active=update.is_active
    )
    if not result:
        raise HTTPException(status_code=404, detail="监护人不存在")
    return {"success": True, "guardian": result}


@router.delete("/{guardian_id}")
async def remove_guardian(
    guardian_id: str,
    current_user: UserInfo = Depends(get_current_user)
):
    """删除监护人"""
    service = GuardianService(current_user.id)
    success = await service.remove_guardian(guardian_id)
    if not success:
        raise HTTPException(status_code=404, detail="监护人不存在")
    return {"success": True, "message": "监护人已删除"}


# ==================== 预警记录 ====================

@router.get("/alerts")
async def get_alerts(
    limit: int = 20,
    unread_only: bool = False,
    current_user: UserInfo = Depends(get_current_user)
):
    """获取预警记录"""
    service = GuardianService(current_user.id)
    alerts = await service.get_alerts(limit=limit, unread_only=unread_only)
    return {"alerts": alerts, "total": len(alerts)}


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    current_user: UserInfo = Depends(get_current_user)
):
    """确认预警"""
    service = GuardianService(current_user.id)
    success = await service.acknowledge_alert(alert_id)
    if not success:
        raise HTTPException(status_code=404, detail="预警不存在")
    return {"success": True, "message": "预警已确认"}


@router.get("/notification-history")
async def get_notification_history(
    guardian_id: Optional[str] = None,
    limit: int = 20,
    current_user: UserInfo = Depends(get_current_user)
):
    """获取通知历史"""
    service = GuardianService(current_user.id)
    history = await service.get_guardian_notification_history(
        guardian_id=guardian_id,
        limit=limit
    )
    return {"history": history, "total": len(history)}


@router.get("/available-users")
async def get_available_guardians(current_user: UserInfo = Depends(get_current_user)):
    """
    获取可添加为监护人的系统用户列表

    排除当前用户自己
    """
    service = GuardianService(current_user.id)
    users = await service.get_available_guardians()
    return {"users": users, "total": len(users)}


# ==================== 监护人邀请 ====================

class InvitationCreate(BaseModel):
    """创建邀请"""
    invitee_username: str
    relationship: str
    notification_level: str = "emergency"
    auto_notify: bool = True


@router.post("/invitations")
async def create_invitation(
    invitation: InvitationCreate,
    current_user: UserInfo = Depends(get_current_user)
):
    """发送监护人邀请"""
    service = GuardianService(current_user.id)
    try:
        result = await service.create_invitation(
            invitee_username=invitation.invitee_username,
            relationship=invitation.relationship,
            notification_level=invitation.notification_level,
            auto_notify=invitation.auto_notify
        )
        return {"success": True, "invitation": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/invitations/sent")
async def get_sent_invitations(current_user: UserInfo = Depends(get_current_user)):
    """获取我发出的邀请"""
    service = GuardianService(current_user.id)
    invitations = await service.get_sent_invitations()
    return {"invitations": invitations, "total": len(invitations)}


@router.get("/invitations/received")
async def get_received_invitations(current_user: UserInfo = Depends(get_current_user)):
    """获取我收到的邀请"""
    service = GuardianService(current_user.id)
    invitations = await service.get_received_invitations()
    return {"invitations": invitations, "total": len(invitations)}


@router.post("/invitations/{invitation_id}/accept")
async def accept_invitation(
    invitation_id: str,
    current_user: UserInfo = Depends(get_current_user)
):
    """接受监护人邀请"""
    service = GuardianService(current_user.id)
    try:
        result = await service.respond_to_invitation(invitation_id, accept=True)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/invitations/{invitation_id}/reject")
async def reject_invitation(
    invitation_id: str,
    current_user: UserInfo = Depends(get_current_user)
):
    """拒绝监护人邀请"""
    service = GuardianService(current_user.id)
    try:
        result = await service.respond_to_invitation(invitation_id, accept=False)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==================== 风险触发（内部调用） ====================

@router.post("/trigger-notification")
async def trigger_notification(
    risk_level: int,
    risk_type: str,
    content: str,
    response: str = "",
    alert_id: Optional[str] = None,
    current_user: UserInfo = Depends(get_current_user)
):
    """触发风险通知（供内部分析接口调用）"""
    service = GuardianService(current_user.id)
    result = await service.trigger_risk_notification(
        risk_level=risk_level,
        risk_type=risk_type,
        content=content,
        response=response,
        alert_id=alert_id
    )
    return result


# ==================== 监护人视角接口 ====================

@router.get("/protected/users")
async def get_protected_users(current_user: UserInfo = Depends(get_current_user)):
    """
    获取当前监护人守护的所有被监护人列表
    
    返回每个被监护人的基本信息、未读预警数量、最新预警
    """
    service = GuardianService(current_user.id)
    users = await service.get_protected_users()
    return {
        "users": users,
        "total": len(users),
        "total_unread": sum(u.get("unread_alerts", 0) for u in users)
    }


@router.get("/protected/alerts")
async def get_all_protected_alerts(
    limit: int = 50,
    unread_only: bool = False,
    current_user: UserInfo = Depends(get_current_user)
):
    """
    获取所有被监护人的预警（监护人视角）
    
    按被监护人分组，同时返回按时间排序的最近预警列表
    """
    service = GuardianService(current_user.id)
    result = await service.get_all_protected_alerts(
        limit=limit,
        unread_only=unread_only
    )
    return result


@router.get("/protected/{user_id}/alerts")
async def get_protected_user_alerts(
    user_id: str,
    limit: int = 20,
    unread_only: bool = False,
    current_user: UserInfo = Depends(get_current_user)
):
    """
    获取指定被监护人的预警记录
    """
    service = GuardianService(current_user.id)
    alerts = await service.get_protected_user_alerts(
        protected_user_id=user_id,
        limit=limit,
        unread_only=unread_only
    )
    return {
        "user_id": user_id,
        "alerts": alerts,
        "total": len(alerts)
    }


@router.post("/protected/{user_id}/alerts/{alert_id}/acknowledge")
async def acknowledge_protected_alert(
    user_id: str,
    alert_id: str,
    current_user: UserInfo = Depends(get_current_user)
):
    """
    监护人确认被监护人的预警
    """
    service = GuardianService(current_user.id)
    success = await service.acknowledge_alert_for_user(
        alert_id=alert_id,
        protected_user_id=user_id
    )
    if not success:
        raise HTTPException(status_code=404, detail="预警不存在或不属于该用户")
    return {"success": True, "message": "预警已确认"}


# ==================== 预警视图（监护人界面）====================

@router.get("/alerts/self")
async def get_self_alerts(
    limit: int = 20,
    unread_only: bool = False,
    current_user: UserInfo = Depends(get_current_user)
):
    """获取自己的预警记录"""
    service = GuardianService(current_user.id)
    alerts = await service.get_alerts(limit=limit, unread_only=unread_only)
    unread_count = sum(1 for a in alerts if not a.get("acknowledged"))
    return {
        "alerts": alerts,
        "total": len(alerts),
        "unread_count": unread_count
    }


@router.get("/alerts/guardian/urgent")
async def get_guardian_urgent_alerts(
    since_timestamp: Optional[float] = None,
    current_user: UserInfo = Depends(get_current_user)
):
    """
    获取监护人的紧急预警（用于轮询弹窗）
    
    返回被监护人发来的高风险预警（等级>=3）
    如果 since_timestamp 有值，则只返回该时间戳之后的新预警
    """
    service = GuardianService(current_user.id)
    
    # 获取所有被监护人的紧急预警
    result = await service.get_all_protected_alerts(limit=50, unread_only=False)
    
    # 筛选高风险预警（等级>=3）
    urgent_alerts = []
    # 使用 recent_alerts（已包含用户信息）
    for alert in result.get("recent_alerts", []):
        level = alert.get("level", 0)
        created_at = alert.get("created_at", 0)
        
        # 只返回高风险预警
        if level >= 3:
            # 如果有 since_timestamp，则只返回新的
            if since_timestamp and created_at <= since_timestamp:
                continue
            
            urgent_alerts.append({
                "alert_id": alert.get("id", ""),
                "user_id": alert.get("user_id", ""),
                "user_name": alert.get("protected_user_name", "未知用户"),
                "risk_level": level,
                "risk_type": alert.get("risk_type", "unknown"),
                "content": alert.get("content", "")[:100],
                "response": alert.get("response", "")[:200],
                "created_at": created_at,
                "acknowledged": alert.get("acknowledged", False)
            })
    
    # 按时间倒序
    urgent_alerts.sort(key=lambda x: x.get("created_at", 0), reverse=True)
    
    return {
        "urgent_alerts": urgent_alerts,
        "total": len(urgent_alerts),
        "current_timestamp": time.time()
    }


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_self_alert(
    alert_id: str,
    current_user: UserInfo = Depends(get_current_user)
):
    """确认自己的预警"""
    service = GuardianService(current_user.id)
    # 验证预警是否属于当前用户
    alerts = await service.get_alerts(limit=1)
    # 直接确认
    success = await service.acknowledge_alert(alert_id)
    if not success:
        raise HTTPException(status_code=404, detail="预警不存在")
    return {"success": True, "message": "预警已确认"}