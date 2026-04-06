"""
多模态融合判别模块
融合文本、语音、图像等多源信息进行综合风险判断
"""

import json
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
import numpy as np


@dataclass
class ModalityFeature:
    """单模态特征"""
    modality: str  # text, audio, image
    features: Dict[str, Any]
    risk_score: float
    confidence: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FusionResult:
    """融合结果"""
    fused_score: float
    final_risk_level: int
    dominant_modality: str
    modality_contributions: Dict[str, float]
    analysis: str
    confidence: float
    warnings: List[str]


class MultimodalFusion:
    """
    多模态融合判别器
    
    整合来自不同模态的风险评估结果，
    通过加权融合和交叉验证，得出最终的风险判断。
    """
    
    # 模态权重配置
    MODALITY_WEIGHTS = {
        "text": 0.5,
        "audio": 0.25,
        "image": 0.25
    }
    
    # 置信度阈值
    CONFIDENCE_THRESHOLDS = {
        "high": 0.8,
        "medium": 0.5,
        "low": 0.3
    }
    
    # 风险等级阈值
    RISK_LEVEL_THRESHOLDS = {
        0: (0.0, "safe"),
        1: (0.3, "attention"),
        2: (0.5, "warning"),
        3: (0.7, "danger"),
        4: (0.9, "emergency")
    }
    
    def __init__(self, config: Optional[Dict] = None):
        """
        初始化多模态融合器
        
        Args:
            config: 配置参数
        """
        self.config = config or self._default_config()
        self.modality_weights = self.config.get(
            "modality_weights", self.MODALITY_WEIGHTS
        )
    
    def _default_config(self) -> Dict:
        """默认配置"""
        return {
            "modality_weights": {
                "text": 0.5,
                "audio": 0.25,
                "image": 0.25
            },
            "enable_cross_validation": True,
            "cross_validation_threshold": 0.3,
            "enable_temporal_fusion": True,
            "temporal_window": 5,
            "fusion_method": "weighted_average"  # weighted_average, attention, voting
        }
    
    def fuse(self, text_feature: Optional[ModalityFeature] = None,
            audio_feature: Optional[ModalityFeature] = None,
            image_feature: Optional[ModalityFeature] = None,
            temporal_context: Optional[List[ModalityFeature]] = None) -> FusionResult:
        """
        多模态特征融合
        
        Args:
            text_feature: 文本模态特征
            audio_feature: 音频模态特征
            image_feature: 图像模态特征
            temporal_context: 时序上下文特征
            
        Returns:
            FusionResult: 融合结果
        """
        # 收集可用的模态
        available_features = []
        if text_feature:
            available_features.append(("text", text_feature))
        if audio_feature:
            available_features.append(("audio", audio_feature))
        if image_feature:
            available_features.append(("image", image_feature))
        
        if not available_features:
            return self._create_default_result()
        
        # 计算归一化权重
        weights = self._normalize_weights()
        
        # 加权融合
        fused_score = self._weighted_fusion(available_features, weights)
        
        # 交叉验证
        cross_validation_result = self._cross_validate(available_features)
        
        # 如果交叉验证发现问题，调整分数
        if cross_validation_result["conflict_detected"]:
            fused_score = self._adjust_for_conflict(
                fused_score, cross_validation_result
            )
        
        # 时序融合
        if temporal_context and self.config.get("enable_temporal_fusion"):
            fused_score = self._temporal_fusion(fused_score, temporal_context)
        
        # 转换为风险等级
        risk_level = self._score_to_level(fused_score)
        
        # 确定主导模态
        dominant_modality = self._determine_dominant_modality(
            available_features, fused_score
        )
        
        # 计算模态贡献度
        contributions = self._calculate_contributions(
            available_features, fused_score
        )
        
        # 生成分析
        analysis = self._generate_analysis(
            available_features, fused_score, dominant_modality
        )
        
        # 生成警告
        warnings = self._generate_warnings(
            available_features, fused_score, cross_validation_result
        )
        
        # 计算总体置信度
        confidence = self._calculate_confidence(
            available_features, cross_validation_result
        )
        
        return FusionResult(
            fused_score=fused_score,
            final_risk_level=risk_level,
            dominant_modality=dominant_modality,
            modality_contributions=contributions,
            analysis=analysis,
            confidence=confidence,
            warnings=warnings
        )
    
    def _normalize_weights(self) -> Dict[str, float]:
        """归一化权重"""
        available_modalities = [
            m for m in ["text", "audio", "image"]
            if hasattr(self, f"{m}_feature") or True  # 简化处理
        ]
        
        total = sum(
            self.modality_weights.get(m, 0)
            for m in available_modalities
        )
        
        if total == 0:
            return {m: 1.0/len(available_modalities) for m in available_modalities}
        
        return {
            m: self.modality_weights.get(m, 0) / total
            for m in available_modalities
        }
    
    def _weighted_fusion(self, features: List[Tuple[str, ModalityFeature]],
                        weights: Dict[str, float]) -> float:
        """加权融合"""
        fusion_method = self.config.get("fusion_method", "weighted_average")
        
        if fusion_method == "weighted_average":
            return self._weighted_average_fusion(features, weights)
        elif fusion_method == "attention":
            return self._attention_fusion(features, weights)
        elif fusion_method == "voting":
            return self._voting_fusion(features)
        else:
            return self._weighted_average_fusion(features, weights)
    
    def _weighted_average_fusion(self, features: List[Tuple[str, ModalityFeature]],
                                  weights: Dict[str, float]) -> float:
        """加权平均融合"""
        weighted_sum = 0.0
        weight_total = 0.0
        
        for modality, feature in features:
            w = weights.get(modality, 1/len(features))
            # 使用置信度作为二次权重
            confidence_weight = feature.confidence
            weighted_sum += feature.risk_score * w * confidence_weight
            weight_total += w * confidence_weight
        
        if weight_total == 0:
            return 0.5
        
        return weighted_sum / weight_total
    
    def _attention_fusion(self, features: List[Tuple[str, ModalityFeature]],
                         weights: Dict[str, float]) -> float:
        """注意力融合"""
        # 简化的注意力机制
        scores = []
        for modality, feature in features:
            w = weights.get(modality, 1/len(features))
            c = feature.confidence
            score = feature.risk_score * w * (1 + c)  # 注意力加权
            scores.append(score)
        
        return sum(scores) / len(scores) if scores else 0.5
    
    def _voting_fusion(self, features: List[Tuple[str, ModalityFeature]]) -> float:
        """投票融合"""
        level_scores = {}
        
        for modality, feature in features:
            level = self._score_to_level(feature.risk_score)
            level_scores[level] = level_scores.get(level, 0) + 1
        
        # 取最高票数的等级
        if level_scores:
            dominant_level = max(level_scores.items(), key=lambda x: x[1])[0]
            return (dominant_level + 0.5) / 5.0  # 转换为0-1分数
        
        return 0.5
    
    def _cross_validate(self, features: List[Tuple[str, ModalityFeature]]) -> Dict:
        """交叉验证"""
        if len(features) < 2:
            return {"conflict_detected": False, "conflict_score": 0}
        
        # 计算各模态分数差异
        scores = [f.risk_score for _, f in features]
        max_diff = max(scores) - min(scores)
        
        conflict_threshold = self.config.get("cross_validation_threshold", 0.3)
        conflict_detected = max_diff > conflict_threshold
        
        return {
            "conflict_detected": conflict_detected,
            "conflict_score": max_diff,
            "score_range": (min(scores), max(scores)),
            "modalities_involved": [m for m, _ in features]
        }
    
    def _adjust_for_conflict(self, fused_score: float,
                           cross_validation: Dict) -> float:
        """冲突调整"""
        # 如果检测到冲突，采用保守策略（取较高值）
        conflict_score = cross_validation.get("conflict_score", 0)
        
        # 冲突越严重，越倾向于保守（取高值）
        adjustment = conflict_score * 0.3
        
        # 如果融合分数已经较高，不做调整
        if fused_score > 0.6:
            return fused_score
        
        # 否则适当提高分数
        return min(fused_score + adjustment, 1.0)
    
    def _temporal_fusion(self, current_score: float,
                        temporal_context: List[ModalityFeature]) -> float:
        """时序融合"""
        if not temporal_context:
            return current_score
        
        # 计算历史分数的移动平均
        historical_scores = [f.risk_score for f in temporal_context]
        
        # 考虑趋势
        if len(historical_scores) >= 2:
            trend = historical_scores[-1] - historical_scores[-2]
            
            # 如果趋势上升，增加当前分数权重
            if trend > 0.1:
                current_score = current_score * 0.7 + np.mean(historical_scores) * 0.3
            # 如果趋势下降，可以适当降低
            elif trend < -0.1:
                current_score = current_score * 0.9 + np.mean(historical_scores) * 0.1
        
        return current_score
    
    def _score_to_level(self, score: float) -> int:
        """分数转等级"""
        for level in range(4, -1, -1):
            threshold, _ = self.RISK_LEVEL_THRESHOLDS[level]
            if score >= threshold:
                return level
        return 0
    
    def _determine_dominant_modality(self,
                                    features: List[Tuple[str, ModalityFeature]],
                                    fused_score: float) -> str:
        """确定主导模态"""
        if not features:
            return "unknown"
        
        # 找到与融合分数最接近的模态
        best_match = None
        best_diff = float('inf')
        
        for modality, feature in features:
            diff = abs(feature.risk_score - fused_score)
            if diff < best_diff:
                best_diff = diff
                best_match = modality
        
        return best_match or "unknown"
    
    def _calculate_contributions(self,
                                features: List[Tuple[str, ModalityFeature]],
                                fused_score: float) -> Dict[str, float]:
        """计算各模态贡献度"""
        contributions = {}
        
        for modality, feature in features:
            if fused_score > 0:
                # 贡献度 = 模态分数 * 权重 / 融合分数
                contribution = (feature.risk_score * 
                             self.modality_weights.get(modality, 0.33)) / fused_score
                contributions[modality] = min(contribution, 1.0)
            else:
                contributions[modality] = 0.0
        
        return contributions
    
    def _generate_analysis(self,
                          features: List[Tuple[str, ModalityFeature]],
                          fused_score: float,
                          dominant_modality: str) -> str:
        """生成分析文本"""
        modality_names = {
            "text": "文本",
            "audio": "音频",
            "image": "图像"
        }
        
        parts = []
        
        # 各模态分数
        for modality, feature in features:
            name = modality_names.get(modality, modality)
            level_name = self._get_level_name(self._score_to_level(feature.risk_score))
            parts.append(f"{name}检测: {level_name}({feature.risk_score:.2f})")
        
        # 主导模态
        if dominant_modality != "unknown":
            name = modality_names.get(dominant_modality, dominant_modality)
            parts.append(f"主要依据: {name}模态")
        
        return " | ".join(parts)
    
    def _generate_warnings(self,
                          features: List[Tuple[str, ModalityFeature]],
                          fused_score: float,
                          cross_validation: Dict) -> List[str]:
        """生成警告"""
        warnings = []
        
        # 高风险警告
        if fused_score > 0.7:
            warnings.append("多模态综合分析显示高风险")
        
        # 模态冲突警告
        if cross_validation.get("conflict_detected"):
            warnings.append("不同模态分析结果存在差异，建议人工复核")
        
        # 置信度警告
        low_confidence = [
            m for m, f in features if f.confidence < self.CONFIDENCE_THRESHOLDS["medium"]
        ]
        if low_confidence:
            modality_names = {"text": "文本", "audio": "音频", "image": "图像"}
            mods = [modality_names.get(m, m) for m in low_confidence]
            warnings.append(f"{'、'.join(mods)}模态置信度较低，分析结果仅供参考")
        
        return warnings
    
    def _calculate_confidence(self,
                             features: List[Tuple[str, ModalityFeature]],
                             cross_validation: Dict) -> float:
        """计算总体置信度"""
        if not features:
            return 0.5
        
        # 基于模态数量
        modality_bonus = len(features) * 0.1
        
        # 基于各模态置信度
        avg_confidence = sum(f.confidence for _, f in features) / len(features)
        
        # 基于一致性惩罚
        consistency_penalty = 0
        if cross_validation.get("conflict_detected"):
            consistency_penalty = cross_validation.get("conflict_score", 0) * 0.2
        
        confidence = avg_confidence * 0.8 + min(modality_bonus, 0.2) - consistency_penalty
        
        return max(0.0, min(1.0, confidence))
    
    def _get_level_name(self, level: int) -> str:
        """获取等级名称"""
        names = {
            0: "安全",
            1: "关注",
            2: "警告",
            3: "危险",
            4: "紧急"
        }
        return names.get(level, "未知")
    
    def _create_default_result(self) -> FusionResult:
        """创建默认结果"""
        return FusionResult(
            fused_score=0.5,
            final_risk_level=1,
            dominant_modality="unknown",
            modality_contributions={},
            analysis="缺少足够的多模态信息进行综合判断",
            confidence=0.3,
            warnings=["数据不完整，建议补充更多信息"]
        )
    
    def update_weights(self, modality: str, weight: float):
        """更新模态权重"""
        self.modality_weights[modality] = max(0.0, min(1.0, weight))
    
    def get_config(self) -> Dict:
        """获取当前配置"""
        return {
            "modality_weights": self.modality_weights,
            "confidence_thresholds": self.CONFIDENCE_THRESHOLDS,
            "risk_level_thresholds": self.RISK_LEVEL_THRESHOLDS,
            **self.config
        }
