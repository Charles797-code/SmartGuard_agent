"""
诈骗举报API
提供用户举报诈骗的接口
"""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Any
from src.api.auth import get_current_user, UserInfo

router = APIRouter(prefix="/api/v1/reports", tags=["诈骗举报"])

from src.services.report_submit_service import report_service, ReportService

# 获取诈骗类型列表
@router.get("/scam-types")
async def get_scam_type_list():
    """获取所有可举报的诈骗类型"""
    return {
        "scam_types": list(ReportService.SCAM_TYPES.keys())
    }

# 提交举报
class SubmitReportRequest(BaseModel):
    scam_type: str = Field(..., description="诈骗类型")
    title: str = Field(..., description="举报标题", min_length=5, max_length=100)
    content: str = Field(..., description="骗子的话术或内容", min_length=10)
    scammer_contact: Optional[str] = Field(None, description="骗子联系方式")
    scammer_account: Optional[str] = Field(None, description="骗子账号")
    platform: Optional[str] = Field(None, description="诈骗平台")
    amount: Optional[float] = Field(None, description="涉案金额")
    description: Optional[str] = Field(None, description="详细描述")

@router.post("/submit")
async def submit_report(
    request: SubmitReportRequest,
    current_user: UserInfo = Depends(get_current_user)
):
    """
    提交诈骗举报
    
    用户提交举报后，系统会：
    1. 自动提取诈骗关键词和模式
    2. 存储举报记录
    3. 为自进化模块提供学习素材
    """
    result = await report_service.submit_report(
        user_id=current_user.username,
        scam_type=request.scam_type,
        title=request.title,
        content=request.content,
        scammer_contact=request.scammer_contact,
        scammer_account=request.scammer_account,
        platform=request.platform,
        amount=request.amount,
        description=request.description
    )
    
    return result

# 获取用户举报列表
@router.get("/my-reports")
async def get_my_reports(
    current_user: UserInfo = Depends(get_current_user)
):
    """获取当前用户的举报记录"""
    reports = await report_service.get_user_reports(current_user.username)
    return {
        "reports": reports,
        "total": len(reports)
    }

# 获取举报详情
@router.get("/{report_id}")
async def get_report_detail(
    report_id: str,
    current_user: UserInfo = Depends(get_current_user)
):
    """获取举报详情"""
    report = await report_service.get_report_detail(report_id, current_user.username)
    if not report:
        return {"error": "举报不存在或无权访问"}
    return report

# 获取举报统计
@router.get("/statistics/summary")
async def get_report_statistics():
    """获取举报统计（公开）"""
    stats = await report_service.get_statistics()
    return stats

# 获取高危关键词（用于自进化）
@router.get("/keywords/dangerous")
async def get_dangerous_keywords(
    current_user: UserInfo = Depends(get_current_user)
):
    """
    获取高危关键词列表
    用于系统自进化和学习
    """
    keywords = report_service._get_top_keywords(50)
    return {
        "keywords": [{"keyword": k, "count": c} for k, c in keywords]
    }