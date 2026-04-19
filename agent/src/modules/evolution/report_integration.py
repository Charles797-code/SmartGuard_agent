"""
举报进化集成模块
将用户举报内容接入自进化系统，支持案例质量过滤、优先级排序和智能融合
"""

import time
import re
import hashlib
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from collections import defaultdict
from enum import Enum

try:
    from src.services.report_submit_service import ReportService, ReportStatus
except ImportError:
    from services.report_submit_service import ReportService, ReportStatus
try:
    from src.services.evolution_service import EvolutionService
except ImportError:
    from services.evolution_service import EvolutionService


# ============================================================
# 数据类定义
# ============================================================

class ReportQuality(Enum):
    """举报质量等级"""
    EXCELLENT = "excellent"    # 优秀
    GOOD = "good"              # 良好
    ACCEPTABLE = "acceptable"  # 可接受
    POOR = "poor"              # 较差
    REJECTED = "rejected"      # 拒绝


class LearningPriority(Enum):
    """学习优先级"""
    HIGH = 1     # 高优先级
    MEDIUM = 2   # 中优先级
    LOW = 3      # 低优先级
    NONE = 4     # 不学习


@dataclass
class CaseQualityFilter:
    """案例质量过滤器"""
    quality_score: float
    quality_level: ReportQuality
    priority: LearningPriority
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)

    # 评分维度
    completeness_score: float = 0.0  # 完整性
    reliability_score: float = 0.0   # 可靠性
    novelty_score: float = 0.0       # 新颖性
    diversity_score: float = 0.0     # 多样性

    # 原始数据
    original_keywords: List[str] = field(default_factory=list)
    extracted_keywords: List[str] = field(default_factory=list)
    matched_patterns: List[str] = field(default_factory=list)


@dataclass
class FusionResult:
    """融合结果"""
    fused_cases: List[Dict]
    keyword_clusters: Dict[str, List[str]]
    pattern_clusters: Dict[str, List[str]]
    new_keywords: List[str]
    new_patterns: List[str]
    duplicates_removed: int
    quality_stats: Dict[str, Any]


@dataclass
class IntegrationReport:
    """集成报告"""
    status: str
    total_reports: int
    qualified_reports: int
    learned_reports: int
    failed_reports: int
    new_keywords_count: int
    new_patterns_count: int
    quality_distribution: Dict[str, int]
    details: Dict[str, Any]


# ============================================================
# 质量评估器
# ============================================================

