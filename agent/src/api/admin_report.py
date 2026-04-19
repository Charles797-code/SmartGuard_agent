"""
管理员API - 举报管理
"""

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from src.api.auth import get_admin_user, UserInfo
from src.services.admin_log_service import get_admin_log_service

router = APIRouter(prefix="/api/v1/admin", tags=["管理员"])


class ReviewReportRequest(BaseModel):
    """审核举报请求"""
    report_ids: List[str] = Field(..., description="要审核的举报ID列表")
    action: str = Field(..., description="审核操作：verify=确认, reject=驳回")
    reason: Optional[str] = Field(None, description="审核理由")


from src.services.report_submit_service import report_service


@router.get("/reports/pending")
async def get_pending_reports(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    scam_type: Optional[str] = Query(None, description="诈骗类型过滤")
):
    """
    获取待审核的举报列表（管理员）
    """
    # 获取所有待处理的举报
    all_reports = [r for r in report_service.reports if r.status == "pending"]
    
    # 按诈骗类型过滤
    if scam_type:
        all_reports = [r for r in all_reports if r.scam_type == scam_type]
    
    # 按时间倒序
    all_reports.sort(key=lambda x: x.created_at, reverse=True)
    
    # 分页
    total = len(all_reports)
    start = (page - 1) * page_size
    end = start + page_size
    paginated = all_reports[start:end]
    
    return {
        "reports": [report_service._report_to_dict(r) for r in paginated],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    }


@router.get("/reports/all")
async def get_all_reports(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, description="状态过滤"),
    scam_type: Optional[str] = Query(None, description="诈骗类型过滤")
):
    """
    获取所有举报列表（管理员）
    """
    all_reports = list(report_service.reports)
    
    # 过滤
    if status:
        all_reports = [r for r in all_reports if r.status == status]
    if scam_type:
        all_reports = [r for r in all_reports if r.scam_type == scam_type]
    
    all_reports.sort(key=lambda x: x.created_at, reverse=True)
    
    total = len(all_reports)
    start = (page - 1) * page_size
    end = start + page_size
    paginated = all_reports[start:end]
    
    return {
        "reports": [report_service._report_to_dict(r) for r in paginated],
        "total": total,
        "page": page,
        "page_size": page_size
    }


@router.post("/reports/review")
async def review_reports(
    request: ReviewReportRequest,
    http_request: Request,
    current_user: UserInfo = Depends(get_admin_user)
):
    """
    批量审核举报（管理员）
    
    管理员确认后，举报内容将接入自进化模块进行学习
    """
    log_service = get_admin_log_service()
    
    results = []
    
    for report_id in request.report_ids:
        report = None
        for r in report_service.reports:
            if r.report_id == report_id:
                report = r
                break
        
        if not report:
            results.append({"report_id": report_id, "status": "not_found"})
            continue
        
        if request.action == "verify":
            # 确认举报，状态改为已验证
            report.status = "verified"
            report.updated_at = __import__('time').time()
            
            # 保存到数据库
            await report_service._update_report_in_db(report.report_id, {
                "status": "verified",
                "updated_at": report.updated_at,
                "learned": 1 if report.learned else 0
            })
            
            # 接入自进化模块
            await _integrate_to_evolution(report)
            
            # 记录操作日志
            await log_service.log(
                admin_id=current_user.id,
                admin_username=current_user.username,
                action=log_service.ACTION_VERIFY_REPORT,
                target_type="report",
                target_id=report_id,
                details={
                    "scam_type": report.scam_type,
                    "reason": request.reason,
                    "action": "verify"
                }
            )
            
            results.append({
                "report_id": report_id,
                "status": "verified",
                "learned": True
            })
            
        elif request.action == "reject":
            # 驳回举报
            report.status = "rejected"
            report.updated_at = __import__('time').time()
            
            # 保存到数据库
            await report_service._update_report_in_db(report.report_id, {
                "status": "rejected",
                "updated_at": report.updated_at
            })
            
            # 记录操作日志
            await log_service.log(
                admin_id=current_user.id,
                admin_username=current_user.username,
                action=log_service.ACTION_REJECT_REPORT,
                target_type="report",
                target_id=report_id,
                details={
                    "scam_type": report.scam_type,
                    "reason": request.reason,
                    "action": "reject"
                }
            )
            
            results.append({"report_id": report_id, "status": "rejected"})
    
    # 记录批量审核日志
    verified_count = len([r for r in results if r.get("status") == "verified"])
    rejected_count = len([r for r in results if r.get("status") == "rejected"])
    
    await log_service.log(
        admin_id=current_user.id,
        admin_username=current_user.username,
        action=log_service.ACTION_REVIEW_REPORT,
        target_type="report",
        target_id=",".join(request.report_ids),
        details={
            "batch_size": len(request.report_ids),
            "verified_count": verified_count,
            "rejected_count": rejected_count,
            "action": request.action,
            "reason": request.reason
        }
    )
    
    return {
        "success": True,
        "message": f"已处理 {len(results)} 条举报",
        "results": results
    }


async def _integrate_to_evolution(report):
    """将举报内容接入自进化模块"""
    import time
    try:
        from src.services.evolution_service import get_evolution_service
        evolution_service = get_evolution_service()
        
        # 添加到进化服务的学习记录
        await evolution_service.record_case(
            user_id=report.user_id,
            content=report.content,
            risk_level=4,  # 高风险
            risk_type=report.scam_type,
            analysis=f"管理员审核通过：从用户举报中学到的诈骗手法",
            response=f"已记录诈骗类型「{report_service._get_type_name(report.scam_type)}」的举报内容"
        )
        
        # 标记为已学习
        report.learned = True
        report.updated_at = time.time()
        
        return True
    except Exception as e:
        print(f"[举报进化] 接入失败: {e}")
        return False


@router.get("/reports/statistics")
async def get_admin_statistics(
    current_user: UserInfo = Depends(get_admin_user)
):
    """
    获取举报统计信息（管理员）
    """
    stats = await report_service.get_statistics()
    
    # 添加更多统计
    stats["pending_reports"] = len([r for r in report_service.reports if r.status == "pending"])
    stats["verified_reports"] = len([r for r in report_service.reports if r.status == "verified"])
    stats["rejected_reports"] = len([r for r in report_service.reports if r.status == "rejected"])
    stats["learned_reports"] = len([r for r in report_service.reports if r.learned])
    
    return stats


@router.get("/evolution/keywords")
async def get_learned_keywords(
    current_user: UserInfo = Depends(get_admin_user)
):
    """
    获取已学习的关键词库（管理员）
    """
    from src.services.evolution_service import get_evolution_service
    evolution_service = get_evolution_service()
    
    result = []
    for scam_type, keywords in evolution_service.learned_keywords.items():
        result.append({
            "scam_type": scam_type,
            "keywords": keywords,
            "count": len(keywords)
        })
    
    return {
        "scam_types": result,
        "total_keywords": sum(len(kw) for kw in evolution_service.learned_keywords.values())
    }


@router.get("/evolution/patterns")
async def get_learned_patterns(
    current_user: UserInfo = Depends(get_admin_user)
):
    """
    获取已学习的模式库（管理员）
    """
    from src.services.evolution_service import get_evolution_service
    evolution_service = get_evolution_service()
    
    result = []
    for scam_type, patterns in evolution_service.learned_patterns.items():
        result.append({
            "scam_type": scam_type,
            "patterns": patterns,
            "count": len(patterns)
        })
    
    return {
        "scam_types": result,
        "total_patterns": sum(len(p) for p in evolution_service.learned_patterns.values())
    }
