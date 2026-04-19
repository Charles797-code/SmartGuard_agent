"""
知识库检索模块
构建并维护反诈向量数据库，支持语义检索和案例匹配
"""

import json
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from abc import ABC, abstractmethod


@dataclass
class KnowledgeEntry:
    """知识条目"""
    id: str
    type: str  # scam_case, law, warning, prevention, news
    title: str
    content: str
    scam_type: Optional[str] = None
    risk_level: Optional[int] = None
    keywords: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "type": self.type,
            "title": self.title,
            "content": self.content,
            "scam_type": self.scam_type,
            "risk_level": self.risk_level,
            "keywords": self.keywords,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }


@dataclass
class RetrievalResult:
    """检索结果"""
    entry: KnowledgeEntry
    score: float
    highlight: Optional[str] = None


class VectorStore(ABC):
    """向量存储抽象基类"""
    
    @abstractmethod
    async def add(self, entries: List[KnowledgeEntry]) -> bool:
        """添加条目"""
        pass
    
    @abstractmethod
    async def search(self, query: str, top_k: int = 5, 
                    filter: Optional[Dict] = None) -> List[RetrievalResult]:
        """向量检索"""
        pass
    
    @abstractmethod
    async def delete(self, ids: List[str]) -> bool:
        """删除条目"""
        pass
    
    @abstractmethod
    async def update(self, entry: KnowledgeEntry) -> bool:
        """更新条目"""
        pass