class ReportQualityEvaluator:
    """
    举报质量评估器

    从多个维度评估举报的质量：
    1. 完整性：是否包含必要的字段和详细信息
    2. 可靠性：来源是否可靠，内容是否一致
    3. 新颖性：是否包含新知识
    4. 多样性：内容是否具有代表性
    """

    # 各维度权重
    WEIGHTS = {
        "completeness": 0.25,
        "reliability": 0.30,
        "novelty": 0.25,
        "diversity": 0.20
    }

    # 必要字段
    REQUIRED_FIELDS = ["title", "content", "scam_type"]

    # 推荐字段
    RECOMMENDED_FIELDS = ["description", "amount", "scammer_contact", "platform"]

    # 高质量关键词（表明详细描述）
    DETAILED_INDICATORS = [
        "具体", "详细", "一开始", "后来", "然后", "最后",
        "第一天", "第二天", "上周", "这个月",
        "金额", "具体金额", "一共有", "累计",
        "对方说", "对方要求", "我按", "对方又"
    ]

    # 可疑低质量指标
    LOW_QUALITY_INDICATORS = [
        "不知道", "不清楚", "忘了", "好像", "大概",
        "没什么", "就这样", "没什么特别"
    ]

    # 新颖性检测（常见已有知识）
    KNOWN_PATTERNS: Dict[str, List[str]] = {
        "police_impersonation": ["公安", "民警", "洗钱", "安全账户", "资金核查"],
        "investment_fraud": ["投资", "理财", "高收益", "保本", "导师"],
        "part_time_fraud": ["刷单", "点赞", "佣金", "日结"],
        "loan_fraud": ["贷款", "无抵押", "手续费", "解冻"],
        "pig_butchery": ["恋爱", "亲爱的", "投资", "平台"],
        "refund_fraud": ["退款", "双倍", "质量问题", "备用金"],
    }

    def evaluate(self, report: Dict) -> CaseQualityFilter:
        """
        评估举报质量

        Args:
            report: 举报字典

        Returns:
            CaseQualityFilter: 质量评估结果
        """
        issues: List[str] = []
        suggestions: List[str] = []

        # 1. 评估完整性
        completeness = self._evaluate_completeness(report, issues, suggestions)

        # 2. 评估可靠性
        reliability = self._evaluate_reliability(report, issues, suggestions)

        # 3. 评估新颖性
        novelty = self._evaluate_novelty(report, issues, suggestions)

        # 4. 评估多样性
        diversity = self._evaluate_diversity(report, issues, suggestions)

        # 计算综合评分
        overall = (
            completeness * self.WEIGHTS["completeness"] +
            reliability * self.WEIGHTS["reliability"] +
            novelty * self.WEIGHTS["novelty"] +
            diversity * self.WEIGHTS["diversity"]
        )

        # 确定质量等级
        quality_level = self._score_to_quality_level(overall)

        # 确定学习优先级
        priority = self._score_to_priority(overall, completeness, novelty)

        # 提取关键词
        original_keywords = report.get("extracted_keywords", [])
        extracted_keywords = self._extract_additional_keywords(report)
        matched_patterns = self._find_matched_patterns(report)

        return CaseQualityFilter(
            quality_score=overall,
            quality_level=quality_level,
            priority=priority,
            issues=issues,
            suggestions=suggestions,
            completeness_score=completeness,
            reliability_score=reliability,
            novelty_score=novelty,
            diversity_score=diversity,
            original_keywords=original_keywords,
            extracted_keywords=extracted_keywords,
            matched_patterns=matched_patterns
        )

    def _evaluate_completeness(self, report: Dict, issues: List[str], suggestions: List[str]) -> float:
        """评估完整性"""
        score = 0.0
        max_score = 1.0

        # 检查必要字段
        missing_fields = []
        for field in self.REQUIRED_FIELDS:
            if not report.get(field):
                missing_fields.append(field)

        if missing_fields:
            score -= 0.3 * len(missing_fields)
            issues.append(f"缺少必要字段: {', '.join(missing_fields)}")

        # 检查推荐字段
        present_recommended = sum(1 for f in self.RECOMMENDED_FIELDS if report.get(f))
        score += (present_recommended / len(self.RECOMMENDED_FIELDS)) * 0.3

        # 内容长度
        content = report.get("content", "")
        title = report.get("title", "")
        total_length = len(content) + len(title)

        if total_length >= 200:
            score += 0.3
        elif total_length >= 100:
            score += 0.2
        elif total_length >= 50:
            score += 0.1
        elif total_length < 20:
            issues.append("内容过于简短")
            score -= 0.1

        # 详细描述指标
        full_text = f"{title} {content}"
        detailed_indicators_count = sum(1 for ind in self.DETAILED_INDICATORS if ind in full_text)
        if detailed_indicators_count >= 3:
            score += 0.2
        elif detailed_indicators_count >= 1:
            score += 0.1
        else:
            suggestions.append("建议提供更详细的时间线和操作过程")

        return max(min(score, max_score), 0.0)

    def _evaluate_reliability(self, report: Dict, issues: List[str], suggestions: List[str]) -> float:
        """评估可靠性"""
        score = 0.5  # 基础分

        # 来源可靠性
        source = report.get("source", "")
        if source == "user_submission":
            score += 0.2
        elif source == "official":
            score += 0.4

        # 状态可靠性
        status = report.get("status", "")
        if status == ReportStatus.VERIFIED.value:
            score += 0.2
        elif status == ReportStatus.REVIEWED.value:
            score += 0.1
        elif status == ReportStatus.PENDING.value:
            score -= 0.1

        # 低质量指标检测
        content = report.get("content", "")
        low_quality_count = sum(1 for ind in self.LOW_QUALITY_INDICATORS if ind in content)
        if low_quality_count >= 3:
            score -= 0.3
            issues.append("内容描述过于模糊，可能影响学习效果")
        elif low_quality_count >= 1:
            score -= 0.1

        # 一致性检查
        title = report.get("title", "")
        scam_type = report.get("scam_type", "")

        # 标题和内容是否与诈骗类型一致
        if scam_type:
            expected_keywords = self.KNOWN_PATTERNS.get(scam_type, [])
            title_content = f"{title} {content}"
            matches = sum(1 for kw in expected_keywords if kw in title_content)
            if matches >= 2:
                score += 0.1  # 一致性加分
            elif matches == 0 and len(expected_keywords) > 0:
                score -= 0.1  # 不一致扣分
                issues.append(f"内容与标注的诈骗类型({scam_type})可能不一致")

        return max(min(score, 1.0), 0.0)

    def _evaluate_novelty(self, report: Dict, issues: List[str], suggestions: List[str]) -> float:
        """评估新颖性"""
        score = 0.5  # 基础分

        content = report.get("content", "")
        scam_type = report.get("scam_type", "")

        # 检测是否包含新的诈骗手法
        novel_indicators = [
            "新型", "最近", "刚开始", "这次", "最近出现",
            "第一次", "之前没遇到过", "新颖"
        ]
        novel_count = sum(1 for ind in novel_indicators if ind in content)
        if novel_count >= 1:
            score += 0.3
            suggestions.append("该案例可能包含新型手法，请仔细核对内容")

        # 检测是否是常见已有模式
        if scam_type:
            known = self.KNOWN_PATTERNS.get(scam_type, [])
            content_kw_set = set(content)
            known_set = set(known)
            overlap = content_kw_set & known_set

            if len(overlap) >= 3:
                score -= 0.2  # 过于常见
            elif len(overlap) <= 1:
                score += 0.2  # 有一定新颖性

        # 包含具体金额（表明是真实案例）
        money_patterns = [r'\d+\s*万', r'\d+\s*千', r'\d+\s*元']
        has_amount = any(re.search(p, content) for p in money_patterns)
        if has_amount:
            score += 0.1

        return max(min(score, 1.0), 0.0)

    def _evaluate_diversity(self, report: Dict, issues: List[str], suggestions: List[str]) -> float:
        """评估多样性"""
        score = 0.5  # 基础分

        content = report.get("content", "")
        title = report.get("title", "")
        full_text = f"{title} {content}"

        # 句式多样性
        sentences = re.split(r'[。！？\n]+', full_text)
        sentences = [s.strip() for s in sentences if s.strip()]

        if len(sentences) >= 5:
            score += 0.2
        elif len(sentences) >= 3:
            score += 0.1
        elif len(sentences) < 2:
            score -= 0.1

        # 提取的关键词多样性
        keywords = report.get("extracted_keywords", [])
        if len(keywords) >= 3:
            score += 0.2
        elif len(keywords) >= 1:
            score += 0.1
        else:
            suggestions.append("建议提取更多关键词以提高多样性")

        # 涉及多方信息
        entities = {
            "time": bool(re.search(r'\d+[年月日时分秒]', full_text)),
            "money": bool(re.search(r'\d+\s*[万千百元块]', full_text)),
            "platform": bool(re.search(r'(APP|平台|网站|微信|QQ)', full_text)),
            "contact": bool(re.search(r'1[3-9]\d{9}', full_text)),
        }
        entity_count = sum(entities.values())
        if entity_count >= 3:
            score += 0.1

        return max(min(score, 1.0), 0.0)

    def _score_to_quality_level(self, score: float) -> ReportQuality:
        """分数转质量等级"""
        if score >= 0.8:
            return ReportQuality.EXCELLENT
        elif score >= 0.6:
            return ReportQuality.GOOD
        elif score >= 0.4:
            return ReportQuality.ACCEPTABLE
        else:
            return ReportQuality.POOR

    def _score_to_priority(self, overall: float, completeness: float, novelty: float) -> LearningPriority:
        """分数转优先级"""
        if overall >= 0.7 and completeness >= 0.5:
            return LearningPriority.HIGH
        elif overall >= 0.5:
            return LearningPriority.MEDIUM
        elif overall >= 0.3 and novelty >= 0.4:
            return LearningPriority.LOW
        else:
            return LearningPriority.NONE

    def _extract_additional_keywords(self, report: Dict) -> List[str]:
        """提取额外关键词"""
        keywords = set(report.get("extracted_keywords", []))

        content = report.get("content", "")
        title = report.get("title", "")
        full_text = f"{title} {content}"

        # 从内容中提取金额词
        money_patterns = [
            r'\d+\s*万', r'\d+\s*千', r'\d+\s*百', r'\d+\s*元'
        ]
        for pattern in money_patterns:
            matches = re.findall(pattern, full_text)
            for m in matches:
                keywords.add(m)

        # 从内容中提取诈骗相关词
        scam_words = [
            "转账", "汇款", "扫码", "验证码", "密码", "登录",
            "下载", "安装", "注册", "充值", "投资", "理财",
            "刷单", "兼职", "贷款", "客服", "退款", "赔偿",
            "公安", "警察", "涉嫌", "洗钱", "安全账户"
        ]
        for word in scam_words:
            if word in full_text:
                keywords.add(word)

        return list(keywords)

    def _find_matched_patterns(self, report: Dict) -> List[str]:
        """查找匹配的模式"""
        patterns = []
        content = report.get("content", "")
        scam_type = report.get("scam_type", "")

        # 从已知模式中匹配
        known = self.KNOWN_PATTERNS.get(scam_type, [])
        for kw in known:
            if kw in content:
                patterns.append(kw)

        # 匹配时间紧迫模式
        urgency_patterns = ["立即", "马上", "立刻", "赶紧", "限时", "否则", "不然"]
        for p in urgency_patterns:
            if p in content:
                patterns.append(f"紧迫感话术:{p}")
                break

        # 匹配信任建立模式
        trust_patterns = ["相信", "信任", "朋友", "认识", "家人"]
        for p in trust_patterns:
            if p in content:
                patterns.append(f"信任建立:{p}")
                break

        return patterns


