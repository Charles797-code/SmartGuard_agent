"""
管理员API - 用户管理
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from typing import Optional, List, Any
from src.api.auth import get_admin_user, UserInfo
from src.data.database import get_database
from src.modules.auth import hash_password
from src.services.admin_log_service import get_admin_log_service
import time
import secrets

router = APIRouter(prefix="/api/v1/admin/users", tags=["管理员-用户管理"])


# ==================== 请求/响应模型 ====================

class CreateUserRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=20, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(..., min_length=6, max_length=50)
    role: str = Field(default="user", pattern=r"^(user|admin)$")
    email: Optional[str] = None
    phone: Optional[str] = None


class UpdateUserRequest(BaseModel):
    password: Optional[str] = Field(None, min_length=6, max_length=50)
    role: Optional[str] = Field(None, pattern=r"^(user|admin)$")
    is_active: Optional[bool] = None
    email: Optional[str] = None
    phone: Optional[str] = None


class UserListResponse(BaseModel):
    users: List[dict]
    total: int
    page: int
    page_size: int


# ==================== 用户列表 ====================

@router.get("", response_model=UserListResponse)
async def list_users(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    role: Optional[str] = Query(None, description="角色过滤"),
    keyword: Optional[str] = Query(None, description="用户名/邮箱搜索"),
    current_user: UserInfo = Depends(get_admin_user),
):
    """
    获取用户列表（管理员）
    """
    db = get_database()
    filters = {}
    if role:
        filters["role"] = role

    all_users = await db.query("users_auth", filters=filters, limit=10000)

    # 关键字搜索
    if keyword:
        kw = keyword.lower()
        all_users = [
            u for u in all_users
            if kw in (u.get("username") or "").lower()
            or kw in (u.get("email") or "").lower()
        ]

    # 排除自己，防止管理员误删自己
    all_users = [u for u in all_users if u["id"] != current_user.id]

    # 排除系统默认用户（system 不可见）
    # root 管理员会显示，但受特殊保护不能删除/降级

    total = len(all_users)
    # 按创建时间倒序
    all_users.sort(key=lambda x: x.get("created_at", 0), reverse=True)

    start = (page - 1) * page_size
    end = start + page_size
    paginated = all_users[start:end]

    users = []
    for u in paginated:
        # 关联的画像信息
        profiles = await db.query("user_profiles", filters={"user_id": u["id"]}, limit=1)
        profile = profiles[0] if profiles else {}
        
        # 获取被监护人数量（该用户作为监护人保护的用户数）
        guardians = await db.query("guardians", filters={"linked_user_id": u["id"]}, limit=1000)
        protected_count = len(guardians)
        
        users.append({
            "id": u["id"],
            "username": u["username"],
            "email": u.get("email"),
            "phone": u.get("phone"),
            "role": u.get("role", "user"),
            "is_active": bool(u.get("is_active", 1)),
            "created_at": u.get("created_at"),
            "last_login": u.get("last_login"),
            "total_consultations": profile.get("total_consultations", 0),
            "risk_count": profile.get("risk_count", 0),
            "reported_scams": profile.get("reported_scams", 0),
            "family_protected": profile.get("family_protected", 0),
            "protected_count": protected_count,  # 作为监护人保护的用户数
        })

    return UserListResponse(
        users=users,
        total=total,
        page=page,
        page_size=page_size,
    )


# ==================== 日志备注 ====================

@router.put("/logs/{log_id}/remark")
async def update_log_remark(
    log_id: str,
    request: Request,
    current_user: UserInfo = Depends(get_admin_user),
):
    """
    更新操作日志备注
    """
    try:
        body = await request.json()
        remark = body.get("remark", "")
    except:
        remark = ""

    db = get_database()
    
    # 检查日志是否存在
    logs = await db.query("admin_operation_logs", filters={"id": log_id}, limit=1)
    if not logs:
        raise HTTPException(status_code=404, detail="日志不存在")
    
    # 更新备注
    await db.update("admin_operation_logs", log_id, {"remark": remark})
    
    return {"success": True, "message": "备注已更新"}


# ==================== 获取单个用户 ====================

@router.get("/{user_id}")
async def get_user(
    user_id: str,
    current_user: UserInfo = Depends(get_admin_user),
):
    """
    获取指定用户详情（管理员）
    """
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="不可查看当前管理员自己的详情，请使用个人中心")

    db = get_database()
    users = await db.query("users_auth", filters={"id": user_id}, limit=1)
    if not users:
        raise HTTPException(status_code=404, detail="用户不存在")

    u = users[0]
    profiles = await db.query("user_profiles", filters={"user_id": u["id"]}, limit=1)
    profile = profiles[0] if profiles else {}
    
    # 获取被监护人列表
    guardians = await db.query("guardians", filters={"linked_user_id": u["id"]}, limit=1000)
    protected_list = []
    for g in guardians:
        # 获取被监护人基本信息
        protected_users = await db.query("users_auth", filters={"id": g.get("user_id")}, limit=1)
        if protected_users:
            protected_user = protected_users[0]
            protected_profiles = await db.query("user_profiles", filters={"user_id": protected_user["id"]}, limit=1)
            protected_profile = protected_profiles[0] if protected_profiles else {}
            protected_list.append({
                "id": protected_user["id"],
                "username": protected_user.get("username"),
                "nickname": protected_profile.get("nickname") or protected_user.get("username"),
                "relationship": g.get("relationship", "家人"),
                "is_active": bool(g.get("is_active", 1)),
            })
    
    return {
        "id": u["id"],
        "username": u["username"],
        "email": u.get("email"),
        "phone": u.get("phone"),
        "role": u.get("role", "user"),
        "is_active": bool(u.get("is_active", 1)),
        "created_at": u.get("created_at"),
        "last_login": u.get("last_login"),
        "total_consultations": profile.get("total_consultations", 0),
        "risk_count": profile.get("risk_count", 0),
        "reported_scams": profile.get("reported_scams", 0),
        "family_protected": profile.get("family_protected", 0),
        "protected_list": protected_list,
    }


# ==================== 创建用户 ====================

@router.post("")
async def create_user(
    req: CreateUserRequest,
    request: Request,
    current_user: UserInfo = Depends(get_admin_user),
):
    """
    创建新用户（管理员）
    """
    db = get_database()
    log_service = get_admin_log_service()

    # 检查用户名唯一性
    existing = await db.query("users_auth", filters={"username": req.username}, limit=1)
    if existing:
        raise HTTPException(status_code=409, detail="用户名已存在")

    user_id = "user_" + secrets.token_hex(8)
    now = time.time()
    await db.insert("users_auth", {
        "id": user_id,
        "username": req.username,
        "password_hash": hash_password(req.password),
        "role": req.role,
        "is_active": 1,
        "created_at": now,
        "updated_at": now,
        "last_login": None,
        "email": req.email,
        "phone": req.phone,
    })

    # 初始化用户画像
    await db.insert("user_profiles", {
        "user_id": user_id,
        "nickname": "",
        "avatar_url": "",
        "bio": "",
        "age_group": "",
        "gender": "",
        "location": "",
        "occupation": "",
        "education": "",
        "risk_awareness": 50,
        "experience_level": "新手",
        "interested_scam_types": "[]",
        "total_consultations": 0,
        "reported_scams": 0,
        "family_protected": 0,
        "learned_topics": "[]",
        "quiz_scores": "{}",
        "risk_count": 0,
        "updated_at": now,
    })

    # 记录操作日志
    await log_service.log(
        admin_id=current_user.id,
        admin_username=current_user.username,
        action=log_service.ACTION_CREATE_USER,
        target_type="user",
        target_id=user_id,
        details={
            "username": req.username,
            "role": req.role,
            "email": req.email
        }
    )

    return {"success": True, "message": f"用户 {req.username} 创建成功", "user_id": user_id}


# ==================== 更新用户 ====================

@router.put("/{user_id}")
async def update_user(
    user_id: str,
    req: UpdateUserRequest,
    request: Request,
    current_user: UserInfo = Depends(get_admin_user),
):
    """
    更新用户信息（管理员）
    """
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="不可修改当前管理员自己")

    db = get_database()
    log_service = get_admin_log_service()
    
    users = await db.query("users_auth", filters={"id": user_id}, limit=1)
    if not users:
        raise HTTPException(status_code=404, detail="用户不存在")

    u = users[0]
    updates = {"updated_at": time.time()}
    change_details = {}

    if req.password is not None:
        updates["password_hash"] = hash_password(req.password)
        change_details["password_changed"] = True
    if req.role is not None:
        updates["role"] = req.role
        change_details["role"] = req.role
    if req.is_active is not None:
        updates["is_active"] = 1 if req.is_active else 0
        change_details["is_active"] = req.is_active
        if not req.is_active:
            change_details["action_type"] = "disable"
        else:
            change_details["action_type"] = "enable"
    if req.email is not None:
        updates["email"] = req.email
        change_details["email"] = req.email
    if req.phone is not None:
        updates["phone"] = req.phone
        change_details["phone"] = req.phone

    # 禁止降级 root 管理员
    if u.get("username") == "root" and req.role and req.role != "admin":
        raise HTTPException(status_code=400, detail="不能取消 root 管理员的身份")

    await db.update("users_auth", user_id, updates)
    
    # 记录操作日志
    if req.is_active is not None and not req.is_active:
        action = log_service.ACTION_DISABLE_USER
    elif req.is_active is not None and req.is_active:
        action = log_service.ACTION_ENABLE_USER
    else:
        action = log_service.ACTION_UPDATE_USER
        
    await log_service.log(
        admin_id=current_user.id,
        admin_username=current_user.username,
        action=action,
        target_type="user",
        target_id=user_id,
        details={
            "username": u.get("username"),
            "changes": change_details
        }
    )

    return {"success": True, "message": "用户信息已更新"}


# ==================== 删除用户 ====================

@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    request: Request,
    current_user: UserInfo = Depends(get_admin_user),
):
    """
    删除用户（管理员）
    """
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="不可删除当前管理员自己")

    db = get_database()
    log_service = get_admin_log_service()
    
    users = await db.query("users_auth", filters={"id": user_id}, limit=1)
    if not users:
        raise HTTPException(status_code=404, detail="用户不存在")

    u = users[0]

    # 禁止删除 root 管理员
    if u.get("username") == "root":
        raise HTTPException(status_code=400, detail="不能删除 root 管理员账户")

    # 删除关联数据
    for table in ["user_profiles", "conversations", "alerts", "guardians", "guardian_invitations"]:
        try:
            # 清理关联此 user_id 的记录
            if table in ["guardians", "guardian_invitations"]:
                await db.execute_raw(
                    f"DELETE FROM {table} WHERE user_id = ? OR linked_user_id = ?",
                    (user_id, user_id),
                )
            else:
                await db.execute_raw(
                    f"DELETE FROM {table} WHERE user_id = ?",
                    (user_id,),
                )
        except Exception:
            pass

    # 保存用户名用于日志
    username = u.get("username")
    
    await db.delete("users_auth", user_id)
    
    # 记录操作日志
    await log_service.log(
        admin_id=current_user.id,
        admin_username=current_user.username,
        action=log_service.ACTION_DELETE_USER,
        target_type="user",
        target_id=user_id,
        details={
            "username": username,
            "deleted_at": time.time()
        }
    )

    return {"success": True, "message": f"用户 {username} 已删除"}


# ==================== 统计 ====================

@router.get("/stats/overview")
async def get_user_stats(
    current_user: UserInfo = Depends(get_admin_user),
):
    """
    获取用户统计概览
    """
    db = get_database()
    all_users = await db.query("users_auth", filters={}, limit=10000)
    total = len(all_users)
    admins = len([u for u in all_users if u.get("role") == "admin"])
    active = len([u for u in all_users if u.get("is_active", 1) == 1])

    return {
        "total_users": total,
        "total_admins": admins,
        "total_normal_users": total - admins,
        "active_users": active,
        "inactive_users": total - active,
    }
