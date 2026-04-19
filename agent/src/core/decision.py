"""
风险决策引擎
基于规则和模型的风险评估决策模块
"""

import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum


class RiskLevel(Enum):
    """风险等级枚举"""
    SAFE = 0
    ATTENTION = 1
    WARNING = 2
    DANGER = 3
    EMERGENCY = 4


class ScamType(Enum):
    """诈骗类型枚举"""
    NORMAL = "normal"
    POLICE_IMPERSONATION = "police_impersonation"
    INVESTMENT_FRAUD = "investment_fraud"
    PART_TIME_FRAUD = "part_time_fraud"
    LOAN_FRAUD = "loan_fraud"
    PIG_BUTCHERY = "pig_butchery"
    AI_VOICE_FRAUD = "ai_voice_fraud"
    DEEPFAKE_FRAUD = "deepfake_fraud"
    CREDIT_FRAUD = "credit_fraud"
    REFUND_FRAUD = "refund_fraud"
    GAMING_FRAUD = "gaming_fraud"
    FAN_FRAUD = "fan_fraud"
    MEDICAL_FRAUD = "medical_fraud"
    UNKNOWN = "unknown"


@dataclass
class RiskAssessment:
    """风险评估结果"""
    risk_level: int
    risk_type: str
    confidence: float
    analysis: str
    suggestion: str
    warning_message: str
    triggered_keywords: List[str]
    recommended_actions: List[str]
    timestamp: float
    _direct_response: str = ""  # LLM 直接生成的完整自然语言响应，优先于模板

    def to_dict(self) -> Dict:
        return {
            "risk_level": self.risk_level,
            "risk_type": self.risk_type,
            "confidence": self.confidence,
            "analysis": self.analysis,
            "suggestion": self.suggestion,
            "warning_message": self.warning_message,
            "triggered_keywords": self.triggered_keywords,
            "recommended_actions": self.recommended_actions,
            "timestamp": self.timestamp
        }