# ============================================================
# 案例融合引擎
# ============================================================

class ReportFusionEngine:
    """
    举报融合引擎

    功能：
    1. 案例去重：识别并合并相似案例
    2. 关键词聚类：将相同主题的关键词聚类
    3. 模式提取：从多个案例中提取通用模式
    4. 知识融合：合并多个案例的知识，生成新的综合案例
    """

    def __init__(self):
        self.quality_evaluator = ReportQualityEvaluator()

    def fuse(self, reports: List[Dict], merge_threshold: float = 0.85) -> FusionResult:
        """
        融合举报案例

        Args:
            reports: 举报列表
            merge_threshold: 相似度阈值，超过则合并

        Returns:
            FusionResult: 融合结果
        """
        if not reports:
            return FusionResult(
                fused_cases=[],
                keyword_clusters={},
                pattern_clusters={},
                new_keywords=[],
                new_patterns=[],
                duplicates_removed=0,
                quality_stats={}
            )

        # 1. 质量评估
        quality_results = []
        for report in reports:
            quality = self.quality_evaluator.evaluate(report)
            quality_results.append((report, quality))

        # 2. 过滤低质量案例
        qualified = [
            (r, q) for r, q in quality_results
            if q.quality_level.value not in [ReportQuality.POOR.value, ReportQuality.REJECTED.value]
        ]

        # 3. 去重
        deduplicated, duplicates_removed = self._deduplicate(qualified, merge_threshold)

        # 4. 关键词聚类
        keyword_clusters = self._cluster_keywords(deduplicated)

        # 5. 模式聚类
        pattern_clusters = self._cluster_patterns(deduplicated)

        # 6. 生成融合案例
        fused_cases = self._generate_fused_cases(deduplicated)

        # 7. 提取新知识
        new_keywords = self._extract_new_keywords(deduplicated, keyword_clusters)
        new_patterns = self._extract_new_patterns(deduplicated, pattern_clusters)

        # 8. 质量统计
        quality_stats = self._calculate_quality_stats(quality_results)

        return FusionResult(
            fused_cases=fused_cases,
            keyword_clusters=keyword_clusters,
            pattern_clusters=pattern_clusters,
            new_keywords=new_keywords,
            new_patterns=new_patterns,
            duplicates_removed=duplicates_removed,
            quality_stats=quality_stats
        )

    def _deduplicate(self, qualified: List[tuple], threshold: float) -> tuple:
        """
        案例去重

        Args:
            qualified: 质量合格的 (report, quality) 列表
            threshold: 相似度阈值

        Returns:
            (去重后的列表, 去重数量)
        """
        unique: List[tuple] = []
        removed_count = 0

        for report, quality in qualified:
            is_duplicate = False

            for unique_report, _ in unique:
                # 计算相似度
                similarity = self._calculate_similarity(report, unique_report)

                if similarity >= threshold:
                    is_duplicate = True
                    # 合并：保留质量更好的
                    if quality.quality_score > self.quality_evaluator.evaluate(unique_report).quality_score:
                        unique.remove((unique_report, self.quality_evaluator.evaluate(unique_report)))
                        unique.append((report, quality))
                    removed_count += 1
                    break

            if not is_duplicate:
                unique.append((report, quality))

        return unique, removed_count

    def _calculate_similarity(self, report1: Dict, report2: Dict) -> float:
        """计算两个案例的相似度"""
        # 基于内容的相似度
        content1 = report1.get("content", "")
        content2 = report2.get("content", "")

        # 简单相似度：基于字符集合
        set1 = set(content1)
        set2 = set(content2)

        if not set1 or not set2:
            return 0.0

        intersection = len(set1 & set2)
        union = len(set1 | set2)

        base_similarity = intersection / union if union > 0 else 0.0

        # 诈骗类型加权
        type_match = 1.0 if report1.get("scam_type") == report2.get("scam_type") else 0.0

        # 综合相似度
        similarity = base_similarity * 0.7 + type_match * 0.3

        return similarity

    def _cluster_keywords(self, qualified: List[tuple]) -> Dict[str, List[str]]:
        """关键词聚类"""
        # 按诈骗类型分组
        clusters: Dict[str, List[str]] = defaultdict(list)

        for report, _ in qualified:
            scam_type = report.get("scam_type", "unknown")
            keywords = report.get("extracted_keywords", [])
            clusters[scam_type].extend(keywords)

        # 去重
        result: Dict[str, List[str]] = {}
        for scam_type, keywords in clusters.items():
            result[scam_type] = list(set(keywords))

        return result

    def _cluster_patterns(self, qualified: List[tuple]) -> Dict[str, List[str]]:
        """模式聚类"""
        clusters: Dict[str, List[str]] = defaultdict(list)

        for report, quality in qualified:
            scam_type = report.get("scam_type", "unknown")
            patterns = quality.matched_patterns
            clusters[scam_type].extend(patterns)

        # 去重
        result: Dict[str, List[str]] = {}
        for scam_type, patterns in clusters.items():
            result[scam_type] = list(set(patterns))

        return result

    def _generate_fused_cases(self, qualified: List[tuple]) -> List[Dict]:
        """生成融合案例"""
        fused = []

        for report, quality in qualified:
            fused_case = {
                "case_id": report.get("report_id", f"fused_{time.time()}"),
                "content": report.get("content", ""),
                "scam_type": report.get("scam_type", "unknown"),
                "risk_level": self._estimate_risk_level(report),
                "keywords": list(set(report.get("extracted_keywords", []) + quality.extracted_keywords)),
                "patterns": quality.matched_patterns,
                "quality_score": quality.quality_score,
                "priority": quality.priority.value,
                "source": "user_report",
                "learned": False,
                "metadata": {
                    "original_report_id": report.get("report_id"),
                    "quality_level": quality.quality_level.value,
                    "integrated_at": time.time()
                }
            }
            fused.append(fused_case)

        return fused

    def _extract_new_keywords(self, qualified: List[tuple],
                            keyword_clusters: Dict[str, List[str]]) -> List[str]:
        """提取新关键词"""
        # 新关键词定义为：在聚类中出现频率低但在案例中出现频率高的词
        all_keywords: Set[str] = set()
        for report, _ in qualified:
            all_keywords.update(report.get("extracted_keywords", []))

        return list(all_keywords)

    def _extract_new_patterns(self, qualified: List[tuple],
                             pattern_clusters: Dict[str, List[str]]) -> List[str]:
        """提取新模式"""
        all_patterns: Set[str] = set()
        for report, quality in qualified:
            all_patterns.update(quality.matched_patterns)

        return list(all_patterns)

    def _estimate_risk_level(self, report: Dict) -> int:
        """估算风险等级"""
        content = report.get("content", "")

        high_risk_indicators = ["转账", "万", "紧急", "马上", "立刻"]
        medium_risk_indicators = ["投资", "理财", "刷单", "佣金"]

        high_count = sum(1 for ind in high_risk_indicators if ind in content)
        medium_count = sum(1 for ind in medium_risk_indicators if ind in content)

        if high_count >= 2:
            return 4
        elif high_count >= 1 or medium_count >= 2:
            return 3
        elif medium_count >= 1:
            return 2
        else:
            return 1

    def _calculate_quality_stats(self, quality_results: List[tuple]) -> Dict[str, Any]:
        """计算质量统计"""
        total = len(quality_results)
        if total == 0:
            return {}

        distribution = defaultdict(int)
        total_score = 0.0

        for _, quality in quality_results:
            distribution[quality.quality_level.value] += 1
            total_score += quality.quality_score

        return {
            "total_reports": total,
            "average_score": total_score / total,
            "distribution": dict(distribution),
            "high_priority_count": sum(1 for _, q in quality_results if q.priority == LearningPriority.HIGH),
            "medium_priority_count": sum(1 for _, q in quality_results if q.priority == LearningPriority.MEDIUM),
            "low_priority_count": sum(1 for _, q in quality_results if q.priority == LearningPriority.LOW),
            "rejected_count": sum(1 for _, q in quality_results if q.priority == LearningPriority.NONE),
        }


