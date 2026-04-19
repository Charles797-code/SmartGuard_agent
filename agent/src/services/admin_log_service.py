"""
管理员操作日志服务
记录所有管理员的操作行为
"""

import time
import secrets
import json
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
from src.data.database import get_database


@dataclass
class AdminOperationLog:
    """管理员操作日志"""
    id: str
    admin_id: str
    admin_username: str
    action: str  # 操作类型
    target_type: str  # 操作对象类型
    target_id: str  # 操作对象ID
    details: str  # 详细信息(JSON字符串)
    remark: str = ""  # 备注
    created_at: float = 0

    def __post_init__(self):
        if self.created_at == 0:
            self.created_at = time.time()


class AdminOperationLogService:
    """管理员操作日志服务"""
    
    # 操作类型常量
    ACTION_LOGIN = "login"  # 登录
    ACTION_LOGOUT = "logout"  # 登出
    ACTION_CREATE_USER = "create_user"  # 创建用户
    ACTION_UPDATE_USER = "update_user"  # 更新用户
    ACTION_DELETE_USER = "delete_user"  # 删除用户
    ACTION_DISABLE_USER = "disable_user"  # 禁用用户
    ACTION_ENABLE_USER = "enable_user"  # 启用用户
    ACTION_REVIEW_REPORT = "review_report"  # 审核举报
    ACTION_VERIFY_REPORT = "verify_report"  # 确认举报
    ACTION_REJECT_REPORT = "reject_report"  # 驳回举报
    ACTION_UPDATE_KNOWLEDGE = "update_knowledge"  # 更新知识库
    ACTION_EXPORT_DATA = "export_data"  # 导出数据
    ACTION_SYSTEM_CONFIG = "system_config"  # 系统配置
    
    def __init__(self):
        self.db = get_database()
    
    async def log(
        self,
        admin_id: str,
        admin_username: str,
        action: str,
        target_type: str = "",
        target_id: str = "",
        details: Optional[Dict[str, Any]] = None,
        remark: str = ""
    ) -> str:
        """
        记录操作日志
        
        Args:
            admin_id: 管理员ID
            admin_username: 管理员用户名
            action: 操作类型
            target_type: 操作对象类型
            target_id: 操作对象ID
            details: 详细信息
            remark: 备注
            
        Returns:
            日志ID
        """
        log_id = f"log_{secrets.token_hex(8)}"
        
        await self.db.insert("admin_operation_logs", {
            "id": log_id,
            "admin_id": admin_id,
            "admin_username": admin_username,
            "action": action,
            "target_type": target_type,
            "target_id": target_id,
            "details": json.dumps(details or {}, ensure_ascii=False),
            "remark": remark,
            "created_at": time.time()
        })
        
        return log_id
    
    async def get_logs(
        self,
        page: int = 1,
        page_size: int = 20,
        admin_id: Optional[str] = None,
        action: Optional[str] = None,
        target_type: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        keyword: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取操作日志列表
        
        Args:
            page: 页码
            page_size: 每页数量
            admin_id: 管理员ID过滤
            action: 操作类型过滤
            target_type: 对象类型过滤
            start_time: 开始时间
            end_time: 结束时间
            keyword: 关键词搜索
            
        Returns:
            日志列表和分页信息
        """
        all_logs = await self.db.query("admin_operation_logs", limit=10000)
        
        # 过滤
        if admin_id:
            all_logs = [l for l in all_logs if l.get("admin_id") == admin_id]
        if action:
            all_logs = [l for l in all_logs if l.get("action") == action]
        if target_type:
            all_logs = [l for l in all_logs if l.get("target_type") == target_type]
        if start_time:
            all_logs = [l for l in all_logs if l.get("created_at", 0) >= start_time]
        if end_time:
            all_logs = [l for l in all_logs if l.get("created_at", 0) <= end_time]
        if keyword:
            kw = keyword.lower()
            all_logs = [
                l for l in all_logs
                if kw in (l.get("admin_username") or "").lower()
                or kw in (l.get("details") or "").lower()
            ]
        
        # 按时间倒序
        all_logs.sort(key=lambda x: x.get("created_at", 0), reverse=True)
        
        total = len(all_logs)
        start = (page - 1) * page_size
        end = start + page_size
        paginated = all_logs[start:end]
        
        return {
            "logs": [self._format_log(l) for l in paginated],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if total > 0 else 1
        }
    
    async def get_log_by_id(self, log_id: str) -> Optional[Dict[str, Any]]:
        """获取指定日志详情"""
        logs = await self.db.query("admin_operation_logs", filters={"id": log_id}, limit=1)
        if logs:
            return self._format_log(logs[0])
        return None
    
    async def get_statistics(self, start_time: Optional[float] = None, end_time: Optional[float] = None) -> Dict[str, Any]:
        """获取操作统计"""
        all_logs = await self.db.query("admin_operation_logs", limit=100000)
        
        # 时间过滤
        if start_time:
            all_logs = [l for l in all_logs if l.get("created_at", 0) >= start_time]
        if end_time:
            all_logs = [l for l in all_logs if l.get("created_at", 0) <= end_time]
        
        # 按操作类型统计
        action_stats = {}
        for log in all_logs:
            action = log.get("action", "unknown")
            action_stats[action] = action_stats.get(action, 0) + 1
        
        # 按管理员统计
        admin_stats = {}
        for log in all_logs:
            admin = log.get("admin_username", "unknown")
            admin_stats[admin] = admin_stats.get(admin, 0) + 1
        
        return {
            "total_operations": len(all_logs),
            "action_stats": action_stats,
            "admin_stats": admin_stats,
            "time_range": {
                "start": start_time,
                "end": end_time
            }
        }
    
    def _format_log(self, log: Dict) -> Dict[str, Any]:
        """格式化日志输出"""
        try:
            details = json.loads(log.get("details", "{}"))
        except:
            details = log.get("details", "{}")
        
        return {
            "id": log.get("id"),
            "admin_id": log.get("admin_id"),
            "admin_username": log.get("admin_username"),
            "action": log.get("action"),
            "action_name": self._get_action_name(log.get("action", "")),
            "target_type": log.get("target_type"),
            "target_id": log.get("target_id"),
            "details": details,
            "remark": log.get("remark", ""),
            "created_at": log.get("created_at"),
            "created_at_str": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(log.get("created_at", 0)))
        }
    
    def _get_action_name(self, action: str) -> str:
        """获取操作类型的中文名称"""
        action_names = {
            self.ACTION_LOGIN: "登录系统",
            self.ACTION_LOGOUT: "退出登录",
            self.ACTION_CREATE_USER: "创建用户",
            self.ACTION_UPDATE_USER: "更新用户",
            self.ACTION_DELETE_USER: "删除用户",
            self.ACTION_DISABLE_USER: "禁用用户",
            self.ACTION_ENABLE_USER: "启用用户",
            self.ACTION_REVIEW_REPORT: "审核举报",
            self.ACTION_VERIFY_REPORT: "确认举报",
            self.ACTION_REJECT_REPORT: "驳回举报",
            self.ACTION_UPDATE_KNOWLEDGE: "更新知识库",
            self.ACTION_EXPORT_DATA: "导出数据",
            self.ACTION_SYSTEM_CONFIG: "系统配置",
        }
        return action_names.get(action, action)


# 全局单例
_log_service: Optional[AdminOperationLogService] = None


def get_admin_log_service() -> AdminOperationLogService:
    """获取日志服务单例"""
    global _log_service
    if _log_service is None:
        _log_service = AdminOperationLogService()
    return _log_service