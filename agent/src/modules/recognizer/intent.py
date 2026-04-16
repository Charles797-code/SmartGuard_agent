"""
意图识别模块
使用Prompt Engineering和大模型进行精准的对话意图判断
"""

import json
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum


class IntentType(Enum):
    """意图类型枚举"""
    NORMAL = "normal"
    INQUIRY = "inquiry"
    COMPLAINT = "complaint"
    SCAM_REPORT = "scam_report"
    SEEK_HELP = "seek_help"
    TRANSFER_REQUEST = "transfer_request"
    PERSONAL_INFO_REQUEST = "personal_info_request"
    UNKNOWN = "unknown"


@dataclass
class IntentResult:
    """意图识别结果"""
    intent: str
    confidence: float
    sub_intent: Optional[str] = None
    entities: List[Dict[str, Any]] = None
    analysis: str = ""
    
    def __post_init__(self):
        if self.entities is None:
            self.entities = []


class IntentRecognizer:
    """
    意图识别器
    
    通过精心设计的Prompt Engineering，实现对用户输入的精准意图判断。
    支持多种意图类型，包括正常对话、咨询、投诉、诈骗举报、求助等。
    """
    
    # 意图识别Prompt模板
    INTENT_PROMPT_TEMPLATE = """你是SmartGuard智能反诈助手的意图识别模块。你的任务是根据用户的输入，准确判断用户的真实意图。

【输入信息】
{user_input}

【上下文信息】
{context}

【意图类型定义】
1. normal - 正常对话：日常交流、寒暄、无风险内容的聊天
2. inquiry - 咨询求助：询问反诈知识、寻求防护建议、了解诈骗手法
3. complaint - 投诉举报：举报诈骗、投诉骚扰、报警
4. scam_report - 诈骗上报：正在遭遇或已经遭遇诈骗，需要帮助
5. seek_help - 寻求帮助：不确定是否被骗，请求分析判断
6. transfer_request - 转账请求：涉及转账、汇款等资金操作
7. personal_info_request - 个人信息请求：对方要求提供身份证、密码等敏感信息
8. unknown - 无法判断：信息不足或模糊

【输出要求】
请仔细分析输入内容，判断最可能的意图类型。如果涉及多个意图，选择风险最高的一个。

请以JSON格式输出：
{{
    "intent": "意图类型",
    "confidence": 置信度(0-1),
    "sub_intent": "子意图(可选)",
    "entities": [{{"type": "实体类型", "value": "实体值"}}],
    "analysis": "简短分析说明"
}}

注意：
- 必须严格遵循JSON格式，不要包含其他内容
- confidence应该反映你对判断的自信程度
- 如果是诈骗相关，entities应包含涉及的金额、账号等信息"""
    
    # 诈骗类型识别子意图
    SCAM_SUB_INTENTS = {
        "police_impersonation": "冒充公检法诈骗",
        "investment_fraud": "投资理财诈骗",
        "part_time_fraud": "兼职刷单诈骗",
        "loan_fraud": "虚假贷款诈骗",
        "pig_butchery": "杀猪盘诈骗",
        "ai_voice_fraud": "AI语音合成诈骗",
        "deepfake_fraud": "视频深度伪造诈骗",
        "credit_fraud": "虚假征信诈骗",
        "refund_fraud": "购物退款诈骗",
        "gaming_fraud": "游戏交易诈骗",
        "fan_fraud": "追星诈骗",
        "medical_fraud": "医保诈骗"
    }
    
    def __init__(self, llm_client: Optional[Any] = None):
        """
        初始化意图识别器
        
        Args:
            llm_client: LLM客户端（可选）
        """
        self.llm_client = llm_client
        self.use_llm_fallback = True  # LLM不可用时使用规则匹配
    
    async def recognize(self, user_input: str, 
                       context: Optional[Dict] = None) -> IntentResult:
        """
        识别用户意图
        
        Args:
            user_input: 用户输入文本
            context: 上下文信息
            
        Returns:
            IntentResult: 意图识别结果
        """
        # 1. 优先使用LLM进行识别
        if self.llm_client:
            try:
                result = await self._llm_recognize(user_input, context)
                if result:
                    return result
            except Exception:
                pass
        
        # 2. 回退到规则匹配
        return self._rule_based_recognize(user_input, context)
    
    async def _llm_recognize(self, user_input: str, 
                            context: Optional[Dict]) -> Optional[IntentResult]:
        """使用LLM进行意图识别"""
        try:
            # 构建Prompt
            context_text = self._format_context(context)
            prompt = self.INTENT_PROMPT_TEMPLATE.format(
                user_input=user_input,
                context=context_text
            )
            
            # 调用LLM
            response = await self.llm_client.generate(prompt)
            
            # 解析响应
            if response and response.strip():
                result = json.loads(response)
                return IntentResult(
                    intent=result.get("intent", "unknown"),
                    confidence=result.get("confidence", 0.5),
                    sub_intent=result.get("sub_intent"),
                    entities=result.get("entities", []),
                    analysis=result.get("analysis", "")
                )
        
        except Exception:
            return None
    
    def _rule_based_recognize(self, user_input: str,
                             context: Optional[Dict]) -> IntentResult:
        """基于规则的意图识别"""
        # 规则模式
        intent_patterns = {
            "transfer_request": {
                "keywords": ["转账", "汇款", "打钱", "付款", "支付", "汇款"],
                "weight": 3.0
            },
            "personal_info_request": {
                "keywords": ["身份证", "密码", "验证码", "账户", "银行卡", "社保卡"],
                "weight": 2.5
            },
            "scam_report": {
                "keywords": ["被骗", "上当了", "诈骗", "举报", "报警"],
                "weight": 3.0
            },
            "seek_help": {
                "keywords": ["帮忙", "帮我看看", "是不是", "会不会", "求助"],
                "weight": 1.5
            },
            "inquiry": {
                "keywords": ["请问", "咨询", "怎么", "如何", "为什么", "什么是"],
                "weight": 1.0
            },
            "complaint": {
                "keywords": ["投诉", "举报", "骚扰", "骗子", "假冒"],
                "weight": 2.0
            }
        }
        
        # 计算各意图分数
        scores = {}
        for intent, config in intent_patterns.items():
            score = 0.0
            keywords = config["keywords"]
            weight = config["weight"]
            
            for keyword in keywords:
                if keyword in user_input:
                    score += weight
            
            if score > 0:
                scores[intent] = score
        
        # 选择最高分意图
        if scores:
            best_intent = max(scores.items(), key=lambda x: x[1])
            intent = best_intent[0]
            # 将分数转换为置信度
            confidence = min(best_intent[1] / 3.0, 1.0)
        else:
            intent = "normal"
            confidence = 0.8
        
        # 检测子意图（诈骗类型）
        sub_intent = self._detect_scam_subtype(user_input)
        
        # 提取实体
        entities = self._extract_intent_entities(user_input, intent)
        
        return IntentResult(
            intent=intent,
            confidence=confidence,
            sub_intent=sub_intent,
            entities=entities,
            analysis=f"基于关键词匹配识别为{intent}类型"
        )
    
    def _detect_scam_subtype(self, text: str) -> Optional[str]:
        """检测诈骗子类型"""
        subtype_patterns = {
            "police_impersonation": ["公安", "民警", "警官", "警察", "洗钱", "涉嫌"],
            "investment_fraud": ["投资", "理财", "高收益", "平台", "博彩"],
            "part_time_fraud": ["兼职", "刷单", "点赞", "日结", "佣金"],
            "loan_fraud": ["贷款", "无抵押", "快速放款", "手续费"],
            "pig_butchery": ["亲爱的", "恋爱", "导师", "下注"],
            "ai_voice_fraud": ["绑架", "出事", "急需", "声音"],
            "credit_fraud": ["征信", "逾期", "修复", "洗白"],
            "refund_fraud": ["退款", "赔偿", "质量问题", "备用金"],
            "gaming_fraud": ["游戏", "装备", "账号", "充值"],
            "fan_fraud": ["粉丝", "追星", "明星", "打榜"],
            "medical_fraud": ["医保", "报销", "异地", "套现"]
        }
        
        for scam_type, keywords in subtype_patterns.items():
            match_count = sum(1 for kw in keywords if kw in text)
            if match_count >= 2:
                return scam_type
        
        return None
    
    def _extract_intent_entities(self, text: str, intent: str) -> List[Dict[str, Any]]:
        """提取意图相关实体"""
        entities = []
        
        # 金额提取
        import re
        money_pattern = r'(\d+(?:\.\d+)?)\s*(?:万|千|百|元|块)'
        moneys = re.findall(money_pattern, text)
        for money, unit in moneys:
            entities.append({
                "type": "money",
                "value": f"{money}{unit}",
                "amount": float(money),
                "unit": unit
            })
        
        # 电话号码提取
        phone_pattern = r'1[3-9]\d{9}'
        phones = re.findall(phone_pattern, text)
        for phone in phones:
            entities.append({
                "type": "phone",
                "value": phone
            })
        
        # 账号提取
        account_pattern = r'([a-zA-Z0-9_]{6,20}@(?:qq|163|126|gmail|outlook)\.com|[a-zA-Z0-9]{8,16})'
        accounts = re.findall(account_pattern, text, re.IGNORECASE)
        for account in accounts:
            entities.append({
                "type": "account",
                "value": account
            })
        
        return entities
    
    def _format_context(self, context: Optional[Dict]) -> str:
        """格式化上下文信息"""
        if not context:
            return "无额外上下文"
        
        parts = []
        
        if "user_profile" in context:
            profile = context["user_profile"]
            parts.append(f"用户画像：年龄{profile.get('age_group', '未知')}，"
                        f"历史风险次数{profile.get('risk_history_count', 0)}")
        
        if "recent_messages" in context:
            recent = context["recent_messages"]
            parts.append(f"最近对话：{recent[-200:] if len(recent) > 200 else recent}")
        
        if "situation" in context:
            parts.append(f"当前情况：{context['situation']}")
        
        return "\n".join(parts) if parts else "无额外上下文"
    
    def batch_recognize(self, inputs: List[str]) -> List[IntentResult]:
        """批量意图识别"""
        return [self._rule_based_recognize(inp, None) for inp in inputs]
    
    def get_intent_hierarchy(self) -> Dict[str, Any]:
        """获取意图层次结构"""
        return {
            "primary_intents": {
                "normal": "正常对话",
                "inquiry": "咨询求助",
                "complaint": "投诉举报",
                "scam_report": "诈骗上报",
                "seek_help": "寻求帮助",
                "transfer_request": "转账请求",
                "personal_info_request": "个人信息请求"
            },
            "scam_subtypes": self.SCAM_SUB_INTENTS,
            "intent_mapping": {
                "high_risk": ["transfer_request", "personal_info_request", "scam_report"],
                "medium_risk": ["seek_help", "complaint"],
                "low_risk": ["inquiry", "normal"]
            }
        }