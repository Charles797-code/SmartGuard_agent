"""
智能学习进化服务
将进化模块集成到主流程，实现持续学习
"""

import time
import json
import asyncio
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from src.data.database import get_database


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
    created_at: float = 0


class EvolutionService:
    """
    智能学习进化服务
    
    功能：
    1. 记录每次风险检测案例
    2. 自动提取新诈骗手法
    3. 更新关键词库和模式库
    4. 定期自我进化优化
    5. 持久化到数据库
    """
    
    def __init__(self, learner=None, updater=None):
        from src.modules.evolution import KnowledgeLearner, KnowledgeUpdater
        
        self.learner = learner or KnowledgeLearner()
        self.updater = updater or KnowledgeUpdater()
        self.db = get_database()
        
        # 学习记录（内存缓存）
        self.learning_records: List[LearningRecord] = []
        self.learned_patterns: Dict[str, List[str]] = {}
        self.learned_keywords: Dict[str, List[str]] = {}
        
        # 进化统计
        self.evolution_stats = {
            "total_records": 0,
            "learned_cases": 0,
            "new_keywords_added": 0,
            "new_patterns_added": 0,
            "last_evolution": None,
            "accuracy_improvement": 0.0
        }
        
        # 自动进化配置
        self.auto_evolution_enabled = True
        self.evolution_threshold = 10
        self._evolution_task = None
        
        # 启动时从数据库加载数据
        asyncio.create_task(self._load_from_db())
    
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
                    created_at=r.get("created_at", 0)
                )
                self.learning_records.append(record)
            
            # 加载学习到的关键词和模式
            knowledge = await self.db.query("evolution_knowledge")
            for k in knowledge:
                k_type = k.get("knowledge_type", "")
                scam_type = k.get("scam_type", "")
                content = k.get("content", "")
                
                if k_type == "keyword":
                    if scam_type not in self.learned_keywords:
                        self.learned_keywords[scam_type] = []
                    if content not in self.learned_keywords[scam_type]:
                        self.learned_keywords[scam_type].append(content)
                elif k_type == "pattern":
                    if scam_type not in self.learned_patterns:
                        self.learned_patterns[scam_type] = []
                    if content not in self.learned_patterns[scam_type]:
                        self.learned_patterns[scam_type].append(content)
            
            print(f"[Evolution] 从数据库加载了 {len(self.learning_records)} 条学习记录")
        except Exception as e:
            print(f"[Evolution] 加载数据库失败: {e}")
    
    async def _save_record_to_db(self, record: LearningRecord):
        """保存学习记录到数据库"""
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
                "created_at": record.created_at
            })
        except Exception as e:
            print(f"[Evolution] 保存记录失败: {e}")
    
    async def _update_record_in_db(self, record_id: str, learned: bool):
        """更新数据库中的记录"""
        try:
            await self.db.update("evolution_records", record_id, {
                "id": record_id,
                "record_id": record_id,
                "learned": 1 if learned else 0
            })
        except Exception as e:
            print(f"[Evolution] 更新记录失败: {e}")
    
    async def _save_knowledge_to_db(self, scam_type: str, knowledge_type: str, content: str):
        """保存知识到数据库"""
        try:
            import uuid
            knowledge_id = f"ek_{uuid.uuid4().hex[:12]}"
            now = time.time()
            
            await self.db.insert("evolution_knowledge", {
                "id": knowledge_id,
                "scam_type": scam_type,
                "knowledge_type": knowledge_type,
                "content": content,
                "created_at": now,
                "updated_at": now
            })
        except Exception as e:
            print(f"[Evolution] 保存知识失败: {e}")
    
    async def record_case(self, user_id: str, content: str, 
                         risk_level: int, risk_type: str,
                         analysis: str, response: str) -> LearningRecord:
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
        
        record = LearningRecord(
            record_id=f"record_{user_id}_{int(time.time())}",
            user_id=user_id,
            content=content,
            risk_level=risk_level,
            risk_type=risk_type,
            analysis=analysis,
            response=response,
            created_at=time.time()
        )
        
        self.learning_records.append(record)
        self.evolution_stats["total_records"] += 1
        
        # 保存到数据库
        await self._save_record_to_db(record)
        
        if len(self.learning_records) >= self.evolution_threshold:
            await self.auto_evolve()
        
        return record
    
    async def auto_evolve(self) -> Dict[str, Any]:
        """
        自动进化
        当积累足够案例时，自动分析学习
        """
        if not self.learning_records:
            return {"status": "no_records"}
        
        unlearned_cases = [
            r for r in self.learning_records 
            if not r.learned and r.risk_level >= 3
        ]
        
        if len(unlearned_cases) < 3:
            return {"status": "insufficient_cases"}
        
        print(f"[Evolution] 开始自动进化，处理 {len(unlearned_cases)} 个案例...", flush=True)
        
        cases = [
            {
                "case_id": r.record_id,
                "content": r.content,
                "label": "scam" if r.risk_level >= 3 else "normal",
                "scam_type": r.risk_type,
                "risk_level": r.risk_level,
                "source": f"user_{r.user_id}"
            }
            for r in unlearned_cases
        ]
        
        result = await self.learner.learn_from_cases(cases)
        
        for r in unlearned_cases:
            r.learned = True
            await self._update_record_in_db(r.record_id, True)
        
        self.evolution_stats["learned_cases"] += result.cases_learned
        self.evolution_stats["new_keywords_added"] += len(result.new_keywords)
        self.evolution_stats["new_patterns_added"] += len(result.new_patterns)
        self.evolution_stats["last_evolution"] = time.time()
        self.evolution_stats["accuracy_improvement"] = result.accuracy_improvement
        
        for kw in result.new_keywords:
            scam_type = self._guess_scam_type(kw)
            if scam_type not in self.learned_keywords:
                self.learned_keywords[scam_type] = []
            if kw not in self.learned_keywords[scam_type]:
                self.learned_keywords[scam_type].append(kw)
                await self._save_knowledge_to_db(scam_type, "keyword", kw)
        
        for pattern in result.new_patterns:
            scam_type = self._guess_scam_type(pattern)
            if scam_type not in self.learned_patterns:
                self.learned_patterns[scam_type] = []
            if pattern not in self.learned_patterns[scam_type]:
                self.learned_patterns[scam_type].append(pattern)
                await self._save_knowledge_to_db(scam_type, "pattern", pattern)
        
        self.learning_records = self.learning_records[-50:]
        
        print(f"[Evolution] 自动进化完成！新增 {len(result.new_keywords)} 个关键词，{len(result.new_patterns)} 个模式", flush=True)
        
        return {
            "status": "success",
            "cases_processed": result.cases_processed,
            "cases_learned": result.cases_learned,
            "new_keywords": result.new_keywords,
            "new_patterns": result.new_patterns,
            "accuracy_improvement": result.accuracy_improvement
        }
    
    def _guess_scam_type(self, keyword: str) -> str:
        """根据关键词猜测诈骗类型"""
        mappings = {
            "转账": "financial_fraud",
            "汇款": "financial_fraud",
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
            "医保": "medical_fraud"
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
        enhanced_result = {
            "base_risk_level": risk_level,
            "enhanced_risk_level": risk_level,
            "learned_keywords_found": [],
            "learned_patterns_found": [],
            "confidence_boost": 0.0
        }
        
        content_lower = content.lower()
        
        for scam_type, keywords in self.learned_keywords.items():
            for kw in keywords:
                if kw.lower() in content_lower:
                    enhanced_result["learned_keywords_found"].append(kw)
                    enhanced_result["confidence_boost"] += 0.2
        
        for scam_type, patterns in self.learned_patterns.items():
            for pattern in patterns:
                if pattern.lower() in content_lower:
                    enhanced_result["learned_patterns_found"].append(pattern)
                    enhanced_result["confidence_boost"] += 0.3
        
        if enhanced_result["confidence_boost"] > 0:
            new_level = min(5, risk_level + int(enhanced_result["confidence_boost"]))
            enhanced_result["enhanced_risk_level"] = new_level
        
        return enhanced_result
    
    def get_learned_knowledge(self, scam_type: Optional[str] = None) -> Dict[str, List[str]]:
        """获取学习到的知识"""
        if scam_type:
            return {
                scam_type: {
                    "keywords": self.learned_keywords.get(scam_type, []),
                    "patterns": self.learned_patterns.get(scam_type, [])
                }
            }
        
        return {
            "keywords": self.learned_keywords,
            "patterns": self.learned_patterns
        }
    
    def get_evolution_stats(self) -> Dict[str, Any]:
        """获取进化统计"""
        return {
            **self.evolution_stats,
            "pending_cases": len([r for r in self.learning_records if not r.learned]),
            "knowledge_count": {
                "keywords": sum(len(v) for v in self.learned_keywords.values()),
                "patterns": sum(len(v) for v in self.learned_patterns.values())
            }
        }
    
    async def manual_learn(self, cases: List[Dict]) -> Dict[str, Any]:
        """手动学习指定案例"""
        result = await self.learner.learn_from_cases(cases)
        
        self.evolution_stats["learned_cases"] += result.cases_learned
        self.evolution_stats["new_keywords_added"] += len(result.new_keywords)
        self.evolution_stats["new_patterns_added"] += len(result.new_patterns)
        self.evolution_stats["last_evolution"] = time.time()
        
        return {
            "cases_processed": result.cases_processed,
            "cases_learned": result.cases_learned,
            "new_keywords": result.new_keywords,
            "new_patterns": result.new_patterns,
            "accuracy_improvement": result.accuracy_improvement
        }
    
    async def export_knowledge(self) -> Dict[str, Any]:
        """导出知识库"""
        return {
            "learned_keywords": self.learned_keywords,
            "learned_patterns": self.learned_patterns,
            "keyword_library": self.learner.get_keyword_library(),
            "pattern_library": self.learner.get_pattern_library(),
            "exported_at": time.time()
        }
    
    async def import_knowledge(self, knowledge: Dict[str, Any]):
        """导入知识库"""
        if "learned_keywords" in knowledge:
            self.learned_keywords = knowledge["learned_keywords"]
            for scam_type, keywords in knowledge["learned_keywords"].items():
                for kw in keywords:
                    await self._save_knowledge_to_db(scam_type, "keyword", kw)
        
        if "learned_patterns" in knowledge:
            self.learned_patterns = knowledge["learned_patterns"]
            for scam_type, patterns in knowledge["learned_patterns"].items():
                for p in patterns:
                    await self._save_knowledge_to_db(scam_type, "pattern", p)
        
        if "keyword_library" in knowledge:
            for scam_type, keywords in knowledge["keyword_library"].items():
                if scam_type in self.learner.extended_keywords:
                    for kw in keywords:
                        if kw not in self.learner.extended_keywords[scam_type]:
                            self.learner.extended_keywords[scam_type].append(kw)


# 全局实例
_evolution_service: Optional[EvolutionService] = None


def get_evolution_service() -> EvolutionService:
    """获取进化服务实例"""
    global _evolution_service
    if _evolution_service is None:
        _evolution_service = EvolutionService()
    return _evolution_service
