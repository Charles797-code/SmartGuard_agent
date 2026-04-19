"""
智能学习进化服务
将进化模块集成到主流程，实现持续学习、自我优化和知识管理
"""

import time
import json
import asyncio
import logging
import hashlib
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field, asdict
from collections import defaultdict
from enum import Enum

try:
    from src.data.database import get_database
except ImportError:
    from data.database import get_database


# ============================================================
# 数据类定义
# ============================================================

class EvolutionStatus(Enum):
    """进化状态"""
    IDLE = "idle"
    LEARNING = "learning"
    EVALUATING = "evaluating"
    OPTIMIZING = "optimizing"
    SYNCING = "syncing"
    ERROR = "error"


@dataclass
class LearningRecord:
    """学习记录"""
    record_id: str
    user_id: str
    content: str
    risk_level: int
    risk_type: str
    analysis: str
    response: str
    learned: bool = False
    created_at: float = field(default_factory=time.time)
    quality_score: float = 0.0
    keywords_found: List[str] = field(default_factory=list)
    patterns_found: List[str] = field(default_factory=list)


@dataclass
class EvolutionStats:
    """进化统计"""
    total_records: int = 0
    learned_cases: int = 0
    new_keywords_added: int = 0
    new_patterns_added: int = 0
    reports_integrated: int = 0
    last_evolution: Optional[float] = None
    last_report_sync: Optional[float] = None
    accuracy_improvement: float = 0.0
    quality_score_avg: float = 0.0
    evolution_count: int = 0


@dataclass
class KnowledgeSnapshot:
    """知识快照"""
    snapshot_id: str
    timestamp: float
    keywords_count: int
    patterns_count: int
    cases_count: int
    checksum: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EvolutionResult:
    """进化结果"""
    status: str
    cases_processed: int
    cases_learned: int
    new_keywords: List[str]
    new_patterns: List[str]
    accuracy_improvement: float
    quality_report: Dict[str, Any]
    warnings: List[str] = field(default_factory=list)
    duration_ms: float = 0.0


# ============================================================
# 知识管理器
# ============================================================

