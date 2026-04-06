"""
安全监测报告API路由
生成可视化报告
"""

import time
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.services.report_service import ReportService
from src.api.auth import get_current_user, UserInfo

router = APIRouter(prefix="/api/v1/reports", tags=["安全报告"])


# ==================== 报告生成 ====================

@router.get("/generate")
async def generate_report(
    report_type: str = Query("weekly", description="报告类型: daily/weekly/monthly"),
    start_date: Optional[float] = Query(None, description="开始时间戳"),
    end_date: Optional[float] = Query(None, description="结束时间戳"),
    current_user: UserInfo = Depends(get_current_user)
):
    """生成安全监测报告"""
    service = ReportService(current_user.id)
    report = await service.generate_report(
        report_type=report_type,
        start_date=start_date,
        end_date=end_date
    )
    return report


@router.get("/summary")
async def get_report_summary(
    current_user: UserInfo = Depends(get_current_user)
):
    """获取快速统计摘要"""
    service = ReportService(current_user.id)
    report = await service.generate_report(report_type="weekly")
    summary = report.get("summary", {})
    risk_dist = report.get("risk_distribution", {})
    return {
        "protection_score": summary.get("protection_score", 0),
        "total_alerts": summary.get("total_alerts", 0),
        "high_risk_alerts": summary.get("high_risk_alerts", 0),
        "guardian_count": summary.get("guardian_count", 0),
        "dominant_risk": risk_dist.get("dominant_label", "无数据"),
        "report_type": "weekly"
    }


# ==================== 历史对话统计 ====================

@router.get("/conversation-stats")
async def get_conversation_stats(
    report_type: str = Query("weekly", description="统计周期: daily/weekly/monthly"),
    current_user: UserInfo = Depends(get_current_user)
):
    """获取对话统计"""
    service = ReportService(current_user.id)
    report = await service.generate_report(report_type=report_type)
    return report.get("conversation_stats", {})


# ==================== 图表数据（单独接口，方便前端按需加载） ====================

@router.get("/charts")
async def get_chart_configs(
    report_type: str = Query("weekly"),
    current_user: UserInfo = Depends(get_current_user)
):
    """获取 ECharts 图表配置"""
    service = ReportService(current_user.id)
    report = await service.generate_report(report_type=report_type)
    return report.get("charts", {})
