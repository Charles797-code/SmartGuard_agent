"""
知识学习模块
从新案例中自动学习，更新知识库和模型，支持增量学习和主动学习机制
"""

import time
import re
import json
import asyncio
import math
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from collections import defaultdict
from difflib import SequenceMatcher
import hashlib


# ============================================================
# 诈骗类型定义
# ============================================================

SCAM_TYPE_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "police_impersonation": {
        "name": "冒充公检法诈骗",
        "description": "骗子冒充公安机关、检察院、法院工作人员，以涉嫌犯罪为由要求转账",
        "core_keywords": ["公安", "民警", "警官", "警察", "检察院", "法院", "洗钱", "涉嫌", "犯罪", "通缉", "逮捕", "拘捕令", "资金核查", "安全账户", "保证金"],
        "temporal_words": ["限时", "立即", "马上", "否则", "不然", "后果", "逮捕", "坐牢"],
        "action_words": ["转账", "汇款", "核查", "验证", "配合", "保密"]
    },
    "investment_fraud": {
        "name": "投资理财诈骗",
        "description": "以高收益、低风险为诱饵，诱导受害者下载虚假投资平台进行充值",
        "core_keywords": ["投资", "理财", "高收益", "保本", "稳赚", "内幕", "导师", "带单", "平台", "博彩", "彩票", "下注"],
        "temporal_words": ["限时", "名额有限", "错过", "截止", "最后机会", "立即加入"],
        "action_words": ["充值", "入金", "提现", "开户", "注册", "跟单"]
    },
    "part_time_fraud": {
        "name": "兼职刷单诈骗",
        "description": "以刷单返利为诱饵，先让受害者小赚，等大额充值后拒绝提现",
        "core_keywords": ["兼职", "刷单", "点赞", "收藏", "关注", "日结", "佣金", "任务", "返利", "垫付"],
        "temporal_words": ["随时", "日结", "立刻返", "马上到账"],
        "action_words": ["垫付", "预付", "押金", "保证金", "连环任务", "三连单"]
    },
    "loan_fraud": {
        "name": "虚假贷款诈骗",
        "description": "以无抵押、低利率、快速放款为诱饵，以各种名义收取费用后失联",
        "core_keywords": ["贷款", "无抵押", "低利率", "快速放款", "手续费", "解冻", "保证金", "验资", "流水"],
        "temporal_words": ["当天", "秒批", "极速", "立刻", "马上"],
        "action_words": ["先付", "预付", "转账", "验资", "激活", "开会员"]
    },
    "pig_butchery": {
        "name": "杀猪盘诈骗",
        "description": "通过婚恋网站或社交平台建立感情，然后诱导受害者参与虚假投资",
        "core_keywords": ["恋爱", "亲爱的", "宝贝", "老公", "老婆", "导师", "下注", "博彩", "内幕", "平台", "投资", "赚钱", "感觉"],
        "temporal_words": ["等", "以后", "将来", "一起", "未来"],
        "action_words": ["投资", "充值", "转账", "跟单", "下注", "借钱"]
    },
    "ai_voice_fraud": {
        "name": "AI语音合成诈骗",
        "description": "利用AI技术合成子女或亲友声音，制造紧急情况要求汇款",
        "core_keywords": ["绑架", "出事", "急需", "汇款", "现钱", "现金", "转账", "救我", "妈妈", "爸爸", "声音"],
        "temporal_words": ["马上", "立刻", "赶紧", "快点", "来不及", "紧急"],
        "action_words": ["汇款", "转账", "现金", "救", "赎金"]
    },
    "credit_fraud": {
        "name": "虚假征信诈骗",
        "description": "声称可以修复不良征信记录，以各种名义收取费用",
        "core_keywords": ["征信", "逾期", "黑名单", "修复", "洗白", "消除", "不良记录", "信用"],
        "temporal_words": ["修复", "恢复", "申诉", "处理"],
        "action_words": ["转账", "付费", "手续费", "服务费", "加急"]
    },
    "refund_fraud": {
        "name": "购物退款诈骗",
        "description": "冒充电商平台或快递客服，以质量问题、双倍赔偿等为由诱导转账",
        "core_keywords": ["退款", "赔偿", "双倍", "备用金", "质量问题", "订单异常", "快递丢失", "客服"],
        "temporal_words": ["过期", "失效", "必须", "马上"],
        "action_words": ["转账", "扫码", "屏幕共享", "验证码", "备用金", "开通"]
    },
    "gaming_fraud": {
        "name": "游戏交易诈骗",
        "description": "以低价出售装备或代练为诱饵，诱导在第三方平台充值后失联",
        "core_keywords": ["游戏", "装备", "账号", "充值", "折扣", "代练", "皮肤", "道具", "交易"],
        "temporal_words": ["限时", "特惠", "最后", "立即"],
        "action_words": ["充值", "转账", "扫码", "付款", "交易"]
    },
    "fan_fraud": {
        "name": "追星诈骗",
        "description": "冒充明星粉丝群管理员或明星本人，以内部福利、门票等为由骗取钱财",
        "core_keywords": ["粉丝", "明星", "偶像", "门票", "签名", "打榜", "福利", "应援", "后援会", "群"],
        "temporal_words": ["限量", "限时", "截止", "错过"],
        "action_words": ["转账", "付款", "押金", "保证金", "入群费"]
    },
    "medical_fraud": {
        "name": "医保诈骗",
        "description": "冒充医保局工作人员，声称医保卡被盗用或涉嫌异地报销",
        "core_keywords": ["医保", "社保", "异地", "报销", "盗用", "冻结", "套现", "资金核查", "安全账户"],
        "temporal_words": ["限时", "立即", "否则", "后果"],
        "action_words": ["转账", "核查", "验证", "解冻"]
    }
}


