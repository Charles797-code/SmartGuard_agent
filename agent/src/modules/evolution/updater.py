"""
知识更新模块
实现自动化流程，支持将新的互联网诈骗案例清洗后导入向量数据库，
支持定时更新、增量更新、增量同步、变更检测等完整功能。
"""

import time
import json
import asyncio
import re
import hashlib
import logging
from typing import Dict, List, Optional, Any, Callable, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
from urllib.parse import urljoin, urlparse
from datetime import datetime, timedelta

try:
    import aiohttp
    _HAS_AIOHTTP = True
except ImportError:
    _HAS_AIOHTTP = False
    aiohttp = None

# ============================================================
# 数据类定义
# ============================================================

class UpdateStatus(Enum):
    """更新任务状态"""
    PENDING = "pending"
    QUEUED = "queued"
    FETCHING = "fetching"
    PROCESSING = "processing"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"  # 部分成功
    CANCELLED = "cancelled"


class DataSourceType(Enum):
    """数据源类型"""
    OFFICIAL_API = "official_api"     # 官方API
    WEB_SCRAPER = "web_scraper"      # 网页爬取
    RSS_FEED = "rss_feed"            # RSS订阅
    FILE_IMPORT = "file_import"      # 文件导入
    USER_REPORT = "user_report"       # 用户举报
    DATABASE_SYNC = "database_sync"   # 数据库同步
    MANUAL = "manual"                 # 手动更新


class UpdateFrequency(Enum):
    """更新频率"""
    REALTIME = "realtime"     # 实时
    HOURLY = "hourly"         # 每小时
    DAILY = "daily"          # 每天
    WEEKLY = "weekly"         # 每周
    MANUAL = "manual"         # 手动


@dataclass
class UpdateTask:
    """更新任务"""
    task_id: str
    task_type: str  # case_import, pattern_update, keyword_update, full_sync
    source: str
    source_type: DataSourceType
    data: List[Dict]
    status: UpdateStatus
    progress: float = 0.0
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    error_message: Optional[str] = None
    result: Optional[Dict] = None
    retry_count: int = 0
    max_retries: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DataSource:
    """数据源配置"""
    source_id: str
    name: str
    source_type: DataSourceType
    url: str
    frequency: UpdateFrequency
    enabled: bool = True
    auth_token: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)
    rate_limit: int = 10  # 每分钟请求数
    last_fetch: Optional[float] = None
    last_success: Optional[float] = None
    consecutive_failures: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def needs_fetch(self) -> bool:
        """判断是否需要抓取"""
        if not self.enabled:
            return False
        if self.last_fetch is None:
            return True

        now = time.time()
        elapsed = now - self.last_fetch

        intervals = {
            UpdateFrequency.REALTIME: 60,        # 1分钟
            UpdateFrequency.HOURLY: 3600,        # 1小时
            UpdateFrequency.DAILY: 86400,         # 1天
            UpdateFrequency.WEEKLY: 604800,       # 1周
            UpdateFrequency.MANUAL: float('inf'),
        }
        return elapsed >= intervals.get(self.frequency, 86400)


@dataclass
class DataChange:
    """数据变更记录"""
    change_id: str
    change_type: str  # added, modified, deleted
    entity_type: str  # case, keyword, pattern
    entity_id: str
    content_hash: str
    timestamp: float
    source: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    """验证结果"""
    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)


# ============================================================
# 外部数据源管理器
# ============================================================

class DataSourceRegistry:
    """数据源注册表 - 管理所有可用的外部数据源"""

    # 预设的官方数据源
    PRESET_SOURCES: List[DataSource] = [
        DataSource(
            source_id="antifraud_gov",
            name="公安部互联网违法犯罪举报网站",
            source_type=DataSourceType.WEB_SCRAPER,
            url="https://www.cyberpolice.cn/",
            frequency=UpdateFrequency.DAILY,
            headers={"User-Agent": "SmartGuard/1.0"},
            metadata={
                "description": "公安部网络违法犯罪举报网站",
                "scam_types_covered": ["all"],
                "reliability": 0.95,
                "coverage": "national"
            }
        ),
        DataSource(
            source_id="12321_.gov",
            name="12321网络不良与垃圾信息举报中心",
            source_type=DataSourceType.WEB_SCRAPER,
            url="https://www.12321.cn/",
            frequency=UpdateFrequency.DAILY,
            headers={"User-Agent": "SmartGuard/1.0"},
            metadata={
                "description": "12321举报中心",
                "scam_types_covered": ["phishing", "spam", "fraud"],
                "reliability": 0.90,
                "coverage": "national"
            }
        ),
        DataSource(
            source_id="news_official",
            name="官方媒体反诈新闻",
            source_type=DataSourceType.RSS_FEED,
            url="https://www.gov.cn/fuwu/xwfby.htm",
            frequency=UpdateFrequency.HOURLY,
            headers={"User-Agent": "SmartGuard/1.0"},
            metadata={
                "description": "中国政府网反诈专栏",
                "scam_types_covered": ["all"],
                "reliability": 0.95,
                "coverage": "national"
            }
        ),
        DataSource(
            source_id="cctv_news",
            name="CCTV新闻反诈报道",
            source_type=DataSourceType.RSS_FEED,
            url="http://www.cctv.com/rss/news.xml",
            frequency=UpdateFrequency.HOURLY,
            headers={"User-Agent": "SmartGuard/1.0"},
            metadata={
                "description": "CCTV新闻RSS",
                "scam_types_covered": ["all"],
                "reliability": 0.90,
                "coverage": "national"
            }
        ),
    ]

    def __init__(self):
        self.sources: Dict[str, DataSource] = {}
        self._init_preset_sources()

    def _init_preset_sources(self):
        """初始化预设数据源"""
        for source in self.PRESET_SOURCES:
            self.sources[source.source_id] = source

    def register(self, source: DataSource) -> bool:
        """注册新数据源"""
        if source.source_id in self.sources:
            logging.warning(f"数据源 {source.source_id} 已存在，将被覆盖")
        self.sources[source.source_id] = source
        return True

    def unregister(self, source_id: str) -> bool:
        """取消注册数据源"""
        if source_id in self.sources:
            del self.sources[source_id]
            return True
        return False

    def get(self, source_id: str) -> Optional[DataSource]:
        """获取数据源"""
        return self.sources.get(source_id)

    def get_all(self) -> List[DataSource]:
        """获取所有数据源"""
        return list(self.sources.values())

    def get_enabled(self) -> List[DataSource]:
        """获取所有启用的数据源"""
        return [s for s in self.sources.values() if s.enabled]

    def get_needing_fetch(self) -> List[DataSource]:
        """获取需要抓取的数据源"""
        return [s for s in self.sources.values() if s.needs_fetch()]

    def update_fetch_status(self, source_id: str, success: bool):
        """更新抓取状态"""
        source = self.sources.get(source_id)
        if not source:
            return

        source.last_fetch = time.time()
        if success:
            source.last_success = time.time()
            source.consecutive_failures = 0
        else:
            source.consecutive_failures += 1