class KnowledgeManager:
    """
    知识管理器

    负责：
    1. 知识的持久化（保存到数据库）
    2. 知识的加载（从数据库恢复）
    3. 知识的导入/导出
    4. 知识的版本管理
    5. 知识的同步
    """

    def __init__(self, db):
        self.db = db
        self.logger = logging.getLogger(__name__)

        # 内存缓存
        self._keyword_cache: Dict[str, Dict[str, Any]] = defaultdict(dict)
        self._pattern_cache: Dict[str, Dict[str, Any]] = defaultdict(dict)
        self._initialized = False

    async def initialize(self):
        """从数据库加载知识"""
        if self._initialized:
            return

        try:
            # 加载关键词
            keywords = await self.db.query("evolution_keywords", limit=10000)
            for kw in keywords:
                scam_type = kw.get("scam_type", "unknown")
                keyword = kw.get("keyword", "")
                self._keyword_cache[scam_type][keyword] = {
                    "keyword": keyword,
                    "scam_type": scam_type,
                    "weight": kw.get("weight", 1.0),
                    "frequency": kw.get("frequency", 1),
                    "is_verified": bool(kw.get("is_verified", 0)),
                    "first_seen": kw.get("first_seen", 0),
                    "last_seen": kw.get("last_seen", 0)
                }

            # 加载模式
            patterns = await self.db.query("evolution_patterns", limit=10000)
            for p in patterns:
                scam_type = p.get("scam_type", "unknown")
                pattern_id = p.get("pattern_id", "")
                self._pattern_cache[scam_type][pattern_id] = {
                    "pattern_id": pattern_id,
                    "pattern_text": p.get("pattern_text", ""),
                    "scam_type": scam_type,
                    "frequency": p.get("frequency", 1),
                    "confidence": p.get("confidence", 0.5),
                    "first_seen": p.get("first_seen", 0),
                    "last_seen": p.get("last_seen", 0)
                }

            self._initialized = True
            self.logger.info(f"[KnowledgeManager] Loaded {len(self._keyword_cache)} keyword types, "
                           f"{len(self._pattern_cache)} pattern types")

        except Exception as e:
            self.logger.error(f"[KnowledgeManager] Failed to initialize: {e}")

    async def save_keyword(self, scam_type: str, keyword: str, weight: float = 1.0,
                         frequency: int = 1, is_verified: bool = False):
        """保存关键词到数据库"""
        try:
            keyword_hash = hashlib.md5(f"{scam_type}:{keyword}".encode()).hexdigest()[:12]
            now = time.time()

            # 检查是否已存在
            existing = await self.db.query(
                "evolution_keywords",
                filters={"keyword": keyword, "scam_type": scam_type},
                limit=1
            )

            if existing:
                # 更新
                await self.db.update("evolution_keywords", existing[0]["id"], {
                    "frequency": existing[0].get("frequency", 0) + frequency,
                    "weight": (existing[0].get("weight", 1.0) + weight) / 2,
                    "last_seen": now,
                    "is_verified": 1 if is_verified else existing[0].get("is_verified", 0)
                })
            else:
                # 插入
                await self.db.insert("evolution_keywords", {
                    "id": f"ek_{keyword_hash}",
                    "keyword": keyword,
                    "scam_type": scam_type,
                    "weight": weight,
                    "frequency": frequency,
                    "is_verified": 1 if is_verified else 0,
                    "first_seen": now,
                    "last_seen": now
                })

            # 更新缓存
            self._keyword_cache[scam_type][keyword] = {
                "keyword": keyword,
                "scam_type": scam_type,
                "weight": weight,
                "frequency": frequency,
                "is_verified": is_verified,
                "last_seen": now
            }

        except Exception as e:
            self.logger.error(f"[KnowledgeManager] Failed to save keyword: {e}")

    async def save_pattern(self, scam_type: str, pattern_id: str, pattern_text: str,
                         frequency: int = 1, confidence: float = 0.5):
        """保存模式到数据库"""
        try:
            pattern_hash = hashlib.md5(pattern_id.encode()).hexdigest()[:12]
            now = time.time()

            # 检查是否已存在
            existing = await self.db.query(
                "evolution_patterns",
                filters={"pattern_id": pattern_id},
                limit=1
            )

            if existing:
                await self.db.update("evolution_patterns", existing[0]["id"], {
                    "frequency": existing[0].get("frequency", 0) + frequency,
                    "confidence": (existing[0].get("confidence", 0.5) + confidence) / 2,
                    "last_seen": now
                })
            else:
                await self.db.insert("evolution_patterns", {
                    "id": f"ep_{pattern_hash}",
                    "pattern_id": pattern_id,
                    "pattern_text": pattern_text,
                    "scam_type": scam_type,
                    "frequency": frequency,
                    "confidence": confidence,
                    "first_seen": now,
                    "last_seen": now
                })

            self._pattern_cache[scam_type][pattern_id] = {
                "pattern_id": pattern_id,
                "pattern_text": pattern_text,
                "scam_type": scam_type,
                "frequency": frequency,
                "confidence": confidence,
                "last_seen": now
            }

        except Exception as e:
            self.logger.error(f"[KnowledgeManager] Failed to save pattern: {e}")

    async def save_learning_record(self, record: LearningRecord):
        """保存学习记录"""
        try:
            await self.db.insert("evolution_records", {
                "id": record.record_id,
                "record_id": record.record_id,
                "user_id": record.user_id,
                "content": record.content,
                "risk_level": record.risk_level,
                "risk_type": record.risk_type,
                "analysis": record.analysis,
                "response": record.response,
                "learned": 1 if record.learned else 0,
                "quality_score": record.quality_score,
                "keywords_found": json.dumps(record.keywords_found, ensure_ascii=False),
                "patterns_found": json.dumps(record.patterns_found, ensure_ascii=False),
                "created_at": record.created_at
            })
        except Exception as e:
            self.logger.error(f"[KnowledgeManager] Failed to save record: {e}")

    def get_keywords(self, scam_type: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """获取关键词"""
        if scam_type:
            return {scam_type: self._keyword_cache.get(scam_type, {})}
        return dict(self._keyword_cache)

    def get_patterns(self, scam_type: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """获取模式"""
        if scam_type:
            return {scam_type: self._pattern_cache.get(scam_type, {})}
        return dict(self._pattern_cache)

    def export_knowledge(self) -> Dict[str, Any]:
        """导出知识"""
        return {
            "keywords": dict(self._keyword_cache),
            "patterns": dict(self._pattern_cache),
            "exported_at": time.time(),
            "checksum": self._calculate_checksum()
        }

    def import_knowledge(self, data: Dict):
        """导入知识"""
        if "keywords" in data:
            for scam_type, keywords in data["keywords"].items():
                self._keyword_cache[scam_type].update(keywords)

        if "patterns" in data:
            for scam_type, patterns in data["patterns"].items():
                self._pattern_cache[scam_type].update(patterns)

    def _calculate_checksum(self) -> str:
        """计算知识库的校验和"""
        data = json.dumps({
            "keywords": dict(self._keyword_cache),
            "patterns": dict(self._pattern_cache)
        }, sort_keys=True)
        return hashlib.md5(data.encode()).hexdigest()

    async def create_snapshot(self) -> KnowledgeSnapshot:
        """创建知识快照"""
        snapshot = KnowledgeSnapshot(
            snapshot_id=f"snap_{int(time.time())}",
            timestamp=time.time(),
            keywords_count=sum(len(v) for v in self._keyword_cache.values()),
            patterns_count=sum(len(v) for v in self._pattern_cache.values()),
            cases_count=0,  # 暂不支持
            checksum=self._calculate_checksum(),
            metadata={
                "evolution_count": 0
            }
        )

        try:
            await self.db.insert("evolution_snapshots", {
                "id": snapshot.snapshot_id,
                "snapshot_id": snapshot.snapshot_id,
                "keywords_count": snapshot.keywords_count,
                "patterns_count": snapshot.patterns_count,
                "cases_count": snapshot.cases_count,
                "checksum": snapshot.checksum,
                "metadata": json.dumps(snapshot.metadata),
                "created_at": snapshot.timestamp
            })
        except Exception as e:
            self.logger.error(f"[KnowledgeManager] Failed to create snapshot: {e}")

        return snapshot


# ============================================================
# 风险检测增强器
# ============================================================

class RiskDetectionEnhancer:
    """
    风险检测增强器

    将学习到的知识应用于风险检测，
    包括动态权重调整、模式匹配增强等。
    """

    def __init__(self, knowledge_manager: KnowledgeManager):
        self.knowledge_manager = knowledge_manager
        self.logger = logging.getLogger(__name__)

        # 动态权重调整
        self._keyword_weights: Dict[str, Dict[str, float]] = defaultdict(dict)
        self._pattern_boosts: Dict[str, Dict[str, float]] = defaultdict(dict)

    def enhance_detection(self, base_risk_level: int, content: str,
                        scam_type: str) -> Dict[str, Any]:
        """
        增强风险检测

        Args:
            base_risk_level: 基础风险等级
            content: 检测内容
            scam_type: 基础诈骗类型

        Returns:
            增强后的检测结果
        """
        result = {
            "base_risk_level": base_risk_level,
            "enhanced_risk_level": base_risk_level,
            "confidence_boost": 0.0,
            "keywords_found": [],
            "patterns_found": [],
            "keyword_matches": [],
            "pattern_matches": []
        }

        content_lower = content.lower()

        # 1. 关键词增强
        keywords = self.knowledge_manager.get_keywords(scam_type)
        for type_kw, kw_data in keywords.items():
            for keyword, info in kw_data.items():
                if keyword.lower() in content_lower:
                    weight = info.get("weight", 1.0)
                    freq = info.get("frequency", 1)

                    result["keywords_found"].append(keyword)
                    result["keyword_matches"].append({
                        "keyword": keyword,
                        "weight": weight,
                        "frequency": freq,
                        "scam_type": type_kw
                    })

                    # 计算置信度提升
                    boost = weight * min(freq / 10.0, 1.0) * 0.15
                    result["confidence_boost"] += boost

        # 2. 模式增强
        patterns = self.knowledge_manager.get_patterns(scam_type)
        for type_pt, pt_data in patterns.items():
            for pattern_id, info in pt_data.items():
                pattern_text = info.get("pattern_text", "")
                if pattern_text and pattern_text.lower() in content_lower:
                    confidence = info.get("confidence", 0.5)
                    freq = info.get("frequency", 1)

                    result["patterns_found"].append(pattern_text)
                    result["pattern_matches"].append({
                        "pattern_id": pattern_id,
                        "pattern_text": pattern_text,
                        "confidence": confidence,
                        "frequency": freq,
                        "scam_type": type_pt
                    })

                    # 模式匹配带来更高的置信度提升
                    boost = confidence * min(freq / 5.0, 1.0) * 0.25
                    result["confidence_boost"] += boost

        # 3. 计算增强后的风险等级
        if result["confidence_boost"] > 0:
            # 风险等级提升：每0.3置信度提升1级
            level_increase = int(result["confidence_boost"] / 0.3)
            new_level = min(base_risk_level + level_increase, 4)
            result["enhanced_risk_level"] = new_level

        return result

    def get_detection_boost(self, content: str) -> Dict[str, Any]:
        """获取全局检测提升（跨所有诈骗类型）"""
        content_lower = content.lower()
        all_boosts: Dict[str, float] = defaultdict(float)
        all_matches: Dict[str, List[str]] = defaultdict(list)

        for scam_type in self.knowledge_manager.get_keywords().keys():
            keywords = self.knowledge_manager.get_keywords(scam_type)
            for type_kw, kw_data in keywords.items():
                for keyword, info in kw_data.items():
                    if keyword.lower() in content_lower:
                        weight = info.get("weight", 1.0)
                        all_boosts[scam_type] += weight * 0.1
                        all_matches[scam_type].append(keyword)

        return {
            "type_boosts": dict(all_boosts),
            "type_matches": dict(all_matches),
            "top_type": max(all_boosts, key=all_boosts.get) if all_boosts else None
        }


# ============================================================
# 进化服务主类
# ============================================================

class EvolutionService:
    """
    智能学习进化服务

    功能：
    1. 记录每次风险检测案例
    2. 自动提取新诈骗手法
    3. 更新关键词库和模式库
    4. 定期自我进化优化
    5. 持久化到数据库
    6. 与举报系统集成
    7. 支持定时自动更新
    8. 知识导入导出
    """

    def __init__(self, learner=None, updater=None):
        try:
            from src.modules.evolution import KnowledgeLearner, KnowledgeUpdater
        except ImportError:
            from modules.evolution import KnowledgeLearner, KnowledgeUpdater

        self.learner = learner or KnowledgeLearner()
        self.updater = updater or KnowledgeUpdater()
        self.db = get_database()

        # 子组件
        self.knowledge_manager = KnowledgeManager(self.db)
        self.risk_enhancer = RiskDetectionEnhancer(self.knowledge_manager)

        # 进化状态
        self.status = EvolutionStatus.IDLE
        self.stats = EvolutionStats()

        # 内存缓存
        self.learning_records: List[LearningRecord] = []
        self.learned_patterns: Dict[str, List[str]] = defaultdict(list)
        self.learned_keywords: Dict[str, List[str]] = defaultdict(list)

        # 自动进化配置
        self.auto_evolution_enabled = True
        self.evolution_threshold = 10  # 积累多少案例触发进化
        self.auto_evolution_interval = 3600  # 最小进化间隔（秒）
        self._evolution_task: Optional[asyncio.Task] = None
        self._last_evolution_time: float = 0

        # 定时同步配置
        self.auto_sync_enabled = True
        self.sync_interval = 300  # 5分钟同步一次举报
        self._sync_task: Optional[asyncio.Task] = None

        # 初始化
        self.logger = logging.getLogger(__name__)

    async def initialize(self):
        """初始化服务"""
        await self.knowledge_manager.initialize()

        # 从数据库加载学习记录
        await self._load_from_db()

        # 启动定时任务
        if self.auto_evolution_enabled:
            self._evolution_task = asyncio.create_task(self._auto_evolution_loop())

        if self.auto_sync_enabled:
            self._sync_task = asyncio.create_task(self._auto_sync_loop())

        self.logger.info("[EvolutionService] Initialized")

    async def shutdown(self):
        """关闭服务"""
        if self._evolution_task:
            self._evolution_task.cancel()
            try:
                await self._evolution_task
            except asyncio.CancelledError:
                pass

        if self._sync_task:
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass

        self.logger.info("[EvolutionService] Shutdown")

    async def _load_from_db(self):
        """从数据库加载进化数据"""
        try:
            # 加载学习记录
            records = await self.db.query("evolution_records", limit=1000)
            for r in records:
                record = LearningRecord(
                    record_id=r.get("record_id", ""),
                    user_id=r.get("user_id", ""),
                    content=r.get("content", ""),
                    risk_level=r.get("risk_level", 0),
                    risk_type=r.get("risk_type", ""),
                    analysis=r.get("analysis", ""),
                    response=r.get("response", ""),
                    learned=bool(r.get("learned", 0)),
                    quality_score=r.get("quality_score", 0.0),
                    keywords_found=json.loads(r.get("keywords_found", "[]")),
                    patterns_found=json.loads(r.get("patterns_found", "[]")),
                    created_at=r.get("created_at", 0)
                )
                self.learning_records.append(record)

            # 从knowledge_manager获取已学习的知识
            self.learned_keywords = {
                st: list(kw_data.keys())
                for st, kw_data in self.knowledge_manager.get_keywords().items()
            }
            self.learned_patterns = {
                st: list(pt_data.keys())
                for st, pt_data in self.knowledge_manager.get_patterns().items()
            }

            # 统计
            self.stats.total_records = len(self.learning_records)
            self.stats.learned_cases = sum(1 for r in self.learning_records if r.learned)
            self.stats.new_keywords_added = sum(len(v) for v in self.learned_keywords.values())
            self.stats.new_patterns_added = sum(len(v) for v in self.learned_patterns.values())

            self.logger.info(f"[EvolutionService] Loaded {len(self.learning_records)} records, "
                           f"{self.stats.new_keywords_added} keywords, {self.stats.new_patterns_added} patterns")

        except Exception as e:
            self.logger.error(f"[EvolutionService] Failed to load from DB: {e}")

    async def _save_record_to_db(self, record: LearningRecord):
        """保存学习记录"""
        try:
            await self.db.insert("evolution_records", {
                "id": record.record_id,
                "record_id": record.record_id,
                "user_id": record.user_id,
                "content": record.content,
                "risk_level": record.risk_level,
                "risk_type": record.risk_type,
                "analysis": record.analysis,
                "response": record.response,
                "learned": 1 if record.learned else 0,
                "quality_score": record.quality_score,
                "keywords_found": json.dumps(record.keywords_found, ensure_ascii=False),
                "patterns_found": json.dumps(record.patterns_found, ensure_ascii=False),
                "created_at": record.created_at
            })
        except Exception as e:
            self.logger.error(f"[EvolutionService] Failed to save record: {e}")

    async def _auto_evolution_loop(self):
        """自动进化循环"""
        while True:
            try:
                await asyncio.sleep(60)  # 每分钟检查一次

                # 检查是否需要进化
                if self.stats.total_records - self.stats.learned_cases >= self.evolution_threshold:
                    now = time.time()
                    if now - self._last_evolution_time >= self.auto_evolution_interval:
                        await self.auto_evolve()

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"[EvolutionService] Auto evolution error: {e}")

    async def _auto_sync_loop(self):
        """自动同步循环"""
        while True:
            try:
                await asyncio.sleep(self.sync_interval)
                await self._sync_reports()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"[EvolutionService] Auto sync error: {e}")

    async def _sync_reports(self):
        """同步举报数据"""
        try:
            try:
                from src.modules.evolution.report_integration import integrate_reports_to_evolution
            except ImportError:
                from modules.evolution.report_integration import integrate_reports_to_evolution
            result = await integrate_reports_to_evolution(evolution_service=self)
            if result and result.get("learned_reports", 0) > 0:
                self.stats.reports_integrated += result["learned_reports"]
                self.stats.last_report_sync = time.time()
                self.logger.info(f"[EvolutionService] Synced {result['learned_reports']} reports")
        except Exception as e:
            self.logger.error(f"[EvolutionService] Report sync failed: {e}")

    async def record_case(self, user_id: str, content: str,
                         risk_level: int, risk_type: str,
                         analysis: str, response: str) -> Optional[LearningRecord]:
        """
        记录风险检测案例

        Args:
            user_id: 用户ID
            content: 用户发送的内容
            risk_level: 风险等级
            risk_type: 风险类型
            analysis: 分析说明
            response: AI回复

        Returns:
            LearningRecord: 学习记录
        """
        if risk_level < 2:
            return None

        # 计算质量评分（基于风险等级和内容长度）
        quality_score = min(0.5 + risk_level * 0.1 + min(len(content) / 1000, 0.3), 1.0)

        record = LearningRecord(
            record_id=f"record_{user_id}_{int(time.time())}",
            user_id=user_id,
            content=content,
            risk_level=risk_level,
            risk_type=risk_type,
            analysis=analysis,
            response=response,
            quality_score=quality_score,
            created_at=time.time()
        )

        self.learning_records.append(record)
        self.stats.total_records += 1

        # 保存到数据库
        await self._save_record_to_db(record)

        # 检查是否触发自动进化
        if self.auto_evolution_enabled:
            unlearned_count = sum(1 for r in self.learning_records if not r.learned)
            if unlearned_count >= self.evolution_threshold:
                now = time.time()
                if now - self._last_evolution_time >= self.auto_evolution_interval:
                    asyncio.create_task(self.auto_evolve())

        return record

    async def auto_evolve(self) -> EvolutionResult:
        """
        自动进化

        当积累足够案例时，自动分析学习
        """
        start_time = time.time()
        self.status = EvolutionStatus.LEARNING

        try:
            # 获取未学习的案例
            unlearned_cases = [
                r for r in self.learning_records
                if not r.learned and r.risk_level >= 2
            ]

            if len(unlearned_cases) < 3:
                return EvolutionResult(
                    status="insufficient_cases",
                    cases_processed=0,
                    cases_learned=0,
                    new_keywords=[],
                    new_patterns=[],
                    accuracy_improvement=0.0,
                    quality_report={}
                )

            self.logger.info(f"[Evolution] Starting auto evolution with {len(unlearned_cases)} cases...")

            # 转换为学习格式
            cases = [
                {
                    "case_id": r.record_id,
                    "content": r.content,
                    "label": "scam",
                    "scam_type": r.risk_type,
                    "risk_level": r.risk_level,
                    "source": f"user_{r.user_id}"
                }
                for r in unlearned_cases
            ]

            # 调用学习器
            result = await self.learner.learn_from_cases(cases)

            # 更新记录状态
            for r in unlearned_cases:
                r.learned = True

            # 保存新知识到数据库
            new_keywords = result.new_keywords
            new_patterns = result.new_patterns

            for kw in new_keywords:
                scam_type = self._guess_scam_type(kw)
                await self.knowledge_manager.save_keyword(scam_type, kw, weight=1.0)
                self.learned_keywords[scam_type].append(kw)

            for pattern in new_patterns:
                scam_type = self._guess_scam_type(pattern)
                pattern_id = f"pt_{hashlib.md5(pattern.encode()).hexdigest()[:8]}"
                await self.knowledge_manager.save_pattern(scam_type, pattern_id, pattern)
                self.learned_patterns[scam_type].append(pattern_id)

            # 更新统计
            self.stats.learned_cases += result.cases_learned
            self.stats.new_keywords_added += len(new_keywords)
            self.stats.new_patterns_added += len(new_patterns)
            self.stats.last_evolution = time.time()
            self.stats.accuracy_improvement = result.accuracy_improvement
            self.stats.evolution_count += 1
            self._last_evolution_time = time.time()

            # 清理过旧的记录
            if len(self.learning_records) > 100:
                self.learning_records = self.learning_records[-80:]

            duration_ms = (time.time() - start_time) * 1000

            self.logger.info(f"[Evolution] Completed! +{len(new_keywords)} keywords, "
                           f"+{len(new_patterns)} patterns, "
                           f"improvement={result.accuracy_improvement:.3f}, "
                           f"took {duration_ms:.1f}ms")

            return EvolutionResult(
                status="success",
                cases_processed=result.cases_processed,
                cases_learned=result.cases_learned,
                new_keywords=new_keywords,
                new_patterns=new_patterns,
                accuracy_improvement=result.accuracy_improvement,
                quality_report=result.quality_report,
                duration_ms=duration_ms
            )

        except Exception as e:
            self.logger.error(f"[EvolutionService] Auto evolution failed: {e}")
            self.status = EvolutionStatus.ERROR
            return EvolutionResult(
                status="error",
                cases_processed=0,
                cases_learned=0,
                new_keywords=[],
                new_patterns=[],
                accuracy_improvement=0.0,
                quality_report={},
                warnings=[str(e)]
            )
        finally:
            self.status = EvolutionStatus.IDLE

    async def learn_from_reports(self, cases: List[Dict]) -> Dict[str, Any]:
        """
        从举报案例学习

        Args:
            cases: 案例列表

        Returns:
            学习结果
        """
        if not cases:
            return {"learned_count": 0, "new_keywords": [], "new_patterns": []}

        # 调用学习器
        result = await self.learner.learn_from_cases(cases)

        # 保存新知识
        for kw in result.new_keywords:
            scam_type = self._guess_scam_type(kw)
            await self.knowledge_manager.save_keyword(scam_type, kw)
            if kw not in self.learned_keywords[scam_type]:
                self.learned_keywords[scam_type].append(kw)

        for pattern in result.new_patterns:
            scam_type = self._guess_scam_type(pattern)
            pattern_id = f"pt_{hashlib.md5(pattern.encode()).hexdigest()[:8]}"
            await self.knowledge_manager.save_pattern(scam_type, pattern_id, pattern)
            if pattern_id not in self.learned_patterns[scam_type]:
                self.learned_patterns[scam_type].append(pattern_id)

        self.stats.reports_integrated += len(cases)
        self.stats.last_report_sync = time.time()

        return {
            "learned_count": result.cases_learned,
            "new_keywords": result.new_keywords,
            "new_patterns": result.new_patterns
        }

    def _guess_scam_type(self, keyword: str) -> str:
        """根据关键词猜测诈骗类型"""
        keyword_lower = keyword.lower()

        mappings = {
            "转账": "financial_fraud", "汇款": "financial_fraud",
            "投资": "investment_fraud", "理财": "investment_fraud",
            "贷款": "loan_fraud",
            "兼职": "part_time_fraud", "刷单": "part_time_fraud",
            "公安": "police_impersonation", "警察": "police_impersonation",
            "洗钱": "police_impersonation", "涉嫌": "police_impersonation",
            "征信": "credit_fraud", "逾期": "credit_fraud",
            "退款": "refund_fraud", "赔偿": "refund_fraud",
            "游戏": "gaming_fraud", "装备": "gaming_fraud",
            "医保": "medical_fraud", "社保": "medical_fraud",
            "追星": "fan_fraud", "粉丝": "fan_fraud",
            "绑架": "ai_voice_fraud", "出事": "ai_voice_fraud",
            "恋爱": "pig_butchery", "亲爱的": "pig_butchery",
            "刷单": "part_time_fraud",
        }

        for key, value in mappings.items():
            if key in keyword:
                return value

        return "unknown"

    async def enhance_risk_detection(self, risk_level: int,
                                     risk_type: str,
                                     content: str) -> Dict[str, Any]:
        """
        增强风险检测

        结合学习到的知识进行更准确的检测
        """
        return self.risk_enhancer.enhance_detection(risk_level, content, risk_type)

    def get_learned_knowledge(self, scam_type: Optional[str] = None) -> Dict[str, Any]:
        """获取学习到的知识"""
        if scam_type:
            return {
                scam_type: {
                    "keywords": self.learned_keywords.get(scam_type, []),
                    "patterns": self.learned_patterns.get(scam_type, [])
                }
            }

        return {
            "keywords": dict(self.learned_keywords),
            "patterns": dict(self.learned_patterns)
        }

    def get_evolution_stats(self) -> Dict[str, Any]:
        """获取进化统计"""
        return {
            **asdict(self.stats),
            "status": self.status.value,
            "pending_cases": sum(1 for r in self.learning_records if not r.learned),
            "knowledge_count": {
                "keywords": self.stats.new_keywords_added,
                "patterns": self.stats.new_patterns_added
            },
            "auto_evolution_enabled": self.auto_evolution_enabled,
            "auto_sync_enabled": self.auto_sync_enabled
        }

    async def manual_learn(self, cases: List[Dict]) -> Dict[str, Any]:
        """手动学习指定案例"""
        result = await self.learner.learn_from_cases(cases)

        self.stats.learned_cases += result.cases_learned
        self.stats.new_keywords_added += len(result.new_keywords)
        self.stats.new_patterns_added += len(result.new_patterns)
        self.stats.last_evolution = time.time()

        return {
            "cases_processed": result.cases_processed,
            "cases_learned": result.cases_learned,
            "new_keywords": result.new_keywords,
            "new_patterns": result.new_patterns,
            "accuracy_improvement": result.accuracy_improvement
        }

    async def trigger_evolution(self) -> EvolutionResult:
        """手动触发进化"""
        return await self.auto_evolve()

    async def trigger_report_sync(self) -> Dict[str, Any]:
        """手动触发举报同步"""
        await self._sync_reports()
        return {"status": "synced", "reports_integrated": self.stats.reports_integrated}

    async def export_knowledge(self) -> Dict[str, Any]:
        """导出知识库"""
        return {
            **self.knowledge_manager.export_knowledge(),
            "learned_keywords": dict(self.learned_keywords),
            "learned_patterns": dict(self.learned_patterns),
            "exported_at": time.time()
        }

    async def import_knowledge(self, knowledge: Dict):
        """导入知识库"""
        if "learned_keywords" in knowledge:
            for scam_type, keywords in knowledge["learned_keywords"].items():
                for kw in keywords:
                    if kw not in self.learned_keywords[scam_type]:
                        self.learned_keywords[scam_type].append(kw)
                        await self.knowledge_manager.save_keyword(scam_type, kw)

        if "learned_patterns" in knowledge:
            for scam_type, patterns in knowledge["learned_patterns"].items():
                for pattern_id in patterns:
                    if pattern_id not in self.learned_patterns[scam_type]:
                        self.learned_patterns[scam_type].append(pattern_id)

        if "keywords" in knowledge:
            self.knowledge_manager.import_knowledge({"keywords": knowledge["keywords"]})

        if "patterns" in knowledge:
            self.knowledge_manager.import_knowledge({"patterns": knowledge["patterns"]})

    async def create_snapshot(self) -> KnowledgeSnapshot:
        """创建知识快照"""
        return await self.knowledge_manager.create_snapshot()


# ============================================================
# 全局实例管理
# ============================================================

_evolution_service: Optional[EvolutionService] = None


def get_evolution_service() -> EvolutionService:
    """获取进化服务实例（全局单例）"""
    global _evolution_service
    if _evolution_service is None:
        _evolution_service = EvolutionService()
    return _evolution_service


async def init_evolution_service() -> EvolutionService:
    """初始化进化服务（异步）"""
    global _evolution_service
    service = get_evolution_service()
    await service.initialize()
    return service


async def shutdown_evolution_service():
    """关闭进化服务"""
    global _evolution_service
    if _evolution_service:
        await _evolution_service.shutdown()
        _evolution_service = None