# ============================================================
# 数据类定义
# ============================================================

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

    # 新增字段
    extracted_entities: Dict[str, Any] = field(default_factory=dict)
    matched_patterns: List[str] = field(default_factory=list)
    confidence: float = 0.0
    quality_score: float = 0.0


@dataclass
class ExtractedPattern:
    """提取的模式"""
    pattern_id: str
    pattern_text: str
    scam_type: str
    frequency: int = 1
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    templates: List[str] = field(default_factory=list)
    slots: List[str] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)
    confidence: float = 0.0
    active: bool = True


@dataclass
class LearnedKeyword:
    """学习到的关键词"""
    keyword: str
    scam_type: str
    weight: float = 1.0
    frequency: int = 1
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    source_cases: List[str] = field(default_factory=list)
    is_verified: bool = False
    is_noisy: bool = False  # 是否是噪音词（如"你好"等）
    context_window: List[str] = field(default_factory=list)  # 上下文窗口


@dataclass
class LearningResult:
    """学习结果"""
    cases_processed: int
    cases_learned: int
    new_keywords: List[str]
    new_patterns: List[str]
    accuracy_improvement: float
    details: Dict[str, Any]

    # 新增字段
    keywords_by_type: Dict[str, List[str]] = field(default_factory=dict)
    patterns_by_type: Dict[str, List[str]] = field(default_factory=dict)
    keyword_weights: Dict[str, float] = field(default_factory=dict)
    removed_noise: List[str] = field(default_factory=list)
    quality_report: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QualityAssessment:
    """质量评估"""
    overall_score: float  # 0-1
    completeness: float  # 0-1
    reliability: float  # 0-1
    novelty: float  # 0-1
    diversity: float  # 0-1
    issues: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


# ============================================================
# NLP 工具类
# ============================================================

class ChineseTextProcessor:
    """中文文本处理工具"""

    # 中文停用词表（常见无信息量词汇）
    STOP_WORDS: Set[str] = {
        "的", "了", "是", "在", "我", "有", "和", "就", "不", "人", "都", "一", "一个",
        "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好",
        "自己", "这", "那", "这个", "那个", "什么", "怎么", "为什么", "呢", "吗", "吧",
        "啊", "哦", "嗯", "呀", "哈", "嘿", "喂", "哎", "唉", "噢", "哇", "呃", "呃",
        "可以", "可能", "应该", "已经", "正在", "还是", "或者", "但是", "因为", "所以",
        "如果", "虽然", "然后", "接着", "最后", "终于", "居然", "竟然", "果然", "当然",
        "真的", "确实", "其实", "不过", "只是", "只有", "还是", "反正", "简直", "简直是",
        "比如", "例如", "包括", "其中", "另外", "此外", "并且", "而且", "同时", "随后",
        "刚才", "刚才", "刚刚", "现在", "今天", "昨天", "明天", "刚才", "一会儿", "马上",
        "之前", "之后", "以前", "以后", "后来", "以前", "当中", "中间", "期间", "之内",
        "可能", "也许", "大概", "估计", "恐怕", "似乎", "好像", "仿佛", "犹如", "如同",
        "各位", "大家", "朋友", "亲", "亲爱的", "宝贝", "哥哥", "姐姐", "叔叔", "阿姨"
    }

    # 诈骗相关但无区分度的词汇（噪音词）
    NOISE_KEYWORDS: Set[str] = {
        "转账", "汇款", "钱", "元", "万", "账户", "银行", "手机", "电话", "微信", "QQ",
        "验证码", "密码", "登录", "下载", "安装", "注册", "打开", "点击", "扫描", "二维码"
    }

    # 金额模式
    MONEY_PATTERNS = [
        (r'(\d+(?:\.\d+)?)\s*(?:万|万千|万块)', '万'),
        (r'(\d+(?:\.\d+)?)\s*(?:千|千百|千块)', '千'),
        (r'(\d+(?:\.\d+)?)\s*(?:百|百块)', '百'),
        (r'(\d+(?:\.\d+)?)\s*(?:元|块)', '元'),
    ]

    # 电话号码模式
    PHONE_PATTERN = r'1[3-9]\d{9}'

    # URL模式
    URL_PATTERN = r'https?://[^\s<>"{}|\\^`\[\]]+|www\.[^\s<>"{}|\\^`\[\]]+'

    # 邮箱模式
    EMAIL_PATTERN = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

    # 银行卡模式
    BANK_PATTERN = r'\d{16,19}'

    # 身份证模式
    ID_PATTERN = r'\d{17}[\dXx]'

    def __init__(self):
        self._idf_cache: Optional[Dict[str, float]] = None
        self._total_docs = 0

    def clean_text(self, text: str) -> str:
        """清洗文本，去除隐私信息和噪声"""
        if not text:
            return ""

        # 移除URL
        text = re.sub(self.URL_PATTERN, '[链接]', text)
        # 移除电话号码
        text = re.sub(self.PHONE_PATTERN, '[电话]', text)
        # 移除邮箱
        text = re.sub(self.EMAIL_PATTERN, '[邮箱]', text)
        # 移除银行卡号
        text = re.sub(self.BANK_PATTERN, '[账号]', text)
        # 移除身份证号
        text = re.sub(self.ID_PATTERN, '[证件]', text)
        # 规范化空白字符
        text = re.sub(r'\s+', ' ', text)
        # 移除首尾空白
        text = text.strip()

        return text

    def segment(self, text: str) -> List[str]:
        """简单分词（基于字符和常见词组合）"""
        if not text:
            return []

        # 移除标点符号和数字
        cleaned = re.sub(r'[^\u4e00-\u9fff]', ' ', text)
        words = cleaned.split()

        # 生成二元组和三元组
        tokens = list(text)
        ngrams = []

        for i in range(len(tokens)):
            # 2-gram
            if i < len(tokens) - 1:
                bigram = tokens[i] + tokens[i + 1]
                if self._is_meaningful_bigram(bigram):
                    ngrams.append(bigram)
            # 3-gram
            if i < len(tokens) - 2:
                trigram = tokens[i] + tokens[i + 1] + tokens[i + 2]
                if self._is_meaningful_trigram(trigram):
                    ngrams.append(trigram)

        # 合并
        all_tokens = words + ngrams
        return [t for t in all_tokens if t not in self.STOP_WORDS and len(t) >= 2]

    def _is_meaningful_bigram(self, bigram: str) -> bool:
        """判断二元组是否有意义"""
        # 排除包含常见助词、介词的组合
        stop_chars = set('的了是在和就都一上个也很到说要去看好自己这那什么')
        if any(c in stop_chars for c in bigram):
            return False
        # 排除相同字符
        if bigram[0] == bigram[1]:
            return False
        return True

    def _is_meaningful_trigram(self, trigram: str) -> bool:
        """判断三元组是否有意义"""
        # 排除包含常见虚词的组合
        stop_words = {'的', '了', '是', '在', '和', '就', '都', '有', '我', '你', '他', '她'}
        if any(w in trigram for w in stop_words):
            return False
        # 需要至少包含一个实体词
        entity_chars = set('转账汇款账户密码验证码投资理财贷款兼职刷单公安警察')
        return any(c in entity_chars for c in trigram)

    def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """提取实体信息"""
        entities: Dict[str, List[str]] = {
            "money": [],
            "phone": [],
            "account": [],
            "platform": [],
            "url": []
        }

        # 提取金额
        for pattern, unit in self.MONEY_PATTERNS:
            matches = re.findall(pattern, text)
            for m in matches:
                amount_str = f"{m}{unit}"
                entities["money"].append(amount_str)

        # 提取电话号码
        phones = re.findall(self.PHONE_PATTERN, text)
        entities["phone"] = phones

        # 提取疑似平台名称
        platform_keywords = ["平台", "APP", "网站", "软件", "系统"]
        for kw in platform_keywords:
            if kw in text:
                idx = text.find(kw)
                # 提取前后各5个字符作为平台名
                start = max(0, idx - 8)
                end = min(len(text), idx + len(kw) + 8)
                potential = text[start:end].strip()
                if potential:
                    entities["platform"].append(potential)

        return entities

    def is_noise_keyword(self, keyword: str) -> bool:
        """判断是否为噪音关键词"""
        if keyword in self.STOP_WORDS:
            return True
        if keyword in self.NOISE_KEYWORDS:
            return True
        return False

    def calculate_similarity(self, text1: str, text2: str) -> float:
        """计算两个文本的相似度"""
        return SequenceMatcher(None, text1, text2).ratio()

    def extract_context_window(self, text: str, keyword: str, window_size: int = 10) -> List[str]:
        """提取关键词的上下文窗口"""
        if keyword not in text:
            return []

        idx = text.find(keyword)
        start = max(0, idx - window_size)
        end = min(len(text), idx + len(keyword) + window_size)
        context = text[start:end]

        # 分词
        words = re.findall(r'[\u4e00-\u9fff]+', context)
        return [w for w in words if w != keyword and not self.is_noise_keyword(w)]