# ============================================================
# 数据获取器
# ============================================================

class DataFetcher:
    """数据获取器 - 从各种数据源抓取案例"""

    def __init__(self, rate_limiter: Optional['RateLimiter'] = None):
        self.rate_limiter = rate_limiter or RateLimiter()
        self.session: Optional[Any] = None
        self.logger = logging.getLogger(__name__)

    async def _get_session(self) -> Any:
        """获取或创建HTTP会话"""
        if not _HAS_AIOHTTP:
            return None
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=30, connect=10)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session

    async def close(self):
        """关闭HTTP会话"""
        if self.session and not self.session.closed:
            await self.session.close()

    async def fetch_webpage(self, url: str, headers: Optional[Dict] = None,
                            timeout: int = 30) -> Optional[str]:
        """抓取网页内容"""
        if not _HAS_AIOHTTP:
            return self._fetch_webpage_fallback(url, headers, timeout)

        try:
            await self.rate_limiter.acquire()
            session = await self._get_session()

            request_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            }
            if headers:
                request_headers.update(headers)

            async with session.get(url, headers=request_headers) as response:
                if response.status == 200:
                    content = await response.text()
                    return content
                else:
                    self.logger.warning(f"HTTP {response.status} for {url}")
                    return None

        except asyncio.TimeoutError:
            self.logger.warning(f"Timeout fetching {url}")
            return None
        except Exception as e:
            self.logger.error(f"Error fetching {url}: {e}")
            return None

    def _fetch_webpage_fallback(self, url: str, headers: Optional[Dict] = None,
                                timeout: int = 30) -> Optional[str]:
        """无aiohttp时的fallback实现（同步）"""
        try:
            import urllib.request
            import ssl

            request_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            }
            if headers:
                request_headers.update(headers)

            req = urllib.request.Request(url, headers=request_headers)
            ctx = ssl.create_default_context()
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as response:
                if response.status == 200:
                    return response.read().decode('utf-8', errors='ignore')
                return None
        except Exception as e:
            self.logger.error(f"Fallback fetch error for {url}: {e}")
            return None

    async def fetch_api(self, url: str, headers: Optional[Dict] = None,
                       params: Optional[Dict] = None) -> Optional[Dict]:
        """调用API获取数据"""
        if not _HAS_AIOHTTP:
            return None

        try:
            await self.rate_limiter.acquire()
            session = await self._get_session()

            request_headers = {"Content-Type": "application/json"}
            if headers:
                request_headers.update(headers)

            async with session.get(url, headers=request_headers, params=params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    self.logger.warning(f"API HTTP {response.status} for {url}")
                    return None

        except Exception as e:
            self.logger.error(f"Error fetching API {url}: {e}")
            return None

    async def parse_rss(self, rss_url: str) -> List[Dict]:
        """解析RSS订阅"""
        import xml.etree.ElementTree as ET

        content = await self.fetch_webpage(rss_url)
        if not content:
            return []

        try:
            items = []
            root = ET.fromstring(content)

            # 尝试不同的RSS命名空间
            namespaces = {
                '': '',  # 默认命名空间
                'media': 'http://search.yahoo.com/mrss/',
                'dc': 'http://purl.org/dc/elements/1.1/',
            }

            for item in root.findall('.//item') + root.findall('.//entry'):
                title = self._get_element_text(item, 'title')
                description = self._get_element_text(item, 'description') or \
                              self._get_element_text(item, 'content:encoded') or \
                              self._get_element_text(item, 'summary')
                link = self._get_element_text(item, 'link')
                pub_date = self._get_element_text(item, 'pubDate') or \
                           self._get_element_text(item, 'published')

                if title:
                    items.append({
                        "title": title,
                        "content": description or "",
                        "link": link,
                        "published": pub_date,
                        "source": urlparse(rss_url).netloc
                    })

            return items

        except Exception as e:
            self.logger.error(f"Error parsing RSS {rss_url}: {e}")
            return []

    def _get_element_text(self, element: Any, tag: str, namespace_prefix: str = '') -> Optional[str]:
        """获取元素文本"""
        if namespace_prefix:
            # 有命名空间的情况
            for prefix, uri in element.nsmap.items():
                if prefix == namespace_prefix:
                    ns_tag = f"{{{uri}}}{tag[len(namespace_prefix)+1:]}"
                    el = element.find(ns_tag)
                    if el is not None:
                        return el.text
        else:
            el = element.find(tag)
            if el is not None:
                return el.text
        return None


class RateLimiter:
    """速率限制器"""

    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.request_times: List[float] = []

    async def acquire(self):
        """获取许可（阻塞直到可以请求）"""
        now = time.time()

        # 清理过期的记录
        self.request_times = [t for t in self.request_times if now - t < 60]

        if len(self.request_times) >= self.requests_per_minute:
            # 需要等待
            wait_time = 60 - (now - self.request_times[0])
            if wait_time > 0:
                await asyncio.sleep(wait_time)

        self.request_times.append(time.time())


# ============================================================
# 案例解析器
# ============================================================

class CaseParser:
    """案例解析器 - 从不同格式的内容中解析案例"""

    # 诈骗类型映射
    SCAM_TYPE_MAPPING: Dict[str, str] = {
        # 中文名 -> 英文ID
        "冒充公检法": "police_impersonation",
        "冒充公安": "police_impersonation",
        "公检法": "police_impersonation",
        "公安": "police_impersonation",
        "投资理财": "investment_fraud",
        "投资": "investment_fraud",
        "理财": "investment_fraud",
        "兼职刷单": "part_time_fraud",
        "刷单": "part_time_fraud",
        "兼职": "part_time_fraud",
        "虚假贷款": "loan_fraud",
        "贷款": "loan_fraud",
        "杀猪盘": "pig_butchery",
        "恋爱诈骗": "pig_butchery",
        "AI诈骗": "ai_voice_fraud",
        "语音诈骗": "ai_voice_fraud",
        "深度伪造": "deepfake_fraud",
        "征信诈骗": "credit_fraud",
        "征信": "credit_fraud",
        "退款诈骗": "refund_fraud",
        "退款": "refund_fraud",
        "购物退款": "refund_fraud",
        "游戏交易": "gaming_fraud",
        "游戏诈骗": "gaming_fraud",
        "追星诈骗": "fan_fraud",
        "粉丝诈骗": "fan_fraud",
        "医保诈骗": "medical_fraud",
        "医保": "medical_fraud",
        "电信诈骗": "telecom_fraud",
        "网络诈骗": "cyber_fraud",
        "假冒客服": "fake_customer",
        "客服": "fake_customer",
    }

    def parse_from_news(self, news_item: Dict) -> Optional[Dict]:
        """从新闻条目解析案例"""
        title = news_item.get("title", "")
        content = news_item.get("content", "")
        link = news_item.get("link", "")
        published = news_item.get("published", "")

        # 合并标题和内容
        full_text = f"{title} {content}"

        # 检测是否包含诈骗相关内容
        if not self._contains_scam_content(full_text):
            return None

        # 提取诈骗类型
        scam_type = self._extract_scam_type(full_text)

        # 提取风险等级（基于关键词）
        risk_level = self._estimate_risk_level(full_text)

        # 提取关键词
        keywords = self._extract_keywords(full_text)

        # 提取金额（如果有）
        amount = self._extract_amount(full_text)

        return {
            "type": "scam_case",
            "scam_type": scam_type,
            "title": title or "新闻案例",
            "content": content or title,
            "risk_level": risk_level,
            "keywords": keywords,
            "amount": amount,
            "source": news_item.get("source", "news"),
            "url": link,
            "published_at": published,
            "metadata": {
                "imported_at": time.time(),
                "source_type": "news",
                "verified": False
            }
        }

    def parse_from_api(self, api_data: Dict) -> Optional[Dict]:
        """从API数据解析案例"""
        try:
            # 尝试不同的API格式
            content = api_data.get("content") or api_data.get("description") or \
                      api_data.get("detail") or api_data.get("text", "")

            title = api_data.get("title") or api_data.get("name") or \
                    api_data.get("subject", "")

            scam_type_raw = api_data.get("scam_type") or api_data.get("type") or \
                           api_data.get("category", "")

            scam_type = self._normalize_scam_type(scam_type_raw)

            return {
                "type": "scam_case",
                "scam_type": scam_type,
                "title": title,
                "content": content,
                "risk_level": api_data.get("risk_level", 3),
                "keywords": api_data.get("keywords", []),
                "source": api_data.get("source", "api"),
                "original_id": api_data.get("id"),
                "metadata": {
                    "imported_at": time.time(),
                    "source_type": "api",
                    "raw_data": api_data
                }
            }

        except Exception:
            return None

    def parse_from_text(self, text: str, metadata: Optional[Dict] = None) -> Optional[Dict]:
        """从纯文本解析案例"""
        if not text or len(text) < 20:
            return None

        # 检测诈骗内容
        if not self._contains_scam_content(text):
            return None

        scam_type = self._extract_scam_type(text)
        risk_level = self._estimate_risk_level(text)
        keywords = self._extract_keywords(text)

        return {
            "type": "scam_case",
            "scam_type": scam_type,
            "title": text[:50] + "..." if len(text) > 50 else text,
            "content": text,
            "risk_level": risk_level,
            "keywords": keywords,
            "source": metadata.get("source", "text") if metadata else "text",
            "metadata": {
                "imported_at": time.time(),
                "source_type": "text",
                **(metadata or {})
            }
        }

    def _contains_scam_content(self, text: str) -> bool:
        """检测文本是否包含诈骗相关内容"""
        scam_indicators = [
            "诈骗", "骗子", "骗取", "诈骗分子", "电信诈骗", "网络诈骗",
            "冒充", "欺诈", "传销", "洗钱", "非法集资",
            "转账", "汇款", "骗钱", "上当", "被诈骗",
            "安全账户", "核查", "解冻费", "保证金",
            "高收益", "稳赚", "内幕", "导师",
            "刷单", "点赞", "佣金", "日结",
            "无抵押", "低利率", "手续费",
            "征信", "逾期", "修复",
            "退税", "退款", "赔偿",
            "绑架", "出事", "急需",
        ]

        text_lower = text.lower()
        matches = sum(1 for ind in scam_indicators if ind in text)
        return matches >= 2

    def _extract_scam_type(self, text: str) -> str:
        """从文本中提取诈骗类型"""
        for cn_type, en_type in self.SCAM_TYPE_MAPPING.items():
            if cn_type in text:
                return en_type

        # 基于关键词的默认推断
        if any(w in text for w in ["转账", "汇款", "账户", "验证码"]):
            return "financial_fraud"
        elif any(w in text for w in ["刷单", "兼职", "佣金", "日结"]):
            return "part_time_fraud"
        elif any(w in text for w in ["投资", "理财", "高收益", "博彩"]):
            return "investment_fraud"
        elif any(w in text for w in ["贷款", "无抵押", "手续费"]):
            return "loan_fraud"
        elif any(w in text for w in ["公安", "警察", "涉嫌", "洗钱"]):
            return "police_impersonation"

        return "unknown"

    def _estimate_risk_level(self, text: str) -> int:
        """估算风险等级"""
        high_risk_indicators = [
            "紧急", "马上", "立刻", "赶紧", "否则", "后果严重",
            "逮捕", "通缉", "坐牢", "涉嫌", "犯罪",
            "转账", "汇款", "大额", "万", "十万", "百万",
            "全部积蓄", "借款", "网贷"
        ]

        medium_risk_indicators = [
            "高收益", "稳赚", "保本", "内幕", "导师",
            "刷单", "兼职", "佣金",
            "无抵押", "贷款", "手续费"
        ]

        high_count = sum(1 for ind in high_risk_indicators if ind in text)
        medium_count = sum(1 for ind in medium_risk_indicators if ind in text)

        if high_count >= 2 or "转账" in text and "万" in text:
            return 4
        elif high_count >= 1 or medium_count >= 2:
            return 3
        elif medium_count >= 1:
            return 2
        else:
            return 1

    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词"""
        keywords = []

        # 常见诈骗关键词
        scam_keywords = [
            "安全账户", "资金核查", "保证金", "解冻费", "手续费",
            "高收益", "稳赚", "保本", "内幕", "导师", "带单",
            "刷单", "点赞", "佣金", "日结", "连环任务",
            "无抵押", "快速放款", "验资", "流水",
            "征信", "逾期", "修复", "洗白",
            "双倍赔偿", "备用金", "质量问题",
            "游戏装备", "代练", "折扣充值",
            "粉丝群", "门票", "签名", "打榜",
            "医保", "异地报销", "盗用"
        ]

        for kw in scam_keywords:
            if kw in text:
                keywords.append(kw)

        return list(set(keywords))

    def _extract_amount(self, text: str) -> Optional[float]:
        """提取涉案金额"""
        # 匹配各种金额格式
        patterns = [
            r'(\d+(?:\.\d+)?)\s*万',
            r'(\d+(?:\.\d+)?)\s*千',
            r'(\d+(?:\.\d+)?)\s*元',
        ]

        max_amount = 0.0
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                amount = float(match)
                if '万' in pattern:
                    amount *= 10000
                elif '千' in pattern:
                    amount *= 1000
                max_amount = max(max_amount, amount)

        return max_amount if max_amount > 0 else None

    def _normalize_scam_type(self, scam_type: str) -> str:
        """标准化诈骗类型"""
        if not scam_type:
            return "unknown"

        return self.SCAM_TYPE_MAPPING.get(scam_type, scam_type)


# ============================================================
# 数据验证器
# ============================================================

class CaseValidator:
    """案例验证器 - 验证案例数据的完整性和可靠性"""

    # 最小内容长度
    MIN_CONTENT_LENGTH = 20

    # 最大内容长度
    MAX_CONTENT_LENGTH = 10000

    # 必须的诈骗类型
    VALID_SCAM_TYPES = {
        "police_impersonation", "investment_fraud", "part_time_fraud",
        "loan_fraud", "pig_butchery", "ai_voice_fraud", "deepfake_fraud",
        "credit_fraud", "refund_fraud", "gaming_fraud", "fan_fraud",
        "medical_fraud", "telecom_fraud", "cyber_fraud", "fake_customer",
        "unknown"
    }

    def validate(self, case: Dict) -> ValidationResult:
        """验证案例"""
        errors: List[str] = []
        warnings: List[str] = []
        suggestions: List[str] = []

        # 1. 必填字段检查
        if not case.get("content"):
            errors.append("缺少内容字段 content")
        elif len(case["content"]) < self.MIN_CONTENT_LENGTH:
            errors.append(f"内容过短（{len(case['content'])} < {self.MIN_CONTENT_LENGTH}字符）")
        elif len(case["content"]) > self.MAX_CONTENT_LENGTH:
            warnings.append(f"内容过长（{len(case['content'])} > {self.MAX_CONTENT_LENGTH}字符），可能被截断")
            case["content"] = case["content"][:self.MAX_CONTENT_LENGTH]

        if not case.get("scam_type"):
            warnings.append("缺少诈骗类型 scam_type，将使用 unknown")
            case["scam_type"] = "unknown"
        elif case["scam_type"] not in self.VALID_SCAM_TYPES:
            warnings.append(f"诈骗类型 {case['scam_type']} 不在标准列表中")

        # 2. 风险等级检查
        risk_level = case.get("risk_level")
        if risk_level is None:
            warnings.append("缺少风险等级 risk_level，建议补充")
            suggestions.append("建议添加风险等级：1-关注, 2-警告, 3-危险, 4-紧急")
        elif not isinstance(risk_level, int) or not (0 <= risk_level <= 4):
            errors.append(f"风险等级无效: {risk_level}，应为0-4的整数")
            case["risk_level"] = 3  # 默认中等风险

        # 3. 来源检查
        if not case.get("source"):
            warnings.append("缺少来源 source 字段")

        # 4. 隐私信息检查
        privacy_patterns = {
            "phone": (r'1[3-9]\d{9}', "电话号码"),
            "email": (r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', "邮箱地址"),
            "id_card": (r'\d{17}[\dXx]', "身份证号"),
            "bank_card": (r'\d{16,19}', "银行卡号"),
        }

        privacy_found = []
        for ptype, (pattern, name) in privacy_patterns.items():
            if re.search(pattern, case.get("content", "")):
                privacy_found.append(name)

        if privacy_found:
            warnings.append(f"内容中包含隐私信息: {', '.join(privacy_found)}")
            suggestions.append("建议在导入前对隐私信息进行脱敏处理")

        # 5. 重复检查
        if self._is_duplicate_content(case):
            warnings.append("内容可能与已有案例重复")
            suggestions.append("建议检查是否需要去重")

        # 6. 质量建议
        if not case.get("keywords"):
            suggestions.append("建议添加关键词 keywords 以提高检索准确性")
        elif len(case["keywords"]) > 20:
            warnings.append("关键词过多，建议精简到20个以内")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions
        )

    def _is_duplicate_content(self, case: Dict) -> bool:
        """检查是否重复内容"""
        content = case.get("content", "")
        if len(content) < 50:
            return False

        # 使用简单的内容哈希检查
        content_hash = hashlib.md5(content.encode()).hexdigest()

        # 检查是否有完全相同的内容
        if hasattr(self, '_content_hashes'):
            if content_hash in self._content_hashes:
                return True
            self._content_hashes.add(content_hash)
        else:
            self._content_hashes: Set[str] = {content_hash}

        return False


# ============================================================
# 知识更新器
# ============================================================

class KnowledgeUpdater:
    """
    知识更新器
    
    实现自动化流程，将新的互联网诈骗案例
    清洗后导入向量数据库，支持定时更新和增量更新。
    """
    
    # 数据清洗规则
    CLEANING_RULES: Dict[str, str] = {
        "remove_urls": r'http[s]?://\S+',
        "remove_phone": r'1[3-9]\d{9}',
        "remove_email": r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
        "remove_id": r'\d{17}[\dXx]',
        "remove_bank": r'\d{16,19}',
        "normalize_whitespace": r'\s+',
    }
    
    def __init__(self, knowledge_base: Optional[Any] = None,
                 vector_store: Optional[Any] = None):
        """
        初始化知识更新器
        
        Args:
            knowledge_base: 知识库实例
            vector_store: 向量存储实例
        """
        self.knowledge_base = knowledge_base
        self.vector_store = vector_store
        
        # 子组件
        self.data_source_registry = DataSourceRegistry()
        self.data_fetcher = DataFetcher()
        self.case_parser = CaseParser()
        self.case_validator = CaseValidator()

        # 任务管理
        self.update_tasks: Dict[str, UpdateTask] = {}
        self.update_history: List[UpdateTask] = []
        self.update_callbacks: List[Callable] = []

        # 变更追踪
        self.change_log: List[DataChange] = []
        
        # 清洗规则
        self.cleaning_patterns: Dict[str, Any] = {
            k: re.compile(v) for k, v in self.CLEANING_RULES.items()
        }
    
        # 缓存
        self._fetched_urls: Set[str] = set()

    async def create_update_task(self, task_type: str, data: List[Dict],
                               source: str = "manual",
                               source_type: DataSourceType = DataSourceType.MANUAL) -> UpdateTask:
        """
        创建更新任务
        
        Args:
            task_type: 任务类型
            data: 更新数据
            source: 数据来源
            source_type: 数据源类型
            
        Returns:
            UpdateTask: 更新任务
        """
        task_id = f"task_{task_type}_{int(time.time())}_{hashlib.md5(str(data).encode()).hexdigest()[:6]}"
        
        task = UpdateTask(
            task_id=task_id,
            task_type=task_type,
            source=source,
            source_type=source_type,
            data=data,
            status=UpdateStatus.PENDING
        )
        
        self.update_tasks[task_id] = task
        return task
    
    async def execute_update_task(self, task_id: str) -> UpdateTask:
        """执行更新任务"""
        task = self.update_tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        task.status = UpdateStatus.PROCESSING
        task.started_at = time.time()
        
        try:
            if task.task_type == "case_import":
                result = await self._import_cases(task.data, task.source)
            elif task.task_type == "pattern_update":
                result = await self._update_patterns(task.data)
            elif task.task_type == "keyword_update":
                result = await self._update_keywords(task.data)
            elif task.task_type == "full_sync":
                result = await self._full_sync(task.data)
            else:
                raise ValueError(f"Unknown task type: {task.task_type}")
            
            task.status = UpdateStatus.COMPLETED
            task.progress = 1.0
            task.result = result
            
        except Exception as e:
            task.status = UpdateStatus.FAILED
            task.error_message = str(e)
            task.retry_count += 1

            if task.retry_count < task.max_retries:
                task.status = UpdateStatus.PENDING
                self.logger.warning(f"Task {task_id} failed, will retry ({task.retry_count}/{task.max_retries})")

        task.completed_at = time.time()
        self.update_history.append(task)

        if task_id in self.update_tasks:
            del self.update_tasks[task_id]
        
        await self._trigger_callbacks(task)
        return task
    
    async def _import_cases(self, cases: List[Dict], source: str) -> Dict:
        """导入案例"""
        processed = 0
        imported = 0
        skipped = 0
        failed = 0
        errors: List[Dict] = []
        warnings: List[Dict] = []
        
        for case_data in cases:
            try:
                processed += 1
                
                # 1. 数据清洗
                cleaned_case = self._clean_case_data(case_data)
                
                # 2. 验证
                validation = self.case_validator.validate(cleaned_case)
                if not validation.valid:
                    errors.append({
                        "case_id": case_data.get("case_id", "unknown"),
                        "errors": validation.errors
                    })
                    failed += 1
                    continue
                
                if validation.warnings:
                    warnings.append({
                        "case_id": case_data.get("case_id", "unknown"),
                        "warnings": validation.warnings
                    })

                # 3. 标准化
                normalized_case = self._normalize_case(cleaned_case)

                # 4. 导入知识库
                if self.knowledge_base:
                    try:
                        await self.knowledge_base.add_entry(normalized_case)
                    except Exception as e:
                        # 知识库可能不支持add_entry，跳过
                        pass
                
                # 5. 向量化存入向量库
                if self.vector_store:
                    await self._add_to_vector_store(normalized_case)
                
                imported += 1
            
            except Exception as e:
                failed += 1
                errors.append({
                    "case_id": case_data.get("case_id", "unknown"),
                    "error": str(e)
                })
        
        return {
            "processed": processed,
            "imported": imported,
            "skipped": skipped,
            "failed": failed,
            "errors": errors[:20],  # 最多保留20条错误
            "warnings": warnings[:20],
            "source": source
        }
    
    def _clean_case_data(self, case_data: Dict) -> Dict:
        """清洗案例数据"""
        cleaned = case_data.copy()
        
        # 清洗内容文本
        if "content" in cleaned:
            content = cleaned["content"]
            for name, pattern in self.cleaning_patterns.items():
                if name != "normalize_whitespace":
                content = pattern.sub('[已隐藏]', content)
                else:
                    content = pattern.sub(' ', content)
            cleaned["content"] = content.strip()
        
        # 清洗标题
        if "title" in cleaned:
            title = cleaned["title"]
            for name, pattern in self.cleaning_patterns.items():
                if name not in ["normalize_whitespace"]:
                    title = pattern.sub('[已隐藏]', title)
            cleaned["title"] = title.strip()
        
        return cleaned
    
    def _normalize_case(self, case_data: Dict) -> Dict:
        """标准化案例"""
        # 解析诈骗类型
        scam_type_raw = case_data.get("scam_type", "")
        scam_type = self.case_parser._normalize_scam_type(scam_type_raw)

        return {
            "type": "scam_case",
            "scam_type": scam_type,
            "title": case_data.get("title", "未知案例"),
            "content": case_data.get("content", ""),
            "risk_level": case_data.get("risk_level", 3),
            "keywords": case_data.get("keywords", []),
            "metadata": {
                "source": case_data.get("source", "unknown"),
                "original_id": case_data.get("case_id"),
                "imported_at": time.time(),
                "original_metadata": case_data.get("metadata", {})
            }
        }
    
    async def _add_to_vector_store(self, case_data: Dict):
        """添加到向量存储"""
        if not self.vector_store:
            return
        
        entry = {
            "id": f"case_{case_data['metadata'].get('original_id', time.time())}",
            "content": case_data["content"],
            "type": "scam_case",
            "metadata": {
                "scam_type": case_data.get("scam_type"),
                "risk_level": case_data.get("risk_level")
            }
        }
        
        try:
            if hasattr(self.vector_store, 'add'):
        await self.vector_store.add([entry])
            elif hasattr(self.vector_store, 'add_documents'):
                self.vector_store.add_documents([entry])
        except Exception:
            pass
    
    async def _update_patterns(self, patterns: List[Dict]) -> Dict:
        """更新模式库"""
        updated = 0
        skipped = 0
        
        for pattern_data in patterns:
            scam_type = pattern_data.get("scam_type")
            pattern = pattern_data.get("pattern")
            
            if not scam_type or not pattern:
                skipped += 1
                continue

            # 记录变更
            change = DataChange(
                change_id=f"change_{int(time.time())}_{hashlib.md5(pattern.encode()).hexdigest()[:6]}",
                change_type="added",
                entity_type="pattern",
                entity_id=pattern[:50],
                content_hash=hashlib.md5(pattern.encode()).hexdigest(),
                timestamp=time.time(),
                source=pattern_data.get("source", "manual")
            )
            self.change_log.append(change)
                updated += 1
        
        return {"updated": updated, "skipped": skipped, "changes": [c.change_id for c in self.change_log[-updated:]]}
    
    async def _update_keywords(self, keywords: List[Dict]) -> Dict:
        """更新关键词库"""
        updated = 0
        skipped = 0
        
        for kw_data in keywords:
            scam_type = kw_data.get("scam_type")
            keyword = kw_data.get("keyword")
            
            if not scam_type or not keyword:
                skipped += 1
                continue

            # 记录变更
            change = DataChange(
                change_id=f"change_{int(time.time())}_{hashlib.md5(keyword.encode()).hexdigest()[:6]}",
                change_type="added",
                entity_type="keyword",
                entity_id=keyword,
                content_hash=hashlib.md5(keyword.encode()).hexdigest(),
                timestamp=time.time(),
                source=kw_data.get("source", "manual")
            )
            self.change_log.append(change)
                updated += 1
        
        return {"updated": updated, "skipped": skipped, "changes": [c.change_id for c in self.change_log[-updated:]]}

    async def _full_sync(self, data: List[Dict]) -> Dict:
        """全量同步"""
        # 复用案例导入逻辑
        return await self._import_cases(data, "full_sync")

    def _record_change(self, change_type: str, entity_type: str, entity_id: str,
                       content: str, source: str):
        """记录数据变更"""
        change = DataChange(
            change_id=f"change_{int(time.time())}_{hashlib.md5(entity_id.encode()).hexdigest()[:6]}",
            change_type=change_type,
            entity_type=entity_type,
            entity_id=entity_id[:100],
            content_hash=hashlib.md5(content.encode()).hexdigest(),
            timestamp=time.time(),
            source=source
        )
        self.change_log.append(change)

        # 限制变更日志大小
        if len(self.change_log) > 10000:
            self.change_log = self.change_log[-5000:]

    async def fetch_from_source(self, source_id: str) -> List[Dict]:
        """从指定数据源抓取数据"""
        source = self.data_source_registry.get(source_id)
        if not source:
            raise ValueError(f"Unknown source: {source_id}")

        cases: List[Dict] = []

        if source.source_type == DataSourceType.WEB_SCRAPER:
            content = await self.data_fetcher.fetch_webpage(source.url, source.headers)
            if content:
                # 简单的HTML解析（实际应该使用BeautifulSoup等库）
                # 这里作为占位实现
                parsed_items = self._parse_html_content(content, source.url)
                for item in parsed_items:
                    case = self.case_parser.parse_from_news(item)
                    if case:
                        cases.append(case)

        elif source.source_type == DataSourceType.RSS_FEED:
            items = await self.data_fetcher.parse_rss(source.url)
            for item in items:
                case = self.case_parser.parse_from_news(item)
                if case:
                    cases.append(case)

        elif source.source_type == DataSourceType.OFFICIAL_API:
            data = await self.data_fetcher.fetch_api(source.url, source.headers)
            if data:
                if isinstance(data, list):
                    for item in data:
                        case = self.case_parser.parse_from_api(item)
                        if case:
                            cases.append(case)
                elif isinstance(data, dict):
                    case = self.case_parser.parse_from_api(data)
                    if case:
                        cases.append(case)

        # 更新数据源状态
        self.data_source_registry.update_fetch_status(
            source_id,
            success=len(cases) > 0
        )

        return cases

    def _parse_html_content(self, html: str, base_url: str) -> List[Dict]:
        """解析HTML内容（简化实现）"""
        # 这是一个简化实现，实际应该使用BeautifulSoup
        items: List[Dict] = []

        # 提取链接
        link_pattern = r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>([^<]+)</a>'
        links = re.findall(link_pattern, html)

        for href, text in links[:20]:  # 限制数量
            if href and text:
                # 合成新闻条目
                items.append({
                    "title": text.strip(),
                    "content": "",
                    "link": urljoin(base_url, href),
                    "source": urlparse(base_url).netloc
                })

        return items
    
    def register_callback(self, callback: Callable[[UpdateTask], None]):
        """注册更新回调"""
        self.update_callbacks.append(callback)
    
    async def _trigger_callbacks(self, task: UpdateTask):
        """触发回调"""
        for callback in self.update_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                await callback(task)
                else:
                    callback(task)
            except Exception:
                pass
    
    def get_task_status(self, task_id: str) -> Optional[UpdateTask]:
        """获取任务状态"""
        return self.update_tasks.get(task_id)

    def get_update_history(self, limit: int = 20) -> List[UpdateTask]:
        """获取更新历史"""
        return self.update_history[-limit:]

    def get_change_log(self, since: Optional[float] = None, limit: int = 100) -> List[DataChange]:
        """获取变更日志"""
        changes = self.change_log
        if since:
            changes = [c for c in changes if c.timestamp >= since]
        return changes[-limit:]

    def get_data_source_stats(self) -> Dict[str, Any]:
        """获取数据源统计"""
        stats = {}
        for source in self.data_source_registry.get_all():
            stats[source.source_id] = {
                "name": source.name,
                "type": source.source_type.value,
                "enabled": source.enabled,
                "frequency": source.frequency.value,
                "last_fetch": source.last_fetch,
                "last_success": source.last_success,
                "consecutive_failures": source.consecutive_failures,
                "needs_fetch": source.needs_fetch()
            }
        return stats

    def export_update_config(self) -> Dict:
        """导出更新配置"""
        return {
            "data_sources": [
                {
                    "source_id": s.source_id,
                    "name": s.name,
                    "type": s.source_type.value,
                    "url": s.url,
                    "frequency": s.frequency.value,
                    "enabled": s.enabled
                }
                for s in self.data_source_registry.get_all()
            ],
            "recent_tasks": [
                {
                    "task_id": t.task_id,
                    "task_type": t.task_type,
                    "status": t.status.value,
                    "progress": t.progress,
                    "created_at": t.created_at,
                    "completed_at": t.completed_at
                }
                for t in self.update_history[-10:]
            ],
            "change_stats": {
                "total_changes": len(self.change_log),
                "recent_changes": len([c for c in self.change_log if time.time() - c.timestamp < 86400])
            }
        }


# ============================================================
# 定时更新调度器（新版完整实现）
# ============================================================

class ScheduledUpdater:
    """
    定时更新调度器

    支持：
    - 多数据源定时抓取
    - 增量更新检测
    - 失败重试
    - 并发控制
    - 事件通知
    """

    def __init__(self, knowledge_updater: Optional[KnowledgeUpdater] = None,
                 check_interval: int = 60):
        """
        初始化调度器

        Args:
            knowledge_updater: 知识更新器实例
            check_interval: 检查间隔（秒）
        """
        self.knowledge_updater = knowledge_updater or KnowledgeUpdater()
        self.check_interval = check_interval

        # 运行状态
        self._running = False
        self._task: Optional[asyncio.Task] = None

        # 事件回调
        self.on_fetch_start: Optional[Callable] = None
        self.on_fetch_complete: Optional[Callable] = None
        self.on_update_complete: Optional[Callable] = None
        self.on_error: Optional[Callable] = None

        # 统计
        self.stats = {
            "total_runs": 0,
            "successful_runs": 0,
            "failed_runs": 0,
            "total_cases_fetched": 0,
            "total_cases_imported": 0,
            "last_run": None,
            "last_success": None
        }

        # 并发控制
        self._semaphore = asyncio.Semaphore(3)  # 最多3个并发抓取

        self.logger = logging.getLogger(__name__)

    async def start(self):
        """启动调度器"""
        if self._running:
            self.logger.warning("Scheduler already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        self.logger.info("ScheduledUpdater started")

    async def stop(self):
        """停止调度器"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self.logger.info("ScheduledUpdater stopped")

    async def _run_loop(self):
        """主循环"""
        while self._running:
            try:
                await self._check_and_update()
                self.stats["total_runs"] += 1
                self.stats["last_run"] = time.time()

            except Exception as e:
                self.stats["failed_runs"] += 1
                self.logger.error(f"Scheduled update failed: {e}")
                if self.on_error:
                    try:
                        self.on_error(e)
                    except Exception:
                        pass

            # 等待下次检查
            await asyncio.sleep(self.check_interval)

    async def _check_and_update(self):
        """检查并执行更新"""
        # 获取需要抓取的数据源
        sources = self.knowledge_updater.data_source_registry.get_needing_fetch()

        if not sources:
            return

        if self.on_fetch_start:
            try:
                self.on_fetch_start(sources)
            except Exception:
                pass

        # 并发抓取
        tasks = [self._fetch_and_import(source) for source in sources]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 统计
        total_fetched = 0
        total_imported = 0

        for result in results:
            if isinstance(result, dict):
                total_fetched += result.get("fetched", 0)
                total_imported += result.get("imported", 0)
            elif isinstance(result, Exception):
                self.logger.error(f"Fetch error: {result}")

        self.stats["total_cases_fetched"] += total_fetched
        self.stats["total_cases_imported"] += total_imported

        if total_imported > 0:
            self.stats["successful_runs"] += 1
            self.stats["last_success"] = time.time()

        if self.on_fetch_complete:
            try:
                self.on_fetch_complete({
                    "sources_checked": len(sources),
                    "fetched": total_fetched,
                    "imported": total_imported
                })
            except Exception:
                pass

    async def _fetch_and_import(self, source: DataSource) -> Dict:
        """抓取并导入单个数据源"""
        async with self._semaphore:
            self.logger.info(f"Fetching from {source.name}...")

            try:
                # 抓取数据
                cases = await self.knowledge_updater.fetch_from_source(source.source_id)

                imported = 0
                if cases:
                    # 创建导入任务
                    task = await self.knowledge_updater.create_update_task(
                        task_type="case_import",
                        data=cases,
                        source=source.source_id,
                        source_type=source.source_type
                    )

                    # 执行任务
                    result_task = await self.knowledge_updater.execute_update_task(task.task_id)

                    if result_task.result:
                        imported = result_task.result.get("imported", 0)

                self.logger.info(f"Fetched {len(cases)} cases, imported {imported} from {source.name}")

                return {"fetched": len(cases), "imported": imported}

            except Exception as e:
                self.logger.error(f"Error fetching {source.name}: {e}")
                raise

    async def force_fetch_all(self) -> Dict:
        """强制抓取所有数据源"""
        sources = self.knowledge_updater.data_source_registry.get_enabled()
        results = []

        for source in sources:
            result = await self._fetch_and_import(source)
            results.append({
                "source_id": source.source_id,
                "name": source.name,
                **result
            })

        return {
            "sources_processed": len(results),
            "results": results,
            "total_fetched": sum(r.get("fetched", 0) for r in results),
            "total_imported": sum(r.get("imported", 0) for r in results)
        }

    async def force_fetch_source(self, source_id: str) -> Dict:
        """强制抓取指定数据源"""
        source = self.knowledge_updater.data_source_registry.get(source_id)
        if not source:
            return {"error": f"Unknown source: {source_id}"}

        result = await self._fetch_and_import(source)
        return {
            "source_id": source_id,
            "name": source.name,
            **result
        }

    def get_stats(self) -> Dict:
        """获取调度器统计"""
        return {
            **self.stats,
            "running": self._running,
            "sources_enabled": len(self.knowledge_updater.data_source_registry.get_enabled()),
            "sources_need_fetch": len(self.knowledge_updater.data_source_registry.get_needing_fetch())
        }


# ============================================================
# 兼容性别名（保留旧接口）
# ============================================================

class KnowledgeUpdaterV2(ScheduledUpdater):
    """知识更新器V2（兼容新版调度器）"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(__name__)