class KnowledgeRetriever:
    """
    知识检索器
    
    维护反诈知识库，支持向量检索和关键词检索，
    为智能体提供案例参考和知识支持。
    """
    
    # 内置知识库数据
    BUILTIN_KNOWLEDGE = [
        # 冒充公检法案例
        {
            "type": "scam_case",
            "scam_type": "police_impersonation",
            "title": "典型冒充公检法诈骗案例",
            "content": """诈骗分子冒充公安局民警，声称受害人身份证被冒用，
            涉嫌一起重大洗钱案件，需要配合调查。骗子会要求受害人将
            资金转入所谓的"安全账户"进行核查，并威胁称不配合将面临
            逮捕。受害人按照指示转账后，发现资金被骗走。""",
            "risk_level": 4,
            "keywords": ["冒充公安", "洗钱", "安全账户", "资金核查", "逮捕"]
        },
        # 投资理财诈骗案例
        {
            "type": "scam_case",
            "scam_type": "investment_fraud",
            "title": "虚假投资平台诈骗案例",
            "content": """骗子通过社交软件添加受害人为好友，经过一段时间的情感培养后，
            透露自己在一个投资平台上赚了大钱，并发送虚假的盈利截图。
            骗子引导受害人注册平台并投入小额资金，初期的确能获得收益
            并成功提现。当受害人加大投入后，平台便无法登录，所谓的
            "好友"也消失不见。""",
            "risk_level": 3,
            "keywords": ["投资平台", "导师", "内幕消息", "高收益", "博彩"]
        },
        # 兼职刷单案例
        {
            "type": "scam_case",
            "scam_type": "part_time_fraud",
            "title": "刷单兼职诈骗案例",
            "content": """骗子在社交群聊中发布兼职信息，声称只需手机点赞、收藏、加关注
            就能获得佣金，日赚300-500元。受害人添加客服后，被引导下载
            刷单APP。起初的小额任务确实有返利，但随后客服以连环任务、
            任务超时等理由要求受害人不断转账，最终发现无法提现，损失巨大。""",
            "risk_level": 3,
            "keywords": ["刷单", "点赞", "佣金", "日结", "连环任务"]
        },
        # 虚假贷款案例
        {
            "type": "scam_case",
            "scam_type": "loan_fraud",
            "title": "套路贷诈骗案例",
            "content": """骗子以"无抵押、低利率、快速放款"为诱饵，吸引急需用钱的受害人。
            受害人下载贷款APP并申请贷款后，被告知需要先支付"手续费"、
            "解冻费"等才能放款。受害人转账后，贷款迟迟不到账，
            而对方继续以各种理由要求转账。""",
            "risk_level": 3,
            "keywords": ["无抵押", "贷款", "手续费", "解冻", "快速放款"]
        },
        # 杀猪盘案例
        {
            "type": "scam_case",
            "scam_type": "pig_butchery",
            "title": "杀猪盘诈骗案例",
            "content": """骗子在婚恋网站或社交软件上寻找目标，经过长期的嘘寒问暖、
            情感交流，建立恋爱关系。在感情成熟后，骗子透露自己发现了一个
            投资赚钱的好机会，带着受害人一起"投资"。受害人先小额尝试，
            确实获得收益。待大额投入后，平台突然关闭，所谓的恋人消失。""",
            "risk_level": 3,
            "keywords": ["恋爱", "投资", "导师", "平台", "内幕"]
        },
        # AI语音合成诈骗
        {
            "type": "scam_case",
            "scam_type": "ai_voice_fraud",
            "title": "AI合成子女声音诈骗案例",
            "content": """受害人接到"子女"的紧急电话，声音与子女相似，但语气慌张，
            声称出了事故或被绑架，需要紧急汇款救人。骗子利用AI语音合成技术，
            模仿子女的声音，制造紧急情况。受害人在慌乱中按照指示汇款，
            事后联系子女才发现是骗局。""",
            "risk_level": 4,
            "keywords": ["绑架", "出事", "急需用钱", "汇款", "子女"]
        },
        # 虚假征信案例
        {
            "type": "scam_case",
            "scam_type": "credit_fraud",
            "title": "征信修复诈骗案例",
            "content": """骗子声称可以帮助修复不良征信记录，消除逾期、黑名单等。
            受害人联系后，被要求提供个人信息、银行卡号，并支付"修复费用"。
            骗子收到钱后便消失，受害人的征信记录未改善，
            还可能面临个人信息泄露和银行卡被盗刷的风险。""",
            "risk_level": 2,
            "keywords": ["征信", "修复", "逾期", "黑名单", "消除"]
        },
        # 购物退款诈骗
        {
            "type": "scam_case",
            "scam_type": "refund_fraud",
            "title": "购物退款诈骗案例",
            "content": """受害人接到"客服"电话，称其购买的商品存在质量问题，
            可以获得双倍赔偿。受害人按照指示，打开支付宝的"备用金"功能，
            发现确实有资金到账（实际上是受害人的额度）。
            随后"客服"要求受害人将多余的钱转回，否则会影响征信。""",
            "risk_level": 3,
            "keywords": ["退款", "双倍赔偿", "质量问题", "备用金", "支付宝"]
        },
        # 游戏交易诈骗
        {
            "type": "scam_case",
            "scam_type": "gaming_fraud",
            "title": "游戏装备交易诈骗案例",
            "content": """受害人在游戏内看到低价出售装备或代练的广告，联系卖家后，
            被引导到第三方交易平台。受害人在平台充值并付款后，
            平台以各种理由（如资金违规、解冻等）要求继续充值。
            最终装备未到账，钱也打了水漂。""",
            "risk_level": 2,
            "keywords": ["游戏", "装备", "交易", "折扣", "代练"]
        },
        # 追星诈骗
        {
            "type": "scam_case",
            "scam_type": "fan_fraud",
            "title": "追星诈骗案例",
            "content": """骗子冒充明星粉丝群的管理员或明星本人，声称有内部福利、
            演唱会门票、签名照等，需要粉丝转账购买或缴纳"保证金"。
            受害人在粉丝群中看到诱人信息后，私下联系骗子转账，
            结果被骗走钱财，而所谓的福利、门票都是假的。""",
            "risk_level": 2,
            "keywords": ["粉丝", "明星", "门票", "签名", "福利"]
        },
        # 医保诈骗
        {
            "type": "scam_case",
            "scam_type": "medical_fraud",
            "title": "医保诈骗案例",
            "content": """骗子冒充医保局工作人员，声称受害人的医保卡涉嫌在外地
            非法报销或被人盗用，需要配合调查。骗子以"资金核查"为名，
            要求受害人将医保账户的资金转入"安全账户"。
            受害人在恐慌中转账，医保资金被骗走。""",
            "risk_level": 3,
            "keywords": ["医保", "异地报销", "盗用", "冻结", "资金核查"]
        },
        # 反诈法律法规
        {
            "type": "law",
            "title": "反电信网络诈骗法要点",
            "content": """《中华人民共和国反电信网络诈骗法》于2022年12月1日起施行。
            该法规定：电信经营者、银行业金融机构、非银行支付机构
            应当依法建立健全反电信网络诈骗工作机制，
            落实电话号码真实登记、账户交易监测等责任。
            对于实施诈骗行为的人员，将依法追究刑事责任。""",
            "risk_level": None,
            "keywords": ["反诈法", "电信诈骗", "法律责任", "刑法"]
        }
    ]
    
    def __init__(self, vector_store: Optional[VectorStore] = None,
                 embedder: Optional[Any] = None):
        """
        初始化知识检索器
        
        Args:
            vector_store: 向量存储实例
            embedder: 文本嵌入模型
        """
        self.vector_store = vector_store
        self.embedder = embedder
        self.knowledge_base: List[KnowledgeEntry] = []
        self._initialized = False
    
    async def initialize(self):
        """初始化知识库"""
        if self._initialized:
            return
        
        # 加载内置知识
        await self._load_builtin_knowledge()
        
        # 如果有向量存储，建立索引
        if self.vector_store:
            await self.vector_store.add(self.knowledge_base)
        
        self._initialized = True
    
    async def _load_builtin_knowledge(self):
        """加载内置知识"""
        for i, item in enumerate(self.BUILTIN_KNOWLEDGE):
            entry = KnowledgeEntry(
                id=f"builtin_{i}_{int(time.time())}",
                type=item["type"],
                title=item["title"],
                content=item["content"],
                scam_type=item.get("scam_type"),
                risk_level=item.get("risk_level"),
                keywords=item.get("keywords", [])
            )
            self.knowledge_base.append(entry)
    
    async def add_entry(self, entry: KnowledgeEntry) -> bool:
        """添加知识条目"""
        entry.id = f"custom_{len(self.knowledge_base)}_{int(time.time())}"
        entry.created_at = time.time()
        entry.updated_at = time.time()
        
        self.knowledge_base.append(entry)
        
        if self.vector_store:
            await self.vector_store.add([entry])
        
        return True
    
    async def search(self, query: str, top_k: int = 5,
                    filter_type: Optional[str] = None) -> List[RetrievalResult]:
        """
        检索相关知识
        
        Args:
            query: 查询文本
            top_k: 返回数量
            filter_type: 过滤类型
            
        Returns:
            List[RetrievalResult]: 检索结果
        """
        # 如果有向量存储，使用向量检索
        if self.vector_store:
            filter_dict = {"type": filter_type} if filter_type else None
            return await self.vector_store.search(query, top_k, filter_dict)
        
        # 回退到关键词匹配
        return self._keyword_search(query, top_k, filter_type)
    
    def _keyword_search(self, query: str, top_k: int = 5,
                      filter_type: Optional[str] = None) -> List[RetrievalResult]:
        """基于关键词的检索"""
        query_keywords = set(query.lower())
        
        results = []
        for entry in self.knowledge_base:
            # 类型过滤
            if filter_type and entry.type != filter_type:
                continue
            
            # 计算关键词匹配分数
            content_keywords = set(entry.content.lower().split())
            title_keywords = set(entry.title.lower().split())
            entry_keywords = set(" ".join(entry.keywords).lower().split())
            
            all_keywords = content_keywords | title_keywords | entry_keywords
            match_count = len(query_keywords & all_keywords)
            
            if match_count > 0:
                score = match_count / max(len(query_keywords), 1)
                results.append(RetrievalResult(
                    entry=entry,
                    score=score,
                    highlight=self._generate_highlight(entry, query)
                ))
        
        # 按分数排序
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]
    
    def _generate_highlight(self, entry: KnowledgeEntry, query: str) -> str:
        """生成高亮文本"""
        # 简单实现：返回标题和内容片段
        highlight = f"【{entry.title}】\n"
        
        # 找到query关键词在内容中的位置
        query_lower = query.lower()
        content_lower = entry.content.lower()
        
        idx = content_lower.find(query_lower)
        if idx == -1:
            highlight += entry.content[:100] + "..."
        else:
            start = max(0, idx - 30)
            end = min(len(entry.content), idx + len(query) + 30)
            highlight += "..." + entry.content[start:end] + "..."
        
        return highlight
    
    async def get_similar_cases(self, text: str, scam_type: Optional[str] = None,
                               top_k: int = 3) -> List[Dict]:
        """获取相似案例"""
        results = await self.search(
            query=text,
            top_k=top_k,
            filter_type="scam_case"
        )
        
        # 如果指定了诈骗类型，进一步过滤
        if scam_type:
            results = [r for r in results if r.entry.scam_type == scam_type]
        
        return [
            {
                "title": r.entry.title,
                "content": r.entry.content,
                "scam_type": r.entry.scam_type,
                "risk_level": r.entry.risk_level,
                "keywords": r.entry.keywords,
                "score": r.score,
                "highlight": r.highlight
            }
            for r in results
        ]
    
    async def get_prevention_tips(self, scam_type: Optional[str] = None) -> List[Dict]:
        """获取防护建议"""
        results = await self.search(
            query="防护建议 预防 避免",
            top_k=5,
            filter_type="scam_case"
        )
        
        tips = []
        for r in results:
            if not scam_type or r.entry.scam_type == scam_type:
                tips.append({
                    "scam_type": r.entry.scam_type,
                    "title": r.entry.title,
                    "tips": self._extract_prevention_tips(r.entry.content)
                })
        
        return tips
    
    def _extract_prevention_tips(self, content: str) -> List[str]:
        """从内容中提取防护建议"""
        tips = []
        
        # 简单的建议提取
        tip_patterns = [
            "不要", "不要轻信", "谨防", "注意", "提高警惕",
            "核实", "确认", "正规渠道", "官方", "报警"
        ]
        
        for pattern in tip_patterns:
            if pattern in content:
                tips.append(f"遇到类似情况要{pattern}")
        
        return tips[:5]
    
    def get_laws_and_regulations(self) -> List[Dict]:
        """获取法律法规"""
        results = [
            r for r in self.knowledge_base
            if r.type == "law"
        ]
        
        return [
            {
                "title": r.title,
                "content": r.content,
                "keywords": r.keywords
            }
            for r in results
        ]
    
    async def update_from_external(self, new_cases: List[Dict]) -> int:
        """
        从外部更新知识库
        
        Args:
            new_cases: 新案例列表
            
        Returns:
            int: 更新数量
        """
        count = 0
        for case in new_cases:
            try:
                entry = KnowledgeEntry(
                    id=f"external_{count}_{int(time.time())}",
                    type="scam_case",
                    title=case.get("title", "未知标题"),
                    content=case.get("content", ""),
                    scam_type=case.get("scam_type"),
                    risk_level=case.get("risk_level", 3),
                    keywords=case.get("keywords", []),
                    metadata={"source": "external", "original_id": case.get("id")}
                )
                
                await self.add_entry(entry)
                count += 1
            except Exception:
                continue
        
        return count
    
    def get_statistics(self) -> Dict:
        """获取知识库统计"""
        type_counts = {}
        scam_type_counts = {}
        
        for entry in self.knowledge_base:
            type_counts[entry.type] = type_counts.get(entry.type, 0) + 1
            
            if entry.scam_type:
                scam_type_counts[entry.scam_type] = \
                    scam_type_counts.get(entry.scam_type, 0) + 1
        
        return {
            "total_entries": len(self.knowledge_base),
            "type_distribution": type_counts,
            "scam_type_distribution": scam_type_counts
        }