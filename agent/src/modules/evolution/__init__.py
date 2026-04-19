"""
自适应进化模块
支持智能体知识的实时扩充和自适应学习
"""

from .learner import (
    KnowledgeLearner,
    LearningCase,
    LearningResult,
    LearnedKeyword,
    ExtractedPattern,
    QualityAssessment,
    ChineseTextProcessor,
    PatternExtractor,
    KeywordWeightCalculator,
    QualityEvaluator,
    SCAM_TYPE_DEFINITIONS,
)
from .updater import (
    KnowledgeUpdater, KnowledgeUpdaterV2, UpdateTask, UpdateStatus,
    UpdateFrequency, DataSource, DataChange,
    ValidationResult, DataSourceRegistry, DataFetcher,
    CaseParser, CaseValidator, ScheduledUpdater,
)
from .report_integration import (
    integrate_reports_to_evolution,
    get_evolution_keywords,
    get_evolution_patterns,
    ReportFusionEngine,
    CaseQualityFilter,
)

__all__ = [
    # learner
    "KnowledgeLearner",
    "LearningCase",
    "LearningResult",
    "LearnedKeyword",
    "ExtractedPattern",
    "QualityAssessment",
    "ChineseTextProcessor",
    "PatternExtractor",
    "KeywordWeightCalculator",
    "QualityEvaluator",
    "SCAM_TYPE_DEFINITIONS",
    # updater
    "KnowledgeUpdater",
    "KnowledgeUpdaterV2",
    "UpdateTask",
    "UpdateStatus",
    "UpdateFrequency",
    "DataSource",
    "DataChange",
    "ValidationResult",
    "DataSourceRegistry",
    "DataFetcher",
    "CaseParser",
    "CaseValidator",
    "ScheduledUpdater",
    # report_integration
    "integrate_reports_to_evolution",
    "get_evolution_keywords",
    "get_evolution_patterns",
    "ReportFusionEngine",
    "CaseQualityFilter",
]
