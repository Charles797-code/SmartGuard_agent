"""
预警管理模块
实现分级预警机制，支持多种预警方式和响应策略
"""

import time
import json
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from collections import defaultdict


class AlertLevel(Enum):
    """预警等级"""
    SAFE = 0
    ATTENTION = 1
    WARNING = 2
    DANGER = 3
    EMERGENCY = 4
    
    @property
    def name_cn(self) -> str:
        names = {
            0: "安全",
            1: "关注",
            2: "警告",
            3: "危险",
            4: "紧急"
        }
        return names.get(self.value, "未知")
    
    @property
    def color(self) -> str:
        colors = {
            0: "#52c41a",  # 绿色
            1: "#faad14",  # 黄色
            2: "#fa8c16",  # 橙色
            3: "#ff4d4f",  # 红色
            4: "#cf1322"   # 深红色
        }
        return colors.get(self.value, "#999999")


@dataclass
class Alert:
    """预警信息"""
    alert_id: str
    user_id: str
    level: AlertLevel
    title: str
    message: str
    risk_type: str
    risk_score: float
    suggestions: List[str]
    actions_taken: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    acknowledged: bool = False
    acknowledged_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "alert_id": self.alert_id,
            "user_id": self.user_id,
            "level": self.level.value,
            "level_name": self.level.name_cn,
            "title": self.title,
            "message": self.message,
            "risk_type": self.risk_type,
            "risk_score": self.risk_score,
            "suggestions": self.suggestions,
            "actions_taken": self.actions_taken,
            "created_at": self.created_at,
            "created_at_str": datetime.fromtimestamp(self.created_at).isoformat(),
            "acknowledged": self.acknowledged,
            "acknowledged_at": self.acknowledged_at,
            "metadata": self.metadata
        }


@dataclass
class AlertTemplate:
    """预警模板"""
    level: AlertLevel
    title_template: str
    message_template: str
    icon: str = "warning"
    
    @classmethod
    def get_templates(cls) -> Dict[AlertLevel, 'AlertTemplate']:
        return {
            AlertLevel.SAFE: cls(
                level=AlertLevel.SAFE,
                title_template="安全提示",
                message_template="当前交流无风险特征，请继续保持警惕。",
                icon="check-circle"
            ),
            AlertLevel.ATTENTION: cls(
                level=AlertLevel.ATTENTION,
                title_template="注意事项",
                message_template="检测到一些需要注意的内容，请仔细核实对方身份。",
                icon="info-circle"
            ),
            AlertLevel.WARNING: cls(
                level=AlertLevel.WARNING,
                title_template="风险警告",
                message_template="检测到较高的诈骗风险特征，请提高警惕！",
                icon="exclamation-circle"
            ),
            AlertLevel.DANGER: cls(
                level=AlertLevel.DANGER,
                title_template="危险警报",
                message_template="检测到高度危险的诈骗行为，请立即停止操作！",
                icon="close-circle"
            ),
            AlertLevel.EMERGENCY: cls(
                level=AlertLevel.EMERGENCY,
                title_template="紧急预警",
                message_template="检测到紧急诈骗风险，正在通知您的监护人！",
                icon="urgent"
            )
        }


