"""
监护人联动服务
支持将其他注册用户绑定为监护人，风险事件即时通报
"""

import json
import time
import uuid
from typing import Dict, List, Optional, Any
from dataclasses import asdict
from src.data.database import get_database


# 风险等级对应的通知策略
RISK_NOTIFY_STRATEGY = {
    5: {"level": "critical", "channels": ["app", "sms"], "description": "极高风险 - 多渠道立即通知"},
    4: {"level": "emergency", "channels": ["app", "sms"], "description": "高风险 - 立即通知"},
    3: {"level": "high", "channels": ["app"], "description": "中等风险 - 应用内通知"},
    2: {"level": "medium", "channels": [], "description": "低风险 - 仅记录"},
    1: {"level": "low", "channels": [], "description": "关注 - 仅记录"},
    0: {"level": "safe", "channels": [], "description": "安全"},
}


class GuardianService:
    """
    监护人联动服务

    功能：
    - 添加监护人（可绑定为系统用户或手机号）
    - 风险事件触发通知
    - 通知历史记录
    - 监护人管理（编辑/删除/启用禁用）
    """

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.db = get_database()
        self._guardians_cache: Dict[str, List[Dict]] = {}

    # ==================== 监护人管理 ====================

    async def add_guardian(
        self,
        relationship: str,
        linked_username: str,
        notification_level: str = "emergency",
        auto_notify: bool = True
    ) -> Dict:
        """
        添加监护人

        Args:
            relationship: 与用户关系（父母/配偶/子女/其他）
            linked_username: 监护人的系统用户名（必填）
            notification_level: 通知触发等级（emergency/high/medium）
            auto_notify: 是否自动通知

        Returns:
            监护人记录
        """
        now = time.time()

        # 获取监护人用户信息
        users = await self.db.query(
            "users_auth",
            filters={"username": linked_username},
            limit=1
        )
        if not users:
            raise ValueError(f"用户 {linked_username} 不存在")

        guardian_user = users[0]
        guardian_user_id = guardian_user["id"]
        guardian_name = guardian_user.get("username", "未知")
        guardian_phone = str(guardian_user.get("phone") or "")

        # 获取监护人的昵称
        profiles = await self.db.query(
            "user_profiles",
            filters={"user_id": guardian_user_id},
            limit=1
        )
        if profiles:
            nickname = profiles[0].get("nickname", "")
            if nickname:
                guardian_name = nickname

        guardian_id = f"gd_{self.user_id[:8]}_{int(now * 1000)}"

        # 检查是否已存在
        existing = await self.db.query(
            "guardians",
            filters={"user_id": self.user_id, "linked_user_id": guardian_user_id},
            limit=1
        )
        if existing:
            return existing[0]

        data = {
            "id": guardian_id,
            "user_id": self.user_id,
            "linked_user_id": guardian_user_id,
            "name": guardian_name,
            "phone": guardian_phone,
            "relationship": relationship,
            "notification_level": notification_level,
            "is_active": 1,
            "auto_notify": 1 if auto_notify else 0,
            "channels": json.dumps(["app"]),
            "created_at": now
        }

        await self.db.insert("guardians", data)

        # 同步更新用户画像中的 family_protected
        await self._update_family_count()

        result = data.copy()
        result["channels"] = ["app"]
        result["linked_username"] = linked_username
        return result

    async def remove_guardian(self, guardian_id: str) -> bool:
        """删除监护人"""
        guardians = await self.db.query(
            "guardians",
            filters={"id": guardian_id, "user_id": self.user_id},
            limit=1
        )
        if not guardians:
            return False

        cursor = self.db.connection.cursor()
        cursor.execute(
            "DELETE FROM guardians WHERE id = ? AND user_id = ?",
            (guardian_id, self.user_id)
        )
        self.db.connection.commit()

        await self._update_family_count()
        return True

    async def update_guardian(
        self,
        guardian_id: str,
        name: Optional[str] = None,
        phone: Optional[str] = None,
        relationship: Optional[str] = None,
        notification_level: Optional[str] = None,
        auto_notify: Optional[bool] = None,
        is_active: Optional[bool] = None
    ) -> Optional[Dict]:
        """更新监护人信息"""
        guardians = await self.db.query(
            "guardians",
            filters={"id": guardian_id, "user_id": self.user_id},
            limit=1
        )
        if not guardians:
            return None

        update_data = {}
        if name is not None:
            update_data["name"] = name
        if phone is not None:
            update_data["phone"] = phone
        if relationship is not None:
            update_data["relationship"] = relationship
        if notification_level is not None:
            update_data["notification_level"] = notification_level
        if auto_notify is not None:
            update_data["auto_notify"] = 1 if auto_notify else 0
        if is_active is not None:
            update_data["is_active"] = 1 if is_active else 0

        if update_data:
            await self.db.update(
                "guardians",
                guardian_id,
                update_data,
                id_field="id"
            )

        updated = await self.db.query("guardians", filters={"id": guardian_id}, limit=1)
        if updated:
            g = updated[0]
            try:
                g["channels"] = json.loads(g.get("channels", "[]"))
            except Exception:
                g["channels"] = ["app"]
            return g
        return None

    async def get_guardians(self) -> List[Dict]:
        """获取当前用户的所有监护人"""
        guardians = await self.db.query(
            "guardians",
            filters={"user_id": self.user_id},
            limit=50
        )

        # 脱敏手机号
        for g in guardians:
            phone = str(g.get("phone") or "")
            if len(phone) >= 7:
                g["phone_masked"] = phone[:3] + "****" + phone[-4:]
            else:
                g["phone_masked"] = "****"
            g["is_active"] = bool(g.get("is_active", 1))
            g["auto_notify"] = bool(g.get("auto_notify", 1))
            try:
                g["channels"] = json.loads(g.get("channels", "[]"))
            except Exception:
                g["channels"] = ["app"]
            # 如果绑定了用户，获取用户名
            if g.get("linked_user_id"):
                linked_users = await self.db.query(
                    "users_auth",
                    filters={"id": g["linked_user_id"]},
                    limit=1
                )
                if linked_users:
                    g["linked_username"] = linked_users[0].get("username", "")

        return guardians

    # ==================== 风险事件通知 ====================

    async def trigger_risk_notification(
        self,
        risk_level: int,
        risk_type: str,
        content: str,
        response: str = "",
        alert_id: Optional[str] = None
    ) -> Dict:
        """
        触发风险通知

        当检测到风险时调用此方法，根据风险等级决定是否通知监护人

        Args:
            risk_level: 风险等级 0-5
            risk_type: 风险类型（如 police_impersonation）
            content: 用户发送的原始内容
            response: AI 响应内容
            alert_id: 关联的预警ID

        Returns:
            {"notified": bool, "guardians_notified": [], "level": str}
        """
        strategy = RISK_NOTIFY_STRATEGY.get(risk_level, RISK_NOTIFY_STRATEGY[0])

        # 获取需要通知的监护人
        guardians = await self.get_guardians()
        active_guardians = [
            g for g in guardians
            if g.get("is_active") and g.get("auto_notify")
        ]

        if not active_guardians:
            return {
                "notified": False,
                "guardians_notified": [],
                "level": strategy["level"],
                "reason": "无活跃监护人"
            }

        channels = strategy["channels"]

        # 生成通知记录
        now = time.time()
        if not alert_id:
            alert_id = f"alert_{int(now * 1000)}"

        # 存储预警记录
        await self._save_alert(alert_id, risk_level, risk_type, content, response)

        notified_guardians = []
        notification_records = []

        for guardian in active_guardians:
            if not channels:
                continue

            notification = {
                "guardian_id": guardian["id"],
                "guardian_name": guardian["name"],
                "guardian_phone_masked": guardian["phone_masked"],
                "channel": channels[0] if channels else "app",
                "status": "pending",
                "sent_at": now,
                "content_preview": self._build_notification_content(
                    guardian["name"], risk_level, risk_type, strategy["description"]
                )[:50] + "..."
            }

            # 实际发送（这里模拟成功）
            # TODO: 接入真实短信/推送服务
            notification["status"] = "sent"

            notification_records.append(notification)
            notified_guardians.append({
                "name": guardian["name"],
                "phone_masked": guardian["phone_masked"],
                "channel": channels[0] if channels else "app"
            })

        # 更新预警记录
        await self._update_alert_notifications(
            alert_id,
            json.dumps(notification_records, ensure_ascii=False)
        )

        return {
            "notified": len(notified_guardians) > 0,
            "guardians_notified": notified_guardians,
            "level": strategy["level"],
            "strategy": strategy["description"],
            "alert_id": alert_id
        }

    async def get_alerts(self, limit: int = 20, unread_only: bool = False) -> List[Dict]:
        """获取预警历史"""
        filters = {"user_id": self.user_id}
        alerts = await self.db.query("alerts", filters=filters, limit=limit)
        alerts.sort(key=lambda x: x.get("created_at", 0), reverse=True)

        if unread_only:
            alerts = [a for a in alerts if not a.get("acknowledged")]

        for a in alerts:
            a["acknowledged"] = bool(a.get("acknowledged"))
            a["guardian_notified"] = bool(a.get("guardian_notified"))
            try:
                a["guardian_notifications"] = json.loads(a.get("guardian_notifications", "[]"))
            except Exception:
                a["guardian_notifications"] = []

        return alerts

    async def acknowledge_alert(self, alert_id: str) -> bool:
        """确认预警"""
        return await self.db.update(
            "alerts",
            alert_id,
            {"acknowledged": 1, "acknowledged_at": time.time()},
            id_field="id"
        )

    async def get_guardian_notification_history(
        self,
        guardian_id: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict]:
        """获取通知历史"""
        alerts = await self.get_alerts(limit=limit)
        history = []
        for alert in alerts:
            notifications = alert.get("guardian_notifications", [])
            for n in notifications:
                if guardian_id is None or n.get("guardian_id") == guardian_id:
                    history.append({
                        "alert_id": alert.get("id"),
                        "risk_level": alert.get("level"),
                        "risk_type": alert.get("risk_type"),
                        "content_preview": alert.get("message", "")[:80],
                        **n
                    })
        return history

    # ==================== 私有方法 ====================

    async def _save_alert(
        self,
        alert_id: str,
        level: int,
        risk_type: str,
        content: str,
        response: str
    ):
        """保存预警记录"""
        now = time.time()
        data = {
            "id": alert_id,
            "user_id": self.user_id,
            "level": level,
            "risk_type": risk_type,
            "message": content[:200],
            "content": content,
            "response": response,
            "acknowledged": 0,
            "guardian_notified": 0,
            "guardian_notifications": "[]",
            "created_at": now
        }
        await self.db.insert("alerts", data)

    async def _update_alert_notifications(self, alert_id: str, notifications_json: str):
        """更新预警的通知状态"""
        await self.db.update(
            "alerts",
            alert_id,
            {
                "guardian_notified": 1,
                "guardian_notifications": notifications_json
            },
            id_field="id"
        )

    async def _update_family_count(self):
        """更新用户画像中的 family_protected 数量"""
        guardians = await self.get_guardians()
        active_count = sum(1 for g in guardians if g.get("is_active"))

        profiles = await self.db.query(
            "user_profiles",
            filters={"user_id": self.user_id},
            limit=1
        )
        if profiles:
            await self.db.update(
                "user_profiles",
                self.user_id,
                {"family_protected": active_count},
                id_field="user_id"
            )
        else:
            await self.db.insert("user_profiles", {
                "user_id": self.user_id,
                "family_protected": active_count
            })

    # ==================== 监护人邀请管理 ====================

    async def create_invitation(
        self,
        invitee_username: str,
        relationship: str,
        notification_level: str = "emergency",
        auto_notify: bool = True
    ) -> Dict:
        """
        创建监护人邀请

        Args:
            invitee_username: 被邀请人的用户名
            relationship: 与被监护人的关系
            notification_level: 通知触发等级
            auto_notify: 是否自动通知

        Returns:
            邀请记录
        """
        now = time.time()

        # 获取被邀请人信息
        users = await self.db.query(
            "users_auth",
            filters={"username": invitee_username},
            limit=1
        )
        if not users:
            raise ValueError(f"用户 {invitee_username} 不存在")

        invitee = users[0]
        invitee_id = invitee["id"]

        # 不能邀请自己
        if invitee_id == self.user_id:
            raise ValueError("不能邀请自己成为监护人")

        # 检查是否已有邀请待处理
        existing = await self.db.query(
            "guardian_invitations",
            filters={
                "inviter_id": self.user_id,
                "invitee_id": invitee_id,
                "status": "pending"
            },
            limit=1
        )
        if existing:
            raise ValueError("已发送邀请，请等待对方确认")

        # 检查是否已经是监护人
        guardians = await self.db.query(
            "guardians",
            filters={
                "user_id": self.user_id,
                "linked_user_id": invitee_id
            },
            limit=1
        )
        if guardians:
            raise ValueError("该用户已是监护人")

        # 获取被邀请人的昵称
        profiles = await self.db.query(
            "user_profiles",
            filters={"user_id": invitee_id},
            limit=1
        )
        invitee_name = invitee.get("username", "未知")
        if profiles:
            nickname = profiles[0].get("nickname", "")
            if nickname:
                invitee_name = nickname

        invitation_id = f"gi_{self.user_id[:8]}_{int(now * 1000)}"

        data = {
            "id": invitation_id,
            "inviter_id": self.user_id,
            "invitee_id": invitee_id,
            "relationship": relationship,
            "status": "pending",
            "notification_level": notification_level,
            "auto_notify": 1 if auto_notify else 0,
            "created_at": now
        }

        await self.db.insert("guardian_invitations", data)

        result = data.copy()
        result["invitee_name"] = invitee_name
        result["invitee_phone_masked"] = self._mask_phone(invitee.get("phone", ""))

        return result

    async def get_sent_invitations(self) -> List[Dict]:
        """获取我发出的邀请列表"""
        invitations = await self.db.query(
            "guardian_invitations",
            filters={"inviter_id": self.user_id},
            limit=50
        )
        invitations.sort(key=lambda x: x.get("created_at", 0), reverse=True)

        result = []
        for inv in invitations:
            users = await self.db.query(
                "users_auth",
                filters={"id": inv["invitee_id"]},
                limit=1
            )
            user = users[0] if users else {}
            profiles = await self.db.query(
                "user_profiles",
                filters={"user_id": inv["invitee_id"]},
                limit=1
            )
            profile = profiles[0] if profiles else {}
            name = profile.get("nickname", "") or user.get("username", "未知")

            result.append({
                "id": inv["id"],
                "invitee_id": inv["invitee_id"],
                "invitee_name": name,
                "invitee_username": user.get("username", ""),
                "invitee_phone_masked": self._mask_phone(user.get("phone", "")),
                "relationship": inv.get("relationship", ""),
                "status": inv.get("status", "pending"),
                "notification_level": inv.get("notification_level", "emergency"),
                "auto_notify": bool(inv.get("auto_notify", 1)),
                "created_at": inv.get("created_at"),
                "responded_at": inv.get("responded_at")
            })

        return result

    async def get_received_invitations(self) -> List[Dict]:
        """获取我收到的邀请列表"""
        invitations = await self.db.query(
            "guardian_invitations",
            filters={"invitee_id": self.user_id},
            limit=50
        )
        invitations.sort(key=lambda x: x.get("created_at", 0), reverse=True)

        result = []
        for inv in invitations:
            users = await self.db.query(
                "users_auth",
                filters={"id": inv["inviter_id"]},
                limit=1
            )
            user = users[0] if users else {}
            profiles = await self.db.query(
                "user_profiles",
                filters={"user_id": inv["inviter_id"]},
                limit=1
            )
            profile = profiles[0] if profiles else {}
            name = profile.get("nickname", "") or user.get("username", "未知")

            result.append({
                "id": inv["id"],
                "inviter_id": inv["inviter_id"],
                "inviter_name": name,
                "inviter_username": user.get("username", ""),
                "inviter_phone_masked": self._mask_phone(user.get("phone", "")),
                "relationship": inv.get("relationship", ""),
                "status": inv.get("status", "pending"),
                "notification_level": inv.get("notification_level", "emergency"),
                "auto_notify": bool(inv.get("auto_notify", 1)),
                "created_at": inv.get("created_at"),
                "responded_at": inv.get("responded_at")
            })

        return result

    async def respond_to_invitation(
        self,
        invitation_id: str,
        accept: bool
    ) -> Dict:
        """响应邀请（接受或拒绝）"""
        now = time.time()

        invitations = await self.db.query(
            "guardian_invitations",
            filters={"id": invitation_id, "invitee_id": self.user_id},
            limit=1
        )
        if not invitations:
            raise ValueError("邀请不存在")

        inv = invitations[0]
        if inv["status"] != "pending":
            raise ValueError("邀请已处理")

        if accept:
            await self._create_bidirectional_guardian(inv)
            new_status = "accepted"
        else:
            new_status = "rejected"

        await self.db.update(
            "guardian_invitations",
            invitation_id,
            {"status": new_status, "responded_at": now},
            id_field="id"
        )

        return {"success": True, "status": new_status, "message": "已接受" if accept else "已拒绝"}

    async def _create_bidirectional_guardian(self, invitation: Dict):
        """创建双向监护人关系"""
        now = time.time()
        inviter_id = invitation["inviter_id"]
        invitee_id = invitation["invitee_id"]

        inviter_users = await self.db.query("users_auth", filters={"id": inviter_id}, limit=1)
        invitee_users = await self.db.query("users_auth", filters={"id": invitee_id}, limit=1)
        inviter_user = inviter_users[0] if inviter_users else {}
        invitee_user = invitee_users[0] if invitee_users else {}

        inviter_profiles = await self.db.query("user_profiles", filters={"user_id": inviter_id}, limit=1)
        invitee_profiles = await self.db.query("user_profiles", filters={"user_id": invitee_id}, limit=1)

        inviter_name = (inviter_profiles[0].get("nickname", "") or inviter_user.get("username", "被监护人")) if inviter_profiles else inviter_user.get("username", "被监护人")
        invitee_name = (invitee_profiles[0].get("nickname", "") or invitee_user.get("username", "监护人")) if invitee_profiles else invitee_user.get("username", "监护人")

        # 监护人记录（被监护人视角）
        existing1 = await self.db.query("guardians", filters={"user_id": inviter_id, "linked_user_id": invitee_id}, limit=1)
        if not existing1:
            guardian_id_1 = f"gd_{inviter_id[:8]}_{int(now * 1000)}"
            await self.db.insert("guardians", {
                "id": guardian_id_1,
                "user_id": inviter_id,
                "linked_user_id": invitee_id,
                "name": invitee_name,
                "phone": str(invitee_user.get("phone") or ""),
                "relationship": invitation.get("relationship", "其他"),
                "notification_level": invitation.get("notification_level", "emergency"),
                "is_active": 1,
                "auto_notify": invitation.get("auto_notify", 1),
                "channels": json.dumps(["app"]),
                "created_at": now
            })

        # 反向监护人记录（监护人视角）
        existing2 = await self.db.query("guardians", filters={"user_id": invitee_id, "linked_user_id": inviter_id}, limit=1)
        if not existing2:
            guardian_id_2 = f"gd_{invitee_id[:8]}_{int(now * 1000)}"
            await self.db.insert("guardians", {
                "id": guardian_id_2,
                "user_id": invitee_id,
                "linked_user_id": inviter_id,
                "name": inviter_name,
                "phone": str(inviter_user.get("phone") or ""),
                "relationship": self._get_reverse_relationship(invitation.get("relationship", "")),
                "notification_level": "emergency",
                "is_active": 1,
                "auto_notify": 1,
                "channels": json.dumps(["app"]),
                "created_at": now
            })

        # 更新双方的 family_protected 计数
        await self._update_family_count_for_user(inviter_id)
        await self._update_family_count_for_user(invitee_id)

    async def _update_family_count_for_user(self, user_id: str):
        """更新指定用户的 family_protected 数量"""
        guardians = await self.db.query("guardians", filters={"linked_user_id": user_id}, limit=100)
        active_count = sum(1 for g in guardians if g.get("is_active"))

        profiles = await self.db.query("user_profiles", filters={"user_id": user_id}, limit=1)
        if profiles:
            await self.db.update("user_profiles", user_id, {"family_protected": active_count}, id_field="user_id")
        else:
            await self.db.insert("user_profiles", {"user_id": user_id, "family_protected": active_count})

    def _get_reverse_relationship(self, relationship: str) -> str:
        """获取反向关系"""
        reverse_map = {"父母": "子女", "配偶": "配偶", "子女": "父母", "兄弟姐妹": "兄弟姐妹", "其他": "其他"}
        return reverse_map.get(relationship, "其他")

    def _mask_phone(self, phone: str) -> str:
        """脱敏手机号"""
        if not phone:
            return "****"
        phone = str(phone)
        if len(phone) >= 7:
            return phone[:3] + "****" + phone[-4:]
        return "****"

    async def _get_user_display_info(self, user_id: str) -> Dict[str, str]:
        """被监护人/用户展示用：昵称优先，否则用户名；脱敏手机号"""
        users = await self.db.query("users_auth", filters={"id": user_id}, limit=1)
        user = users[0] if users else {}
        profiles = await self.db.query("user_profiles", filters={"user_id": user_id}, limit=1)
        profile = profiles[0] if profiles else {}
        nickname = (profile.get("nickname") or "").strip()
        name = nickname or user.get("username") or "未知"
        phone_raw = str(user.get("phone") or "")
        return {"name": name, "phone_masked": self._mask_phone(phone_raw)}

    def _build_notification_content(
        self,
        guardian_name: str,
        risk_level: int,
        risk_type: str,
        description: str
    ) -> str:
        """构建通知内容"""
        level_names = {0: "安全", 1: "关注", 2: "低风险", 3: "中等风险", 4: "高风险", 5: "极高风险"}
        risk_names = {
            "police_impersonation": "冒充公检法",
            "investment_fraud": "投资理财诈骗",
            "part_time_fraud": "兼职刷单诈骗",
            "loan_fraud": "虚假贷款诈骗",
            "pig_butchery": "杀猪盘",
            "ai_voice_fraud": "AI语音诈骗",
            "credit_fraud": "虚假征信",
            "refund_fraud": "购物退款",
            "normal": "正常交流"
        }

        risk_name = risk_names.get(risk_type, risk_type)
        level_name = level_names.get(risk_level, "未知")

        return (
            f"【SmartGuard预警】{guardian_name}您好，"
            f"您的家人可能正在遭遇{risk_name}，风险等级：{level_name}。"
            f"详情：{description}。请尽快联系确认！"
        )

    # ==================== 监护人视角 ====================

    async def get_protected_users(self) -> List[Dict]:
        """
        获取当前用户（监护人）守护的所有被监护人列表
        
        guardians 表中「user_id=被监护人, linked_user_id=监护人」表示被监护人添加了监护人。
        该行的 name/phone 存的是监护人信息（方便被监护人看自己的监护人列表），
        监护人视角下必须用 user_id 解析被监护人资料，关系字段需做反向（我对 TA 是什么）。
        
        Returns:
            被监护人列表，每个包含 user_id, name, relationship 等
        """
        protected = await self.db.query(
            "guardians",
            filters={"linked_user_id": self.user_id},
            limit=100
        )

        result = []
        for record in protected:
            ward_id = record.get("user_id")
            if not ward_id or ward_id == self.user_id:
                continue
            if not record.get("is_active", 1):
                continue

            info = await self._get_user_display_info(ward_id)
            unread_count = await self._get_unread_alerts_count(ward_id)
            latest_alert = await self._get_latest_alert(ward_id)
            # 记录里 relationship 含义多为「对方是我的什么人」（如父母=监护人是我的父母）
            rel = self._get_reverse_relationship(record.get("relationship", "") or "")

            result.append({
                "user_id": ward_id,
                "name": info["name"],
                "relationship": rel,
                "phone": info["phone_masked"],
                "guardian_record_id": record.get("id"),
                "is_active": bool(record.get("is_active", 1)),
                "unread_alerts": unread_count,
                "latest_alert": latest_alert
            })

        return result

    async def get_protected_user_alerts(
        self, 
        protected_user_id: str,
        limit: int = 20,
        unread_only: bool = False
    ) -> List[Dict]:
        """
        获取指定被监护人的预警记录
        
        Args:
            protected_user_id: 被监护人ID
            limit: 返回数量
            unread_only: 仅未读
        """
        filters = {"user_id": protected_user_id}
        alerts = await self.db.query("alerts", filters=filters, limit=limit)
        alerts.sort(key=lambda x: x.get("created_at", 0), reverse=True)

        if unread_only:
            alerts = [a for a in alerts if not a.get("acknowledged")]

        for a in alerts:
            a["acknowledged"] = bool(a.get("acknowledged"))
            a["guardian_notified"] = bool(a.get("guardian_notified"))
            try:
                a["guardian_notifications"] = json.loads(a.get("guardian_notifications", "[]"))
            except Exception:
                a["guardian_notifications"] = []

        return alerts

    async def get_all_protected_alerts(
        self,
        limit: int = 50,
        unread_only: bool = False
    ) -> Dict:
        """
        获取所有被监护人的预警（监护人视角）
        
        Returns:
            {
                "total": int,
                "unread_total": int,
                "by_user": {
                    "user_id": {
                        "user_name": str,
                        "relationship": str,
                        "alerts": [...],
                        "unread_count": int
                    }
                },
                "recent_alerts": [...]  # 按时间排序的所有预警
            }
        """
        # 获取所有被监护人
        protected_users = await self.get_protected_users()
        
        result = {
            "total": 0,
            "unread_total": 0,
            "by_user": {},
            "recent_alerts": []
        }
        
        all_alerts = []
        
        for user in protected_users:
            user_id = user["user_id"]
            alerts = await self.get_protected_user_alerts(
                user_id, 
                limit=limit,
                unread_only=unread_only
            )
            
            unread_count = sum(1 for a in alerts if not a.get("acknowledged"))
            
            result["by_user"][user_id] = {
                "user_name": user["name"],
                "relationship": user["relationship"],
                "unread_count": unread_count,
                "total_count": len(alerts),
                "alerts": alerts
            }
            
            result["total"] += len(alerts)
            result["unread_total"] += unread_count
            
            # 添加到总列表（带用户信息）
            for alert in alerts:
                alert["protected_user_name"] = user["name"]
                alert["protected_relationship"] = user["relationship"]
                all_alerts.append(alert)
        
        # 按时间排序
        all_alerts.sort(key=lambda x: x.get("created_at", 0), reverse=True)
        result["recent_alerts"] = all_alerts[:limit]
        
        return result

    async def acknowledge_alert_for_user(
        self, 
        alert_id: str, 
        protected_user_id: str
    ) -> bool:
        """
        监护人确认被监护人的预警
        
        Args:
            alert_id: 预警ID
            protected_user_id: 被监护人ID（验证归属）
        """
        # 验证预警确实属于被监护人
        alerts = await self.db.query(
            "alerts", 
            filters={"id": alert_id, "user_id": protected_user_id},
            limit=1
        )
        
        if not alerts:
            return False
        
        return await self.db.update(
            "alerts",
            alert_id,
            {"acknowledged": 1, "acknowledged_at": time.time()},
            id_field="id"
        )

    async def _get_unread_alerts_count(self, user_id: str) -> int:
        """获取用户未读预警数量"""
        alerts = await self.db.query(
            "alerts",
            filters={"user_id": user_id, "acknowledged": 0},
            limit=100
        )
        return len(alerts)

    async def _get_latest_alert(self, user_id: str) -> Optional[Dict]:
        """获取用户最新预警"""
        alerts = await self.db.query(
            "alerts",
            filters={"user_id": user_id},
            limit=1
        )
        if alerts:
            a = alerts[0]
            return {
                "level": a.get("level"),
                "risk_type": a.get("risk_type"),
                "created_at": a.get("created_at"),
                "acknowledged": bool(a.get("acknowledged"))
            }
        return None

    async def get_available_guardians(self) -> List[Dict]:
        """
        获取可用的监护人列表（排除当前用户自己）

        Returns:
            可用用户列表，包含 id, username, nickname
        """
        # 获取所有活跃用户，排除当前用户
        users = await self.db.query(
            "users_auth",
            filters={"is_active": 1},
            limit=100
        )

        result = []
        for user in users:
            # 排除当前用户
            if user["id"] == self.user_id:
                continue

            # 获取用户昵称
            profiles = await self.db.query(
                "user_profiles",
                filters={"user_id": user["id"]},
                limit=1
            )
            profile = profiles[0] if profiles else {}
            nickname = profile.get("nickname", "")

            result.append({
                "user_id": user["id"],
                "username": user.get("username", ""),
                "nickname": nickname or user.get("username", ""),
                "phone": str(user.get("phone") or ""),
                "display": (nickname or user.get("username", "")) + (" (" + str(user.get("phone") or "") + ")" if user.get("phone") else "")
            })

        return result
