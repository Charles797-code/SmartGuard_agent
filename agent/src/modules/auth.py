"""
认证模块
用户注册、登录、JWT Token 管理
"""

import hashlib
import secrets
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass
import jwt
import os

# JWT 配置 - 使用固定Secret或从环境变量读取
_JWT_SECRET_ENV = os.getenv("JWT_SECRET")
# 如果环境变量未设置，使用一个固定的默认Secret（仅用于开发，生产环境应设置环境变量）
JWT_SECRET = _JWT_SECRET_ENV if _JWT_SECRET_ENV else "smartguard_jwt_secret_key_do_not_change_in_production_2024"
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24 * 7  # 7天过期


@dataclass
class User:
    """用户数据模型"""
    id: str
    username: str
    email: Optional[str]
    phone: Optional[str]
    password_hash: str
    is_active: bool
    created_at: float
    updated_at: float
    last_login: Optional[float]


def hash_password(password: str) -> str:
    """密码哈希 - 使用 PBKDF2"""
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    )
    return f"{salt}${key.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    """验证密码"""
    try:
        salt, key_hex = password_hash.split('$')
        expected_key = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000
        )
        return secrets.compare_digest(expected_key.hex(), key_hex)
    except:
        return False


def generate_token(user_id: str) -> tuple[str, float]:
    """生成 JWT Token"""
    expire = time.time() + JWT_EXPIRE_HOURS * 3600
    payload = {
        "user_id": user_id,
        "exp": expire,
        "iat": time.time()
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token, expire


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """验证并解析 Token"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None  # Token 已过期
    except jwt.InvalidTokenError:
        return None  # Token 无效


def get_user_id_from_token(authorization: str) -> Optional[str]:
    """
    从 Authorization 头或纯 JWT 字符串解析 user_id。

    FastAPI HTTPBearer 的 credentials.credentials 已是「去掉 Bearer 后的 token」，
    若仍按「Bearer xxx」整串解析会导致永远解析失败 → 所有需登录接口返回 401。
    """
    if not authorization:
        print("[auth] 授权头为空", flush=True)
        return None

    raw = authorization.strip()
    parts = raw.split(None, 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        token = parts[1].strip()
    else:
        token = raw

    if not token:
        print("[auth] token 为空，raw='%s'" % raw[:80], flush=True)
        return None

    # 打印 token 的前 20 和后 20 字符用于调试
    print("[auth] 收到token: 前20=%s ... 后20=%s" % (token[:20], token[-20:]), flush=True)
    print("[auth] 当前JWT_SECRET: %s" % JWT_SECRET[:20], flush=True)

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        print("[auth] JWT解析成功, user_id=%s" % payload.get("user_id"), flush=True)
        return payload.get("user_id")
    except jwt.ExpiredSignatureError:
        print("[auth] JWT已过期", flush=True)
        return None
    except jwt.InvalidSignatureError:
        print("[auth] JWT签名无效! 可能是token由不同Secret签发", flush=True)
        print("[auth] 当前Secret前20字符: %s" % JWT_SECRET[:20], flush=True)
        # 尝试用备用方式解析（打印payload但不信任）
        try:
            payload_unsafe = jwt.decode(token, options={"verify_signature": False})
            print("[auth] 不验证签名的payload: %s" % str(payload_unsafe)[:200], flush=True)
        except Exception as e2:
            print("[auth] 无法解析payload: %s" % e2, flush=True)
        return None
    except jwt.InvalidTokenError as e:
        print("[auth] JWT无效: %s" % e, flush=True)
        return None
    except Exception as e:
        print("[auth] 未知错误: %s" % e, flush=True)
        return None