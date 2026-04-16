"""
报告生成服务（增强版）
基于用户画像、历史对话、预警记录生成可视化安全监测报告
"""

import json
import time
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from collections import defaultdict
from src.data.database import get_database
from src.services.conversation_service import ConversationService
from src.services.guardian_service import GuardianService, RISK_NOTIFY_STRATEGY


# 诈骗类型中文名映射
SCAM_TYPE_NAMES = {
    "police_impersonation": "冒充公检法",
    "investment_fraud": "投资理财诈骗",
    "part_time_fraud": "兼职刷单诈骗",
    "loan_fraud": "虚假贷款诈骗",
    "pig_butchery": "杀猪盘",
    "ai_voice_fraud": "AI语音合成诈骗",
    "ai_deepfake_fraud": "AI换脸诈骗",
    "credit_fraud": "虚假征信诈骗",
    "refund_fraud": "购物退款诈骗",
    "gaming_fraud": "游戏交易诈骗",
    "fan_fraud": "追星诈骗",
    "medical_fraud": "医保诈骗",
    "normal": "正常交流"
}

# 风险等级中文名
RISK_LEVEL_NAMES = {
    0: "安全",
    1: "关注",
    2: "低风险",
    3: "中等风险",
    4: "高风险",
    5: "极高风险"
}

# 风险等级颜色
RISK_LEVEL_COLORS = {
    0: "#52c41a",
    1: "#1890ff",
    2: "#faad14",
    3: "#fa8c16",
    4: "#f5222d",
    5: "#d4380d"
}


