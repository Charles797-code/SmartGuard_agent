"""
认证API路由
用户注册、登录、Token验证
"""

import time
import secrets
from typing import Optional
from fastapi import APIRouter, HTTPException, Header, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.data.database import get_database
from src.modules.auth import (
    hash_password, verify_password, generate_token, verify_token,
    get_user_id_from_token, User
)
from src.modules.user_profile import UserProfile

router = APIRouter(prefix="/api/v1/auth", tags=["认证"])

security = HTTPBearer(auto_error=False)


# ==================== 请求/响应模型 ====================

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=20, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(..., min_length=6, max_length=50)
    email: Optional[str] = None
    phone: Optional[str] = None


class LoginRequest(BaseModel):
    username: str = Field(...)
    password: str = Field(...)
    # user=普通用户登录页；admin=管理员登录页（用于区分同一账号不可混用入口）
    portal: str = Field(default="user", pattern=r"^(user|admin)$")


class AuthResponse(BaseModel):
    success: bool
    message: str
    token: Optional[str] = None
    expire_at: Optional[float] = None
    user: Optional[dict] = None


class UserInfo(BaseModel):
    id: str
    username: str
    email: Optional[str] = None
    phone: Optional[str] = None
    role: str = "user"  # user=普通用户, admin=管理员
    created_at: float
    last_login: Optional[float] = None


# ==================== 依赖项 ====================

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> UserInfo:
    """获取当前登录用户（需要Token）"""
    print("[get_current_user] START credentials=%s" % credentials, flush=True)
    print("[get_current_user] type(credentials)=%s" % type(credentials).__name__, flush=True)
    if hasattr(credentials, 'credentials'):
        print("[get_current_user] credentials.credentials=%s" % str(credentials.credentials)[:80], flush=True)
    else:
        print("[get_current_user] credentials has NO 'credentials' attr, attrs=%s" % dir(credentials), flush=True)

    if not credentials:
        print("[auth] 401: 缺少 Authorization（HTTPBearer 未收到凭证）", flush=True)
        raise HTTPException(status_code=401, detail="请先登录")

    user_id = get_user_id_from_token(credentials.credentials)
    if not user_id:
        print("[auth] 401: JWT 无效或已过期（credentials 已收到但解析失败）", flush=True)
        raise HTTPException(status_code=401, detail="Token无效或已过期")

    db = get_database()
    users = await db.query("users_auth", filters={"id": user_id})

    if not users:
        raise HTTPException(status_code=401, detail="用户不存在")

    user_data = users[0]
    if not user_data.get("is_active"):
        raise HTTPException(status_code=401, detail="账号已被禁用")

    return UserInfo(
        id=user_data["id"],
        username=user_data["username"],
        email=user_data.get("email"),
        phone=user_data.get("phone"),
        role=user_data.get("role", "user"),
        created_at=user_data["created_at"],
        last_login=user_data.get("last_login")
    )


async def get_admin_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> UserInfo:
    """获取当前管理员用户（需要Token且角色为admin）"""
    # 先获取当前用户
    current_user = await get_current_user(credentials)
    
    # 检查是否为管理员
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    
    return current_user


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Optional[UserInfo]:
    """获取当前用户（可选，不强制登录）"""
    if not credentials:
        return None

    user_id = get_user_id_from_token(credentials.credentials)
    if not user_id:
        return None

    try:
        db = get_database()
        users = await db.query("users_auth", filters={"id": user_id})
        if users:
            user_data = users[0]
            if user_data.get("is_active"):
                return UserInfo(
                    id=user_data["id"],
                    username=user_data["username"],
                    email=user_data.get("email"),
                    phone=user_data.get("phone"),
                    role=user_data.get("role", "user"),
                    created_at=user_data["created_at"],
                    last_login=user_data.get("last_login")
                )
    except:
        pass

    return None


# ==================== 认证接口 ====================

