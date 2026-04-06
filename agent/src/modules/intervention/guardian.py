"""
监护人联动模块
实现监护人管理、紧急通知、远程干预等功能
"""

import time
import json
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Guardian:
    """监护人信息"""
    guardian_id: str
    user_id: str
    name: str
    phone: str
    relationship: str
    priority: int = 1  # 优先级，1最高
    is_active: bool = True
    notification_enabled: bool = True
    notification_types: List[str] = field(default_factory=lambda: ["emergency", "high_risk"])
    created_at: float = field(default_factory=time.time)
    last_notified: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "guardian_id": self.guardian_id,
            "user_id": self.user_id,
            "name": self.name,
            "phone": self._mask_phone(self.phone),
            "relationship": self.relationship,
            "priority": self.priority,
            "is_active": self.is_active,
            "notification_enabled": self.notification_enabled,
            "notification_types": self.notification_types,
            "created_at": self.created_at,
            "last_notified": self.last_notified,
            "metadata": self.metadata
        }
    
    def _mask_phone(self, phone: str) -> str:
        """隐藏中间位数"""
        if len(phone) >= 7:
            return phone[:3] + "****" + phone[-4:]
        return "****"
    
    def should_notify(self, alert_level: int, risk_type: str) -> bool:
        """判断是否应该通知"""
        if not self.is_active or not self.notification_enabled:
            return False
        
        # 检查通知类型
        if "emergency" in self.notification_types and alert_level >= 4:
            return True
        if "high_risk" in self.notification_types and alert_level >= 3:
            return True
        if risk_type in self.notification_types:
            return True
        
        return False


@dataclass
class Notification:
    """通知记录"""
    notification_id: str
    guardian_id: str
    user_id: str
    alert_id: str
    channel: str  # sms, wechat, phone, app
    content: str
    status: str  # pending, sent, delivered, failed
    sent_at: Optional[float] = None
    delivered_at: Optional[float] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "notification_id": self.notification_id,
            "guardian_id": self.guardian_id,
            "user_id": self.user_id,
            "alert_id": self.alert_id,
            "channel": self.channel,
            "content": self.content[:100] + "..." if len(self.content) > 100 else self.content,
            "status": self.status,
            "sent_at": self.sent_at,
            "delivered_at": self.delivered_at,
            "error_message": self.error_message,
            "metadata": self.metadata
        }