class PatternExtractor:
    """模式提取器 - 从案例中自动发现诈骗模式"""

    # 诈骗话术中的槽位标记
    SLOT_MARKERS: Dict[str, List[str]] = {
        "<金额>": ["万", "千", "百", "元", "块"],
        "<时间>": ["分钟", "小时", "天", "马上", "立即", "立刻", "赶紧", "快点"],
        "<身份>": ["民警", "警官", "警察", "检察官", "法官", "客服", "老师", "导师"],
        "<罪名>": ["洗钱", "贩毒", "诈骗", "盗窃", "走私", "非法集资"],
        "<账号>": ["账户", "账号", "卡号", "收款码"],
        "<平台>": ["APP", "平台", "网站", "系统"],
        "<理由>": ["安全", "核查", "验证", "解冻", "修复", "激活"],
    }

    def __init__(self, text_processor: ChineseTextProcessor):
        self.text_processor = text_processor

    def extract_patterns(self, cases: List[LearningCase]) -> List[ExtractedPattern]:
        """从案例列表中提取模式"""
        patterns_by_type: Dict[str, List[str]] = defaultdict(list)
        pattern_examples: Dict[str, List[str]] = defaultdict(list)

        for case in cases:
            if case.label != "scam" or not case.scam_type:
                continue

            scam_type = case.scam_type
            sentences = self._split_sentences(case.content)

            for sentence in sentences:
                if self._is_potential_pattern_sentence(sentence):
                    # 抽象化模式
                    abstracted = self._abstract_sentence(sentence)
                    if abstracted and len(abstracted) >= 5:
                        patterns_by_type[scam_type].append(abstracted)
                        if len(pattern_examples[abstracted]) < 5:
                            pattern_examples[abstracted].append(sentence)

        # 转换为ExtractedPattern对象
        result = []
        for scam_type, patterns in patterns_by_type.items():
            # 去重并统计频率
            pattern_counts: Dict[str, int] = defaultdict(int)
            for p in patterns:
                # 与已有模式比较，去重
                is_duplicate = False
                for existing in pattern_counts:
                    if self.text_processor.calculate_similarity(p, existing) > 0.8:
                        pattern_counts[existing] += 1
                        is_duplicate = True
                        break
                if not is_duplicate:
                    pattern_counts[p] = 1

            for pattern_text, freq in pattern_counts.items():
                pattern = ExtractedPattern(
                    pattern_id=self._generate_pattern_id(pattern_text),
                    pattern_text=pattern_text,
                    scam_type=scam_type,
                    frequency=freq,
                    examples=pattern_examples.get(pattern_text, []),
                    confidence=min(1.0, freq / 3.0)  # 频率越高置信度越高
                )
                result.append(pattern)

        return result

    def _split_sentences(self, text: str) -> List[str]:
        """分割句子"""
        # 按标点和换行分割
        sentences = re.split(r'[。！？\n]+', text)
        result = []
        for s in sentences:
            s = s.strip()
            if len(s) >= 5:  # 过滤太短的句子
                result.append(s)
        return result

    def _is_potential_pattern_sentence(self, sentence: str) -> bool:
        """判断句子是否可能包含诈骗模式"""
        # 必须包含诈骗相关词
        scam_indicators = [
            "转账", "汇款", "账户", "验证码", "密码", "投资", "赚钱",
            "涉嫌", "犯罪", "安全", "核查", "解冻", "保证金", "手续费",
            "充值", "登录", "下载", "注册", "平台", "贷款", "刷单"
        ]

        indicator_count = sum(1 for ind in scam_indicators if ind in sentence)
        if indicator_count < 1:
            return False

        # 不能太短
        if len(sentence) < 8:
            return False

        # 不能是纯叙述性句子（需要包含行动词或要求）
        action_indicators = ["请", "需要", "必须", "要", "请立即", "马上", "立刻", "赶紧", "否则", "不然"]
        if not any(ai in sentence for ai in action_indicators):
            return False

        return True

    def _abstract_sentence(self, sentence: str) -> str:
        """将句子抽象化，替换具体值为槽位"""
        abstracted = sentence

        # 替换金额
        for pattern, _ in ChineseTextProcessor.MONEY_PATTERNS:
            abstracted = re.sub(pattern + r'[万千百元块]?', '<金额>', abstracted)

        # 替换时间
        time_patterns = [
            (r'\d+分钟', '<时间>'),
            (r'\d+小时', '<时间>'),
            (r'\d+天', '<时间>'),
        ]
        for pattern, replacement in time_patterns:
            abstracted = re.sub(pattern, replacement, abstracted)

        # 替换常见词为槽位
        replacements = {
            "安全账户": "<账号>安全账户",
            "核查账户": "<账号>核查",
            "保证金": "<金额>保证金",
            "手续费": "<金额>手续费",
            "解冻费": "<金额>解冻费",
        }

        for old, new in replacements.items():
            abstracted = abstracted.replace(old, new)

        # 清理多余空格
        abstracted = re.sub(r'\s+', '', abstracted)

        return abstracted

    def _generate_pattern_id(self, pattern_text: str) -> str:
        """生成模式ID"""
        hash_val = hashlib.md5(pattern_text.encode()).hexdigest()[:8]
        return f"pattern_{hash_val}"