class RiskDecisionEngine:
    """风险决策引擎"""
    
    # 诈骗关键词权重
    KEYWORD_WEIGHTS = {
        # 冒充公检法
        "安全账户": 3.0,
        "资金核查": 2.5,
        "洗钱": 2.0,
        "拘捕令": 2.5,
        "公安民警": 2.0,
        "检察院": 1.5,
        "验证码": 2.0,
        
        # 投资理财
        "高收益": 2.0,
        "保本": 2.5,
        "内幕消息": 2.0,
        "稳赚不赔": 3.0,
        "导师带单": 2.5,
        "投资平台": 1.5,
        "博彩": 2.0,
        
        # 兼职刷单
        "刷单": 2.5,
        "点赞": 1.5,
        "日结": 1.5,
        "佣金": 1.5,
        "任务单": 1.5,
        "足不出户": 1.0,
        
        # 贷款诈骗
        "无抵押": 1.5,
        "低利率": 1.5,
        "低利息": 1.5,
        "两厘": 2.5,
        "利息": 1.0,
        "快速放款": 1.5,
        "解冻": 2.0,
        "手续费": 1.5,
        "审核": 1.0,
        "填表": 1.0,
        "申请": 1.0,
        "客户经理": 1.0,
        "链接": 2.5,
        "网址": 2.0,
        "官网": 0.5,
        "建行": 1.0,
        "银行": 1.0,
        "资金周转": 1.5,
        "急需": 1.0,
        "流水": 1.5,
        "收入证明": 1.5,
        
        # 杀猪盘
        "亲爱的": 1.0,
        "恋爱": 1.0,
        "博彩平台": 2.5,
        "下注": 2.0,
        
        # AI诈骗
        "绑架": 3.0,
        "出事": 2.0,
        "急需用钱": 2.0,
        "汇款": 2.5,
        
        # 征信诈骗
        "征信": 1.5,
        "逾期": 1.5,
        "修复": 2.0,
        "洗白": 2.5,
        
        # 退款诈骗
        "双倍赔偿": 2.0,
        "退款": 1.5,
        "备用金": 2.0,
        
        # 游戏交易
        "装备": 1.0,
        "账号买卖": 1.5,
        "折扣": 1.0,
        
        # 追星诈骗
        "粉丝群": 1.0,
        "打榜": 1.0,
        "明星福利": 1.5,
        "门票": 1.0,
        
        # 医保诈骗
        "医保": 1.5,
        "异地报销": 2.0,
        "套现": 2.5,
        
        # 通用高风险词
        "转账": 2.0,
        "汇款": 2.0,
        "密码": 2.5,
        "验证码": 2.5,
        "账户": 1.5,
        "银行": 1.5,
    }
    
    # 诈骗类型特征组合
    SCAM_PATTERNS = {
        "police_impersonation": {
            "required_keywords": ["公安", "民警", "警官", "洗钱", "涉嫌"],
            "additional_score": 1.5,
            "context_patterns": ["资金", "账户", "转账", "验证码"]
        },
        "investment_fraud": {
            "required_keywords": ["高收益", "投资", "理财"],
            "additional_score": 1.5,
            "context_patterns": ["保本", "稳赚", "平台", "导师"]
        },
        "part_time_fraud": {
            "required_keywords": ["兼职", "刷单", "点赞"],
            "additional_score": 1.5,
            "context_patterns": ["日结", "佣金", "任务", "返利"]
        },
        "loan_fraud": {
            "required_keywords": ["贷款", "无抵押"],
            "additional_score": 1.5,
            "context_patterns": ["手续费", "解冻", "快速"]
        },
        "pig_butchery": {
            "required_keywords": ["投资", "平台", "赚钱"],
            "additional_score": 1.5,
            "context_patterns": ["恋爱", "亲爱的", "导师", "博彩"]
        },
        "ai_voice_fraud": {
            "required_keywords": ["绑架", "出事", "急需"],
            "additional_score": 2.0,
            "context_patterns": ["汇款", "转账", "现金"]
        },
        "credit_fraud": {
            "required_keywords": ["征信", "逾期"],
            "additional_score": 1.5,
            "context_patterns": ["修复", "洗白", "消除"]
        },
        "refund_fraud": {
            "required_keywords": ["退款", "赔偿"],
            "additional_score": 1.5,
            "context_patterns": ["质量问题", "双倍", "备用金"]
        }
    }
    
    # 用户画像风险调整
    PROFILE_ADJUSTMENTS = {
        "elderly": {
            "base_adjustment": 1,  # 风险等级+1
            "money_keywords_boost": 2.0,  # 涉钱关键词权重翻倍
            "description": "老年人风险阈值降低"
        },
        "minor": {
            "base_adjustment": 1,
            "money_keywords_boost": 2.5,
            "description": "未成年人更严格的风险评估"
        },
        "accounting": {
            "base_adjustment": 1,
            "transaction_boost": 2.0,
            "description": "财会人员增加交易验证"
        },
        "default": {
            "base_adjustment": 0,
            "description": "默认配置"
        }
    }
    
    def __init__(self):
        """初始化决策引擎"""
        self.risk_threshold = {
            "safe": 0,
            "attention": 2.0,
            "warning": 4.0,
            "danger": 6.0,
            "emergency": 8.0
        }
    
    def assess_risk(self, text: str, user_profile: Optional[Dict] = None,
                   context: Optional[Dict] = None) -> RiskAssessment:
        """
        综合风险评估
        
        Args:
            text: 输入文本
            user_profile: 用户画像
            context: 上下文信息
            
        Returns:
            RiskAssessment: 风险评估结果
        """
        # 1. 关键词检测
        triggered_keywords = self._detect_keywords(text)
        keyword_score = self._calculate_keyword_score(triggered_keywords)
        
        # 2. 模式匹配
        matched_patterns = self._match_scam_patterns(text)
        pattern_score = len(matched_patterns) * 1.5
        
        # 3. 上下文增强
        context_boost = self._analyze_context_boost(text, context or {})
        
        # 4. 基础风险分数
        base_score = keyword_score + pattern_score + context_boost
        
        # 5. 用户画像调整
        adjusted_score = self._apply_profile_adjustment(
            base_score, user_profile or {}, text
        )
        
        # 6. 确定风险类型
        risk_type = self._determine_risk_type(matched_patterns, triggered_keywords)
        
        # 7. 风险等级映射
        risk_level = self._score_to_level(adjusted_score)
        
        # 8. 生成分析和建议
        analysis, suggestion = self._generate_analysis_and_suggestion(
            risk_level, risk_type, triggered_keywords, matched_patterns
        )
        
        # 9. 生成警告信息
        warning_message = self._generate_warning_message(
            risk_level, risk_type, suggestion
        )
        
        # 10. 推荐行动
        recommended_actions = self._get_recommended_actions(risk_level, risk_type)
        
        # 11. 计算置信度
        confidence = self._calculate_confidence(
            keyword_score, pattern_score, context_boost
        )
        
        return RiskAssessment(
            risk_level=risk_level,
            risk_type=risk_type,
            confidence=confidence,
            analysis=analysis,
            suggestion=suggestion,
            warning_message=warning_message,
            triggered_keywords=triggered_keywords,
            recommended_actions=recommended_actions,
            timestamp=time.time()
        )
    
    def _detect_keywords(self, text: str) -> List[Tuple[str, float]]:
        """检测触发关键词"""
        triggered = []
        text_lower = text.lower()
        
        for keyword, weight in self.KEYWORD_WEIGHTS.items():
            if keyword in text or keyword.lower() in text_lower:
                triggered.append((keyword, weight))
        
        return triggered
    
    def _calculate_keyword_score(self, triggered: List[Tuple[str, float]]) -> float:
        """计算关键词分数"""
        if not triggered:
            return 0.0
        
        # 加权求和
        total = sum(weight for _, weight in triggered)
        
        # 多重触发奖励
        bonus = 0.5 * (len(triggered) - 1) if len(triggered) > 1 else 0
        
        return min(total + bonus, 10.0)  # 上限10分
    
    def _match_scam_patterns(self, text: str) -> List[str]:
        """匹配诈骗模式"""
        matched = []
        
        for scam_type, pattern in self.SCAM_PATTERNS.items():
            required = pattern["required_keywords"]
            
            # 检查是否包含所有必需关键词
            if all(kw in text for kw in required):
                matched.append(scam_type)
            # 或者包含多个必需关键词
            elif sum(kw in text for kw in required) >= 2:
                matched.append(scam_type)
        
        return matched
    
    def _analyze_context_boost(self, text: str, context: Dict) -> float:
        """分析上下文增强"""
        boost = 0.0
        
        # 上下文中的风险指示
        if context.get("recent_high_risk"):
            boost += 1.0
        
        # 连续对话中的风险递增
        if context.get("risk_escalation"):
            boost += 1.5
        
        # 涉及金额
        money_mentioned = any(word in text for word in ["钱", "元", "万", "转账", "汇款"])
        if money_mentioned and context.get("urgency"):
            boost += 2.0
        
        return boost
    
    def _apply_profile_adjustment(self, base_score: float, 
                                  profile: Dict, text: str) -> float:
        """应用用户画像调整"""
        age_group = profile.get("age_group", "default")
        adjustment_config = self.PROFILE_ADJUSTMENTS.get(
            age_group, self.PROFILE_ADJUSTMENTS["default"]
        )
        
        adjusted = base_score + adjustment_config["base_adjustment"]
        
        # 涉钱关键词权重增强
        if "money_keywords_boost" in adjustment_config:
            if any(word in text for word in ["转账", "汇款", "钱", "支付"]):
                adjusted += adjustment_config["money_keywords_boost"]
        
        # 财会人员交易验证增强
        if "transaction_boost" in adjustment_config:
            if any(word in text for word in ["汇款", "转账", "支付", "账户"]):
                adjusted += adjustment_config["transaction_boost"]
        
        return adjusted
    
    def _determine_risk_type(self, patterns: List[str], 
                            keywords: List[Tuple[str, float]]) -> str:
        """确定风险类型"""
        if not patterns:
            # 基于关键词推断
            keyword_names = [kw[0] for kw in keywords]
            
            if "安全账户" in keyword_names or "验证码" in keyword_names:
                return "police_impersonation"
            elif "高收益" in keyword_names or "保本" in keyword_names:
                return "investment_fraud"
            elif "刷单" in keyword_names or "日结" in keyword_names:
                return "part_time_fraud"
            elif "贷款" in keyword_names:
                return "loan_fraud"
            elif "征信" in keyword_names:
                return "credit_fraud"
            elif "退款" in keyword_names:
                return "refund_fraud"
            else:
                return "normal"
        
        return patterns[0] if patterns else "normal"
    
    def _score_to_level(self, score: float) -> int:
        """分数转等级"""
        if score < self.risk_threshold["attention"]:
            return 0
        elif score < self.risk_threshold["warning"]:
            return 1
        elif score < self.risk_threshold["danger"]:
            return 2
        elif score < self.risk_threshold["emergency"]:
            return 3
        else:
            return 4
    
    def _generate_analysis_and_suggestion(self, level: int, risk_type: str,
                                        keywords: List[Tuple], patterns: List[str]) -> Tuple[str, str]:
        """生成分析和建议"""
        if level == 0:
            return ("未检测到明显的诈骗特征", "正常交流即可")
        
        # 风险类型中文名
        type_names = {
            "police_impersonation": "冒充公检法诈骗",
            "investment_fraud": "投资理财诈骗",
            "part_time_fraud": "兼职刷单诈骗",
            "loan_fraud": "虚假贷款诈骗",
            "pig_butchery": "杀猪盘诈骗",
            "ai_voice_fraud": "AI语音合成诈骗",
            "credit_fraud": "虚假征信诈骗",
            "refund_fraud": "购物退款诈骗",
            "normal": "未知诈骗"
        }
        
        type_name = type_names.get(risk_type, "未知诈骗")
        
        # 构建分析文本
        keyword_list = [kw[0] for kw in keywords[:5]]
        analysis = f"检测到{type_name}特征，触发关键词: {', '.join(keyword_list)}"
        
        if level >= 3:
            suggestion = f"请立即停止操作！不要转账或提供任何个人信息。"
        elif level == 2:
            suggestion = f"高度怀疑为{type_name}，建议核实对方身份后再操作。"
        else:
            suggestion = f"存在一定的{type_name}风险，请保持警惕。"
        
        return analysis, suggestion
    
    def _generate_warning_message(self, level: int, risk_type: str, 
                                  suggestion: str) -> str:
        """生成警告信息"""
        messages = {
            0: "",
            1: f"💡 温馨提示：{suggestion}",
            2: f"⚠️ 警告：{suggestion}",
            3: f"🚨 危险：{suggestion}\n请立即停止操作！",
            4: f"🆘 紧急风险：{suggestion}\n正在通知您的监护人..."
        }
        
        return messages.get(level, "")
    
    def _get_recommended_actions(self, level: int, risk_type: str) -> List[str]:
        """获取推荐行动"""
        base_actions = {
            0: ["继续保持警惕"],
            1: ["核实对方身份", "不要轻易转账"],
            2: ["停止当前操作", "报警咨询", "联系家人"],
            3: ["立即停止操作", "不转账不透露密码", "报警处理"],
            4: ["立即报警", "联系监护人", "保留证据"]
        }
        
        type_specific = {
            "police_impersonation": ["不要转账到安全账户", "拨打110核实"],
            "investment_fraud": ["不要相信高收益承诺", "通过正规渠道投资"],
            "part_time_fraud": ["刷单是违法行为", "远离刷单兼职"],
            "loan_fraud": ["通过正规金融机构贷款", "不要预付费用"],
            "pig_butchery": ["网络交友需谨慎", "不要轻信投资建议"],
            "ai_voice_fraud": ["先电话核实家人情况", "不要急于转账"],
            "credit_fraud": ["征信无法人为修复", "通过正当途径办理"]
        }
        
        actions = base_actions.get(level, [])
        
        if risk_type in type_specific:
            actions.extend(type_specific[risk_type])
        
        return list(set(actions))[:5]  # 去重，限制数量
    
    def _calculate_confidence(self, keyword_score: float, 
                             pattern_score: float, context_boost: float) -> float:
        """计算置信度"""
        # 基于分数的置信度
        score_components = [
            min(keyword_score / 5.0, 1.0) * 0.4,  # 关键词占40%
            min(pattern_score / 3.0, 1.0) * 0.4,  # 模式占40%
            min(context_boost / 3.0, 1.0) * 0.2  # 上下文占20%
        ]
        
        confidence = sum(score_components)
        
        # 模式匹配增加置信度
        if pattern_score > 0:
            confidence = min(confidence * 1.2, 1.0)
        
        return round(confidence, 2)
    
    def fuse_multimodal_risk(self, text_risk: RiskAssessment,
                            image_risk: Optional[RiskAssessment] = None,
                            audio_risk: Optional[RiskAssessment] = None) -> RiskAssessment:
        """多模态风险融合"""
        # 收集所有风险评估
        risks = [text_risk]
        if image_risk:
            risks.append(image_risk)
        if audio_risk:
            risks.append(audio_risk)
        
        # 加权融合
        total_weight = len(risks)
        
        fused_level = sum(r.risk_level for r in risks) / total_weight
        fused_confidence = sum(r.confidence for r in risks) / total_weight
        
        # 取最高风险类型
        risk_types = [r.risk_type for r in risks if r.risk_type != "normal"]
        primary_type = risk_types[0] if risk_types else "normal"
        
        # 合并触发关键词
        all_keywords = []
        for r in risks:
            all_keywords.extend(r.triggered_keywords)
        all_keywords = list(set(all_keywords))[:10]
        
        # 取最高等级的风险评估详情
        max_risk = max(risks, key=lambda x: x.risk_level)
        
        return RiskAssessment(
            risk_level=round(fused_level),
            risk_type=primary_type,
            confidence=fused_confidence,
            analysis=max_risk.analysis,
            suggestion=max_risk.suggestion,
            warning_message=max_risk.warning_message,
            triggered_keywords=all_keywords,
            recommended_actions=max_risk.recommended_actions,
            timestamp=time.time()
        )