class GuardianNotifier:
    """
    监护人通知器
    
    管理监护人信息，发送紧急通知，
    支持多种通知渠道（短信、微信、电话、应用推送）。
    """
    
    # 通知模板
    NOTIFICATION_TEMPLATES = {
        "emergency": {
            "sms": "【紧急预警】{guardian_name}，您的家人{user_name}可能正在遭遇诈骗，请立即联系确认！诈骗类型：{risk_type}。如已转账，请立即报警。",
            "wechat": "紧急预警通知\n\n{guardian_name}，您好！\n\n您的家人 {user_name} 可能正在遭遇诈骗！\n\n诈骗类型：{risk_type}\n风险等级：紧急\n\n请立即通过电话或其他方式联系 {user_name} 确认情况。\n\n如已发生转账，请立即拨打110报警！\n\n—— SmartGuard智能反诈助手",
            "app": {
                "title": "紧急预警",
                "body": "{guardian_name}，您的家人{user_name}可能正在遭遇{risk_type}，请立即联系确认！",
                "data": {}
            }
        },
        "high_risk": {
            "sms": "【风险提示】{guardian_name}，您的家人{user_name}遇到了潜在的诈骗风险，建议您关注一下。",
            "wechat": "风险提示\n\n{guardian_name}，您好！\n\n您的家人 {user_name} 遇到了潜在的诈骗风险。\n\n诈骗类型：{risk_type}\n风险等级：{risk_level}\n\n建议您适当关注，与 {user_name} 沟通了解情况。\n\n—— SmartGuard智能反诈助手",
            "app": {
                "title": "风险提示",
                "body": "{guardian_name}，您的家人{user_name}遇到了风险，请关注。",
                "data": {}
            }
        }
    }
    
    def __init__(self, storage: Optional[Any] = None,
                 sms_client: Optional[Any] = None,
                 wechat_client: Optional[Any] = None):
        """
        初始化监护人通知器
        
        Args:
            storage: 存储后端
            sms_client: 短信发送客户端
            wechat_client: 微信发送客户端
        """
        self.storage = storage
        self.sms_client = sms_client
        self.wechat_client = wechat_client
        
        self.guardians: Dict[str, List[Guardian]] = {}
        self.notifications: List[Notification] = []
        self.notification_count = 0
        
        self.notification_callbacks: List[Callable] = []
    
    def add_guardian(self, user_id: str, name: str, phone: str,
                    relationship: str, priority: int = 1,
                    notification_types: Optional[List[str]] = None) -> Guardian:
        """
        添加监护人
        
        Args:
            user_id: 用户ID
            name: 监护人姓名
            phone: 监护人电话
            relationship: 关系
            priority: 优先级
            notification_types: 通知类型列表
            
        Returns:
            Guardian: 监护人对象
        """
        guardian_id = f"guardian_{user_id}_{len(self.guardians.get(user_id, []))}_{int(time.time())}"
        
        guardian = Guardian(
            guardian_id=guardian_id,
            user_id=user_id,
            name=name,
            phone=phone,
            relationship=relationship,
            priority=priority,
            notification_types=notification_types or ["emergency", "high_risk"]
        )
        
        if user_id not in self.guardians:
            self.guardians[user_id] = []
        
        self.guardians[user_id].append(guardian)
        
        # 按优先级排序
        self.guardians[user_id].sort(key=lambda g: g.priority)
        
        # 持久化
        if self.storage:
            # self.storage.save_guardian(guardian)
            pass
        
        return guardian
    
    def remove_guardian(self, user_id: str, guardian_id: str) -> bool:
        """移除监护人"""
        if user_id not in self.guardians:
            return False
        
        self.guardians[user_id] = [
            g for g in self.guardians[user_id]
            if g.guardian_id != guardian_id
        ]
        
        return True
    
    def get_guardians(self, user_id: str) -> List[Guardian]:
        """获取监护人列表"""
        return self.guardians.get(user_id, [])
    
    def update_guardian(self, guardian_id: str, **kwargs) -> bool:
        """更新监护人信息"""
        for user_guardians in self.guardians.values():
            for guardian in user_guardians:
                if guardian.guardian_id == guardian_id:
                    for key, value in kwargs.items():
                        if hasattr(guardian, key):
                            setattr(guardian, key, value)
                    return True
        return False
    
    async def notify_guardians(self, user_id: str, user_name: str,
                              alert_level: int, risk_type: str,
                              alert_id: Optional[str] = None,
                              channels: Optional[List[str]] = None) -> List[Notification]:
        """
        通知监护人
        
        Args:
            user_id: 用户ID
            user_name: 用户姓名
            alert_level: 预警等级
            risk_type: 风险类型
            alert_id: 关联的预警ID
            channels: 通知渠道列表
            
        Returns:
            List[Notification]: 通知记录列表
        """
        guardians = self.guardians.get(user_id, [])
        
        if not guardians:
            return []
        
        # 确定通知类型
        notification_type = "emergency" if alert_level >= 4 else "high_risk"
        
        # 确定通知渠道
        if channels is None:
            channels = ["sms", "wechat"] if self.wechat_client else ["sms"]
        
        notifications = []
        
        for guardian in guardians:
            if not guardian.should_notify(alert_level, risk_type):
                continue
            
            for channel in channels:
                notification = await self._send_notification(
                    guardian=guardian,
                    user_name=user_name,
                    notification_type=notification_type,
                    risk_type=risk_type,
                    alert_level=alert_level,
                    channel=channel,
                    alert_id=alert_id
                )
                
                if notification:
                    notifications.append(notification)
                    guardian.last_notified = time.time()
        
        return notifications
    
    async def _send_notification(self, guardian: Guardian, user_name: str,
                                 notification_type: str, risk_type: str,
                                 alert_level: int, channel: str,
                                 alert_id: Optional[str]) -> Optional[Notification]:
        """发送单条通知"""
        self.notification_count += 1
        
        # 获取模板
        templates = self.NOTIFICATION_TEMPLATES.get(notification_type, {})
        template = templates.get(channel, "")
        
        if not template:
            return None
        
        # 格式化内容
        content = template.format(
            guardian_name=guardian.name,
            user_name=user_name,
            risk_type=risk_type,
            risk_level=["安全", "关注", "警告", "危险", "紧急"][alert_level]
        )
        
        notification = Notification(
            notification_id=f"notif_{guardian.guardian_id}_{self.notification_count}_{int(time.time())}",
            guardian_id=guardian.guardian_id,
            user_id=guardian.user_id,
            alert_id=alert_id or "",
            channel=channel,
            content=content,
            status="pending"
        )
        
        # 发送
        try:
            if channel == "sms" and self.sms_client:
                success = await self._send_sms(guardian.phone, content)
                notification.status = "sent" if success else "failed"
                notification.sent_at = time.time()
            
            elif channel == "wechat" and self.wechat_client:
                success = await self._send_wechat(guardian, content, notification_type)
                notification.status = "sent" if success else "failed"
                notification.sent_at = time.time()
            
            elif channel == "app":
                # 应用内推送
                notification.status = "sent"
                notification.sent_at = time.time()
            
            else:
                notification.status = "failed"
                notification.error_message = f"Channel {channel} not configured"
        
        except Exception as e:
            notification.status = "failed"
            notification.error_message = str(e)
        
        # 存储记录
        self.notifications.append(notification)
        
        # 触发回调
        self._trigger_callbacks(notification)
        
        return notification
    
    async def _send_sms(self, phone: str, content: str) -> bool:
        """发送短信"""
        if not self.sms_client:
            return False
        
        try:
            # 实际实现需要调用短信API
            # result = await self.sms_client.send(phone, content)
            # return result.success
            return True
        except Exception:
            return False
    
    async def _send_wechat(self, guardian: Guardian, content: str, 
                          notification_type: str) -> bool:
        """发送微信通知"""
        if not self.wechat_client:
            return False
        
        try:
            # 实际实现需要调用微信API
            # result = await self.wechat_client.send_message(
            #     openid=guardian.metadata.get("wechat_openid"),
            #     content=content,
            #     template_id=guardian.metadata.get("wechat_template_id")
            # )
            # return result.success
            return True
        except Exception:
            return False
    
    def register_notification_callback(self, callback: Callable[[Notification], None]):
        """注册通知回调"""
        self.notification_callbacks.append(callback)
    
    def _trigger_callbacks(self, notification: Notification):
        """触发回调"""
        for callback in self.notification_callbacks:
            try:
                callback(notification)
            except Exception:
                pass
    
    def get_notification_history(self, user_id: Optional[str] = None,
                               guardian_id: Optional[str] = None,
                               limit: int = 50) -> List[Notification]:
        """获取通知历史"""
        notifications = self.notifications
        
        if user_id:
            notifications = [n for n in notifications if n.user_id == user_id]
        
        if guardian_id:
            notifications = [n for n in notifications if n.guardian_id == guardian_id]
        
        # 按时间倒序
        notifications.sort(key=lambda x: x.sent_at or 0, reverse=True)
        
        return notifications[:limit]
    
    def get_statistics(self, user_id: Optional[str] = None) -> Dict:
        """获取统计信息"""
        notifications = self.notifications
        
        if user_id:
            notifications = [n for n in notifications if n.user_id == user_id]
        
        total = len(notifications)
        sent = sum(1 for n in notifications if n.status == "sent")
        failed = sum(1 for n in notifications if n.status == "failed")
        
        channel_counts = {}
        for n in notifications:
            channel_counts[n.channel] = channel_counts.get(n.channel, 0) + 1
        
        return {
            "total_notifications": total,
            "sent": sent,
            "failed": failed,
            "success_rate": sent / total if total > 0 else 0,
            "channel_distribution": channel_counts,
            "guardian_count": len(self.guardians.get(user_id, [])) if user_id else 0
        }