# ============================================================
# 举报到进化的集成入口
# ============================================================

# 全局融合引擎实例
_fusion_engine: Optional[ReportFusionEngine] = None


def get_fusion_engine() -> ReportFusionEngine:
    """获取融合引擎实例"""
    global _fusion_engine
    if _fusion_engine is None:
        _fusion_engine = ReportFusionEngine()
    return _fusion_engine


async def integrate_reports_to_evolution(
    evolution_service: Optional[EvolutionService] = None,
    report_service: Optional[ReportService] = None,
    max_reports: int = 50,
    quality_threshold: float = 0.4
) -> IntegrationReport:
    """
    将举报内容接入自进化模块（核心入口）

    流程：
    1. 从举报服务获取待学习的举报
    2. 对每个举报进行质量评估
    3. 过滤低质量举报
    4. 案例去重和融合
    5. 提取新关键词和模式
    6. 调用进化服务进行学习

    Args:
        evolution_service: 进化服务实例
        report_service: 举报服务实例
        max_reports: 最大处理数量
        quality_threshold: 质量阈值

    Returns:
        IntegrationReport: 集成报告
    """
    try:
        from src.services.report_submit_service import report_service as default_report_service
    except ImportError:
        from services.report_submit_service import report_service as default_report_service
    try:
        from src.services.evolution_service import get_evolution_service as _get_evo
    except ImportError:
        from services.evolution_service import get_evolution_service as _get_evo
    evo_service = evolution_service or _get_evo()
    rep_service = report_service or default_report_service

    # 获取待学习的举报
    reports = await rep_service.get_reports_for_evolution(limit=max_reports)

    if not reports:
        return IntegrationReport(
            status="no_reports",
            total_reports=0,
            qualified_reports=0,
            learned_reports=0,
            failed_reports=0,
            new_keywords_count=0,
            new_patterns_count=0,
            quality_distribution={},
            details={"message": "没有待学习的举报"}
        )

    # 质量评估
    fusion_engine = get_fusion_engine()
    quality_results: List[tuple] = []
    qualified_reports = []

    for report in reports:
        quality = fusion_engine.quality_evaluator.evaluate(report)
        quality_results.append((report, quality))

        if quality.quality_score >= quality_threshold:
            qualified_reports.append(report)

    # 融合处理
    fusion_result = fusion_engine.fuse(qualified_reports)

    # 调用进化服务学习
    learned_count = 0
    new_keywords: List[str] = []
    new_patterns: List[str] = []

    if fusion_result.fused_cases:
        # 转换为学习案例格式
        learn_cases = fusion_result.fused_cases

        try:
            result = await evo_service.learn_from_reports(learn_cases)
            if result:
                learned_count = result.get("learned_count", 0)
                new_keywords = result.get("new_keywords", [])
                new_patterns = result.get("new_patterns", [])
        except Exception as e:
            # 降级处理：逐个学习
            for case in fusion_result.fused_cases:
                try:
                    case_dict = {
                        "case_id": case.get("case_id"),
                        "content": case.get("content"),
                        "label": "scam",
                        "scam_type": case.get("scam_type"),
                        "risk_level": case.get("risk_level"),
                        "keywords": case.get("keywords", []),
                        "source": "user_report"
                    }
                    await evo_service.learner.learn_from_cases([case_dict])
                    learned_count += 1
                    new_keywords.extend(case.get("keywords", []))
                    new_patterns.extend(case.get("patterns", []))
                except Exception:
                    pass

    # 标记为已学习
    if qualified_reports:
        report_ids = [r.get("report_id") for r in qualified_reports if r.get("report_id")]
        if report_ids:
            await rep_service.mark_as_learned(report_ids)

    # 统计质量分布
    quality_distribution = defaultdict(int)
    for _, quality in quality_results:
        quality_distribution[quality.quality_level.value] += 1

    return IntegrationReport(
        status="success",
        total_reports=len(reports),
        qualified_reports=len(qualified_reports),
        learned_reports=learned_count,
        failed_reports=len(reports) - len(qualified_reports),
        new_keywords_count=len(set(new_keywords)),
        new_patterns_count=len(set(new_patterns)),
        quality_distribution=dict(quality_distribution),
        details={
            "fusion_result": {
                "duplicates_removed": fusion_result.duplicates_removed,
                "keyword_clusters": fusion_result.keyword_clusters,
                "pattern_clusters": fusion_result.pattern_clusters,
            },
            "new_keywords": list(set(new_keywords))[:20],
            "new_patterns": list(set(new_patterns))[:20],
        }
    )


