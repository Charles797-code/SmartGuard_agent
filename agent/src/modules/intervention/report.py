"""
报告生成模块
自动生成可视化的安全监测报告
"""

import time
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
import base64
from io import BytesIO


@dataclass
class ReportConfig:
    """报告配置"""
    report_type: str = "daily"  # daily, weekly, monthly, custom
    include_charts: bool = True
    include_recommendations: bool = True
    include_alert_details: bool = False
    output_format: str = "json"  # json, html, pdf
    user_id: str = ""
    start_date: Optional[float] = None
    end_date: Optional[float] = None


class ReportGenerator:
    """
    报告生成器
    
    自动生成安全监测报告，包含：
    - 风险统计概览
    - 诈骗类型分布
    - 时间趋势分析
    - 个性化防护建议
    """
    
    def __init__(self, data_provider: Optional[Any] = None):
        """
        初始化报告生成器
        
        Args:
            data_provider: 数据提供器
        """
        self.data_provider = data_provider
    
    async def generate_report(self, config: ReportConfig) -> Dict:
        """
        生成报告
        
        Args:
            config: 报告配置
            
        Returns:
            Dict: 报告数据
        """
        # 确定时间范围
        if config.start_date and config.end_date:
            start_time = config.start_date
            end_time = config.end_date
        else:
            start_time, end_time = self._get_time_range(config.report_type)
        
        # 获取数据
        alerts = await self._get_alerts(config.user_id, start_time, end_time)
        risk_events = await self._get_risk_events(config.user_id, start_time, end_time)
        user_profile = await self._get_user_profile(config.user_id)
        
        # 生成报告各部分
        report = {
            "report_info": {
                "report_type": config.report_type,
                "user_id": config.user_id,
                "start_date": datetime.fromtimestamp(start_time).isoformat(),
                "end_date": datetime.fromtimestamp(end_time).isoformat(),
                "generated_at": datetime.now().isoformat(),
                "period_days": int((end_time - start_time) / 86400)
            },
            "summary": self._generate_summary(alerts, risk_events),
            "risk_distribution": self._analyze_risk_distribution(alerts),
            "time_trend": self._analyze_time_trend(alerts),
            "scam_type_analysis": self._analyze_scam_types(alerts),
            "user_behavior": self._analyze_user_behavior(alerts, user_profile),
            "recommendations": self._generate_recommendations(alerts, user_profile),
            "charts": {} if config.include_charts else None,
            "alert_details": [a.to_dict() for a in alerts] if config.include_alert_details else []
        }
        
        # 生成图表数据
        if config.include_charts:
            report["charts"] = self._generate_chart_data(alerts)
        
        # 转换为指定格式
        if config.output_format == "html":
            report = self._convert_to_html(report)
        elif config.output_format == "pdf":
            report = self._prepare_for_pdf(report)
        
        return report
    
    def _get_time_range(self, report_type: str) -> tuple:
        """获取时间范围"""
        end_time = time.time()
        
        if report_type == "daily":
            start_time = end_time - 86400
        elif report_type == "weekly":
            start_time = end_time - 86400 * 7
        elif report_type == "monthly":
            start_time = end_time - 86400 * 30
        else:
            start_time = end_time - 86400
        
        return start_time, end_time
    
    async def _get_alerts(self, user_id: str, 
                         start_time: float, end_time: float) -> List:
        """获取预警数据"""
        # 实际实现需要从数据库获取
        # 这里返回空列表作为示例
        return []
    
    async def _get_risk_events(self, user_id: str,
                             start_time: float, end_time: float) -> List:
        """获取风险事件数据"""
        return []
    
    async def _get_user_profile(self, user_id: str) -> Dict:
        """获取用户画像"""
        return {
            "age_group": "adult",
            "occupation": "未知",
            "risk_history_count": 0,
            "conversation_count": 0
        }
    
    def _generate_summary(self, alerts: List, risk_events: List) -> Dict:
        """生成摘要"""
        total_alerts = len(alerts)
        
        # 等级分布
        level_counts = defaultdict(int)
        for alert in alerts:
            level_counts[alert.level.value if hasattr(alert, 'level') else 0] += 1
        
        # 高风险事件
        high_risk_count = sum(
            1 for alert in alerts 
            if (hasattr(alert, 'level') and alert.level.value >= 3)
        )
        
        # 计算环比（假设有上一周期的数据）
        # 这里简化处理
        week_over_week = 0.0
        
        return {
            "total_alerts": total_alerts,
            "high_risk_alerts": high_risk_count,
            "level_distribution": dict(level_counts),
            "risk_rate": high_risk_count / total_alerts if total_alerts > 0 else 0,
            "week_over_week_change": week_over_week,
            "protection_score": self._calculate_protection_score(
                total_alerts, high_risk_count
            )
        }
    
    def _calculate_protection_score(self, total: int, high_risk: int) -> float:
        """计算防护评分"""
        if total == 0:
            return 100.0
        
        # 基于风险事件的防护评分
        base_score = 100.0
        penalty = high_risk * 10  # 每个高风险事件扣10分
        penalty += (total - high_risk) * 2  # 每个普通事件扣2分
        
        return max(0.0, min(100.0, base_score - penalty))
    
    def _analyze_risk_distribution(self, alerts: List) -> Dict:
        """分析风险分布"""
        levels = defaultdict(int)
        
        for alert in alerts:
            if hasattr(alert, 'level'):
                levels[alert.level.name_cn] += 1
        
        total = sum(levels.values())
        
        return {
            "distribution": {
                k: {
                    "count": v,
                    "percentage": v / total if total > 0 else 0
                }
                for k, v in levels.items()
            },
            "dominant_level": max(levels.items(), key=lambda x: x[1])[0] if levels else "无数据"
        }
    
    def _analyze_time_trend(self, alerts: List) -> Dict:
        """分析时间趋势"""
        daily_counts = defaultdict(int)
        
        for alert in alerts:
            if hasattr(alert, 'created_at'):
                date = datetime.fromtimestamp(alert.created_at).strftime("%Y-%m-%d")
                daily_counts[date] += 1
        
        # 生成时间序列
        dates = sorted(daily_counts.keys())
        values = [daily_counts[d] for d in dates]
        
        # 计算趋势
        trend = "stable"
        if len(values) >= 2:
            if values[-1] > values[0] * 1.2:
                trend = "increasing"
            elif values[-1] < values[0] * 0.8:
                trend = "decreasing"
        
        return {
            "daily_counts": dict(daily_counts),
            "trend": trend,
            "peak_date": max(daily_counts.items(), key=lambda x: x[1])[0] if daily_counts else None,
            "average_daily": sum(values) / len(values) if values else 0
        }
    
    def _analyze_scam_types(self, alerts: List) -> Dict:
        """分析诈骗类型"""
        type_counts = defaultdict(int)
        type_details = defaultdict(list)
        
        for alert in alerts:
            if hasattr(alert, 'risk_type'):
                risk_type = alert.risk_type
                type_counts[risk_type] += 1
                
                if hasattr(alert, 'suggestions'):
                    type_details[risk_type].extend(alert.suggestions)
        
        # 类型名称映射
        type_names = {
            "police_impersonation": "冒充公检法",
            "investment_fraud": "投资理财诈骗",
            "part_time_fraud": "兼职刷单诈骗",
            "loan_fraud": "虚假贷款诈骗",
            "pig_butchery": "杀猪盘",
            "ai_voice_fraud": "AI语音合成诈骗",
            "credit_fraud": "虚假征信诈骗",
            "refund_fraud": "购物退款诈骗",
            "gaming_fraud": "游戏交易诈骗",
            "fan_fraud": "追星诈骗",
            "medical_fraud": "医保诈骗",
            "normal": "正常交流"
        }
        
        return {
            "type_distribution": {
                "data": [
                    {
                        "type": t,
                        "name": type_names.get(t, t),
                        "count": c,
                        "percentage": c / sum(type_counts.values()) if type_counts else 0
                    }
                    for t, c in sorted(type_counts.items(), key=lambda x: x[1], reverse=True)
                ]
            },
            "most_common": type_names.get(
                max(type_counts.items(), key=lambda x: x[1])[0] if type_counts else "", "未知"
            ) if type_counts else "无数据"
        }
    
    def _analyze_user_behavior(self, alerts: List, profile: Dict) -> Dict:
        """分析用户行为"""
        # 基于预警数据分析用户行为
        risk_awareness = 0.8  # 简化处理
        
        # 检查用户对预警的响应
        acknowledged = sum(
            1 for alert in alerts 
            if hasattr(alert, 'acknowledged') and alert.acknowledged
        )
        total = len(alerts)
        
        return {
            "risk_awareness_score": risk_awareness,
            "alert_response_rate": acknowledged / total if total > 0 else 0,
            "conversation_count": profile.get("conversation_count", 0),
            "profile_completeness": self._calculate_profile_completeness(profile)
        }
    
    def _calculate_profile_completeness(self, profile: Dict) -> float:
        """计算画像完整度"""
        required_fields = ["age_group", "occupation", "risk_history_count"]
        filled = sum(1 for f in required_fields if profile.get(f))
        return filled / len(required_fields)
    
    def _generate_recommendations(self, alerts: List, profile: Dict) -> List[Dict]:
        """生成防护建议"""
        recommendations = []
        
        # 基于风险分布的建议
        risk_types = defaultdict(int)
        for alert in alerts:
            if hasattr(alert, 'risk_type'):
                risk_types[alert.risk_type] += 1
        
        if risk_types:
            top_type = max(risk_types.items(), key=lambda x: x[1])[0]
            type_suggestions = {
                "police_impersonation": "接到自称公检法的电话时，不要慌张。真正的警方不会通过电话办案，更不会要求转账到安全账户。",
                "investment_fraud": "高收益必然伴随高风险，正规投资不会承诺保本。请通过官方渠道核实投资平台资质。",
                "part_time_fraud": "刷单是违法行为。正规兼职不会收取任何费用，遇到要先交钱的工作请立即拒绝。",
                "loan_fraud": "申请贷款请通过银行等正规金融机构，不要轻信无抵押、低利率的贷款广告。",
                "pig_butchery": "网络交友需谨慎，特别是从未见面的「恋人」突然带你投资，基本都是诈骗。",
                "ai_voice_fraud": "遇到家人紧急要钱的情况，先电话或视频核实，必要时可直接报警。",
                "credit_fraud": "征信记录无法人为修复，任何声称能消除逾期记录的都是诈骗。",
                "refund_fraud": "退款操作应在原平台进行，不要点击对方发来的链接或下载其他APP。"
            }
            
            if top_type in type_suggestions:
                recommendations.append({
                    "category": "specific",
                    "priority": "high",
                    "title": f"针对{top_type}的防护建议",
                    "content": type_suggestions[top_type]
                })
        
        # 基于年龄段的建议
        age_group = profile.get("age_group", "adult")
        age_suggestions = {
            "elderly": "老年人是诈骗的重点目标，请子女多关心父母，提醒他们不要轻信陌生来电。",
            "minor": "未成年人要警惕游戏交易、追星诈骗，不要私下与陌生人交易。",
            "adult": "中青年要警惕投资理财、刷单兼职、虚假贷款等诈骗手段。"
        }
        
        if age_group in age_suggestions:
            recommendations.append({
                "category": "general",
                "priority": "medium",
                "title": "针对性防护建议",
                "content": age_suggestions[age_group]
            })
        
        # 通用建议
        recommendations.append({
            "category": "general",
            "priority": "low",
            "title": "通用防护措施",
            "content": "遇到涉及转账、验证码、密码的情况务必谨慎，多与家人商量或拨打反诈热线96110咨询。"
        })
        
        return recommendations
    
    def _generate_chart_data(self, alerts: List) -> Dict:
        """生成图表数据"""
        charts = {}
        
        # 风险等级饼图
        level_data = defaultdict(int)
        for alert in alerts:
            if hasattr(alert, 'level'):
                level_data[alert.level.name_cn] += 1
        
        charts["risk_level_pie"] = {
            "type": "pie",
            "data": [
                {"name": k, "value": v}
                for k, v in level_data.items()
            ]
        }
        
        # 时间折线图
        daily_data = defaultdict(int)
        for alert in alerts:
            if hasattr(alert, 'created_at'):
                date = datetime.fromtimestamp(alert.created_at).strftime("%m-%d")
                daily_data[date] += 1
        
        charts["daily_trend_line"] = {
            "type": "line",
            "data": {
                "dates": list(daily_data.keys()),
                "values": list(daily_data.values())
            }
        }
        
        # 诈骗类型柱状图
        type_data = defaultdict(int)
        for alert in alerts:
            if hasattr(alert, 'risk_type') and alert.risk_type != "normal":
                type_data[alert.risk_type] += 1
        
        charts["scam_type_bar"] = {
            "type": "bar",
            "data": [
                {"name": k, "value": v}
                for k, v in sorted(type_data.items(), key=lambda x: x[1], reverse=True)[:10]
            ]
        }
        
        return charts
    
    def _convert_to_html(self, report: Dict) -> Dict:
        """转换为HTML格式"""
        # 生成HTML内容
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>SmartGuard 安全监测报告</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                .header {{ text-align: center; margin-bottom: 30px; }}
                .section {{ margin: 20px 0; }}
                .metric {{ display: inline-block; margin: 10px 20px; text-align: center; }}
                .metric-value {{ font-size: 2em; font-weight: bold; color: #1890ff; }}
                .metric-label {{ color: #666; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>SmartGuard 安全监测报告</h1>
                <p>报告周期: {report['report_info']['start_date']} 至 {report['report_info']['end_date']}</p>
            </div>
            
            <div class="section">
                <h2>安全概览</h2>
                <div class="metric">
                    <div class="metric-value">{report['summary']['total_alerts']}</div>
                    <div class="metric-label">预警总数</div>
                </div>
                <div class="metric">
                    <div class="metric-value">{report['summary']['high_risk_alerts']}</div>
                    <div class="metric-label">高风险预警</div>
                </div>
                <div class="metric">
                    <div class="metric-value">{report['summary']['protection_score']:.1f}</div>
                    <div class="metric-label">防护评分</div>
                </div>
            </div>
        </body>
        </html>
        """
        
        return {
            "format": "html",
            "content": html_content,
            "report": report
        }
    
    def _prepare_for_pdf(self, report: Dict) -> Dict:
        """准备PDF输出"""
        # 简化处理，实际需要使用reportlab等库生成PDF
        return {
            "format": "pdf",
            "content": None,
            "report": report
        }