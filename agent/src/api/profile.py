"""
用户画像API路由
用户画像的查询和更新
"""

import json
import time
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.data.database import get_database
from src.modules.user_profile import (
    UserProfile, SCAM_TYPE_LABELS, AGE_GROUPS,
    OCCUPATIONS, EDUCATIONS, GENDERS
)
from src.api.auth import get_current_user, UserInfo

router = APIRouter(prefix="/api/v1/profile", tags=["用户画像"])


# ==================== 请求/响应模型 ====================

class ProfileUpdate(BaseModel):
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    age_group: Optional[str] = None
    gender: Optional[str] = None
    location: Optional[str] = None
    occupation: Optional[str] = None
    education: Optional[str] = None
    risk_awareness: Optional[int] = None
    experience_level: Optional[str] = None
    interested_scam_types: Optional[List[str]] = None
    family_protected: Optional[int] = None


class ProfileResponse(BaseModel):
    success: bool
    message: str
    profile: Optional[dict] = None


# ==================== 用户画像接口 ====================

@router.get("/", response_model=ProfileResponse)
async def get_profile(current_user: UserInfo = Depends(get_current_user)):
    """获取当前用户画像"""
    db = get_database()

    profiles = await db.query("user_profiles", filters={"user_id": current_user.id})

    if not profiles:
        # 创建默认画像
        profile = UserProfile(nickname=current_user.username)
        profile_dict = profile.to_dict()
        profile_dict["interested_scam_types"] = "[]"
        profile_dict["learned_topics"] = "[]"
        profile_dict["quiz_scores"] = "{}"
        profile_dict["updated_at"] = time.time()
        await db.insert("user_profiles", {"user_id": current_user.id, **profile_dict})
        return ProfileResponse(
            success=True,
            message="获取成功",
            profile=profile_dict
        )

    profile_data = profiles[0]

    # 解析JSON字段
    if isinstance(profile_data.get("interested_scam_types"), str):
        profile_data["interested_scam_types"] = json.loads(
            profile_data.get("interested_scam_types", "[]")
        )
    if isinstance(profile_data.get("learned_topics"), str):
        profile_data["learned_topics"] = json.loads(
            profile_data.get("learned_topics", "[]")
        )
    if isinstance(profile_data.get("quiz_scores"), str):
        profile_data["quiz_scores"] = json.loads(
            profile_data.get("quiz_scores", "{}")
        )

    return ProfileResponse(
        success=True,
        message="获取成功",
        profile=profile_data
    )


@router.put("/", response_model=ProfileResponse)
async def update_profile(
    update: ProfileUpdate,
    current_user: UserInfo = Depends(get_current_user)
):
    """更新用户画像"""
    db = get_database()

    # 获取现有画像
    profiles = await db.query("user_profiles", filters={"user_id": current_user.id})

    if not profiles:
        # 创建新画像
        profile = UserProfile(nickname=current_user.username)
        profile_dict = profile.to_dict()
        profile_dict["interested_scam_types"] = "[]"
        profile_dict["learned_topics"] = "[]"
        profile_dict["quiz_scores"] = "{}"
        profile_dict["updated_at"] = time.time()
        await db.insert("user_profiles", {"user_id": current_user.id, **profile_dict})
        profiles = await db.query("user_profiles", filters={"user_id": current_user.id})

    existing = profiles[0]

    # 构建更新数据
    update_data = {}
    # Pydantic v2 使用 model_dump；保留与 v1 的兼容
    update_fields = (
        update.model_dump(exclude_none=True)
        if hasattr(update, "model_dump")
        else update.dict(exclude_none=True)
    )

    for key, value in update_fields.items():
        if key in ["interested_scam_types", "learned_topics"]:
            # 这些字段存储为JSON字符串
            update_data[key] = json.dumps(value, ensure_ascii=False)
        elif key == "quiz_scores":
            update_data[key] = json.dumps(value, ensure_ascii=False)
        elif key == "risk_awareness":
            # 确保在有效范围内
            update_data[key] = max(0, min(100, value))
        else:
            update_data[key] = value

    if update_data:
        update_data["updated_at"] = time.time()
        # user_profiles 表的主键是 user_id
        success = await db.update("user_profiles", current_user.id, update_data, id_field="user_id")
        if not success:
            raise HTTPException(status_code=500, detail="更新失败")

    # 返回更新后的画像
    profiles = await db.query("user_profiles", filters={"user_id": current_user.id})
    profile_data = profiles[0]

    # 解析JSON字段
    if isinstance(profile_data.get("interested_scam_types"), str):
        profile_data["interested_scam_types"] = json.loads(
            profile_data.get("interested_scam_types", "[]")
        )
    if isinstance(profile_data.get("learned_topics"), str):
        profile_data["learned_topics"] = json.loads(
            profile_data.get("learned_topics", "[]")
        )
    if isinstance(profile_data.get("quiz_scores"), str):
        profile_data["quiz_scores"] = json.loads(
            profile_data.get("quiz_scores", "{}")
        )

    return ProfileResponse(
        success=True,
        message="更新成功",
        profile=profile_data
    )


@router.post("/complete")
async def complete_profile(
    profile: ProfileUpdate,
    current_user: UserInfo = Depends(get_current_user)
):
    """完善用户画像（批量更新）"""
    return await update_profile(profile, current_user)


@router.get("/options")
async def get_profile_options():
    """获取画像选项配置"""
    return {
        "scam_types": SCAM_TYPE_LABELS,
        "age_groups": AGE_GROUPS,
        "occupations": OCCUPATIONS,
        "educations": EDUCATIONS,
        "genders": GENDERS,
        "experience_levels": [
            {"value": "新手", "label": "新手 - 对诈骗了解很少"},
            {"value": "了解", "label": "了解 - 知道一些常见诈骗"},
            {"value": "熟悉", "label": "熟悉 - 比较了解各种手法"},
            {"value": "专业", "label": "专业 - 对反诈很有经验"}
        ]
    }


@router.get("/stats")
async def get_user_stats(current_user: UserInfo = Depends(get_current_user)):
    """获取用户统计信息"""
    db = get_database()

    # 获取预警数量
    alerts = await db.query("alerts", filters={"user_id": current_user.id})
    unread_alerts = len([a for a in alerts if not a.get("acknowledged")])

    # 获取对话数量
    conversations = await db.query("conversations", filters={"user_id": current_user.id})

    # 获取画像
    profiles = await db.query("user_profiles", filters={"user_id": current_user.id})
    profile_data = profiles[0] if profiles else {}

    return {
        "user_id": current_user.id,
        "username": current_user.username,
        "total_consultations": profile_data.get("total_consultations", 0),
        "reported_scams": profile_data.get("reported_scams", 0),
        "family_protected": profile_data.get("family_protected", 0),
        "unread_alerts": unread_alerts,
        "conversation_count": len(conversations),
        "learned_topics_count": len(json.loads(profile_data.get("learned_topics", "[]")))
    }


@router.post("/increment/consultation")
async def increment_consultation(current_user: UserInfo = Depends(get_current_user)):
    """增加咨询次数"""
    db = get_database()

    profiles = await db.query("user_profiles", filters={"user_id": current_user.id})
    if profiles:
        current_count = profiles[0].get("total_consultations", 0)
        await db.update("user_profiles", current_user.id, {
            "total_consultations": current_count + 1,
            "updated_at": time.time()
        }, id_field="user_id")

    return {"success": True}
