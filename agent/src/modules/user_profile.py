"""
用户画像模块
管理用户画像数据，支持个性化推荐
"""

import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict, field


@dataclass
class UserProfile:
    """用户画像数据模型"""
    # 基础信息
    nickname: str = ""
    avatar_url: str = ""
    bio: str = ""  # 个人简介
    
    # 人口统计
    age_group: str = ""  # 18-25, 26-35, 36-45, 46-55, 56+
    gender: str = ""  # male, female, other
    location: str = ""  # 地区
    
    # 职业信息
    occupation: str = ""  # 学生, 上班族, 自由职业, 退休, 其他
    education: str = ""  # 高中及以下, 大专, 本科, 硕士, 博士
    
    # 反诈相关偏好
    risk_awareness: int = 50  # 0-100, 反诈意识水平
    experience_level: str = "新手"  # 新手, 了解, 熟悉, 专业
    interested_scam_types: List[str] = field(default_factory=list)  # 感兴趣的诈骗类型
    
    # 行为数据
    total_consultations: int = 0  # 总咨询次数
    reported_scams: int = 0  # 举报的诈骗次数
    family_protected: int = 0  # 受保护的家人数量
    
    # 学习进度
    learned_topics: List[str] = field(default_factory=list)  # 已学习的专题
    quiz_scores: Dict[str, int] = field(default_factory=dict)  # 测验分数 {topic: score}
    
    # 系统字段
    updated_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserProfile":
        """从字典创建"""
        if not data:
            return cls()
        # 移除系统字段
        data.pop('updated_at', None)
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
    
    def get_risk_context(self) -> str:
        """获取风险上下文，用于AI生成个性化回复"""
        contexts = []
        
        if self.age_group:
            age_labels = {
                "18-25": "年轻人",
                "26-35": "青年人",
                "36-45": "中年人",
                "46-55": "中老年人",
                "56+": "老年人"
            }
            contexts.append(f"用户是{age_labels.get(self.age_group, '')}")
        
        if self.occupation:
            occ_labels = {
                "学生": "学生群体",
                "上班族": "职场人士",
                "自由职业": "自由职业者",
                "退休": "退休人员",
                "其他": ""
            }
            label = occ_labels.get(self.occupation, self.occupation)
            if label:
                contexts.append(label)
        
        if self.experience_level:
            level_descriptions = {
                "新手": "对诈骗手法了解较少，需要更详细的解释和基础知识的普及",
                "了解": "对常见诈骗有一定了解，可以讲解进阶内容",
                "熟悉": "对各种诈骗手法比较熟悉，适合分享最新的诈骗手法和深度分析",
                "专业": "对反诈非常专业，可以讨论复杂案例和专业术语"
            }
            contexts.append(level_descriptions.get(self.experience_level, ""))
        
        if self.interested_scam_types:
            contexts.append(f"特别关注: {', '.join(self.interested_scam_types)}")
        
        if self.total_consultations > 0:
            contexts.append(f"已有 {self.total_consultations} 次咨询经验")
        
        if self.family_protected > 0:
            contexts.append(f"需要保护 {self.family_protected} 位家人")
        
        return "；".join(filter(None, contexts))
    
    def get_personalized_prompt(self) -> str:
        """获取个性化提示词"""
        context = self.get_risk_context()
        if not context:
            return ""
        
        return f"""【用户画像】
{context}

请根据以上用户画像，调整你的回答风格和内容深度，使用贴近用户群体的表达方式。"""


# 诈骗类型标签映射（用于兴趣选择）
SCAM_TYPE_LABELS = {
    "police": "冒充公检法诈骗",
    "investment": "投资理财诈骗",
    "part_time": "兼职刷单诈骗",
    "loan": "虚假贷款诈骗",
    "pig": "杀猪盘诈骗",
    "ai_voice": "AI语音合成诈骗",
    "ai_deepfake": "AI换脸诈骗",
    "refund": "购物退款诈骗",
    "credit": "虚假征信诈骗",
    "gaming": "游戏交易诈骗",
    "fan": "追星诈骗",
    "medical": "医保诈骗",
    "online_dating": "网络交友诈骗",
    "job": "招聘诈骗",
    "charity": "虚假慈善诈骗",
    "shipping": "快递诈骗"
}

# 年龄段标签
AGE_GROUPS = [
    ("18-25", "18-25岁 (青年)"),
    ("26-35", "26-35岁 (中青年)"),
    ("36-45", "36-45岁 (中年)"),
    ("46-55", "46-55岁 (中老年)"),
    ("56+", "56岁及以上 (老年)")
]

# 职业标签
OCCUPATIONS = [
    ("学生", "学生"),
    ("上班族", "上班族/职员"),
    ("自由职业", "自由职业者"),
    ("个体经营", "个体经营者/老板"),
    ("退休", "退休人员"),
    ("家庭主妇/夫", "家庭主妇/夫"),
    ("其他", "其他")
]

# 学历标签
EDUCATIONS = [
    ("高中及以下", "高中及以下"),
    ("大专", "大专"),
    ("本科", "本科"),
    ("硕士", "硕士"),
    ("博士", "博士及以上")
]

# 性别选项
GENDERS = [
    ("male", "男"),
    ("female", "女"),
    ("other", "其他/保密")
]
