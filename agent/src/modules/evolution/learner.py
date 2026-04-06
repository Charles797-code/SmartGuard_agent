"""
知识学习模块
从新案例中自动学习，更新知识库和模型
"""

import time
import json
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import re


@dataclass
class LearningCase:
    """学习案例"""
    case_id: str
    content: str
    modality: str  # text, audio, image, video
    label: str  # scam, normal
    scam_type: Optional[str] = None
    risk_level: Optional[int] = None
    source: str = "unknown"
    keywords: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    learned: bool = False
    learning_score: float = 0.0


@dataclass
class LearningResult:
    """学习结果"""
    cases_processed: int
    cases_learned: int
    new_keywords: List[str]
    new_patterns: List[str]
    accuracy_improvement: float
    details: Dict[str, Any]


class KnowledgeLearner:
    """
    知识学习器
    
    自动从新案例中提取知识，更新关键词库和模式库，
    支持增量学习和主动学习机制。
    """
    
    # 内置诈骗关键词库
    SCAM_KEYWORDS = {
        "police_impersonation": ["公安", "民警", "洗钱", "安全账户", "资金核查", "涉嫌", "逮捕"],
        "investment_fraud": ["投资", "理财", "高收益", "保本", "平台", "导师", "博彩"],
        "part_time_fraud": ["兼职", "刷单", "点赞", "日结", "佣金", "任务"],
        "loan_fraud": ["贷款", "无抵押", "快速放款", "手续费", "解冻"],
        "pig_butchery": ["恋爱", "亲爱的", "导师", "下注", "内幕"],
        "ai_voice_fraud": ["绑架", "出事", "急需", "声音", "汇款"],
        "credit_fraud": ["征信", "逾期", "修复", "洗白", "消除"],
        "refund_fraud": ["退款", "赔偿", "双倍", "备用金", "质量问题"],
        "gaming_fraud": ["游戏", "装备", "账号", "充值", "折扣"],
        "fan_fraud": ["粉丝", "明星", "门票", "打榜", "签名"],
        "medical_fraud": ["医保", "异地", "报销", "套现", "冻结"]
    }
    
    # 诈骗模式库
    SCAM_PATTERNS = {
        "police_impersonation": [
            "你好，我是{authority}民警，你的{issue}被人盗用",
            "涉嫌{crime}，需要将资金转入{account}进行核查",
            "不配合将面临{consequence}"
        ],
        "investment_fraud": [
            "我们有一款高收益理财产品，年化收益率{rate}",
            "跟着{role}下单，保证稳赚不赔",
            "已经有很多人赚了{amount}"
        ],
        "part_time_fraud": [
            "好消息！足不出户，日赚{amount}",
            "只需{action}，一单一结",
            "现在加入还有{bonus}"
        ],
        "pig_butchery": [
            "亲爱的，我发现了一个赚钱的好机会",
            "跟着{role}在{platform}下注",
            "我已经赚了{amount}了"
        ]
    }
    
    def __init__(self, knowledge_base: Optional[Any] = None):
        """
        初始化知识学习器
        
        Args:
            knowledge_base: 知识库实例
        """
        self.knowledge_base = knowledge_base
        
        # 扩展关键词库
        self.extended_keywords: Dict[str, List[str]] = {
            k: list(v) for k, v in self.SCAM_KEYWORDS.items()
        }
        
        # 扩展模式库
        self.extended_patterns: Dict[str, List[str]] = {
            k: list(v) for k, v in self.SCAM_PATTERNS.items()
        }
        
        # 学习统计
        self.learning_stats = {
            "total_cases": 0,
            "learned_cases": 0,
            "new_keywords": [],
            "new_patterns": []
        }
    
    async def learn_from_cases(self, cases: List[Dict]) -> LearningResult:
        """
        从案例中学习
        
        Args:
            cases: 案例列表
            
        Returns:
            LearningResult: 学习结果
        """
        self.learning_stats["total_cases"] += len(cases)
        
        cases_processed = 0
        cases_learned = 0
        new_keywords = []
        new_patterns = []
        
        for case_data in cases:
            try:
                case = self._parse_case(case_data)
                if not case:
                    continue
                
                cases_processed += 1
                
                # 学习关键词
                keywords = await self._learn_keywords(case)
                new_keywords.extend(keywords)
                
                # 学习模式
                patterns = await self._learn_patterns(case)
                new_patterns.extend(patterns)
                
                # 更新知识库
                if keywords or patterns:
                    await self._update_knowledge(case, keywords, patterns)
                    cases_learned += 1
                    case.learned = True
            
            except Exception:
                continue
        
        # 去重
        new_keywords = list(set(new_keywords))
        new_patterns = list(set(new_patterns))
        
        # 更新统计
        self.learning_stats["learned_cases"] += cases_learned
        self.learning_stats["new_keywords"].extend(new_keywords)
        self.learning_stats["new_patterns"].extend(new_patterns)
        
        # 计算准确率提升
        accuracy_improvement = self._calculate_improvement()
        
        return LearningResult(
            cases_processed=cases_processed,
            cases_learned=cases_learned,
            new_keywords=new_keywords,
            new_patterns=new_patterns,
            accuracy_improvement=accuracy_improvement,
            details={
                "total_processed": self.learning_stats["total_cases"],
                "total_learned": self.learning_stats["learned_cases"],
                "keyword_count": len(self.learning_stats["new_keywords"]),
                "pattern_count": len(self.learning_stats["new_patterns"])
            }
        )
    
    def _parse_case(self, case_data: Dict) -> Optional[LearningCase]:
        """解析案例数据"""
        try:
            return LearningCase(
                case_id=case_data.get("case_id", f"case_{time.time()}"),
                content=case_data.get("content", ""),
                modality=case_data.get("modality", "text"),
                label=case_data.get("label", "normal"),
                scam_type=case_data.get("scam_type"),
                risk_level=case_data.get("risk_level"),
                source=case_data.get("source", "unknown"),
                keywords=case_data.get("keywords", []),
                metadata=case_data.get("metadata", {})
            )
        except Exception:
            return None
    
    async def _learn_keywords(self, case: LearningCase) -> List[str]:
        """从案例中学习关键词"""
        if case.label != "scam":
            return []
        
        new_keywords = []
        
        # 提取新关键词
        extracted = self._extract_keywords(case.content)
        
        scam_type = case.scam_type or "unknown"
        
        # 检查是否是新关键词
        existing = self.extended_keywords.get(scam_type, [])
        for kw in extracted:
            if kw not in existing and len(kw) >= 2:
                new_keywords.append(kw)
                existing.append(kw)
        
        # 更新关键词库
        if new_keywords:
            self.extended_keywords[scam_type] = existing
        
        return new_keywords
    
    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词"""
        keywords = []
        
        # 简单的关键词提取
        # 1. 提取数字+单位组合
        money_pattern = r'(\d+(?:\.\d+)?)\s*(?:万|千|百|元|块)'
        matches = re.findall(money_pattern, text)
        for m in matches:
            keywords.append(f"{m}元")
        
        # 2. 提取专业术语
        terms = [
            "安全账户", "资金核查", "导师带单", "连环任务",
            "征信修复", "备用金", "保证金", "解冻费"
        ]
        for term in terms:
            if term in text:
                keywords.append(term)
        
        # 3. 提取情感词
        emotion_words = [
            "紧急", "马上", "立刻", "赶紧", "快点",
            "高收益", "稳赚", "内幕", "保本"
        ]
        for word in emotion_words:
            if word in text:
                keywords.append(word)
        
        return list(set(keywords))
    
    async def _learn_patterns(self, case: LearningCase) -> List[str]:
        """从案例中学习模式"""
        if case.label != "scam" or not case.scam_type:
            return []
        
        new_patterns = []
        
        # 简化实现：提取句式模式
        # 实际需要更复杂的NLP处理
        
        sentences = self._split_sentences(case.content)
        
        for sentence in sentences:
            # 检查是否是潜在的模式
            if self._is_potential_pattern(sentence):
                new_patterns.append(sentence)
                
                # 添加到模式库
                if case.scam_type not in self.extended_patterns:
                    self.extended_patterns[case.scam_type] = []
                
                if sentence not in self.extended_patterns[case.scam_type]:
                    self.extended_patterns[case.scam_type].append(sentence)
        
        return new_patterns
    
    def _split_sentences(self, text: str) -> List[str]:
        """分割句子"""
        # 按标点分割
        sentences = re.split(r'[。！？\n]', text)
        return [s.strip() for s in sentences if s.strip()]
    
    def _is_potential_pattern(self, sentence: str) -> bool:
        """判断是否是潜在模式"""
        # 简单判断
        # 1. 包含诈骗特征的句子
        scam_features = [
            "需要", "必须", "请", "转账", "汇款",
            "账户", "密码", "验证码", "投资", "赚钱"
        ]
        
        feature_count = sum(1 for f in scam_features if f in sentence)
        
        return feature_count >= 2 and len(sentence) >= 10
    
    async def _update_knowledge(self, case: LearningCase, 
                               keywords: List[str], patterns: List[str]):
        """更新知识库"""
        if not self.knowledge_base:
            return
        
        # 构建知识条目
        entry = {
            "type": "scam_case",
            "scam_type": case.scam_type,
            "title": f"新学习案例 - {case.scam_type}",
            "content": case.content,
            "risk_level": case.risk_level or 3,
            "keywords": keywords,
            "metadata": {
                "source": case.source,
                "learned_at": time.time(),
                "patterns": patterns
            }
        }
        
        # 添加到知识库
        await self.knowledge_base.add_entry(entry)
    
    def _calculate_improvement(self) -> float:
        """计算学习提升"""
        # 简化计算
        total = self.learning_stats["total_cases"]
        learned = self.learning_stats["learned_cases"]
        
        if total == 0:
            return 0.0
        
        return learned / total
    
    def get_keyword_library(self, scam_type: Optional[str] = None) -> Dict[str, List[str]]:
        """获取关键词库"""
        if scam_type:
            return {scam_type: self.extended_keywords.get(scam_type, [])}
        return self.extended_keywords
    
    def get_pattern_library(self, scam_type: Optional[str] = None) -> Dict[str, List[str]]:
        """获取模式库"""
        if scam_type:
            return {scam_type: self.extended_patterns.get(scam_type, [])}
        return self.extended_patterns
    
    def export_learning_state(self) -> Dict:
        """导出学习状态"""
        return {
            "extended_keywords": self.extended_keywords,
            "extended_patterns": self.extended_patterns,
            "learning_stats": self.learning_stats
        }
    
    def import_learning_state(self, state: Dict):
        """导入学习状态"""
        if "extended_keywords" in state:
            self.extended_keywords = state["extended_keywords"]
        if "extended_patterns" in state:
            self.extended_patterns = state["extended_patterns"]
        if "learning_stats" in state:
            self.learning_stats = state["learning_stats"]