class KeywordWeightCalculator:
    """关键词权重计算器"""

    def __init__(self, text_processor: ChineseTextProcessor):
        self.text_processor = text_processor
        # 每种诈骗类型已知的核心关键词及其权重
        self.core_keywords: Dict[str, Dict[str, float]] = {
            st: info["core_keywords"]
            for st, info in SCAM_TYPE_DEFINITIONS.items()
        }

    def calculate_weight(self, keyword: str, scam_type: str, cases: List[LearningCase]) -> float:
        """
        计算关键词权重
        基于：TF-IDF、区分度、上下文相关性
        """
        if not keyword or not scam_type:
            return 0.0

        # 基础权重：是否在核心关键词中
        base_weight = 0.5
        if keyword in self.core_keywords.get(scam_type, []):
            base_weight = 1.0

        # TF: 词频
        tf = self._calculate_tf(keyword, cases)

        # IDF: 逆文档频率（区分度）
        idf = self._calculate_idf(keyword, cases)

        # 上下文相关性
        context_score = self._calculate_context_relevance(keyword, scam_type)

        # 综合权重
        weight = base_weight * (0.3 + tf * 0.3 + idf * 0.2 + context_score * 0.2)

        return min(max(weight, 0.1), 1.5)  # 限制在0.1-1.5之间

    def _calculate_tf(self, keyword: str, cases: List[LearningCase]) -> float:
        """计算词频"""
        scam_cases = [c for c in cases if c.label == "scam"]
        if not scam_cases:
            return 0.0

        total_count = sum(c.content.count(keyword) for c in scam_cases)
        max_count = max(c.content.count(keyword) for c in scam_cases) if scam_cases else 1

        return total_count / (len(scam_cases) * max(max_count, 1))

    def _calculate_idf(self, keyword: str, cases: List[LearningCase]) -> float:
        """计算逆文档频率"""
        if not cases:
            return 0.0

        docs_with_keyword = sum(1 for c in cases if keyword in c.content)
        if docs_with_keyword == 0:
            return 0.0

        # IDF = log(N / df)
        idf = math.log(len(cases) / docs_with_keyword)
        return min(max(idf / 5.0, 0), 1.0)  # 归一化到0-1

    def _calculate_context_relevance(self, keyword: str, scam_type: str) -> float:
        """计算上下文相关性"""
        definitions = SCAM_TYPE_DEFINITIONS.get(scam_type, {})
        core_kws = definitions.get("core_keywords", [])
        temporal_kws = definitions.get("temporal_words", [])
        action_kws = definitions.get("action_words", [])

        score = 0.0

        # 与核心关键词共现
        if any(kw in keyword or keyword in kw for kw in core_kws):
            score += 0.4

        # 与时间词共现
        if any(kw in keyword or keyword in kw for kw in temporal_kws):
            score += 0.3

        # 与行动词共现
        if any(kw in keyword or keyword in kw for kw in action_kws):
            score += 0.3

        return score