class AlertManager:
    """
    预警管理器
    
    负责生成、存储、发送预警信息，
    支持分级预警、预警确认、预警统计等功能。
    """
    
    def __init__(self, storage: Optional[Any] = None):
        """
        初始化预警管理器
        
        Args:
            storage: 存储后端（可选，用于持久化预警记录）
        """
        self.storage = storage
        self.templates = AlertTemplate.get_templates()
        self.alert_history: Dict[str, List[Alert]] = defaultdict(list)
        self.alert_callbacks: List[Callable] = []
        self.alert_count = 0
    
    def create_alert(self, user_id: str, level: int, risk_type: str,
                    risk_score: float, analysis: str, suggestions: List[str],
                    metadata: Optional[Dict] = None) -> Alert:
        """
        创建预警
        
        Args:
            user_id: 用户ID
            level: 风险等级
            risk_type: 风险类型
            risk_score: 风险分数
            analysis: 分析说明
            suggestions: 建议
            metadata: 元数据
            
        Returns:
            Alert: 预警对象
        """
        self.alert_count += 1
        
        # 获取模板
        alert_level = AlertLevel(level)
        template = self.templates.get(alert_level)
        
        # 格式化消息
        message = template.message_template if template else analysis[:200]
        title = template.title_template if template else "风险提醒"
        
        alert = Alert(
            alert_id=f"alert_{user_id}_{self.alert_count}_{int(time.time())}",
            user_id=user_id,
            level=alert_level,
            title=title,
            message=message,
            risk_type=risk_type,
            risk_score=risk_score,
            suggestions=suggestions,
            metadata=metadata or {}
        )
        
        # 存储
        self.alert_history[user_id].append(alert)
        
        # 如果有存储后端，持久化
        if self.storage:
            # self.storage.save_alert(alert)
            pass
        
        # 触发回调
        self._trigger_callbacks(alert)
        
        return alert
    
    def create_alert_from_assessment(self, user_id: str, assessment: Dict) -> Alert:
        """
        从风险评估结果创建预警
        
        Args:
            user_id: 用户ID
            assessment: 风险评估结果
            
        Returns:
            Alert: 预警对象
        """
        return self.create_alert(
            user_id=user_id,
            level=assessment.get("risk_level", 0),
            risk_type=assessment.get("risk_type", "unknown"),
            risk_score=assessment.get("confidence", 0.0),
            analysis=assessment.get("analysis", ""),
            suggestions=assessment.get("recommended_actions", []),
            metadata={
                "warning_message": assessment.get("warning_message", ""),
                "triggered_keywords": assessment.get("triggered_keywords", [])
            }
        )
    
    def acknowledge_alert(self, alert_id: str, user_id: str) -> bool:
        """
        确认预警
        
        Args:
            alert_id: 预警ID
            user_id: 用户ID
            
        Returns:
            bool: 是否成功
        """
        alerts = self.alert_history.get(user_id, [])
        
        for alert in alerts:
            if alert.alert_id == alert_id:
                alert.acknowledged = True
                alert.acknowledged_at = time.time()
                return True
        
        return False
    
    def get_user_alerts(self, user_id: str, 
                       unread_only: bool = False,
                       limit: int = 20) -> List[Alert]:
        """
        获取用户预警列表
        
        Args:
            user_id: 用户ID
            unread_only: 仅未读
            limit: 数量限制
            
        Returns:
            List[Alert]: 预警列表
        """
        alerts = self.alert_history.get(user_id, [])
        
        if unread_only:
            alerts = [a for a in alerts if not a.acknowledged]
        
        # 按时间倒序
        alerts.sort(key=lambda x: x.created_at, reverse=True)
        
        return alerts[:limit]
    
    def get_unread_count(self, user_id: str) -> int:
        """获取未读预警数量"""
        alerts = self.alert_history.get(user_id, [])
        return sum(1 for a in alerts if not a.acknowledged)
    
    def get_statistics(self, user_id: Optional[str] = None) -> Dict:
        """获取预警统计"""
        if user_id:
            alerts = self.alert_history.get(user_id, [])
        else:
            alerts = []
            for user_alerts in self.alert_history.values():
                alerts.extend(user_alerts)
        
        # 按等级统计
        level_counts = defaultdict(int)
        for alert in alerts:
            level_counts[alert.level.value] += 1
        
        # 确认率
        total = len(alerts)
        acknowledged = sum(1 for a in alerts if a.acknowledged)
        ack_rate = acknowledged / total if total > 0 else 0
        
        return {
            "total_alerts": total,
            "acknowledged": acknowledged,
            "unacknowledged": total - acknowledged,
            "acknowledgement_rate": ack_rate,
            "level_distribution": dict(level_counts),
            "recent_24h": sum(
                1 for a in alerts 
                if time.time() - a.created_at < 86400
            )
        }
    
    def register_callback(self, callback: Callable[[Alert], None]):
        """注册预警回调"""
        self.alert_callbacks.append(callback)
    
    def _trigger_callbacks(self, alert: Alert):
        """触发回调"""
        for callback in self.alert_callbacks:
            try:
                callback(alert)
            except Exception:
                pass
    
    def clear_history(self, user_id: str, before_timestamp: Optional[float] = None):
        """
        清除历史预警
        
        Args:
            user_id: 用户ID
            before_timestamp: 仅清除此时间之前的预警
        """
        if before_timestamp:
            self.alert_history[user_id] = [
                a for a in self.alert_history[user_id]
                if a.created_at >= before_timestamp
            ]
        else:
            self.alert_history[user_id] = []
    
    def generate_alert_report(self, user_id: str, 
                            start_time: Optional[float] = None,
                            end_time: Optional[float] = None) -> Dict:
        """
        生成预警报告
        
        Args:
            user_id: 用户ID
            start_time: 开始时间
            end_time: 结束时间
            
        Returns:
            Dict: 报告数据
        """
        alerts = self.alert_history.get(user_id, [])
        
        # 时间过滤
        if start_time:
            alerts = [a for a in alerts if a.created_at >= start_time]
        if end_time:
            alerts = [a for a in alerts if a.created_at <= end_time]
        
        # 统计
        risk_types = defaultdict(int)
        total_risk_score = 0
        
        for alert in alerts:
            risk_types[alert.risk_type] += 1
            total_risk_score += alert.risk_score
        
        avg_risk_score = total_risk_score / len(alerts) if alerts else 0
        
        return {
            "user_id": user_id,
            "period": {
                "start": start_time,
                "end": end_time,
                "start_str": datetime.fromtimestamp(start_time).isoformat() if start_time else None,
                "end_str": datetime.fromtimestamp(end_time).isoformat() if end_time else None
            },
            "summary": {
                "total_alerts": len(alerts),
                "high_risk_alerts": sum(1 for a in alerts if a.level.value >= 3),
                "acknowledged": sum(1 for a in alerts if a.acknowledged),
                "average_risk_score": avg_risk_score
            },
            "risk_type_distribution": dict(risk_types),
            "alerts": [a.to_dict() for a in alerts]
        }