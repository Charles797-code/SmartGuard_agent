"""
提示词工程模块
包含系统提示词、任务指令、少样本示例等设计
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass


@dataclass
class PromptTemplate:
    """提示词模板"""
    role: str
    task: str
    constraints: List[str]
    few_shot_examples: List[Dict[str, str]]
    
    def format(self, **kwargs) -> str:
        """格式化提示词"""
        examples_text = "\n\n".join([
            f"示例 {i+1}:\n输入: {ex['input']}\n输出: {ex['output']}"
            for i, ex in enumerate(self.few_shot_examples)
        ])
        
        return f"""角色设定: {self.role}

任务指令: {self.task}

约束条件:
{chr(10).join(['- ' + c for c in self.constraints])}

少样本示例:
{examples_text}

{chr(10).join([f'{k}: {v}' for k, v in kwargs.items()])}"""


class PromptEngine:
    """提示词引擎"""
    
    # 诈骗类型定义
    SCAM_TYPES = {
        "police_impersonation": {
            "name": "冒充公检法诈骗",
            "keywords": ["涉嫌洗钱", "拘捕令", "资金核查", "安全账户", "银行账户"]
        },
        "investment_fraud": {
            "name": "投资理财诈骗",
            "keywords": ["高收益", "保本", "内幕消息", "稳赚不赔", "导师带单"]
        },
        "part_time_fraud": {
            "name": "兼职刷单诈骗",
            "keywords": ["点赞返利", "足不出户", "日结", "刷单赚佣金", "任务单"]
        },
        "loan_fraud": {
            "name": "虚假贷款诈骗",
            "keywords": ["无抵押", "低利率", "快速放款", "贷款解冻", "手续费"]
        },
        "pig_butchery": {
            "name": "杀猪盘诈骗",
            "keywords": ["博彩平台", "投资平台", "恋爱", "导师", "内幕"]
        },
        "ai_voice_fraud": {
            "name": "AI语音合成诈骗",
            "keywords": ["子女声音", "紧急汇款", "绑架", "事故", "转账"]
        },
        "deepfake_fraud": {
            "name": "视频深度伪造诈骗",
            "keywords": ["熟人借钱", "裸聊", "录屏", "威胁", "私密照"]
        },
        "credit_fraud": {
            "name": "虚假征信诈骗",
            "keywords": ["征信修复", "逾期洗白", "征信污点", "消除记录"]
        },
        "refund_fraud": {
            "name": "购物退款诈骗",
            "keywords": ["质量问题", "双倍赔偿", "退款链接", "支付宝", "备用金"]
        },
        "gaming_fraud": {
            "name": "游戏交易诈骗",
            "keywords": ["装备交易", "账号买卖", "游戏充值", "折扣", "优惠"]
        },
        "fan_fraud": {
            "name": "追星诈骗",
            "keywords": ["粉丝群", "打榜", "明星福利", "门票", "签名"]
        },
        "medical_fraud": {
            "name": "医保诈骗",
            "keywords": ["异地报销", "医保冻结", "解冻", "额度", "套现"]
        }
    }
    
    # 风险等级定义
    RISK_LEVELS = {
        "safe": {"level": 0, "description": "安全", "action": "正常对话"},
        "attention": {"level": 1, "description": "关注", "action": "温和提醒"},
        "warning": {"level": 2, "description": "警告", "action": "弹窗警告"},
        "danger": {"level": 3, "description": "危险", "action": "强制阻断"},
        "emergency": {"level": 4, "description": "紧急", "action": "立即通知监护人"}
    }
    
    def __init__(self):
        """初始化提示词引擎"""
        self.system_prompt = self._build_system_prompt()
        self.few_shot_examples = self._load_few_shot_examples()
    
    def _build_system_prompt(self) -> str:
        """构建系统提示词"""
        scam_types_text = "\n".join([
            f"  {i+1}. {v['name']}: {', '.join(v['keywords'])}"
            for i, v in enumerate(self.SCAM_TYPES.values())
        ])
        
        return f"""你是SmartGuard智能反诈助手，一位专业的反诈安全顾问。你的任务是帮助用户识别和防范各种类型的电信网络诈骗。

【核心能力】
1. 多模态感知：能够分析文本、语音、图像、视频等多种形式的输入
2. 精准识别：准确判断对话意图和潜在诈骗风险
3. 智能决策：基于知识库和上下文做出风险评估
4. 及时干预：在发现危险时立即采取保护措施
5. 持续进化：不断学习新的诈骗手法，提升防护能力

【支持的诈骗类型】
{scam_types_text}

【风险等级定义】
- 安全(0): 正常交流，无风险特征
- 关注(1): 发现模糊风险信号，需要提醒
- 警告(2): 中度风险特征，需要明确警告
- 危险(3): 高风险特征，需要强制干预
- 紧急(4): 涉及资金转账的紧急情况，需要立即通知监护人

【响应要求】
- 保持专业、友善的服务态度
- 用词通俗易懂，适合各年龄段用户
- 紧急情况下保持冷静，有条理地指导用户