class QualityEvaluator:
    """案例质量评估器"""

    def __init__(self, text_processor: ChineseTextProcessor):
        self.text_processor = text_processor

    def assess_case_quality(self, case: LearningCase) -> QualityAssessment:
        """评估单个案例的质量"""
        issues: List[str] = []
        recommendations: List[str] = []

        # 完整性评分
        completeness = self._assess_completeness(case, issues, recommendations)

        # 可靠性评分
        reliability = self._assess_reliability(case, issues, recommendations)

        # 新颖性评分
        novelty = self._assess_novelty(case, issues, recommendations)

        # 多样性评分
        diversity = self._assess_diversity(case, issues, recommendations)

        # 综合评分
        overall = completeness * 0.25 + reliability * 0.30 + novelty * 0.25 + diversity * 0.20

        return QualityAssessment(
            overall_score=overall,
            completeness=completeness,
            reliability=reliability,
            novelty=novelty,
            diversity=diversity,
            issues=issues,
            recommendations=recommendations
        )

    def _assess_completeness(self, case: LearningCase, issues: List[str], recs: List[str]) -> float:
        """评估完整性"""
        score = 1.0

        # 检查必要字段
        if not case.content or len(case.content) < 20:
            score -= 0.3
            issues.append("内容过短或为空")

        if not case.scam_type:
            score -= 0.3
            issues.append("缺少诈骗类型标注")

        if case.risk_level is None:
            score -= 0.1

        if not case.keywords:
            score -= 0.1

        # 内容长度适中给加分
        if 50 <= len(case.content) <= 500:
            score = min(score + 0.1, 1.0)
        elif len(case.content) > 1000:
            score -= 0.1
            issues.append("内容过长，可能包含无关信息")

        return max(score, 0.0)

    def _assess_reliability(self, case: LearningCase, issues: List[str], recs: List[str]) -> float:
        """评估可靠性"""
        score = 0.5  # 默认中等可靠

        # 来源评估
        reliable_sources = ["official", "verified", "police", "court"]
        if case.source in reliable_sources:
            score += 0.3
        elif case.source == "user_report":
            score += 0.1  # 用户举报，可靠性稍低

        # 包含实体信息（金额、联系方式等）加分
        entities = self.text_processor.extract_entities(case.content)
        if entities["money"]:
            score += 0.1
        if entities["phone"] or entities["account"]:
            score += 0.1

        # 内容一致性（提取的关键词与诈骗类型是否匹配）
        if case.keywords and case.scam_type:
            expected_kws = SCAM_TYPE_DEFINITIONS.get(case.scam_type, {}).get("core_keywords", [])
            if expected_kws:
                match_ratio = len([k for k in case.keywords if k in expected_kws]) / len(expected_kws)
                score += match_ratio * 0.2

        return min(max(score, 0.0), 1.0)

    def _assess_novelty(self, case: LearningCase, issues: List[str], recs: List[str]) -> float:
        """评估新颖性"""
        score = 0.5

        # 来源新颖性（官方来源通常不是新案例）
        if case.source in ["user_report", "news", "social_media"]:
            score += 0.3

        # 包含新关键词加分
        if case.metadata.get("is_new_keyword", False):
            score += 0.2

        return min(max(score, 0.0), 1.0)

    def _assess_diversity(self, case: LearningCase, issues: List[str], recs: List[str]) -> float:
        """评估多样性"""
        score = 0.5

        # 关键词多样性
        if len(case.keywords) >= 3:
            score += 0.3
        elif len(case.keywords) == 0:
            score -= 0.2

        # 内容多样性（是否包含多种句式）
        sentences = len(re.split(r'[。！？\n]+', case.content))
        if 2 <= sentences <= 10:
            score += 0.2
        elif sentences > 10:
            score += 0.1

        return min(max(score, 0.0), 1.0)


# ============================================================
# 主类：知识学习器
# ============================================================

