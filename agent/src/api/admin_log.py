"""
管理员API - 操作日志
"""

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from typing import Optional, List
from src.api.auth import get_admin_user, UserInfo
from src.services.admin_log_service import get_admin_log_service


router = APIRouter(prefix="/api/v1/admin/logs", tags=["管理员-操作日志"])


class LogListResponse(BaseModel):
    logs: List[dict]
    total: int
    page: int
    page_size: int
    total_pages: int


@router.get("", response_model=LogListResponse)
async def list_operation_logs(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    admin_id: Optional[str] = Query(None, description="管理员ID过滤"),
    action: Optional[str] = Query(None, description="操作类型过滤"),
    target_type: Optional[str] = Query(None, description="对象类型过滤"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    request: Request = None,
    current_user: UserInfo = Depends(get_admin_user),
):
    """
    获取管理员操作日志列表
    """
    log_service = get_admin_log_service()
    
    result = await log_service.get_logs(
        page=page,
        page_size=page_size,
        admin_id=admin_id,
        action=action,
        target_type=target_type,
        keyword=keyword
    )
    
    return LogListResponse(**result)


@router.get("/statistics")
async def get_log_statistics(
    start_time: Optional[float] = Query(None, description="开始时间戳"),
    end_time: Optional[float] = Query(None, description="结束时间戳"),
    current_user: UserInfo = Depends(get_admin_user),
):
    """
    获取操作日志统计
    """
    log_service = get_admin_log_service()
    return await log_service.get_statistics(start_time, end_time)


@router.get("/actions")
async def get_action_types(
    current_user: UserInfo = Depends(get_admin_user),
):
    """
    获取所有操作类型
    """
    log_service = get_admin_log_service()
    return {
        "actions": [
            {"value": log_service.ACTION_LOGIN, "label": "登录系统"},
            {"value": log_service.ACTION_LOGOUT, "label": "退出登录"},
            {"value": log_service.ACTION_CREATE_USER, "label": "创建用户"},
            {"value": log_service.ACTION_UPDATE_USER, "label": "更新用户"},
            {"value": log_service.ACTION_DELETE_USER, "label": "删除用户"},
            {"value": log_service.ACTION_DISABLE_USER, "label": "禁用用户"},
            {"value": log_service.ACTION_ENABLE_USER, "label": "启用用户"},
            {"value": log_service.ACTION_REVIEW_REPORT, "label": "审核举报"},
            {"value": log_service.ACTION_VERIFY_REPORT, "label": "确认举报"},
            {"value": log_service.ACTION_REJECT_REPORT, "label": "驳回举报"},
            {"value": log_service.ACTION_UPDATE_KNOWLEDGE, "label": "更新知识库"},
            {"value": log_service.ACTION_EXPORT_DATA, "label": "导出数据"},
            {"value": log_service.ACTION_SYSTEM_CONFIG, "label": "系统配置"},
        ]
    }
