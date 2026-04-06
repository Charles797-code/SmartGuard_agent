"""
知识百科API路由
提供诈骗手法百科全书的API接口
"""

from fastapi import APIRouter, HTTPException
from typing import Optional, List, Dict
from pydantic import BaseModel

from src.modules.encyclopedia import (
    SCAM_ENCYCLOPEDIA,
    get_encyclopedia_categories,
    get_all_scam_types,
    get_scam_detail,
    search_encyclopedia,
    get_prevention_by_risk_level,
    get_statistics
)

router = APIRouter(prefix="/api/v1/encyclopedia", tags=["知识百科"])


class ScamDetailResponse(BaseModel):
    """诈骗详情响应"""
    id: str
    name: str
    icon: str
    color: str
    short_desc: str
    risk_level: int
    techniques: List[str]
    typical_cases: List[Dict]
    prevention_tips: List[str]
    warning_signs: List[str]
    keywords: List[str]


class SearchResult(BaseModel):
    """搜索结果"""
    id: str
    name: str
    icon: str
    color: str
    short_desc: str
    risk_level: int
    score: float
    matched_in: List[str]


@router.get("/")
async def get_encyclopedia_home():
    """获取百科首页数据"""
    categories = get_encyclopedia_categories()
    scam_types = get_all_scam_types()
    stats = get_statistics()
    
    return {
        "categories": categories,
        "scam_types": scam_types,
        "statistics": stats
    }


@router.get("/categories")
async def get_categories():
    """获取诈骗分类"""
    return {
        "categories": get_encyclopedia_categories()
    }


@router.get("/scam-types")
async def get_types():
    """获取所有诈骗类型列表"""
    return {
        "scam_types": get_all_scam_types()
    }


@router.get("/scam-types/{scam_id}")
async def get_detail(scam_id: str):
    """获取诈骗类型详情"""
    detail = get_scam_detail(scam_id)
    
    if not detail:
        raise HTTPException(status_code=404, detail="未找到该诈骗类型")
    
    return {
        "detail": detail
    }


@router.get("/search")
async def search(keyword: str, limit: int = 10):
    """搜索百科内容"""
    if not keyword or len(keyword.strip()) < 1:
        return {"results": [], "total": 0}
    
    results = search_encyclopedia(keyword.strip())
    return {
        "results": results[:limit],
        "total": len(results),
        "keyword": keyword
    }


@router.get("/prevention-tips")
async def get_tips(risk_level: Optional[int] = None):
    """获取防范建议"""
    if risk_level:
        tips = get_prevention_by_risk_level(risk_level)
    else:
        # 返回所有诈骗类型的防范建议
        tips = []
        for scam_id, scam_data in SCAM_ENCYCLOPEDIA.items():
            tips.append({
                "id": scam_data["id"],
                "name": scam_data["name"],
                "icon": scam_data["icon"],
                "risk_level": scam_data["risk_level"],
                "tips": scam_data["prevention_tips"]
            })
    
    return {
        "tips": tips,
        "risk_level": risk_level
    }


@router.get("/statistics")
async def get_stats():
    """获取百科统计"""
    return get_statistics()


@router.get("/warnings")
async def get_warning_signs():
    """获取所有诈骗类型的警示信号"""
    warnings = []
    for scam_id, scam_data in SCAM_ENCYCLOPEDIA.items():
        warnings.append({
            "scam_id": scam_id,
            "scam_name": scam_data["name"],
            "scam_icon": scam_data["icon"],
            "warning_signs": scam_data["warning_signs"]
        })
    
    return {
        "warnings": warnings
    }


@router.get("/techniques")
async def get_all_techniques():
    """获取所有诈骗手法"""
    techniques = []
    for scam_id, scam_data in SCAM_ENCYCLOPEDIA.items():
        techniques.append({
            "scam_id": scam_id,
            "scam_name": scam_data["name"],
            "scam_icon": scam_data["icon"],
            "risk_level": scam_data["risk_level"],
            "techniques": scam_data["techniques"]
        })
    
    return {
        "techniques": techniques
    }


@router.get("/cases")
async def get_all_cases():
    """获取所有典型案例"""
    cases = []
    for scam_id, scam_data in SCAM_ENCYCLOPEDIA.items():
        for case in scam_data["typical_cases"]:
            cases.append({
                "scam_id": scam_id,
                "scam_name": scam_data["name"],
                "scam_icon": scam_data["icon"],
                "title": case["title"],
                "content": case["content"]
            })
    
    return {
        "cases": cases,
        "total": len(cases)
    }


@router.get("/by-risk/{risk_level}")
async def get_by_risk(risk_level: int):
    """按风险等级获取诈骗类型"""
    if risk_level < 1 or risk_level > 5:
        raise HTTPException(status_code=400, detail="风险等级应在1-5之间")
    
    results = []
    for scam_id, scam_data in SCAM_ENCYCLOPEDIA.items():
        if scam_data["risk_level"] == risk_level:
            results.append({
                "id": scam_data["id"],
                "name": scam_data["name"],
                "icon": scam_data["icon"],
                "color": scam_data["color"],
                "short_desc": scam_data["short_desc"],
                "risk_level": scam_data["risk_level"]
            })
    
    return {
        "risk_level": risk_level,
        "scam_types": results
    }
