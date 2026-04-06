"""
邮件监控API接口
提供邮件监控配置和预警查询接口
"""

from fastapi import APIRouter, HTTPException, Body, Depends
from pydantic import BaseModel
from typing import Optional, List
from src.api.auth import get_current_user, UserInfo

router = APIRouter(prefix="/api/v1/email-monitor", tags=["邮件监控"])


class EmailConfigRequest(BaseModel):
    """添加邮件监控配置请求"""
    email_address: str
    username: Optional[str] = None
    password: str


class EmailAlertResponse(BaseModel):
    """邮件预警响应"""
    id: str
    subject: str
    sender: str
    email_date: float
    scam_score: float
    risk_level: str
    keywords: List[dict]
    patterns: List[str]
    status: str
    is_read: bool
    created_at: float


@router.post("/config", summary="添加邮件监控配置")
async def add_email_config(
    request: EmailConfigRequest,
    current_user: UserInfo = Depends(get_current_user)
):
    """
    添加邮件监控配置
    
    支持的邮箱类型：
    - QQ邮箱
    - Gmail
    - 163邮箱
    - Outlook
    - 新浪邮箱
    - TOM邮箱
    
    Args:
        email_address: 邮箱地址
        username: 登录用户名（可选，通常与邮箱相同）
        password: 密码或授权码（QQ邮箱需要使用授权码）
    """
    from src.services.email_monitor_service import email_monitor_service
    
    try:
        result = await email_monitor_service.add_email_config(
            user_id=current_user.id,
            email_address=request.email_address,
            username=request.username or request.email_address,
            password=request.password
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/config/{config_id}", summary="移除邮件监控配置")
async def remove_email_config(
    config_id: str,
    current_user: UserInfo = Depends(get_current_user)
):
    """移除邮件监控配置"""
    from src.services.email_monitor_service import email_monitor_service
    
    success = await email_monitor_service.remove_email_config(
        config_id=config_id,
        user_id=current_user.id
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="配置不存在")
    
    return {"success": True, "message": "邮件监控已移除"}


@router.get("/configs", summary="获取邮件监控配置列表")
async def get_email_configs(
    current_user: UserInfo = Depends(get_current_user)
):
    """获取当前用户的所有邮件监控配置"""
    from src.services.email_monitor_service import email_monitor_service
    
    configs = await email_monitor_service.get_user_configs(current_user.id)
    return {"configs": configs}


@router.get("/alerts", summary="获取邮件预警列表")
async def get_email_alerts(
    limit: int = 50,
    current_user: UserInfo = Depends(get_current_user)
):
    """
    获取邮件监控预警列表
    
    返回所有检测到的可疑邮件，按时间倒序排列
    """
    from src.services.email_monitor_service import email_monitor_service
    
    alerts = await email_monitor_service.get_user_alerts(
        user_id=current_user.id,
        limit=limit
    )
    
    # 统计未读数量
    unread_count = await email_monitor_service.get_unread_alert_count(current_user.id)
    
    # 获取LLM状态
    llm_client = email_monitor_service._get_llm_client()
    llm_available = llm_client.is_available if llm_client else False
    
    return {
        "alerts": alerts,
        "total": len(alerts),
        "unread_count": unread_count,
        "llm_analysis_enabled": llm_available
    }


@router.post("/alerts/{alert_id}/read", summary="标记预警为已读")
async def mark_alert_read(
    alert_id: str,
    current_user: UserInfo = Depends(get_current_user)
):
    """标记指定预警为已读"""
    from src.services.email_monitor_service import email_monitor_service
    
    await email_monitor_service.mark_alert_read(
        log_id=alert_id,
        user_id=current_user.id
    )
    
    return {"success": True}


@router.get("/alerts/unread-count", summary="获取未读预警数量")
async def get_unread_count(
    current_user: UserInfo = Depends(get_current_user)
):
    """获取未读预警数量"""
    from src.services.email_monitor_service import email_monitor_service
    
    count = await email_monitor_service.get_unread_alert_count(current_user.id)
    return {"unread_count": count}


@router.get("/test-connection", summary="测试邮件连接")
async def test_connection(
    email_address: str,
    password: str,
    username: Optional[str] = None
):
    """
    测试邮件连接
    
    用于在添加配置前测试邮箱连接是否正常
    """
    import imaplib
    
    # 自动检测IMAP服务器
    domain = email_address.split("@")[-1].lower()
    
    if "qq" in domain:
        host, port = "imap.qq.com", 993
    elif "gmail" in domain:
        host, port = "imap.gmail.com", 993
    elif "163" in domain:
        host, port = "imap.163.com", 993
    elif "126" in domain:
        host, port = "imap.126.com", 993
    elif "outlook" in domain or "hotmail" in domain:
        host, port = "outlook.office365.com", 993
    else:
        host, port = "imap.qq.com", 993  # 默认
    
    try:
        mail = imaplib.IMAP4_SSL(host, port)
        mail.login(username or email_address, password)
        mail.logout()
        return {
            "success": True,
            "message": "连接成功",
            "server": host
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"连接失败: {str(e)}")