class ReportService:
    """
    安全监测报告生成服务

    数据来源：
    - 对话历史（conversations 表）
    - 预警记录（alerts 表）
    - 用户画像（user_profiles 表）
    - 监护人记录（guardians 表）
    """

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.db = get_database()
        self.conversation_service = ConversationService(user_id)
        self.guardian_service = GuardianService(user_id)

    async def generate_report(
        self,
        report_type: str = "weekly",
        start_date: Optional[float] = None,
        end_date: Optional[float] = None
    ) -> Dict:
        """
        生成安全监测报告

        Args:
            report_type: 报告类型（daily/weekly/monthly）
            start_date: 开始时间戳（可选）
            end_date: 结束时间戳（可选）

        Returns:
            包含统计数据和 ECharts 图表配置的报告字典
        """
        # 确定时间范围
        if start_date and end_date:
            start_ts, end_ts = start_date, end_date
        else:
            start_ts, end_ts = self._get_time_range(report_type)

        # 收集数据
        alerts = await self._collect_alerts(start_ts, end_ts)
        conversations = await self._collect_conversations(start_ts, end_ts)
        profile = await self._collect_profile()
        guardians = await self._collect_guardians()
        risk_events = await self._collect_risk_events(conversations)

        # 生成报告各部分
        report = {
            "report_info": {
                "report_type": report_type,
                "user_id": self.user_id,
                "start_date": datetime.fromtimestamp(start_ts).strftime("%Y-%m-%d %H:%M"),
                "end_date": datetime.fromtimestamp(end_ts).strftime("%Y-%m-%d %H:%M"),
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "period_days": int((end_ts - start_ts) / 86400)
            },
            "summary": self._generate_summary(alerts, conversations, profile),
            "risk_distribution": self._analyze_risk_distribution(alerts),
            "time_trend": self._analyze_time_trend(alerts, report_type),
            "scam_type_analysis": self._analyze_scam_types(alerts),
            "user_behavior": self._analyze_user_behavior(conversations, alerts, profile),
            "conversation_stats": self._analyze_conversations(conversations),
            "guardian_status": self._analyze_guardians(guardians, alerts),
            "recommendations": self._generate_recommendations(alerts, risk_events, profile, guardians),
            "charts": self._generate_echarts_config(alerts, conversations, report_type),
            "alert_details": [self._format_alert(a) for a in alerts[:20]]
        }

        return report

    def _get_time_range(self, report_type: str) -> tuple:
        """获取时间范围"""
        end_ts = time.time()
        if report_type == "daily":
            start_ts = end_ts - 86400
        elif report_type == "weekly":
            start_ts = end_ts - 86400 * 7
        elif report_type == "monthly":
            start_ts = end_ts - 86400 * 30
        else:
            start_ts = end_ts - 86400 * 7
        return start_ts, end_ts

    async def _collect_alerts(self, start_ts: float, end_ts: float) -> List[Dict]:
        """收集预警记录"""
        all_alerts = await self.db.query(
            "alerts",
            filters={"user_id": self.user_id},
            limit=500
        )
        alerts = [
            a for a in all_alerts
            if start_ts <= a.get("created_at", 0) <= end_ts
        ]
        alerts.sort(key=lambda x: x.get("created_at", 0))
        for a in alerts:
            try:
                a["guardian_notifications"] = json.loads(a.get("guardian_notifications", "[]"))
            except Exception:
                a["guardian_notifications"] = []
        return alerts

    async def _collect_conversations(self, start_ts: float, end_ts: float) -> List[Dict]:
        """收集对话记录"""


        sessions = await self.conversation_service.load_sessions(limit=100)
        
        # 过滤时间范围内的会话
        relevant = [
            s for s in sessions
            if start_ts <= s.get("updated_at", 0) <= end_ts
        ]
        
        # 如果时间范围内没有会话，获取所有最近的会话
        if not relevant and sessions:
            relevant = sessions[:20]
        
        for session in relevant:
            try:
                session["_messages"] = json.loads(session.get("messages", "[]"))
            except Exception:
                session["_messages"] = []
        
        # 如果没有收集到任何会话，尝试从数据库直接获取用户的所有对话
        if not relevant:
            all_sessions = await self.db.query(
                "conversations",
                filters={"user_id": self.user_id},
                limit=50
            )
            # 按更新时间排序
            all_sessions.sort(key=lambda x: x.get("updated_at", 0), reverse=True)
            for session in all_sessions:
                try:
                    session["_messages"] = json.loads(session.get("messages", "[]"))
                except Exception:
                    session["_messages"] = []
            if all_sessions:
                relevant = all_sessions[:20]
        
        return relevant

    async def _collect_profile(self) -> Dict:
        """收集用户画像"""
        profiles = await self.db.query(
            "user_profiles",
            filters={"user_id": self.user_id},
            limit=1
        )
        if profiles:
            p = profiles[0]
            try:
                p["interested_scam_types"] = json.loads(p.get("interested_scam_types", "[]"))
            except Exception:
                p["interested_scam_types"] = []
            return p
        return {}

    async def _collect_guardians(self) -> List[Dict]:
        """收集监护人信息"""
        return await self.guardian_service.get_guardians()

    async def _collect_risk_events(self, conversations: List[Dict]) -> List[Dict]:
        """从对话中提取风险事件"""
        events = []
        for conv in conversations:
            messages = conv.get("_messages", [])
            for msg in messages:
                if msg.get("role") == "user":
                    metadata = msg.get("metadata", {})
                    if isinstance(metadata, str):
                        try:
                            metadata = json.loads(metadata)
                        except Exception:
                            metadata = {}
                    risk_level = metadata.get("risk_level", 0)
                    if risk_level >= 2:
                        events.append({
                            "content": msg.get("content", "")[:100],
                            "risk_level": risk_level,
                            "risk_type": metadata.get("risk_type", "unknown"),
                            "timestamp": msg.get("timestamp", 0)
                        })
        return events

    def _generate_summary(
        self,
        alerts: List[Dict],
        conversations: List[Dict],
        profile: Dict
    ) -> Dict:
        """生成摘要统计"""
        total_alerts = len(alerts)
        high_risk_alerts = sum(1 for a in alerts if a.get("level", 0) >= 3)
        medium_risk_alerts = sum(1 for a in alerts if 2 <= a.get("level", 0) < 3)
        low_risk_alerts = sum(1 for a in alerts if a.get("level", 0) < 2)
        
        # 实时计算对话和消息数
        total_messages = 0
        for conv in conversations:
            messages = conv.get("_messages", [])
            total_messages += len(messages)
        
        # 获取用户画像中的咨询次数
        total_consultations = profile.get("total_consultations", 0) or 0
        
        # 实时计算被承认/处理的预警数
        acknowledged_alerts = sum(1 for a in alerts if a.get("acknowledged"))
        
        guardian_count = profile.get("family_protected", 0) or 0
        
        # 风险趋势计算
        trend_change = 0
        if len(alerts) > 0:
            mid_point = len(alerts) // 2
            first_half = sum(a.get("level", 0) for a in alerts[:mid_point])
            second_half = sum(a.get("level", 0) for a in alerts[mid_point:])
            if mid_point > 0:
                trend_change = (second_half / mid_point) - (first_half / mid_point)
        
        # 防护评分（0-100）：基于预警数量和等级实时计算
        protection_score = max(0, min(100, 100 - high_risk_alerts * 10 - medium_risk_alerts * 3 - low_risk_alerts * 1))
        
        # 反诈意识（0-100）：基于响应率和风险识别能力
        acknowledgment_rate = round(acknowledged_alerts / total_alerts, 2) if total_alerts > 0 else 1.0
        risk_awareness = round(min(100, acknowledgment_rate * 50 + protection_score * 0.5), 1)
        
        # 风险率
        risk_rate = round(high_risk_alerts / total_alerts, 2) if total_alerts > 0 else 0
        
        return {
            "total_consultations": total_consultations,
            "total_messages": total_messages,
            "total_alerts": total_alerts,
            "high_risk_alerts": high_risk_alerts,
            "medium_risk_alerts": medium_risk_alerts,
            "low_risk_alerts": low_risk_alerts,
            "acknowledged_alerts": acknowledged_alerts,
            "acknowledgment_rate": acknowledgment_rate,
            "guardian_count": guardian_count,
            "risk_rate": risk_rate,
            "protection_score": protection_score,
            "risk_trend_change": round(trend_change, 2),
            "risk_awareness": risk_awareness,
            "risk_count": profile.get("risk_count", 0) or 0
        }

    def _analyze_risk_distribution(self, alerts: List[Dict]) -> Dict:
        """分析风险等级分布"""
        level_counts = defaultdict(int)
        for a in alerts:
            level_counts[a.get("level", 0)] += 1

        total = len(alerts) or 1
        distribution = {}
        for level in range(6):
            count = level_counts.get(level, 0)
            distribution[str(level)] = {
                "count": count,
                "percentage": round(count / total * 100, 1),
                "label": RISK_LEVEL_NAMES.get(level, "未知"),
                "color": RISK_LEVEL_COLORS.get(level, "#999")
            }

        dominant = max(level_counts.items(), key=lambda x: x[1]) if level_counts else (0, 0)

        return {
            "distribution": distribution,
            "dominant_level": dominant[0],
            "dominant_label": RISK_LEVEL_NAMES.get(dominant[0], "未知"),
            "high_risk_ratio": round(level_counts.get(4, 0) + level_counts.get(5, 0) / total * 100, 1)
        }

    def _analyze_time_trend(self, alerts: List[Dict], report_type: str) -> Dict:
        """分析时间趋势"""
        daily_counts = defaultdict(lambda: defaultdict(int))
        for a in alerts:
            ts = a.get("created_at", 0)
            if ts > 0:
                date_key = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
                level = a.get("level", 0)
                daily_counts[date_key]["total"] += 1
                if level >= 3:
                    daily_counts[date_key]["high_risk"] += 1

        dates = sorted(daily_counts.keys())
        total_series = [daily_counts[d]["total"] for d in dates]
        high_risk_series = [daily_counts[d]["high_risk"] for d in dates]

        # 计算趋势
        trend = "stable"
        if len(total_series) >= 2:
            if total_series[-1] > total_series[0] * 1.3:
                trend = "increasing"
            elif total_series[-1] < total_series[0] * 0.7:
                trend = "decreasing"

        return {
            "dates": dates,
            "total_series": total_series,
            "high_risk_series": high_risk_series,
            "trend": trend,
            "peak_date": max(daily_counts.items(), key=lambda x: x[1]["total"])[0] if daily_counts else None,
            "peak_count": max(t for d in total_series for t in [d]) if total_series else 0,
            "average_daily": round(sum(total_series) / len(total_series), 1) if total_series else 0
        }

    def _analyze_scam_types(self, alerts: List[Dict]) -> Dict:
        """分析诈骗类型"""
        type_counts = defaultdict(int)
        type_high_risk = defaultdict(int)
        for a in alerts:
            t = a.get("risk_type", "unknown")
            type_counts[t] += 1
            if a.get("level", 0) >= 3:
                type_high_risk[t] += 1

        total = sum(type_counts.values()) or 1
        type_distribution = []
        for t, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
            type_distribution.append({
                "type": t,
                "name": SCAM_TYPE_NAMES.get(t, t),
                "count": count,
                "percentage": round(count / total * 100, 1),
                "high_risk_count": type_high_risk.get(t, 0)
            })

        return {
            "type_distribution": type_distribution,
            "most_common": SCAM_TYPE_NAMES.get(
                max(type_counts.items(), key=lambda x: x[1])[0] if type_counts else "",
                "未知"
            ) if type_counts else "无数据"
        }

    def _analyze_user_behavior(
        self,
        conversations: List[Dict],
        alerts: List[Dict],
        profile: Dict
    ) -> Dict:
        """分析用户行为"""
        total_messages = sum(len(c.get("_messages", [])) for c in conversations)
        user_messages = sum(
            1 for c in conversations
            for m in c.get("_messages", [])
            if m.get("role") == "user"
        )
        responded_alerts = sum(1 for a in alerts if a.get("acknowledged"))
        total_alerts = len(alerts)

        # 画像完整度
        profile_fields = ["nickname", "age_group", "occupation", "gender", "location"]
        filled = sum(1 for f in profile_fields if profile.get(f))
        completeness = round(filled / len(profile_fields) * 100, 1)

        # 学习进度
        learned = profile.get("learned_topics", [])
        if isinstance(learned, str):
            try:
                learned = json.loads(learned)
            except Exception:
                learned = []

        return {
            "total_conversations": len(conversations),
            "user_messages": user_messages,
            "message_response_ratio": round(user_messages / total_messages * 100, 1) if total_messages > 0 else 0,
            "alert_response_rate": round(responded_alerts / total_alerts * 100, 1) if total_alerts > 0 else 0,
            "profile_completeness": completeness,
            "learned_topics_count": len(learned) if isinstance(learned, list) else 0
        }

    def _analyze_conversations(self, conversations: List[Dict]) -> Dict:
        """分析对话统计"""
        mode_counts = defaultdict(int)
        for c in conversations:
            mode = c.get("mode", "risk")
            mode_counts[mode] += 1

        mode_stats = {
            "risk": mode_counts.get("risk", 0),
            "chat": mode_counts.get("chat", 0),
            "learn": mode_counts.get("learn", 0)
        }

        return {
            "mode_stats": mode_stats,
            "active_sessions": len(conversations)
        }

    def _analyze_guardians(self, guardians: List[Dict], alerts: List[Dict]) -> Dict:
        """分析监护人状态"""
        active = sum(1 for g in guardians if g.get("is_active"))
        total = len(guardians)
        notified = sum(1 for a in alerts if a.get("guardian_notified"))

        return {
            "total": total,
            "active": active,
            "notification_history_count": notified,
            "has_guardians": total > 0
        }

    def _generate_recommendations(
        self,
        alerts: List[Dict],
        risk_events: List[Dict],
        profile: Dict,
        guardians: List[Dict]
    ) -> List[Dict]:
        """生成个性化防护建议"""
        recommendations = []

        # 基于风险类型的建议
        type_counts = defaultdict(int)
        for a in alerts:
            type_counts[a.get("risk_type", "unknown")] += 1

        type_suggestions = {
            "police_impersonation": {
                "title": "防范冒充公检法诈骗",
                "content": "接到自称公检法的电话不要慌张。真正的警方不会通过电话办案，更不会要求转账到「安全账户」。遇到此类情况，可直接拨打110核实。"
            },
            "investment_fraud": {
                "title": "防范投资理财诈骗",
                "content": "高收益必然伴随高风险。正规投资不会承诺保本，更不会要求转账到个人账户。请务必通过官方渠道核实投资平台资质。"
            },
            "part_time_fraud": {
                "title": "防范兼职刷单诈骗",
                "content": "刷单是违法行为。正规兼职不会收取任何费用，遇到要先交「保证金」「培训费」的工作请立即拒绝。"
            },
            "pig_butchery": {
                "title": "防范杀猪盘诈骗",
                "content": "网络交友需谨慎。从未见面却带你投资理财的「恋人」，基本是诈骗分子。切勿向陌生人转账。"
            },
            "ai_voice_fraud": {
                "title": "防范AI诈骗",
                "content": "遇到家人、朋友紧急要钱的情况，务必通过电话或视频核实。AI合成声音已可模拟真人，文字消息不足以信。"
            }
        }

        for risk_type, suggestion in type_suggestions.items():
            if type_counts.get(risk_type, 0) > 0:
                recommendations.append({
                    "category": "risk_specific",
                    "priority": "high",
                    "risk_type": risk_type,
                    **suggestion
                })

        # 基于年龄段的建议
        age_group = profile.get("age_group", "")
        age_suggestions = {
            "18-25": {
                "title": "青年用户安全提示",
                "content": "作为年轻人，请特别警惕游戏交易、追星诈骗、网络贷款等。不要轻信「无抵押、低利率」的贷款广告，保护好个人金融信息。"
            },
            "26-35": {
                "title": "中青年用户安全提示",
                "content": "中青年是投资理财诈骗的高发群体。请选择正规金融机构，警惕高收益诱惑，不盲目跟风投资。"
            },
            "36-45": {
                "title": "中年用户安全提示",
                "content": "中年用户需警惕冒充领导、熟人诈骗。收到转账要求时，务必通过其他渠道核实对方身份。"
            },
            "46-55": {
                "title": "中老年用户安全提示",
                "content": "中老年是电信诈骗的重点目标。请提醒家人不要轻信陌生来电，遇到紧急情况多与子女商量。"
            },
            "56+": {
                "title": "老年用户安全提示",
                "content": "老年人接到陌生电话要格外警惕，尤其是自称公检法、子女出事的来电。建议与家人约定「安全暗语」，遇到紧急情况先联系子女确认。"
            }
        }
        if age_group in age_suggestions:
            recommendations.append({
                "category": "age_group",
                "priority": "medium",
                **age_suggestions[age_group]
            })

        # 监护人建议
        if len(guardians) == 0:
            recommendations.append({
                "category": "family_protection",
                "priority": "high",
                "title": "添加监护人",
                "content": "您还没有添加监护人。建议添加家人作为监护人，当检测到风险时系统可自动通知家人，及时获得帮助。"
            })

        # 通用建议
        recommendations.append({
            "category": "general",
            "priority": "low",
            "title": "通用防护措施",
            "content": "记住「三不一多」原则：不明链接不点击、陌生来电不轻信、个人信息不透露、转账汇款多核实。遇到可疑情况可拨打反诈热线96110咨询。"
        })

        return recommendations

    def _generate_echarts_config(
        self,
        alerts: List[Dict],
        conversations: List[Dict],
        report_type: str
    ) -> Dict:
        """生成 ECharts 图表配置"""
        # 1. 风险等级分布饼图（增强版）
        level_counts = defaultdict(int)
        for a in alerts:
            level_counts[a.get("level", 0)] += 1

        pie_data = []
        total_count = 0
        for level in range(6):
            count = level_counts.get(level, 0)
            total_count += count
            if count > 0:
                pie_data.append({
                    "name": RISK_LEVEL_NAMES.get(level, "未知"),
                    "value": count,
                    "itemStyle": {"color": RISK_LEVEL_COLORS.get(level, "#999")}
                })

        pie_config = {
            "backgroundColor": "transparent",
            "title": {
                "text": "🎯 风险等级分布",
                "left": "center",
                "textStyle": {"fontSize": 14, "fontWeight": "bold", "color": "#f1f5f9"}
            },
            "tooltip": {
                "trigger": "item",
                "backgroundColor": "rgba(30,41,59,0.95)",
                "borderColor": "#475569",
                "textStyle": {"color": "#f1f5f9"},
                "formatter": "{b}: {c}次 ({d}%)"
            },
            "legend": {
                "orient": "vertical",
                "right": "5%",
                "top": "center",
                "itemWidth": 12,
                "itemHeight": 12,
                "itemGap": 12,
                "textStyle": {"fontSize": 12, "color": "#94a3b8"}
            },
            "series": [{
                "name": "风险分布",
                "type": "pie",
                "center": ["40%", "50%"],
                "radius": ["35%", "65%"],
                "avoidLabelOverlap": True,
                "itemStyle": {
                    "borderRadius": 8,
                    "borderColor": "#1e293b",
                    "borderWidth": 3
                },
                "label": {
                    "show": total_count <= 5,
                    "position": "outside",
                    "formatter": "{b}\n{c}次",
                    "fontSize": 12,
                    "color": "#94a3b8"
                },
                "labelLine": {
                    "show": total_count <= 5,
                    "lineStyle": {"color": "#64748b"}
                },
                "emphasis": {
                    "label": {"show": True, "fontSize": 14, "fontWeight": "bold", "color": "#f1f5f9"},
                    "itemStyle": {"shadowBlur": 10, "shadowOffsetX": 0, "shadowColor": "rgba(0, 0, 0, 0.5)"}
                },
                "data": pie_data if pie_data else [
                    {"name": "暂无数据", "value": 1, "itemStyle": {"color": "#334155"}}
                ]
            }]
        }

        # 2. 时间趋势折线图（增强版）
        daily_data = defaultdict(lambda: {"total": 0, "high_risk": 0, "medium_risk": 0})
        for a in alerts:
            ts = a.get("created_at", 0)
            if ts > 0:
                date_key = datetime.fromtimestamp(ts).strftime("%m-%d")
                level = a.get("level", 0)
                daily_data[date_key]["total"] += 1
                if level >= 3:
                    daily_data[date_key]["high_risk"] += 1
                elif level >= 2:
                    daily_data[date_key]["medium_risk"] += 1

        # 生成最近7天日期（确保有数据）
        all_dates = sorted(daily_data.keys())
        if not all_dates:
            # 生成最近7天的空数据
            today = datetime.now()
            all_dates = [(today - timedelta(days=i)).strftime("%m-%d") for i in range(6, -1, -1)]
        
        total_series = [daily_data.get(d, {}).get("total", 0) for d in all_dates]
        high_risk_series = [daily_data.get(d, {}).get("high_risk", 0) for d in all_dates]
        medium_risk_series = [daily_data.get(d, {}).get("medium_risk", 0) for d in all_dates]
        
        # 计算平均值
        avg_total = round(sum(total_series) / len(total_series), 1) if total_series else 0

        line_config = {
            "backgroundColor": "transparent",
            "title": {
                "text": "📈 风险预警趋势（近7天）",
                "left": "center",
                "textStyle": {"fontSize": 14, "fontWeight": "bold", "color": "#f1f5f9"}
            },
            "tooltip": {
                "trigger": "axis",
                "backgroundColor": "rgba(30,41,59,0.95)",
                "borderColor": "#475569",
                "borderWidth": 1,
                "textStyle": {"color": "#f1f5f9"}
            },
            "legend": {
                "data": ["全部预警", "中风险", "高风险"],
                "bottom": 5,
                "textStyle": {"fontSize": 11, "color": "#94a3b8"}
            },
            "grid": {"left": 45, "right": 25, "top": 55, "bottom": 55},
            "xAxis": {
                "type": "category",
                "data": all_dates,
                "axisLine": {"lineStyle": {"color": "#475569"}},
                "axisLabel": {"color": "#94a3b8", "fontSize": 11}
            },
            "yAxis": {
                "type": "value",
                "minInterval": 1,
                "splitLine": {"lineStyle": {"color": "#334155"}},
                "axisLine": {"show": False},
                "axisLabel": {"color": "#94a3b8"}
            },
            "series": [
                {
                    "name": "全部预警",
                    "type": "line",
                    "smooth": 0.4,
                    "symbol": "circle",
                    "symbolSize": 8,
                    "data": total_series,
                    "lineStyle": {"color": "#818cf8", "width": 3},
                    "itemStyle": {"color": "#818cf8", "borderWidth": 2, "borderColor": "#1e293b"},
                    "areaStyle": {
                        "color": {
                            "type": "linear",
                            "x": 0, "y": 0, "x2": 0, "y2": 1,
                            "colorStops": [
                                {"offset": 0, "color": "rgba(129,140,248,0.3)"},
                                {"offset": 1, "color": "rgba(129,140,248,0.02)"}
                            ]
                        }
                    }
                },
                {
                    "name": "中风险",
                    "type": "bar",
                    "stack": "risk",
                    "barWidth": "60%",
                    "data": medium_risk_series,
                    "itemStyle": {"color": "#f59e0b", "borderRadius": [0, 0, 0, 0]}
                },
                {
                    "name": "高风险",
                    "type": "bar",
                    "stack": "risk",
                    "barWidth": "60%",
                    "data": high_risk_series,
                    "itemStyle": {"color": "#ef4444", "borderRadius": [4, 4, 0, 0]}
                },
                {
                    "name": "平均线",
                    "type": "line",
                    "data": [avg_total] * len(all_dates),
                    "lineStyle": {"color": "#22c55e", "width": 2, "type": "dashed"},
                    "symbol": "none",
                    "tooltip": {"show": False}
                }
            ]
        }

        # 3. 诈骗类型分布横向柱状图（增强版）
        type_counts = defaultdict(int)
        for a in alerts:
            t = a.get("risk_type", "unknown")
            if t != "normal":
                type_counts[t] += 1

        sorted_types = sorted(type_counts.items(), key=lambda x: x[1], reverse=True)[:6]
        bar_data = [
            {"name": SCAM_TYPE_NAMES.get(t, t), "value": c, "type": t}
            for t, c in sorted_types
        ]

        # 诈骗类型对应的颜色
        type_colors = {
            "police_impersonation": "#f5222d",
            "investment_fraud": "#fa8c16",
            "part_time_fraud": "#faad14",
            "loan_fraud": "#52c41a",
            "pig_butchery": "#eb2f96",
            "ai_voice_fraud": "#722ed1",
            "credit_fraud": "#13c2c2",
            "refund_fraud": "#1890ff",
            "gaming_fraud": "#2f54eb",
            "fan_fraud": "#fa541c",
            "medical_fraud": "#0e9f68",
            "unknown": "#8c8c8c"
        }

        bar_config = {
            "backgroundColor": "transparent",
            "title": {
                "text": "🔍 诈骗类型分布",
                "left": "center",
                "textStyle": {"fontSize": 14, "fontWeight": "bold", "color": "#f1f5f9"}
            },
            "tooltip": {
                "trigger": "axis",
                "axisPointer": {"type": "shadow"},
                "backgroundColor": "rgba(30,41,59,0.95)",
                "borderColor": "#475569",
                "textStyle": {"color": "#f1f5f9"}
            },
            "grid": {"left": 120, "right": 50, "top": 55, "bottom": 20},
            "xAxis": {
                "type": "value",
                "splitLine": {"lineStyle": {"color": "#334155"}},
                "axisLabel": {"color": "#94a3b8"}
            },
            "yAxis": {
                "type": "category",
                "data": [d["name"] for d in bar_data],
                "axisLine": {"show": False},
                "axisTick": {"show": False},
                "axisLabel": {"color": "#94a3b8", "fontSize": 12}
            },
            "series": [{
                "type": "bar",
                "data": [{
                    "value": d["value"],
                    "type": d["type"],
                    "itemStyle": {
                        "color": {
                            "type": "linear",
                            "x": 0, "y": 0, "x2": 1, "y2": 0,
                            "colorStops": [
                                {"offset": 0, "color": type_colors.get(d["type"], "#818cf8")},
                                {"offset": 1, "color": type_colors.get(d["type"], "#a78bfa")}
                            ]
                        },
                        "borderRadius": [0, 4, 4, 0]
                    }
                } for d in bar_data],
                "barWidth": "50%",
                "label": {
                    "show": True,
                    "position": "right",
                    "formatter": "{c}次",
                    "fontSize": 12,
                    "color": "#94a3b8"
                }
            }]
        }

        # 如果没有数据，显示空状态
        if not bar_data:
            bar_config = {
                "backgroundColor": "transparent",
                "title": {
                    "text": "🔍 诈骗类型分布",
                    "left": "center",
                    "textStyle": {"fontSize": 14, "fontWeight": "bold", "color": "#f1f5f9"}
                },
                "series": [{
                    "type": "bar",
                    "data": [],
                    "label": {"show": True, "position": "center", "formatter": "暂无数据", "color": "#64748b"}
                }]
            }

        # 4. 防护雷达图（增强版）
        summary = self._generate_summary(alerts, conversations, {})
        radar_data = [
            summary.get("protection_score", 50),  # 防护评分
            summary.get("acknowledgment_rate", 0) * 100,  # 响应率
            min(100, summary.get("guardian_count", 0) * 20),  # 监护覆盖率
            50,  # 学习进度（固定基础值）
            max(0, 100 - summary.get("risk_rate", 0) * 100)  # 风险控制
        ]

        radar_config = {
            "backgroundColor": "transparent",
            "title": {
                "text": "🛡️ 安全防护能力",
                "left": "center",
                "textStyle": {"fontSize": 14, "fontWeight": "bold", "color": "#f1f5f9"}
            },
            "tooltip": {
                "trigger": "item",
                "backgroundColor": "rgba(30,41,59,0.95)",
                "borderColor": "#475569",
                "textStyle": {"color": "#f1f5f9"}
            },
            "legend": {
                "bottom": 5,
                "data": ["你的防护能力"],
                "textStyle": {"fontSize": 12, "color": "#94a3b8"}
            },
            "radar": {
                "indicator": [
                    {"name": "防护评分", "max": 100, "color": "#94a3b8"},
                    {"name": "预警响应", "max": 100, "color": "#94a3b8"},
                    {"name": "监护覆盖", "max": 100, "color": "#94a3b8"},
                    {"name": "安全学习", "max": 100, "color": "#94a3b8"},
                    {"name": "风险控制", "max": 100, "color": "#94a3b8"}
                ],
                "radius": "60%",
                "splitNumber": 4,
                "axisLine": {"show": True, "lineStyle": {"color": "#475569"}},
                "splitLine": {"show": True, "lineStyle": {"color": "#334155"}},
                "splitArea": {"show": False},
                "name": {"textStyle": {"color": "#94a3b8", "fontSize": 12}}
            },
            "series": [{
                "type": "radar",
                "data": [{
                    "value": radar_data,
                    "name": "你的防护能力",
                    "lineStyle": {"color": "#818cf8", "width": 2},
                    "areaStyle": {
                        "color": {
                            "type": "radial",
                            "x": 0.5, "y": 0.5, "r": 0.5,
                            "colorStops": [
                                {"offset": 0, "color": "rgba(129,140,248,0.5)"},
                                {"offset": 1, "color": "rgba(129,140,248,0.1)"}
                            ]
                        }
                    },
                    "itemStyle": {"color": "#818cf8"},
                    "label": {
                        "show": True,
                        "formatter": "{c}",
                        "fontSize": 10,
                        "color": "#f1f5f9"
                    }
                }]
            }]
        }

        return {
            "risk_level_pie": pie_config,
            "time_trend_line": line_config,
            "scam_type_bar": bar_config,
            "protection_radar": radar_config
        }

    def _format_alert(self, alert: Dict) -> Dict:
        """格式化预警记录"""
        level = alert.get("level", 0)
        risk_type = alert.get("risk_type", "unknown")
        return {
            "id": alert.get("id"),
            "level": level,
            "level_label": RISK_LEVEL_NAMES.get(level, "未知"),
            "level_color": RISK_LEVEL_COLORS.get(level, "#999"),
            "risk_type": risk_type,
            "risk_type_name": SCAM_TYPE_NAMES.get(risk_type, risk_type),
            "message": alert.get("message", "")[:100],
            "acknowledged": alert.get("acknowledged", False),
            "guardian_notified": alert.get("guardian_notified", False),
            "created_at": datetime.fromtimestamp(alert.get("created_at", 0)).strftime("%Y-%m-%d %H:%M"),
            "notifications": alert.get("guardian_notifications", [])
        }