@router.post("/register", response_model=AuthResponse)
async def register(request: RegisterRequest):
    """用户注册"""
    db = get_database()

    # 检查用户名是否已存在
    existing = await db.query("users_auth", filters={"username": request.username})
    if existing:
        raise HTTPException(status_code=400, detail="用户名已存在")

    # 检查邮箱是否已存在
    if request.email:
        existing = await db.query("users_auth", filters={"email": request.email})
        if existing:
            raise HTTPException(status_code=400, detail="邮箱已被注册")

    # 检查手机号是否已存在
    if request.phone:
        existing = await db.query("users_auth", filters={"phone": request.phone})
        if existing:
            raise HTTPException(status_code=400, detail="手机号已被注册")

    # 创建用户
    user_id = f"user_{secrets.token_hex(8)}"
    now = time.time()

    user_data = {
        "id": user_id,
        "username": request.username,
        "password_hash": hash_password(request.password),
        "email": request.email,
        "phone": request.phone,
        "is_active": 1,
        "created_at": now,
        "last_login": None
    }

    # 插入用户
    result = await db.insert("users_auth", user_data)
    if not result:
        raise HTTPException(status_code=500, detail="注册失败，请稍后重试")

    # 创建用户画像
    profile_data = {
        "user_id": user_id,
        "nickname": request.username,
        "interested_scam_types": "[]",
        "learned_topics": "[]",
        "quiz_scores": "{}",
        "updated_at": now
    }
    await db.insert("user_profiles", profile_data)

    # 生成Token
    token, expire_at = generate_token(user_id)

    return AuthResponse(
        success=True,
        message="注册成功",
        token=token,
        expire_at=expire_at,
        user={
            "id": user_id,
            "username": request.username,
            "email": request.email,
            "phone": request.phone,
            "role": "user"
        }
    )


@router.post("/login", response_model=AuthResponse)
async def login(request: LoginRequest):
    """用户登录"""
    db = get_database()

    # 查找用户
    users = await db.query("users_auth", filters={"username": request.username})
    if not users:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    user_data = users[0]

    # 验证密码
    if not verify_password(request.password, user_data["password_hash"]):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    # 检查账号状态
    if not user_data.get("is_active"):
        raise HTTPException(status_code=401, detail="账号已被禁用")

    role = user_data.get("role") or "user"
    portal = request.portal or "user"
    if portal == "user" and role == "admin":
        raise HTTPException(
            status_code=403,
            detail="管理员账号请使用「管理员登录」入口，勿在普通用户登录",
        )
    if portal == "admin" and role != "admin":
        raise HTTPException(status_code=403, detail="该账号不是管理员")

    # 更新最后登录时间
    await db.update("users_auth", user_data["id"], {
        "last_login": time.time()
    })

    # 生成Token
    token, expire_at = generate_token(user_data["id"])

    return AuthResponse(
        success=True,
        message="登录成功",
        token=token,
        expire_at=expire_at,
        user={
            "id": user_data["id"],
            "username": user_data["username"],
            "email": user_data.get("email"),
            "phone": user_data.get("phone"),
            "role": role
        }
    )


@router.post("/logout")
async def logout(current_user: UserInfo = Depends(get_current_user)):
    """用户登出"""
    # JWT是无状态的，登出由前端删除Token
    return {"success": True, "message": "已退出登录"}


@router.get("/me", response_model=UserInfo)
async def get_me(current_user: UserInfo = Depends(get_current_user)):
    """获取当前用户信息"""
    return current_user


@router.post("/refresh")
async def refresh_token(current_user: UserInfo = Depends(get_current_user)):
    """刷新Token"""
    token, expire_at = generate_token(current_user.id)
    return {
        "success": True,
        "token": token,
        "expire_at": expire_at
    }


@router.get("/verify")
async def verify_token_endpoint(
    current_user: Optional[UserInfo] = Depends(get_optional_user)
):
    """验证Token是否有效"""
    if current_user:
        user_payload = (
            current_user.model_dump()
            if hasattr(current_user, "model_dump")
            else current_user.dict()
        )
        return {
            "valid": True,
            "user": user_payload
        }
    else:
        return {"valid": False, "user": None}