【输出格式】
请以JSON格式输出分析结果：
{{
    "risk_level": 风险等级(0-4),
    "risk_type": 诈骗类型或"normal",
    "confidence": 置信度(0-1),
    "analysis": "分析说明",
    "suggestion": "防护建议",
    "warning_message": "需要显示给用户的警告信息"
}}"""
    
    def _load_few_shot_examples(self) -> List[Dict[str, str]]:
        """加载少样本示例"""
        return [
            {
                "input": "【冒充公检法】您好，我是公安局民警，您的身份证被人盗用，涉嫌一起洗钱案件，现在需要您配合调查，请把资金转入安全账户。",
                "output": '{"risk_level": 4, "risk_type": "police_impersonation", "confidence": 0.95, "analysis": "典型的冒充公检法诈骗手法，包含安全账户、资金核查等关键词", "suggestion": "立即报警，不要转账，核实对方身份", "warning_message": "⚠️ 紧急风险！这是典型的冒充公检法诈骗，真正的警方不会要求转账到安全账户！"}'
            },
            {
                "input": "【投资理财】您好，我是XX投资平台的客服，我们有一款高收益保本理财产品，年化收益率15%，现在加入还能获得新手礼包。",
                "output": '{"risk_level": 3, "risk_type": "investment_fraud", "confidence": 0.88, "analysis": "高收益保本承诺是典型的投资诈骗特征，正规理财产品不会承诺保本", "suggestion": "远离此类平台，高收益必然伴随高风险", "warning_message": "⚠️ 高风险！正规理财产品不会承诺保本，高收益往往是诈骗陷阱！"}'
            },
            {
                "input": "【正常交流】妈，今天我不回家吃饭了，公司加班。你和爸注意身体。",
                "output": '{"risk_level": 0, "risk_type": "normal", "confidence": 0.99, "analysis": "普通的家庭问候，没有任何诈骗特征", "suggestion": "正常交流即可", "warning_message": ""}'
            },
            {
                "input": "【兼职刷单】好消息！足不出户，日赚300-500元！只需手机点赞、收藏、加关注，一单一结，感兴趣请加群。",
                "output": '{"risk_level": 3, "risk_type": "part_time_fraud", "confidence": 0.92, "analysis": "典型的刷单诈骗话术，包含高佣金、足不出户等关键词", "suggestion": "刷单是违法行为，正规兼职不会收取任何费用", "warning_message": "⚠️ 高风险！这是典型的刷单诈骗，前期小恩小惠后期大额投入！"}'
            },
            {
                "input": "【杀猪盘】亲爱的，我发现了一个赚钱的好机会，跟着导师下注，保证稳赚不赔，我已经赚了好几万了，你要不要一起？",
                "output": '{"risk_level": 3, "risk_type": "pig_butchery", "confidence": 0.90, "analysis": "杀猪盘典型话术，通过感情培养诱导投资诈骗", "suggestion": "网络交友需谨慎，涉及金钱投资更要小心", "warning_message": "⚠️ 高风险！这可能是杀猪盘诈骗，请勿轻信网络投资！"}'
            }
        ]
    
    def get_analysis_prompt(self, user_input: str, context: Optional[Dict] = None) -> str:
        """获取分析提示词"""
        context_text = ""
        if context:
            context_text = f"\n\n【上下文信息】\n用户画像: {context.get('user_profile', '未知')}\n历史对话: {context.get('conversation_history', '无')}"
        
        return f"""{self.system_prompt}

【当前输入】
{user_input}
{context_text}

【分析要求】
1. 判断输入内容的风险等级
2. 如果是诈骗，识别具体的诈骗类型
3. 给出置信度和分析说明
4. 提供防护建议

请输出JSON格式的分析结果。"""
    
    def get_multimodal_analysis_prompt(self, text: str, image_desc: str = "", 
                                       audio_desc: str = "") -> str:
        """获取多模态分析提示词"""
        multimodal_context = f"""
【多模态输入】
- 文本内容: {text}
- 图像信息: {image_desc if image_desc else '无'}
- 语音信息: {audio_desc if audio_desc else '无'}
"""
        
        return f"""{self.system_prompt}
{multimodal_context}

【分析要求】
综合分析上述多模态信息，判断整体风险等级。不同模态的信息可以相互印证，提高判断准确性。

请输出JSON格式的分析结果。"""
    
    def get_risk_assessment_prompt(self, base_risk: int, user_profile: Dict) -> str:
        """获取风险评估提示词（考虑用户画像）"""
        profile_text = f"""
【用户画像】
年龄段: {user_profile.get('age_group', '未知')}
职业: {user_profile.get('occupation', '未知')}
历史风险次数: {user_profile.get('risk_history_count', 0)}
风险偏好: {user_profile.get('risk_preference', '未知')}
"""
        
        adjustment_rules = ""
        age_group = user_profile.get('age_group', 'unknown')
        
        if age_group == 'elderly':
            adjustment_rules = """
【老年人风险调整】
- 基础风险等级+1（降低阈值50%）
- 涉及金钱的话题增加确认环节
- 提供更详细的解释和警告"""
        elif age_group == 'minor':
            adjustment_rules = """
【未成年人风险调整】
- 所有涉及转账的话题直接标记为警告
- 增加家长确认提示
- 限制敏感话题讨论"""
        elif age_group == 'accounting':
            adjustment_rules = """
【财会人员风险调整】
- 涉及汇款、转账的话题增加多重验证
- 提示核实对方身份和账户信息
- 要求主管确认"""
        
        return f"""{self.system_prompt}
{profile_text}
{adjustment_rules}

【风险评估调整】
基于用户画像调整后的风险评估：
基础风险等级: {base_risk}

请输出调整后的风险等级和具体建议。"""
    
    def format_warning_message(self, risk_level: int, scam_type: str, 
                               suggestion: str) -> str:
        """格式化警告信息"""
        warning_templates = {
            0: "",
            1: f"💡 温馨提示：{suggestion}",
            2: f"⚠️ 警告：{suggestion}",
            3: f"🚨 危险：{suggestion}",
            4: f"🆘 紧急：{suggestion}\n正在通知您的监护人..."
        }
        
        return warning_templates.get(risk_level, "")
