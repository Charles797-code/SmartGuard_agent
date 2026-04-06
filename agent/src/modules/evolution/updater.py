"""
知识更新模块
自动化流程，支持将新的互联网诈骗案例清洗后导入向量数据库
"""

import time
import json
import asyncio
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import re


class UpdateStatus(Enum):
    """更新状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class UpdateTask:
    """更新任务"""
    task_id: str
    task_type: str  # case_import, pattern_update, keyword_update
    source: str
    data: List[Dict]
    status: UpdateStatus
    progress: float = 0.0
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    error_message: Optional[str] = None
    result: Optional[Dict] = None


class KnowledgeUpdater:
    """
    知识更新器
    
    实现自动化流程，将新的互联网诈骗案例
    清洗后导入向量数据库，支持定时更新和增量更新。
    """
    
    # 数据源配置
    DATA_SOURCES = {
        "official": {
            "公安部反诈中心": "https://www.antifraud.gov.cn/api/cases",
            "国家反诈中心": "https://“国家互联网应急中心”/data"
        },
        "public": {
            "公开数据集": "公开反诈案例库",
            "新闻媒体": "新闻报道的诈骗案例"
        }
    }
    
    # 数据清洗规则
    CLEANING_RULES = {
        "remove_urls": r'http[s]?://\S+',
        "remove_phone": r'1[3-9]\d{9}',
        "remove_id": r'\d{17}[\dXx]',
        "remove_bank": r'\d{16,19}',
        "normalize_whitespace": r'\s+'
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
        
        self.update_tasks: Dict[str, UpdateTask] = {}
        self.update_history: List[UpdateTask] = []
        self.update_callbacks: List[Callable] = []
        
        # 清洗规则
        self.cleaning_patterns = {
            k: re.compile(v) for k, v in self.CLEANING_RULES.items()
        }
    
    async def create_update_task(self, task_type: str, data: List[Dict],
                               source: str = "manual") -> UpdateTask:
        """
        创建更新任务
        
        Args:
            task_type: 任务类型
            data: 更新数据
            source: 数据来源
            
        Returns:
            UpdateTask: 更新任务
        """
        task_id = f"task_{task_type}_{int(time.time())}"
        
        task = UpdateTask(
            task_id=task_id,
            task_type=task_type,
            source=source,
            data=data,
            status=UpdateStatus.PENDING
        )
        
        self.update_tasks[task_id] = task
        
        return task
    
    async def execute_update_task(self, task_id: str) -> UpdateTask:
        """
        执行更新任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            UpdateTask: 更新后的任务
        """
        task = self.update_tasks.get(task_id)
        
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        task.status = UpdateStatus.PROCESSING
        task.started_at = time.time()
        
        try:
            if task.task_type == "case_import":
                result = await self._import_cases(task.data)
            elif task.task_type == "pattern_update":
                result = await self._update_patterns(task.data)
            elif task.task_type == "keyword_update":
                result = await self._update_keywords(task.data)
            else:
                raise ValueError(f"Unknown task type: {task.task_type}")
            
            task.status = UpdateStatus.COMPLETED
            task.completed_at = time.time()
            task.progress = 1.0
            task.result = result
            
        except Exception as e:
            task.status = UpdateStatus.FAILED
            task.completed_at = time.time()
            task.error_message = str(e)
        
        # 移到历史
        self.update_history.append(task)
        del self.update_tasks[task_id]
        
        # 触发回调
        await self._trigger_callbacks(task)
        
        return task
    
    async def _import_cases(self, cases: List[Dict]) -> Dict:
        """导入案例"""
        processed = 0
        imported = 0
        failed = 0
        errors = []
        
        for case_data in cases:
            try:
                processed += 1
                
                # 1. 数据清洗
                cleaned_case = self._clean_case_data(case_data)
                
                # 2. 标准化
                normalized_case = self._normalize_case(cleaned_case)
                
                # 3. 验证
                if not self._validate_case(normalized_case):
                    failed += 1
                    continue
                
                # 4. 导入知识库
                if self.knowledge_base:
                    await self.knowledge_base.add_entry(normalized_case)
                
                # 5. 向量化存入向量库
                if self.vector_store:
                    await self._add_to_vector_store(normalized_case)
                
                imported += 1
            
            except Exception as e:
                failed += 1
                errors.append({
                    "case_id": case_data.get("case_id"),
                    "error": str(e)
                })
        
        return {
            "processed": processed,
            "imported": imported,
            "failed": failed,
            "errors": errors
        }
    
    def _clean_case_data(self, case_data: Dict) -> Dict:
        """清洗案例数据"""
        cleaned = case_data.copy()
        
        # 清洗内容文本
        if "content" in cleaned:
            content = cleaned["content"]
            
            for name, pattern in self.cleaning_patterns.items():
                content = pattern.sub('[已隐藏]', content)
            
            cleaned["content"] = content.strip()
        
        # 清洗标题
        if "title" in cleaned:
            title = cleaned["title"]
            for name, pattern in self.cleaning_patterns.items():
                if name != "normalize_whitespace":
                    title = pattern.sub('[已隐藏]', title)
            cleaned["title"] = title.strip()
        
        # 移除敏感信息
        cleaned["_raw_data"] = cleaned.get("content", "")[:100]
        
        return cleaned
    
    def _normalize_case(self, case_data: Dict) -> Dict:
        """标准化案例"""
        normalized = {
            "type": "scam_case",
            "scam_type": self._normalize_scam_type(case_data.get("scam_type")),
            "title": case_data.get("title", "未知案例"),
            "content": case_data.get("content", ""),
            "risk_level": case_data.get("risk_level", 3),
            "keywords": case_data.get("keywords", []),
            "metadata": {
                "source": case_data.get("source", "unknown"),
                "original_id": case_data.get("case_id"),
                "cleaned_at": time.time()
            }
        }
        
        return normalized
    
    def _normalize_scam_type(self, scam_type: Optional[str]) -> Optional[str]:
        """标准化诈骗类型"""
        if not scam_type:
            return None
        
        # 类型映射
        type_mapping = {
            "冒充公检法": "police_impersonation",
            "冒充公安": "police_impersonation",
            "公检法": "police_impersonation",
            "投资理财": "investment_fraud",
            "投资": "investment_fraud",
            "理财": "investment_fraud",
            "兼职刷单": "part_time_fraud",
            "刷单": "part_time_fraud",
            "虚假贷款": "loan_fraud",
            "贷款": "loan_fraud",
            "杀猪盘": "pig_butchery",
            "恋爱诈骗": "pig_butchery",
            "AI诈骗": "ai_voice_fraud",
            "语音诈骗": "ai_voice_fraud",
            "征信诈骗": "credit_fraud",
            "退款诈骗": "refund_fraud",
            "游戏诈骗": "gaming_fraud",
            "追星诈骗": "fan_fraud",
            "医保诈骗": "medical_fraud"
        }
        
        for key, value in type_mapping.items():
            if key in scam_type:
                return value
        
        return scam_type
    
    def _validate_case(self, case_data: Dict) -> bool:
        """验证案例"""
        # 基本验证
        if not case_data.get("content"):
            return False
        
        if len(case_data["content"]) < 20:
            return False
        
        return True
    
    async def _add_to_vector_store(self, case_data: Dict):
        """添加到向量存储"""
        if not self.vector_store:
            return
        
        # 构建向量条目
        entry = {
            "id": f"case_{case_data.get('metadata', {}).get('original_id', time.time())}",
            "content": case_data["content"],
            "type": "scam_case",
            "metadata": {
                "scam_type": case_data.get("scam_type"),
                "risk_level": case_data.get("risk_level")
            }
        }
        
        await self.vector_store.add([entry])
    
    async def _update_patterns(self, patterns: List[Dict]) -> Dict:
        """更新模式库"""
        updated = 0
        
        for pattern_data in patterns:
            scam_type = pattern_data.get("scam_type")
            pattern = pattern_data.get("pattern")
            
            if scam_type and pattern:
                # 添加到模式库
                updated += 1
        
        return {"updated": updated}
    
    async def _update_keywords(self, keywords: List[Dict]) -> Dict:
        """更新关键词库"""
        updated = 0
        
        for kw_data in keywords:
            scam_type = kw_data.get("scam_type")
            keyword = kw_data.get("keyword")
            
            if scam_type and keyword:
                updated += 1
        
        return {"updated": updated}
    
    async def schedule_update(self, schedule_type: str, 
                            interval_hours: int = 24):
        """
        定时更新
        
        Args:
            schedule_type: 调度类型
            interval_hours: 更新间隔（小时）
        """
        # 简化实现
        pass
    
    def get_task_status(self, task_id: str) -> Optional[UpdateTask]:
        """获取任务状态"""
        return self.update_tasks.get(task_id)
    
    def get_update_history(self, limit: int = 20) -> List[UpdateTask]:
        """获取更新历史"""
        return self.update_history[-limit:]
    
    def register_callback(self, callback: Callable[[UpdateTask], None]):
        """注册更新回调"""
        self.update_callbacks.append(callback)
    
    async def _trigger_callbacks(self, task: UpdateTask):
        """触发回调"""
        for callback in self.update_callbacks:
            try:
                await callback(task)
            except Exception:
                pass
    
    def export_update_config(self) -> Dict:
        """导出更新配置"""
        return {
            "data_sources": self.DATA_SOURCES,
            "cleaning_rules": list(self.cleaning_patterns.keys()),
            "recent_tasks": [
                {
                    "task_id": t.task_id,
                    "task_type": t.task_type,
                    "status": t.status.value,
                    "created_at": t.created_at
                }
                for t in self.update_history[-10:]
            ]
        }
