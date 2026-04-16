"""
文本输入处理模块
支持聊天记录、短信、OCR识别等文本输入
"""

import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime


@dataclass
class TextInput:
    """文本输入结构"""
    content: str
    source: str = "manual"  # manual, chat, sms, ocr
    timestamp: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class TextAnalysis:
    """文本分析结果"""
    original_text: str
    cleaned_text: str
    language: str
    entity_tags: List[Dict[str, Any]]
    intent_signals: List[str]
    risk_indicators: List[str]
    metadata: Dict[str, Any]


class TextInputHandler:
    """文本输入处理器"""
    
    # 风险信号词库
    RISK_SIGNALS = {
        "money": ["转账", "汇款", "钱", "元", "万", "支付宝", "微信", "银行卡"],
        "urgency": ["紧急", "立刻", "马上", "立即", "限时", "过期", "速"],
        "threat": ["威胁", "恐吓", "逮捕", "起诉", "坐牢", "违法"],
        "secret": ["保密", "秘密", "不能告诉", "别说", "单独"],
        "authority": ["公安", "法院", "检察院", "警察", "局长", "领导"],
        "reward": ["奖金", "中奖", "返利", "佣金", "收益", "赚钱"]
    }
    
    # 意图信号
    INTENT_PATTERNS = {
        "inquiry": ["请问", "我想知道", "问一下", "咨询", "怎么办"],
        "complaint": ["投诉", "举报", "报警", "被骗了"],
        "transfer": ["转账", "汇款", "打钱", "支付"],
        "account": ["账户", "密码", "验证码", "登录"],
        "personal": ["身份证", "姓名", "电话", "地址"]
    }
    
    def __init__(self):
        """初始化文本处理器"""
        self.supported_sources = ["manual", "chat", "sms", "ocr"]
    
    async def process(self, text_input: TextInput) -> TextAnalysis:
        """
        处理文本输入
        
        Args:
            text_input: 文本输入
            
        Returns:
            TextAnalysis: 文本分析结果
        """
        # 1. 清洗文本
        cleaned = self._clean_text(text_input.content)
        
        # 2. 检测语言
        language = self._detect_language(cleaned)
        
        # 3. 实体标注
        entities = self._extract_entities(cleaned)
        
        # 4. 意图识别
        intents = self._detect_intent(cleaned)
        
        # 5. 风险指标检测
        risk_indicators = self._detect_risk_indicators(cleaned)
        
        return TextAnalysis(
            original_text=text_input.content,
            cleaned_text=cleaned,
            language=language,
            entity_tags=entities,
            intent_signals=intents,
            risk_indicators=risk_indicators,
            metadata={
                "source": text_input.source,
                "timestamp": text_input.timestamp or datetime.now().isoformat(),
                **text_input.metadata
            }
        )
    
    def _clean_text(self, text: str) -> str:
        """清洗文本"""
        # 移除多余空白
        text = re.sub(r'\s+', ' ', text)
        
        # 移除特殊字符（保留中文、英文、数字、常用标点）
        text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9\s.,!?;:', '', text)
        
        # 规范化引号
        text = text.replace('"', '"').replace('"', '"')
        text = text.replace(''', "'").replace(''', "'")
        
        # 移除URL
        text = re.sub(r'http[s]?://\S+', '[网址]', text)
        
        # 移除电话号码（保留格式用于分析）
        phone_pattern = r'1[3-9]\d{9}'
        phones = re.findall(phone_pattern, text)
        text = re.sub(phone_pattern, '[电话号码]', text)
        
        # 移除银行卡号
        text = re.sub(r'\d{16,19}', '[银行卡号]', text)
        
        return text.strip()
    
    def _detect_language(self, text: str) -> str:
        """检测语言"""
        # 简单实现：基于字符编码范围
        chinese_chars = len(re.findall(r'[\u4e00-\u9fa5]', text))
        english_chars = len(re.findall(r'[a-zA-Z]', text))
        
        if chinese_chars > english_chars:
            return "zh"
        elif english_chars > 0:
            return "en"
        else:
            return "unknown"
    
    def _extract_entities(self, text: str) -> List[Dict[str, Any]]:
        """提取实体"""
        entities = []
        
        # 电话号码
        phone_pattern = r'1[3-9]\d{9}'
        phones = re.findall(phone_pattern, text)
        for phone in phones:
            entities.append({
                "type": "phone",
                "value": phone,
                "start": text.find(phone)
            })
        
        # 金额
        money_pattern = r'(\d+(?:\.\d+)?)\s*(?:万|千|百|元|块)'
        moneys = re.findall(money_pattern, text)
        for money, unit in moneys:
            entities.append({
                "type": "money",
                "value": f"{money}{unit}",
                "amount": float(money),
                "unit": unit
            })
        
        # 银行相关
        banks = ["工商银行", "农业银行", "中国银行", "建设银行", "招商银行", "支付宝", "微信"]
        for bank in banks:
            if bank in text:
                entities.append({
                    "type": "bank",
                    "value": bank
                })
        
        # 机构名称
        authorities = ["公安局", "检察院", "法院", "公安局", "海关", "税务局"]
        for auth in authorities:
            if auth in text:
                entities.append({
                    "type": "authority",
                    "value": auth
                })
        
        return entities
    
    def _detect_intent(self, text: str) -> List[str]:
        """检测意图"""
        detected_intents = []
        
        for intent, patterns in self.INTENT_PATTERNS.items():
            for pattern in patterns:
                if pattern in text:
                    detected_intents.append(intent)
                    break
        
        return detected_intents
    
    def _detect_risk_indicators(self, text: str) -> List[str]:
        """检测风险指标"""
        indicators = []
        
        text_lower = text.lower()
        
        for category, keywords in self.RISK_SIGNALS.items():
            for keyword in keywords:
                if keyword in text or keyword.lower() in text_lower:
                    indicators.append(f"{category}:{keyword}")
        
        # 特殊模式检测
        special_patterns = {
            "安全账户": "要求转入所谓安全账户",
            "验证码": "要求提供验证码",
            "转账": "涉及资金转账",
            "密码": "涉及密码信息",
            "投资": "涉及投资理财",
            "高收益": "承诺高收益",
            "保本": "承诺保本",
            "无抵押": "无抵押贷款",
            "刷单": "兼职刷单"
        }
        
        for pattern, description in special_patterns.items():
            if pattern in text:
                indicators.append(description)
        
        return list(set(indicators))
    
    def extract_conversation(self, text: str) -> List[Dict[str, str]]:
        """提取对话结构"""
        # 尝试识别对话格式
        messages = []
        
        # 简单实现：按换行分割
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 简单判断发送者
            if line.startswith('对方:') or line.startswith('他:'):
                messages.append({
                    "sender": "other",
                    "content": line.split(':', 1)[1].strip()
                })
            elif line.startswith('我:') or line.startswith('自己:'):
                messages.append({
                    "sender": "self",
                    "content": line.split(':', 1)[1].strip()
                })
            else:
                # 尝试自动判断
                if "?" in line or "吗" in line or "？" in line:
                    messages.append({
                        "sender": "other",
                        "content": line
                    })
                else:
                    messages.append({
                        "sender": "unknown",
                        "content": line
                    })
        
        return messages
    
    def summarize_for_context(self, analysis: TextAnalysis, max_length: int = 200) -> str:
        """生成上下文摘要"""
        parts = []
        
        # 原始文本（截断）
        if len(analysis.cleaned_text) > max_length:
            parts.append(analysis.cleaned_text[:max_length] + "...")
        else:
            parts.append(analysis.cleaned_text)
        
        # 关键实体
        if analysis.entity_tags:
            entity_types = list(set([e["type"] for e in analysis.entity_tags]))
            parts.append(f"涉及实体: {', '.join(entity_types)}")
        
        # 意图信号
        if analysis.intent_signals:
            parts.append(f"意图信号: {', '.join(analysis.intent_signals)}")
        
        # 风险指标
        if analysis.risk_indicators:
            parts.append(f"风险指标: {', '.join(analysis.risk_indicators[:5])}")
        
        return " | ".join(parts)