class KnowledgeLearner:
    """
    知识学习器

    自动从新案例中提取知识，更新关键词库和模式库，
    支持增量学习和主动学习机制。

    核心功能：
    1. 案例预处理：清洗、去噪、标准化
    2. 关键词提取：基于TF-IDF、上下文分析、诈骗类型关联
    3. 模式发现：从对话中自动发现诈骗话术模板
    4. 质量评估：对案例和提取的知识进行质量评分
    5. 增量更新：仅更新新知识，避免重复学习
    """

    def __init__(self, knowledge_base: Optional[Any] = None):
        """
        初始化知识学习器

        Args:
            knowledge_base: 知识库实例（可选）
        """
        self.knowledge_base = knowledge_base

        # 文本处理工具
        self.text_processor = ChineseTextProcessor()
        self.pattern_extractor = PatternExtractor(self.text_processor)
        self.weight_calculator = KeywordWeightCalculator(self.text_processor)
        self.quality_evaluator = QualityEvaluator(self.text_processor)

        # 扩展关键词库：{scam_type: {keyword: LearnedKeyword}}
        self.extended_keywords: Dict[str, Dict[str, LearnedKeyword]] = defaultdict(dict)

        # 扩展模式库：{scam_type: {pattern_id: ExtractedPattern}}
        self.extended_patterns: Dict[str, Dict[str, ExtractedPattern]] = defaultdict(dict)

        # 初始化内置关键词
        self._init_builtin_keywords()

        # 学习统计
        self.learning_stats = {
            "total_cases": 0,
            "learned_cases": 0,
            "total_keywords": 0,
            "total_patterns": 0,
            "quality_scores": [],
            "last_updated": None
        }

        # 相似案例缓存（用于去重）
        self._case_similarity_cache: Dict[str, float] = {}

    def _init_builtin_keywords(self):
        """初始化内置关键词库"""
        for scam_type, info in SCAM_TYPE_DEFINITIONS.items():
            for kw in info["core_keywords"]:
                self.extended_keywords[scam_type][kw] = LearnedKeyword(
                    keyword=kw,
                    scam_type=scam_type,
                    weight=1.0,
                    frequency=1,
                    first_seen=0,  # 内置关键词
                    last_seen=0,
                    is_verified=True,
                    source_cases=["builtin"]
                )

    async def learn_from_cases(self, cases: List[Dict]) -> LearningResult:
        """
        从案例中学习（核心入口）

        Args:
            cases: 案例列表

        Returns:
            LearningResult: 学习结果
        """
        self.learning_stats["total_cases"] += len(cases)

        # 第一阶段：预处理
        processed_cases = []
        for case_data in cases:
            case = await self._preprocess_case(case_data)
            if case:
                processed_cases.append(case)

        # 第二阶段：质量评估（过滤低质量案例）
        qualified_cases = []
        quality_report = {"assessed": 0, "qualified": 0, "rejected": 0, "reasons": []}

        for case in processed_cases:
            quality_report["assessed"] += 1
            quality = self.quality_evaluator.assess_case_quality(case)
            case.quality_score = quality.overall_score

            if quality.overall_score >= 0.3:  # 质量阈值
                case.confidence = quality.overall_score
                qualified_cases.append(case)
                quality_report["qualified"] += 1
            else:
                quality_report["rejected"] += 1
                if quality.issues:
                    quality_report["reasons"].append({
                        "case_id": case.case_id,
                        "issues": quality.issues
                    })

        # 第三阶段：去重
        unique_cases = self._deduplicate_cases(qualified_cases)

        # 第四阶段：提取关键词
        new_keywords = await self._extract_keywords_from_cases(unique_cases)

        # 第五阶段：提取模式
        new_patterns = await self._extract_patterns_from_cases(unique_cases)

        # 第六阶段：更新知识库
        for case in unique_cases:
            case.learned = True

        # 第七阶段：计算改进度
        accuracy_improvement = self._calculate_improvement(unique_cases, new_keywords, new_patterns)

        # 按诈骗类型分类结果
        keywords_by_type: Dict[str, List[str]] = defaultdict(list)
        for kw in new_keywords:
            scam_type = self._guess_scam_type(kw)
            keywords_by_type[scam_type].append(kw)

        patterns_by_type: Dict[str, List[str]] = defaultdict(list)
        for pid, pattern in new_patterns.items():
            patterns_by_type[pattern.scam_type].append(pattern.pattern_text)

        # 关键词权重
        keyword_weights: Dict[str, float] = {
            kw: self.extended_keywords.get(self._guess_scam_type(kw), {}).get(kw, LearnedKeyword(kw, "unknown")).weight
            for kw in new_keywords
        }

        self.learning_stats["total_keywords"] = sum(len(v) for v in self.extended_keywords.values())
        self.learning_stats["total_patterns"] = sum(len(v) for v in self.extended_patterns.values())
        self.learning_stats["learned_cases"] += len(unique_cases)
        self.learning_stats["quality_scores"].append(sum(c.quality_score for c in unique_cases) / max(len(unique_cases), 1))
        self.learning_stats["last_updated"] = time.time()

        return LearningResult(
            cases_processed=len(cases),
            cases_learned=len(unique_cases),
            new_keywords=new_keywords,
            new_patterns=list(set(p.pattern_text for p in new_patterns.values())),
            accuracy_improvement=accuracy_improvement,
            details={
                "total_processed": self.learning_stats["total_cases"],
                "total_learned": self.learning_stats["learned_cases"],
                "keyword_count": self.learning_stats["total_keywords"],
                "pattern_count": self.learning_stats["total_patterns"]
            },
            keywords_by_type=dict(keywords_by_type),
            patterns_by_type=dict(patterns_by_type),
            keyword_weights=keyword_weights,
            removed_noise=[],
            quality_report=quality_report
        )

    async def _preprocess_case(self, case_data: Dict) -> Optional[LearningCase]:
        """预处理单个案例"""
        try:
            # 解析案例
            case = LearningCase(
                case_id=case_data.get("case_id", f"case_{time.time()}_{id(case_data)}"),
                content=case_data.get("content", ""),
                modality=case_data.get("modality", "text"),
                label=case_data.get("label", "normal"),
                scam_type=case_data.get("scam_type"),
                risk_level=case_data.get("risk_level"),
                source=case_data.get("source", "unknown"),
                keywords=case_data.get("keywords", []),
                metadata=case_data.get("metadata", {})
            )

            # 清洗内容
            case.content = self.text_processor.clean_text(case.content)

            # 提取实体
            case.extracted_entities = self.text_processor.extract_entities(case.content)

            # 提取上下文相关的新关键词
            if case.label == "scam" and case.scam_type:
                context_kws = self._extract_context_keywords(case)
                case.keywords.extend(context_kws)
                case.keywords = list(set(case.keywords))

            return case

        except Exception:
            return None

    def _extract_context_keywords(self, case: LearningCase) -> List[str]:
        """从案例中提取上下文关键词"""
        keywords = []

        # 利用诈骗类型定义提取相关关键词
        scam_info = SCAM_TYPE_DEFINITIONS.get(case.scam_type, {})
        all_type_keywords = (
            scam_info.get("core_keywords", []) +
            scam_info.get("temporal_words", []) +
            scam_info.get("action_words", [])
        )

        for kw in all_type_keywords:
            if kw in case.content and kw not in case.keywords:
                keywords.append(kw)

        # 从内容中提取未见过的诈骗词
        tokens = self.text_processor.segment(case.content)
        for token in tokens:
            # 排除噪音词和已有关键词
            if self.text_processor.is_noise_keyword(token):
                continue
            if token in case.keywords:
                continue
            # 检查是否是潜在诈骗词（短匹配）
            for type_kw in all_type_keywords:
                if token in type_kw or type_kw in token:
                    if len(token) >= 2:
                        keywords.append(token)
                    break

        return list(set(keywords))

    def _deduplicate_cases(self, cases: List[LearningCase]) -> List[LearningCase]:
        """案例去重"""
        if not cases:
            return []

        unique_cases = []
        existing_contents: List[str] = []

        for case in cases:
            # 检查是否与已有案例高度相似
            is_duplicate = False
            for existing_content in existing_contents:
                similarity = self.text_processor.calculate_similarity(
                    case.content, existing_content
                )
                if similarity > 0.85:  # 相似度阈值
                    is_duplicate = True
                    break

            if not is_duplicate:
                unique_cases.append(case)
                existing_contents.append(case.content)

        return unique_cases

    async def _extract_keywords_from_cases(self, cases: List[LearningCase]) -> List[str]:
        """从案例中提取关键词"""
        new_keywords = []

        for case in cases:
            if case.label != "scam" or not case.scam_type:
                continue

            scam_type = case.scam_type

            # 使用质量评分调整权重
            quality_weight = case.confidence if case.confidence > 0 else 0.5

            for keyword in case.keywords:
                # 跳过噪音词
                if self.text_processor.is_noise_keyword(keyword):
                    continue

                # 计算权重
                weight = self.weight_calculator.calculate_weight(
                    keyword, scam_type, cases
                )
                weight *= quality_weight

                # 检查是否已存在
                existing = self.extended_keywords[scam_type].get(keyword)

                if existing:
                    # 更新现有关键词
                    existing.frequency += 1
                    existing.weight = (existing.weight + weight) / 2
                    existing.last_seen = time.time()
                    if case.case_id not in existing.source_cases:
                        existing.source_cases.append(case.case_id)
                    if case.case_id not in existing.context_window:
                        ctx = self.text_processor.extract_context_window(case.content, keyword)
                        existing.context_window = ctx[:5]
                else:
                    # 新增关键词
                    learned_kw = LearnedKeyword(
                        keyword=keyword,
                        scam_type=scam_type,
                        weight=weight,
                        frequency=1,
                        first_seen=time.time(),
                        last_seen=time.time(),
                        source_cases=[case.case_id],
                        is_verified=False,
                        context_window=self.text_processor.extract_context_window(
                            case.content, keyword
                        )[:5]
                    )
                    self.extended_keywords[scam_type][keyword] = learned_kw
                    new_keywords.append(keyword)

        return new_keywords

    async def _extract_patterns_from_cases(self, cases: List[LearningCase]) -> Dict[str, ExtractedPattern]:
        """从案例中提取模式"""
        # 使用模式提取器
        extracted = self.pattern_extractor.extract_patterns(cases)

        new_patterns: Dict[str, ExtractedPattern] = {}

        for pattern in extracted:
            scam_type = pattern.scam_type

            # 检查是否已存在相似模式
            is_new = True
            for existing_id, existing in self.extended_patterns[scam_type].items():
                similarity = self.text_processor.calculate_similarity(
                    pattern.pattern_text, existing.pattern_text
                )
                if similarity > 0.8:
                    # 合并到已有模式
                    existing.frequency += pattern.frequency
                    existing.last_seen = time.time()
                    existing.examples.extend(pattern.examples[:2])
                    existing.examples = existing.examples[:5]
                    is_new = False
                    break

            if is_new:
                self.extended_patterns[scam_type][pattern.pattern_id] = pattern
                new_patterns[pattern.pattern_id] = pattern

        return new_patterns

    def _guess_scam_type(self, keyword: str) -> str:
        """根据关键词猜测诈骗类型"""
        keyword_lower = keyword.lower()

        # 建立倒排索引：关键词 -> 诈骗类型
        for scam_type, info in SCAM_TYPE_DEFINITIONS.items():
            for kw in info["core_keywords"]:
                if kw in keyword or keyword in kw:
                    return scam_type
                # 部分匹配
                if len(kw) >= 2 and len(keyword) >= 2:
                    if kw[:2] in keyword or keyword[:2] in kw:
                        return scam_type

        # 基于关键词前缀猜测
        prefix_map = {
            "投资": "investment_fraud",
            "理财": "investment_fraud",
            "贷款": "loan_fraud",
            "兼职": "part_time_fraud",
            "刷单": "part_time_fraud",
            "公安": "police_impersonation",
            "警察": "police_impersonation",
            "洗钱": "police_impersonation",
            "征信": "credit_fraud",
            "退款": "refund_fraud",
            "游戏": "gaming_fraud",
            "粉丝": "fan_fraud",
            "医保": "medical_fraud",
            "绑架": "ai_voice_fraud",
            "恋爱": "pig_butchery",
            "亲爱的": "pig_butchery",
        }

        for prefix, scam_type in prefix_map.items():
            if prefix in keyword:
                return scam_type

        return "unknown"

    async def _update_knowledge(self, case: LearningCase,
                                keywords: List[str], patterns: List[str]):
        """更新知识库"""
        if not self.knowledge_base:
            return

        # 构建知识条目
        entry = {
            "type": "scam_case",
            "scam_type": case.scam_type,
            "title": f"学习案例 - {SCAM_TYPE_DEFINITIONS.get(case.scam_type, {}).get('name', case.scam_type)}",
            "content": case.content,
            "risk_level": case.risk_level or 3,
            "keywords": keywords,
            "metadata": {
                "source": case.source,
                "learned_at": time.time(),
                "patterns": patterns,
                "quality_score": case.quality_score,
                "confidence": case.confidence
            }
        }

        await self.knowledge_base.add_entry(entry)

    def _calculate_improvement(self, cases: List[LearningCase],
                             new_keywords: List[str],
                             new_patterns: Dict[str, ExtractedPattern]) -> float:
        """计算学习提升"""
        if not cases:
            return 0.0

        # 基于新增知识量和案例质量计算改进度
        keyword_improvement = len(new_keywords) / max(len(cases), 1) * 0.1
        pattern_improvement = len(new_patterns) / max(len(cases), 1) * 0.1
        quality_improvement = sum(c.confidence for c in cases) / len(cases) * 0.3

        improvement = keyword_improvement + pattern_improvement + quality_improvement

        # 历史调整
        if self.learning_stats["learned_cases"] > 0:
            history_factor = 1.0 / (1.0 + math.log1p(self.learning_stats["learned_cases"]))
            improvement *= (0.5 + 0.5 * history_factor)

        return min(improvement, 1.0)

    def get_keyword_library(self, scam_type: Optional[str] = None) -> Dict[str, List[str]]:
        """获取关键词库"""
        if scam_type:
            kw_list = [
                kw for kw, info in self.extended_keywords.get(scam_type, {}).items()
                if not info.is_noisy and info.weight >= 0.3
            ]
            return {scam_type: kw_list}

        result = {}
        for st, keywords in self.extended_keywords.items():
            result[st] = [
                kw for kw, info in keywords.items()
                if not info.is_noisy and info.weight >= 0.3
            ]
        return result

    def get_pattern_library(self, scam_type: Optional[str] = None) -> Dict[str, List[str]]:
        """获取模式库"""
        if scam_type:
            patterns = [
                p.pattern_text
                for p in self.extended_patterns.get(scam_type, {}).values()
                if p.active and p.confidence >= 0.3
            ]
            return {scam_type: patterns}

        result = {}
        for st, patterns in self.extended_patterns.items():
            result[st] = [
                p.pattern_text
                for p in patterns.values()
                if p.active and p.confidence >= 0.3
            ]
        return result

    def get_keyword_details(self, scam_type: str, keyword: str) -> Optional[Dict]:
        """获取关键词详情"""
        kw_info = self.extended_keywords.get(scam_type, {}).get(keyword)
        if not kw_info:
            return None

        return {
            "keyword": kw_info.keyword,
            "scam_type": kw_info.scam_type,
            "weight": kw_info.weight,
            "frequency": kw_info.frequency,
            "is_verified": kw_info.is_verified,
            "is_noisy": kw_info.is_noisy,
            "context_window": kw_info.context_window,
            "first_seen": kw_info.first_seen,
            "last_seen": kw_info.last_seen,
            "source_cases_count": len(kw_info.source_cases)
        }

    def get_pattern_details(self, scam_type: str, pattern_id: str) -> Optional[Dict]:
        """获取模式详情"""
        pattern = self.extended_patterns.get(scam_type, {}).get(pattern_id)
        if not pattern:
            return None

        return {
            "pattern_id": pattern.pattern_id,
            "pattern_text": pattern.pattern_text,
            "scam_type": pattern.scam_type,
            "frequency": pattern.frequency,
            "confidence": pattern.confidence,
            "slots": pattern.slots,
            "examples": pattern.examples,
            "active": pattern.active,
            "first_seen": pattern.first_seen,
            "last_seen": pattern.last_seen
        }

    def export_learning_state(self) -> Dict:
        """导出学习状态"""
        # 导出关键词
        exported_keywords = {}
        for scam_type, keywords in self.extended_keywords.items():
            exported_keywords[scam_type] = [
                {
                    "keyword": kw,
                    "weight": info.weight,
                    "frequency": info.frequency,
                    "is_verified": info.is_verified,
                    "is_noisy": info.is_noisy,
                    "context_window": info.context_window,
                    "first_seen": info.first_seen,
                    "last_seen": info.last_seen
                }
                for kw, info in keywords.items()
                if not info.is_noisy
            ]

        # 导出模式
        exported_patterns = {}
        for scam_type, patterns in self.extended_patterns.items():
            exported_patterns[scam_type] = [
                {
                    "pattern_id": pid,
                    "pattern_text": p.pattern_text,
                    "frequency": p.frequency,
                    "confidence": p.confidence,
                    "slots": p.slots,
                    "examples": p.examples,
                    "active": p.active
                }
                for pid, p in patterns.items()
                if p.active
            ]

        return {
            "extended_keywords": exported_keywords,
            "extended_patterns": exported_patterns,
            "learning_stats": self.learning_stats,
            "exported_at": time.time()
        }

    def import_learning_state(self, state: Dict):
        """导入学习状态"""
        if "extended_keywords" in state:
            for scam_type, keywords_data in state["extended_keywords"].items():
                for kw_data in keywords_data:
                    kw_info = LearnedKeyword(
                        keyword=kw_data["keyword"],
                        scam_type=scam_type,
                        weight=kw_data.get("weight", 1.0),
                        frequency=kw_data.get("frequency", 1),
                        is_verified=kw_data.get("is_verified", False),
                        is_noisy=kw_data.get("is_noisy", False),
                        context_window=kw_data.get("context_window", []),
                        first_seen=kw_data.get("first_seen", time.time()),
                        last_seen=kw_data.get("last_seen", time.time())
                    )
                    self.extended_keywords[scam_type][kw_data["keyword"]] = kw_info

        if "extended_patterns" in state:
            for scam_type, patterns_data in state["extended_patterns"].items():
                for p_data in patterns_data:
                    pattern = ExtractedPattern(
                        pattern_id=p_data["pattern_id"],
                        pattern_text=p_data["pattern_text"],
                        scam_type=scam_type,
                        frequency=p_data.get("frequency", 1),
                        confidence=p_data.get("confidence", 0.5),
                        slots=p_data.get("slots", []),
                        examples=p_data.get("examples", []),
                        active=p_data.get("active", True)
                    )
                    self.extended_patterns[scam_type][p_data["pattern_id"]] = pattern

        if "learning_stats" in state:
            for key, value in state["learning_stats"].items():
                if key in self.learning_stats:
                    self.learning_stats[key] = value