def get_evolution_keywords() -> List[Dict[str, Any]]:
    """
    获取进化后的关键词库
    供识别模块使用
    """
    try:
        from src.services.evolution_service import get_evolution_service
    except ImportError:
        from services.evolution_service import get_evolution_service

    evo_service = get_evolution_service()
    learned = evo_service.get_learned_knowledge()

    result = []
    for scam_type, knowledge in learned.items():
        keywords = knowledge.get("keywords", []) if isinstance(knowledge, dict) else []
        result.append({
            "scam_type": scam_type,
            "keywords": keywords,
            "count": len(keywords)
        })

    return result


def get_evolution_patterns() -> List[Dict[str, Any]]:
    """
    获取进化后的模式库
    供识别模块使用
    """
    try:
        from src.services.evolution_service import get_evolution_service
    except ImportError:
        from services.evolution_service import get_evolution_service

    evo_service = get_evolution_service()
    learned = evo_service.get_learned_knowledge()

    result = []
    for scam_type, knowledge in learned.items():
        patterns = knowledge.get("patterns", []) if isinstance(knowledge, dict) else []
        result.append({
            "scam_type": scam_type,
            "patterns": patterns,
            "count": len(patterns)
        })

    return result


def batch_evaluate_reports(reports: List[Dict]) -> List[CaseQualityFilter]:
    """
    批量评估举报质量

    Args:
        reports: 举报列表

    Returns:
        质量评估结果列表
    """
    evaluator = ReportQualityEvaluator()
    return [evaluator.evaluate(report) for report in reports]
