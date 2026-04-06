"""
FastAPI主应用
多模态反诈智能助手API服务
"""

import asyncio
import time
import os
from typing import Dict, List, Optional, Any
from contextlib import asynccontextmanager

# 设置 HuggingFace 离线模式，防止下载模型
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

# 导入核心模块
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.core.agent import AntiFraudAgent, AgentInput
from src.modules.input_handler import TextInputHandler, AudioInputHandler, VisualInputHandler, VisualInput
from src.modules.intervention import AlertManager, GuardianNotifier, ReportGenerator
from src.modules.recognizer import KnowledgeRetriever
from src.modules.llm import QwenLLM, create_qwen_client
from src.data.vector_store import create_vector_store
from src.data.database import get_database
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


# ==================== Pydantic模型定义 ====================

class UserProfileUpdate(BaseModel):
    """用户画像更新"""
    age_group: Optional[str] = None
    gender: Optional[str] = None
    occupation: Optional[str] = None
    risk_preference: Optional[str] = None


class GuardianAdd(BaseModel):
    """添加监护人"""
    name: str
    phone: str
    relationship: str
    priority: int = 1


class AnalysisRequest(BaseModel):
    """分析请求"""
    text: Optional[str] = None
    modality: str = "text"
    user_id: str = "default_user"
    include_context: bool = True


class AnalysisResponse(BaseModel):
    """分析响应"""
    response: str
    risk_level: int
    risk_type: str
    confidence: float
    analysis: str
    suggestion: str
    warning_message: str
    suggestions: List[str]
    guardian_notified: bool
    processing_time: float


class ReportRequest(BaseModel):
    """报告请求"""
    user_id: str
    report_type: str = "daily"
    start_date: Optional[float] = None
    end_date: Optional[float] = None


# ==================== 生命周期管理 ====================

# 全局组件实例
agent_instances: Dict[str, AntiFraudAgent] = {}
text_handler = TextInputHandler()
knowledge_retriever = KnowledgeRetriever()
alert_manager = AlertManager()
guardian_notifier = GuardianNotifier()
report_generator = ReportGenerator()

# LLM 客户端 (通义千问)
llm_client: Optional[QwenLLM] = None


def init_llm():
    """初始化 LLM 客户端"""
    global llm_client
    from dotenv import load_dotenv
    load_dotenv()

    api_key = os.getenv("DASHSCOPE_API_KEY")
    model = os.getenv("QWEN_MODEL", "qwen-turbo")

    if api_key:
        llm_client = create_qwen_client(api_key=api_key, model=model)
        if llm_client.is_available:
            print(f"[OK] Qwen LLM enabled (model: {model})")
        else:
            print("[WARNING] Qwen LLM init failed")
    else:
        print("[WARNING] DASHSCOPE_API_KEY not set, using local rule engine")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    # 启动时
    print("SmartGuard API starting...")

    # 初始化 LLM
    init_llm()

    # 初始化举报服务
    try:
        from src.services.report_submit_service import report_service
        await report_service.initialize()
        print("[OK] Report service initialized")
    except Exception as e:
        print(f"[WARNING] Failed to init report service: {e}")

    # 初始化全局共享知识库（只加载一次）
    knowledge_base_path = "D:\\agent\\knowledge_base"
    local_model_path = "D:\\agent\\models\\models--shibing624--text2vec-base-chinese"

    from src.core.agent import init_shared_knowledge_base
    init_shared_knowledge_base(knowledge_base_path, local_model_path)

    # 启动邮件监控服务
    try:
        from src.services.email_monitor_service import email_monitor_service
        await email_monitor_service.start_all_monitoring()
        print("[OK] Email monitor service started")
    except Exception as e:
        print(f"[WARNING] Failed to start email monitor: {e}")

    print("[OK] Init complete")

    yield

    # 关闭时
    print("SmartGuard API shutdown")
    
    # 停止邮件监控
    try:
        from src.services.email_monitor_service import email_monitor_service
        await email_monitor_service.stop_all_monitoring()
    except:
        pass


# ==================== FastAPI应用 ====================

app = FastAPI(
    title="SmartGuard API",
    description="多模态反诈智能助手API服务",
    version="1.0.0",
    lifespan=lifespan
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
from src.api.auth import router as auth_router, get_current_user, UserInfo
from src.api.profile import router as profile_router
from src.api.conversations import router as conversations_router
from src.api.guardians import router as guardians_router
from src.api.reports import router as reports_router
from src.api.encyclopedia import router as encyclopedia_router
from src.api.report_submit import router as report_submit_router
from src.api.admin_report import router as admin_router
from src.api.admin_user import router as admin_user_router
from src.api.admin_log import router as admin_log_router
from src.api.email_monitor import router as email_monitor_router

app.include_router(auth_router)
app.include_router(profile_router)
app.include_router(conversations_router)
app.include_router(guardians_router)
app.include_router(reports_router)
app.include_router(encyclopedia_router)
app.include_router(report_submit_router)
app.include_router(admin_router)
app.include_router(admin_user_router)
app.include_router(admin_log_router)
app.include_router(email_monitor_router)


# ==================== 辅助函数 ====================

def get_or_create_agent(user_id: str) -> AntiFraudAgent:
    """获取或创建Agent实例"""
    if user_id not in agent_instances:
        # 知识库路径
        knowledge_base_path = "D:\\agent\\knowledge_base"
        # 本地嵌入模型路径
        local_model_path = "D:\\agent\\models\\models--shibing624--text2vec-base-chinese"

        agent = AntiFraudAgent(
            user_id=user_id,
            llm_client=llm_client,  # 传入 LLM 客户端
            knowledge_base_path=knowledge_base_path,
            local_model_path=local_model_path,
            use_shared_knowledge=True  # 共享知识库
        )
        agent_instances[user_id] = agent
        print(f"[Agent] Agent {user_id} created with LLM: {llm_client is not None and llm_client.is_available}")
    return agent_instances[user_id]


# ==================== 路由定义 ====================

@app.get("/")
async def root():
    """根路径"""
    return {
        "name": "SmartGuard API",
        "version": "1.0.0",
        "status": "running",
        "description": "多模态反诈智能助手API服务"
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "timestamp": time.time()
    }


@app.get("/api/v1/health")
async def api_health_check():
    """API健康检查"""
    return {
        "status": "healthy",
        "timestamp": time.time()
    }


# ==================== 分析接口 ====================

@app.post("/api/v1/analyze", response_model=AnalysisResponse)
async def analyze_content(request: AnalysisRequest):
    """分析内容风险"""
    start_time = time.time()

    try:
        # 获取Agent
        agent = get_or_create_agent(request.user_id)

        # 构建输入
        input_data = AgentInput(
            text=request.text,
            modality=request.modality
        )

        # 处理分析
        result = await agent.process(input_data)

        # 保存预警记录（如果风险等级>=2）
        risk_level = result.risk_assessment.get("risk_level", 0)
        if risk_level >= 2:
            try:
                db = get_database()
                alert_data = {
                    "id": f"alert_{request.user_id}_{int(time.time() * 1000)}",
                    "user_id": request.user_id,
                    "level": risk_level,
                    "risk_type": result.risk_assessment.get("risk_type", "unknown"),
                    "message": request.text[:200] if request.text else "",
                    "content": request.text or "",
                    "response": result.response or "",
                    "acknowledged": 0,
                    "guardian_notified": 1 if result.guardian_notified else 0,
                    "guardian_notifications": "[]",
                    "created_at": time.time()
                }
                await db.insert("alerts", alert_data)
            except Exception as alert_err:
                print(f"[Warning] 保存预警记录失败: {alert_err}")

        processing_time = time.time() - start_time

        return AnalysisResponse(
            response=result.response,
            risk_level=risk_level,
            risk_type=result.risk_assessment.get("risk_type", "normal"),
            confidence=result.risk_assessment.get("confidence", 0.0),
            analysis=result.risk_assessment.get("analysis", ""),
            suggestion=result.risk_assessment.get("suggestion", ""),
            warning_message=result.risk_assessment.get("warning_message", ""),
            suggestions=result.suggestions,
            guardian_notified=result.guardian_notified,
            processing_time=processing_time
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/analyze/text")
async def analyze_text(
    text: str = Form(...),
    user_id: str = Form("default_user")
):
    """分析文本内容"""
    request = AnalysisRequest(
        text=text,
        modality="text",
        user_id=user_id
    )
    return await analyze_content(request)


@app.post("/api/v1/analyze/multimodal")
async def analyze_multimodal(
    text: Optional[str] = Form(None),
    audio: Optional[UploadFile] = File(None),
    image: Optional[UploadFile] = File(None),
    user_id: str = Form("default_user"),
    login_session_id: Optional[str] = Form(None, description="登录会话ID")
):
    """多模态分析"""
    from src.modules.input_handler import AudioInput, VisualInput

    # 处理各种输入
    audio_text = None
    image_desc = None
    has_audio = False
    has_image = False

    # 如果有音频，处理音频
    if audio:
        try:
            audio_bytes = await audio.read()
            audio_input = AudioInput(audio_data=audio_bytes)
            audio_handler = AudioInputHandler()
            audio_result = await audio_handler.process(audio_input)
            audio_text = audio_result.transcription
            has_audio = True
            print(f"[Audio] Transcription: {audio_text}")
        except Exception as e:
            print(f"[ERROR] [Audio] Processing failed: {e}")
            audio_text = None

    # 如果有图片，处理图片
    if image:
        try:
            image_bytes = await image.read()
            visual_input = VisualInput(image_data=image_bytes)
            visual_handler = VisualInputHandler()
            visual_result = await visual_handler.process(visual_input)
            image_desc = visual_result.image_description
            has_image = True
            print(f"[Image] Description: {image_desc}")
        except Exception as e:
            print(f"[ERROR] [Image] Processing failed: {e}")
            image_desc = None

    # 构建文本描述
    combined_text = text or ""

    # 处理音频转写结果
    if audio_text and audio_text not in ["[这是语音转写文本的占位符]", "[Whisper未安装，无法转写音频]", ""]:
        combined_text = f"{combined_text}\n\n【语音转写】\n{audio_text}".strip()
    elif has_audio and not text:
        if audio_text == "[Whisper未安装，无法转写音频]":
            combined_text = f"⚠️ 音频已收到，但当前系统未安装语音识别功能。\n如需分析音频内容，请先安装 Whisper：pip install openai-whisper"
        else:
            combined_text = f"【用户发送了语音消息，内容无法识别】\n⚠️ 当前语音识别功能不可用，请尝试发送文字描述内容。"

    # 处理图片描述结果
    if image_desc and image_desc not in ["[图像描述占位符]", ""]:
        combined_text = f"{combined_text}\n\n【图片描述】\n{image_desc}".strip()
    elif has_image and not text and not combined_text:
        combined_text = f"{combined_text}\n\n【用户发送了图片】\n⚠️ 当前图片识别功能不可用，请描述图片内容。"

    # 如果没有文本输入但有音频/图片转写结果，使用转写结果作为输入
    final_text = combined_text if combined_text else (text or "【无文本内容】")

    # 确定模态
    modalities = []
    if text:
        modalities.append("text")
    if has_audio:
        modalities.append("audio")
    if has_image:
        modalities.append("image")

    modality = "+".join(modalities) if modalities else "text"

    # 构建输入
    input_data = AgentInput(
        text=final_text,
        audio_text=audio_text,
        image_desc=image_desc,
        modality=modality
    )

    # 处理
    agent = get_or_create_agent(user_id)
    result = await agent.process(input_data)

    # === 持久化对话（多模态分析） ===
    if user_id != "default_user":
        try:
            from src.services.conversation_service import ConversationService
            conv_service = ConversationService(user_id, login_session_id)
            risk_level = result.risk_assessment.get("risk_level", 0)
            risk_type = result.risk_assessment.get("risk_type", "normal")
            # 保存用户消息
            content = text or ""
            if image_desc:
                content = f"{content}\n\n【图片】{image_desc}".strip()
            if audio_text:
                content = f"{content}\n\n【音频】{audio_text}".strip()
            await conv_service.add_message(role="user", content=content, mode="risk", metadata={"risk_level": risk_level, "risk_type": risk_type})
            # 保存助手响应
            await conv_service.add_message(role="assistant", content=result.response, mode="risk", metadata={"risk_level": risk_level, "risk_type": risk_type})
        except Exception as e:
            print(f"[Multimodal API] 持久化对话失败: {e}", flush=True)

    return {
        "response": result.response,
        "risk_assessment": result.risk_assessment,
        "suggestions": result.suggestions,
        "guardian_notified": result.guardian_notified
    }


# ==================== 用户管理接口 ====================

@app.get("/api/v1/users/{user_id}/profile")
async def get_user_profile(user_id: str):
    """获取用户画像"""
    agent = get_or_create_agent(user_id)
    profile = agent.memory.user_profile.to_dict()

    return {
        "user_id": user_id,
        "profile": profile
    }


@app.put("/api/v1/users/{user_id}/profile")
async def update_user_profile(user_id: str, update: UserProfileUpdate):
    """更新用户画像"""
    agent = get_or_create_agent(user_id)

    update_data = update.dict(exclude_none=True)
    agent.update_profile(**update_data)

    return {
        "success": True,
        "message": "用户画像已更新"
    }


@app.post("/api/v1/users/{user_id}/guardians")
async def add_guardian(user_id: str, guardian: GuardianAdd):
    """添加监护人"""
    agent = get_or_create_agent(user_id)
    agent.add_guardian(
        name=guardian.name,
        phone=guardian.phone,
        relationship=guardian.relationship
    )

    return {
        "success": True,
        "message": "监护人已添加"
    }


@app.get("/api/v1/users/{user_id}/guardians")
async def get_guardians(user_id: str):
    """获取监护人列表"""
    agent = get_or_create_agent(user_id)
    guardians = agent.memory.user_profile.guardians

    return {
        "user_id": user_id,
        "guardians": guardians
    }


# ==================== 预警接口 ====================

@app.get("/api/v1/users/{user_id}/alerts")
async def get_user_alerts(
    user_id: str,
    unread_only: bool = False,
    limit: int = 20
):
    """获取用户预警列表"""
    alerts = alert_manager.get_user_alerts(user_id, unread_only, limit)

    return {
        "user_id": user_id,
        "total": len(alerts),
        "unread_count": alert_manager.get_unread_count(user_id),
        "alerts": [a.to_dict() for a in alerts]
    }


@app.post("/api/v1/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str, user_id: str):
    """确认预警"""
    success = alert_manager.acknowledge_alert(alert_id, user_id)

    if success:
        return {"success": True, "message": "预警已确认"}
    else:
        raise HTTPException(status_code=404, detail="预警不存在")


@app.get("/api/v1/users/{user_id}/alerts/statistics")
async def get_alert_statistics(user_id: str):
    """获取预警统计"""
    stats = alert_manager.get_statistics(user_id)

    return {
        "user_id": user_id,
        "statistics": stats
    }


# ==================== 知识库接口 ====================

@app.get("/api/v1/knowledge/scam-types")
async def get_scam_types():
    """获取支持的诈骗类型"""
    return {
        "scam_types": [
            {"id": "police_impersonation", "name": "冒充公检法诈骗"},
            {"id": "investment_fraud", "name": "投资理财诈骗"},
            {"id": "part_time_fraud", "name": "兼职刷单诈骗"},
            {"id": "loan_fraud", "name": "虚假贷款诈骗"},
            {"id": "pig_butchery", "name": "杀猪盘诈骗"},
            {"id": "ai_voice_fraud", "name": "AI语音合成诈骗"},
            {"id": "deepfake_fraud", "name": "视频深度伪造诈骗"},
            {"id": "credit_fraud", "name": "虚假征信诈骗"},
            {"id": "refund_fraud", "name": "购物退款诈骗"},
            {"id": "gaming_fraud", "name": "游戏交易诈骗"},
            {"id": "fan_fraud", "name": "追星诈骗"},
            {"id": "medical_fraud", "name": "医保诈骗"}
        ]
    }


@app.get("/api/v1/knowledge/cases")
async def get_similar_cases(
    text: str,
    scam_type: Optional[str] = None,
    top_k: int = 3
):
    """获取相似案例"""
    cases = await knowledge_retriever.get_similar_cases(text, scam_type, top_k)

    return {
        "query": text,
        "cases": cases
    }


@app.get("/api/v1/knowledge/statistics")
async def get_knowledge_statistics():
    """获取知识库统计"""
    stats = knowledge_retriever.get_statistics()

    return stats


# ==================== Agent状态接口 ====================

@app.get("/api/v1/users/{user_id}/status")
async def get_agent_status(user_id: str):
    """获取Agent状态"""
    agent = get_or_create_agent(user_id)
    status = agent.get_status()

    return status


@app.post("/api/v1/users/{user_id}/reset")
async def reset_session(user_id: str):
    """重置会话"""
    agent = get_or_create_agent(user_id)
    agent.reset_session()

    return {
        "success": True,
        "message": "会话已重置"
    }


# ==================== 测试接口 ====================

@app.get("/api/v1/test/cases")
async def get_test_cases():
    """获取测试案例列表"""
    from src.data.test_cases import get_test_dataset

    dataset = get_test_dataset()

    return {
        "statistics": dataset.get_statistics(),
        "cases": [case.to_dict() for case in dataset.get_all_cases()]
    }


@app.post("/api/v1/test/run")
async def run_test_suite():
    """运行测试套件"""
    from src.data.test_cases import get_test_dataset
    import time

    dataset = get_test_dataset()
    cases = dataset.get_all_cases()

    results = {
        "total": len(cases),
        "passed": 0,
        "failed": 0,
        "details": []
    }

    for case in cases:
        agent = get_or_create_agent("test_user")

        input_data = AgentInput(
            text=case.content,
            modality=case.modality
        )

        try:
            start = time.time()
            result = await agent.process(input_data)
            duration = time.time() - start

            # 判断是否正确
            predicted_label = "scam" if result.risk_assessment.get("risk_level", 0) >= 2 else "normal"
            correct = predicted_label == case.label

            if correct:
                results["passed"] += 1
            else:
                results["failed"] += 1

            results["details"].append({
                "case_id": case.case_id,
                "modality": case.modality,
                "expected": case.label,
                "predicted": predicted_label,
                "risk_level": result.risk_assessment.get("risk_level", 0),
                "correct": correct,
                "duration": duration
            })

        except Exception as e:
            results["failed"] += 1
            results["details"].append({
                "case_id": case.case_id,
                "error": str(e),
                "correct": False
            })

    # 计算指标
    results["accuracy"] = results["passed"] / results["total"] if results["total"] > 0 else 0

    return results


async def _update_profile_stats(user_id: str, mode: str = "risk", risk_level: int = 0, risk_type: str = "normal"):
    """更新用户画像统计"""
    try:
        db = get_database()
        
        # 获取当前用户画像
        profiles = await db.query("user_profiles", filters={"user_id": user_id}, limit=1)
        
        now = time.time()
        
        if profiles:
            # 更新现有画像
            profile = profiles[0]
            updates = {
                "updated_at": now,
                "total_consultations": profile.get("total_consultations", 0) + 1,
                f"{mode}_count": profile.get(f"{mode}_count", 0) + 1
            }
            if risk_level >= 2:
                updates["risk_count"] = profile.get("risk_count", 0) + 1
            await db.update("user_profiles", user_id, updates, id_field="user_id")
        else:
            # 创建新画像
            new_profile = {
                "user_id": user_id,
                "total_consultations": 1,
                f"{mode}_count": 1,
                "risk_count": 1 if risk_level >= 2 else 0,
                "created_at": now,
                "updated_at": now
            }
            await db.insert("user_profiles", new_profile)
    except Exception as e:
        print(f"[Profile Stats] 更新失败: {e}", flush=True)


# ==================== 通用对话接口（支持三种模式 + 持久化 + 监护人联动） ====================

@app.post("/api/v1/chat")
async def chat(
    text: Optional[str] = Form(None),
    user_id: str = Form("default_user"),
    mode: str = Form("risk"),
    image: Optional[UploadFile] = File(None),
    history: Optional[str] = Form(None),
    persist: bool = Form(True),
    login_session_id: Optional[str] = Form(None, description="登录会话ID，用于会话分组")
):
    """
    通用对话接口

    支持三种模式：
    - risk: 风险分析模式 - 分析可疑内容是否诈骗
    - chat: 反诈助手模式 - 智能问答，自然聊天
    - learn: 知识百科模式 - 学习诈骗防范知识

    新增功能：
    - 自动保存对话到数据库（persist=True）
    - 高风险时触发监护人通知
    - 按 login_session_id 分组会话
    """
    # 导入服务（延迟加载避免循环依赖）
    try:
        from src.services.conversation_service import ConversationService
        from src.services.guardian_service import GuardianService
    except ImportError as e:
        print(f"[Chat API] 服务导入失败: {e}", flush=True)
        persist = False

    # 获取Agent
    agent = get_or_create_agent(user_id)

    # 处理图片
    image_desc = None
    if image:
        try:
            image_bytes = await image.read()
            visual_input = VisualInput(image_data=image_bytes)
            visual_handler = VisualInputHandler()
            visual_result = await visual_handler.process(visual_input)
            image_desc = visual_result.image_description
            print(f"[Chat API] Image description: {image_desc}")
        except Exception as e:
            print(f"[ERROR] [Chat API] Image processing failed: {e}")

    # 处理历史消息
    chat_history = None
    if history:
        try:
            import json
            chat_history = json.loads(history)
        except:
            chat_history = None

    if mode == "risk":
        # 获取用户画像（与chat/learn模式一致）
        user_profile_risk = None
        try:
            from src.modules.user_profile import UserProfile
            db = get_database()
            profiles = await db.query("user_profiles", filters={"user_id": user_id})
            if profiles:
                import json
                p = profiles[0]
                if isinstance(p.get("interested_scam_types"), str):
                    p["interested_scam_types"] = json.loads(p.get("interested_scam_types", "[]"))
                if isinstance(p.get("learned_topics"), str):
                    p["learned_topics"] = json.loads(p.get("learned_topics", "[]"))
                if isinstance(p.get("quiz_scores"), str):
                    p["quiz_scores"] = json.loads(p.get("quiz_scores", "{}"))
                user_profile_risk = p
        except Exception as e:
            print(f"获取用户画像失败: {e}")

        # 构建用户画像上下文
        profile_context = ""
        if user_profile_risk:
            profile_parts = []
            if user_profile_risk.get("age_group"):
                age_labels = {"18-25": "年轻人", "26-35": "中青年", "36-45": "中年人", "46-55": "中老年", "56+": "老年人"}
                profile_parts.append(f"用户是{age_labels.get(user_profile_risk['age_group'], '')}")
            if user_profile_risk.get("occupation"):
                profile_parts.append(f"职业是{user_profile_risk['occupation']}")
            if user_profile_risk.get("experience_level"):
                level_desc = {"新手": "对诈骗了解较少", "了解": "知道一些常见诈骗", "熟悉": "比较了解各种手法", "专业": "对反诈很有经验"}
                profile_parts.append(level_desc.get(user_profile_risk['experience_level'], ''))
            if user_profile_risk.get("interested_scam_types"):
                interests = user_profile_risk['interested_scam_types']
                if isinstance(interests, list) and interests:
                    profile_parts.append(f"特别关注: {', '.join(interests)}")
            if profile_parts:
                profile_context = "【用户背景】" + "；".join(profile_parts) + "\n\n"

        # 风险分析模式 - 使用规则引擎+LLM
        input_text = text or ""
        if image_desc:
            input_text = f"{input_text}\n\n【图片内容】\n{image_desc}".strip()
        if profile_context:
            input_text = profile_context + input_text
        input_data = AgentInput(text=input_text, modality="text")
        # 通过 context 传入用户画像，供 agent 内部各层使用
        result = await agent.process(input_data, context={"user_profile": user_profile_risk})

        risk_level = result.risk_assessment.get("risk_level", 0)
        risk_type = result.risk_assessment.get("risk_type", "normal")

        # === 保存预警记录（如果风险等级>=2）===
        if persist and user_id != "default_user" and risk_level >= 2:
            try:
                db = get_database()
                alert_data = {
                    "id": f"alert_{user_id}_{int(time.time() * 1000)}",
                    "user_id": user_id,
                    "level": risk_level,
                    "risk_type": risk_type,
                    "message": text[:200] if text else "",
                    "content": text or "",
                    "response": result.response or "",
                    "acknowledged": 0,
                    "guardian_notified": 1 if risk_level >= 3 else 0,
                    "guardian_notifications": "[]",
                    "created_at": time.time()
                }
                await db.insert("alerts", alert_data)
            except Exception as alert_err:
                print(f"[Warning] 保存预警记录失败: {alert_err}", flush=True)

        # === 持久化对话 ===
        if persist and user_id != "default_user":
            try:
                conv_service = ConversationService(user_id, login_session_id)
                await conv_service.add_message(role="user", content=text or "", mode="risk", metadata={"risk_level": risk_level, "risk_type": risk_type})
                await conv_service.add_message(role="assistant", content=result.response, mode="risk", metadata={"risk_level": risk_level, "risk_type": risk_type})
                await _update_profile_stats(user_id, mode="risk", risk_level=risk_level, risk_type=risk_type)
            except Exception as e:
                print(f"[Chat API] 持久化对话失败: {e}", flush=True)

        # === 高风险触发监护人通知 ===
        guardian_notify_result = None
        if persist and user_id != "default_user" and risk_level >= 3:
            try:
                guardian_service = GuardianService(user_id)
                guardian_notify_result = await guardian_service.trigger_risk_notification(
                    risk_level=risk_level,
                    risk_type=risk_type,
                    content=text or "",
                    response=result.response
                )
                if guardian_notify_result.get("notified"):
                    print(f"[Chat API] 监护人已通知: {guardian_notify_result}", flush=True)
            except Exception as e:
                print(f"[Chat API] 监护人通知失败: {e}", flush=True)

        response = {
            "response": result.response,
            "risk_assessment": result.risk_assessment,
            "suggestions": result.suggestions
        }
        if guardian_notify_result:
            response["guardian_notification"] = guardian_notify_result
        return response

    elif mode in ["chat", "learn"]:
        # 反诈助手/知识百科模式 - 直接调用LLM
        # 获取用户画像
        user_profile = None
        try:
            from src.modules.user_profile import UserProfile
            db = get_database()
            profiles = await db.query("user_profiles", filters={"user_id": user_id})
            if profiles:
                import json
                p = profiles[0]
                if isinstance(p.get("interested_scam_types"), str):
                    p["interested_scam_types"] = json.loads(p.get("interested_scam_types", "[]"))
                if isinstance(p.get("learned_topics"), str):
                    p["learned_topics"] = json.loads(p.get("learned_topics", "[]"))
                if isinstance(p.get("quiz_scores"), str):
                    p["quiz_scores"] = json.loads(p.get("quiz_scores", "{}"))
                user_profile = p
        except Exception as e:
            print(f"获取用户画像失败: {e}")

        # 获取LLM响应和风险评估
        llm_result = await llm_chat_mode(
            text, mode, agent, image_desc, chat_history, user_profile,
            user_id=user_id, login_session_id=login_session_id
        )
        response = llm_result.get("response", "")
        risk_assessment = llm_result.get("risk_assessment", {})
        risk_level = risk_assessment.get("risk_level", 0)
        risk_type = risk_assessment.get("risk_type", "normal")

        # === 持久化对话（chat/learn模式） ===
        if persist and user_id != "default_user":
            try:
                conv_service = ConversationService(user_id, login_session_id)
                await conv_service.add_message(role="user", content=text or "", mode=mode, metadata={"risk_level": risk_level, "risk_type": risk_type})
                await conv_service.add_message(role="assistant", content=response, mode=mode, metadata={"risk_level": risk_level, "risk_type": risk_type})
                await _update_profile_stats(user_id, mode=mode, risk_level=risk_level, risk_type=risk_type)
            except Exception as e:
                print(f"[Chat API] 持久化对话失败: {e}", flush=True)

        # === 高风险触发监护人通知 ===
        guardian_notify_result = None
        if persist and user_id != "default_user" and risk_level >= 3:
            try:
                guardian_service = GuardianService(user_id)
                guardian_notify_result = await guardian_service.trigger_risk_notification(
                    risk_level=risk_level,
                    risk_type=risk_type,
                    content=text or "",
                    response=response
                )
                if guardian_notify_result.get("notified"):
                    print(f"[Chat API] 监护人已通知: {guardian_notify_result}", flush=True)
            except Exception as e:
                print(f"[Chat API] 监护人通知失败: {e}", flush=True)

        # === 智能学习进化：记录案例供学习 ===
        if persist and user_id != "default_user" and risk_level >= 2:
            try:
                from src.services.evolution_service import get_evolution_service
                evolution_service = get_evolution_service()
                await evolution_service.record_case(
                    user_id=user_id,
                    content=text or "",
                    risk_level=risk_level,
                    risk_type=risk_type,
                    analysis=final_analysis,
                    response=response
                )
            except Exception as e:
                print(f"[Evolution] 记录学习案例失败: {e}", flush=True)

        # === 构建响应 ===
        result = {
            "response": response,
            "risk_assessment": risk_assessment,
            "suggestions": []
        }
        if guardian_notify_result:
            result["guardian_notification"] = guardian_notify_result
        
        return result

    else:
        input_data = AgentInput(text=text or "", modality="text")
        result = await agent.process(input_data)

        risk_level = result.risk_assessment.get("risk_level", 0)
        risk_type = result.risk_assessment.get("risk_type", "normal")

        # === 保存预警记录（如果风险等级>=2）===
        if persist and user_id != "default_user" and risk_level >= 2:
            try:
                db = get_database()
                alert_data = {
                    "id": f"alert_{user_id}_{int(time.time() * 1000)}",
                    "user_id": user_id,
                    "level": risk_level,
                    "risk_type": risk_type,
                    "message": text[:200] if text else "",
                    "content": text or "",
                    "response": result.response or "",
                    "acknowledged": 0,
                    "guardian_notified": 1 if result.guardian_notified else 0,
                    "guardian_notifications": "[]",
                    "created_at": time.time()
                }
                await db.insert("alerts", alert_data)
            except Exception as alert_err:
                print(f"[Warning] 保存预警记录失败: {alert_err}", flush=True)

        # === 持久化对话 ===
        if persist and user_id != "default_user":
            try:
                conv_service = ConversationService(user_id, login_session_id)
                await conv_service.add_message(role="user", content=text or "", mode=mode, metadata={"risk_level": risk_level, "risk_type": risk_type})
                await conv_service.add_message(role="assistant", content=result.response, mode=mode, metadata={"risk_level": risk_level, "risk_type": risk_type})
                await _update_profile_stats(user_id, mode="risk", risk_level=risk_level, risk_type=risk_type)
            except Exception as e:
                print(f"[Chat API] 持久化对话失败: {e}", flush=True)

        return {
            "response": result.response,
            "risk_assessment": result.risk_assessment,
            "suggestions": result.suggestions
        }


async def llm_chat_mode(
    text: Optional[str],
    mode: str,
    agent: AntiFraudAgent,
    image_desc: Optional[str] = None,
    chat_history: Optional[List[Dict]] = None,
    user_profile: Optional[Dict] = None,
    user_id: str = "default_user",
    login_session_id: Optional[str] = None
) -> Dict:
    """使用LLM进行对话，返回响应和风险评估"""
    global llm_client

    # 构建完整的用户消息
    user_message = text or ""
    if image_desc and image_desc not in ["[图像描述占位符]", ""]:
        user_message = f"{user_message}\n\n【用户发送了一张图片，图片内容描述如下】\n{image_desc}".strip()

    if not user_message.strip():
        user_message = "你好"  # 默认消息

    # 构建用户画像上下文
    profile_context = ""
    if user_profile:
        profile_parts = []
        if user_profile.get("age_group"):
            age_labels = {"18-25": "年轻人", "26-35": "中青年", "36-45": "中年人", "46-55": "中老年", "56+": "老年人"}
            profile_parts.append(f"用户是{age_labels.get(user_profile['age_group'], '')}")
        if user_profile.get("occupation"):
            profile_parts.append(f"职业是{user_profile['occupation']}")
        if user_profile.get("experience_level"):
            level_desc = {"新手": "对诈骗了解较少", "了解": "知道一些常见诈骗", "熟悉": "比较了解各种手法", "专业": "对反诈很有经验"}
            profile_parts.append(level_desc.get(user_profile['experience_level'], ''))
        if user_profile.get("interested_scam_types"):
            interests = user_profile['interested_scam_types']
            if isinstance(interests, list) and interests:
                profile_parts.append(f"特别关注: {', '.join(interests)}")
        if profile_parts:
            profile_context = "【用户背景】" + "；".join(profile_parts) + "\n\n"

    # ==================== 加载完整对话历史（确保记忆连贯） ====================
    # 优先使用传入的 chat_history，如果没有则从数据库加载
    full_history = chat_history.copy() if chat_history else []
    
    # 从 full_history 中移除最后一条用户消息（因为 text 参数已经包含它了，避免重复）
    if full_history and len(full_history) > 0:
        last_msg = full_history[-1]
        if last_msg.get("role") == "user" and last_msg.get("content") == (text or ""):
            full_history = full_history[:-1]
            print(f"[LLM Chat] 移除重复的最后一条用户消息", flush=True)
    
    if not full_history and user_id != "default_user":
        # 从数据库加载该模式的历史对话
        try:
            from src.services.conversation_service import ConversationService
            conv_service = ConversationService(user_id, login_session_id)
            # 获取当前模式最近的20条消息作为上下文
            db_messages = await conv_service.get_messages(mode=mode, limit=20)
            
            # 过滤出当前模式的消息（如果有）
            mode_messages = [m for m in db_messages if m.get("mode") == mode or not m.get("mode")]
            
            # 转换为聊天格式
            for m in mode_messages:
                role = m.get("role", "user")
                content = m.get("content", m.get("text", ""))
                if content:
                    full_history.append({"role": role, "content": content})
                    
            print(f"[LLM Chat] 从数据库加载了 {len(full_history)} 条历史消息 (mode={mode})", flush=True)
        except Exception as e:
            print(f"[LLM Chat] 加载历史失败: {e}", flush=True)

    # ==================== 风险检测（在chat模式中检测用户是否正在被骗）====================
    # 第一步：快速关键词检测（作为LLM分析的参考上下文）
    risk_level = 0
    risk_type = "normal"
    risk_analysis = ""
    keyword_found = None
    
    # 定义风险关键词
    risk_keywords = {
        4: ["公安", "警察", "检察院", "法院", "通缉", "洗钱", "犯罪", "违法", "逮捕", "涉案"],
        3: ["转账", "汇款", "打钱", "付款", "充值", "投资", "理财", "赚钱", "博彩", "赌博", 
            "验证码", "密码", "账户", "银行卡", "安全账户", "核查", "保证金"],
        2: ["帮我", "借我", "急需", "紧急", "快点", "马上", "快点转", "先转", "转给我"],
        1: ["红包", "返利", "佣金", "中奖", "免费", "优惠", "打折", "赚钱", "兼职", "日结"]
    }
    
    text_lower = (text or "").lower()
    
    # 检测风险关键词（从高到低）
    for level in [4, 3, 2, 1]:
        for keyword in risk_keywords.get(level, []):
            if keyword in text_lower:
                risk_level = level
                risk_type = _detect_risk_type(text_lower)
                keyword_found = keyword
                risk_analysis = f"初步检测关键词: {keyword}"
                break
        if keyword_found:
            break
    
    # 第二步：LLM深入分析（将关键词检测结果作为参考，由LLM最终决定风险等级）
    response_text = ""
    final_risk_level = 0
    final_risk_type = "normal"
    final_analysis = ""
    
    if llm_client and llm_client.is_available:
        if mode == "chat":
            # 构建关键词检测上下文
            keyword_context = f"初步关键词检测结果：等级{risk_level}，关键词「{keyword_found}」" if keyword_found else "初步关键词检测：无明显风险关键词"
            
            system_prompt = f"""{profile_context}你叫SmartGuard，是一位专业、友善的反诈助手。

重要任务：你需要分析用户消息，判断是否存在诈骗风险。

{keyword_context}

分析要求：
1. 结合对话历史上下文进行综合判断
2. 不要仅依赖关键词，要看整体语义和意图
3. 警惕常见的诈骗话术和模式
4. 如果用户表现出被操控或洗脑的迹象，要提高风险等级

回复格式（必须严格遵守）：
[AI回复内容...]

[RISK_ANALYSIS]
risk_level: <0-5的数字，0=安全，5=极危>
risk_type: <风险类型，如 normal/police_impersonation/investment_fraud/loan_fraud 等>
analysis: <简要分析说明，20字以内>
[/RISK_ANALYSIS]

风险等级参考：
- 0: 安全（正常聊天、咨询反诈知识等）
- 1: 关注（涉及金钱相关但无明显风险意图）
- 2: 警告（有可疑表述，但不确定是否在被骗）
- 3: 危险（明显可疑，很可能正在被骗）
- 4: 紧急（高度可疑，正在被骗）
- 5: 极危（确认被骗或正在被深度洗脑，需立即干预）"""
        else:
            system_prompt = """你是一位反诈教育专家，负责向用户讲解各种诈骗手法和防范知识。

你的讲解风格：
- 生动有趣，用真实案例说明问题
- 重点突出，让大家记住关键点
- 实用性强，讲解防范技巧
- 语言通俗易懂，老少皆宜

讲解内容包括但不限于：
- 冒充公检法诈骗
- 杀猪盘（网恋诈骗）
- 兼职刷单诈骗
- 投资理财诈骗
- 虚假贷款诈骗
- AI诈骗（语音合成、换脸）
- 购物退款诈骗
- 虚假征信诈骗

每次讲解要包含：
1. 骗子的套路（怎么骗的）
2. 真实案例（让人警醒）
3. 防范技巧（实用有效）

用通俗易懂的语言，让用户听完就能记住！"""

        # 构建消息列表（使用完整历史上下文）
        messages = []
        for h in full_history:
            role = h.get("role", "user")
            content = h.get("content", "")
            if role == "assistant":
                messages.append({"role": "assistant", "content": content})
            else:
                messages.append({"role": "user", "content": content})

        messages.append({"role": "user", "content": user_message})

        try:
            raw_response = await llm_client.chat(messages, system_prompt=system_prompt)
            
            # 解析LLM返回的风险分析
            import re
            risk_match = re.search(r'\[RISK_ANALYSIS\]\s*risk_level:\s*(\d+)\s*risk_type:\s*(\w+)\s*analysis:\s*(.+?)\s*\[/RISK_ANALYSIS\]', raw_response, re.DOTALL)
            
            if risk_match:
                final_risk_level = int(risk_match.group(1))
                final_risk_type = risk_match.group(2).strip()
                final_analysis = risk_match.group(3).strip()
                
                # 提取AI回复部分（去掉风险分析标签）
                response_text = re.sub(r'\[RISK_ANALYSIS\].*?\[/RISK_ANALYSIS\]', '', raw_response, flags=re.DOTALL).strip()
            else:
                # 无法解析风险标签，保守处理
                response_text = raw_response
                final_risk_level = 0
                final_analysis = "无法解析LLM风险评估"
                
        except Exception as e:
            response_text = f"抱歉，AI服务暂时不可用: {str(e)}\n\n请稍后再试。"
            final_risk_level = 0
            final_analysis = f"LLM调用失败: {str(e)}"

    else:
        response_text = """嗨！我现在无法连接到AI服务（LLM未配置或不可用）。

请在 .env 文件中设置 DASHSCOPE_API_KEY 来启用AI对话功能。

或者你可以切换到「风险分析」模式，我可以帮你分析可疑内容。"""
        final_risk_level = 0
        final_analysis = "LLM不可用"

    # 返回响应和风险评估（使用LLM的最终决定）
    return {
        "response": response_text,
        "risk_assessment": {
            "risk_level": final_risk_level,
            "risk_type": final_risk_type,
            "analysis": final_analysis,
            "confidence": 0.9 if final_risk_level >= 3 else 0.6
        }
    }


def _detect_risk_type(text: str) -> str:
    """检测风险类型"""
    if any(k in text for k in ["公安", "警察", "检察院", "法院", "通缉", "洗钱"]):
        return "police_impersonation"
    if any(k in text for k in ["投资", "理财", "赚钱", "平台", "导师", "内幕"]):
        return "investment_fraud"
    if any(k in text for k in ["转账", "汇款", "账户", "银行卡", "安全账户"]):
        return "financial_fraud"
    if any(k in text for k in ["刷单", "兼职", "点赞", "佣金"]):
        return "part_time_fraud"
    if any(k in text for k in ["贷款", "无抵押", "快速放款"]):
        return "loan_fraud"
    return "unknown"


# ==================== LLM 接口 ====================

class LLMChatRequest(BaseModel):
    """LLM 对话请求"""
    message: str
    system_prompt: Optional[str] = None
    temperature: Optional[float] = None


class LLMAnalysisRequest(BaseModel):
    """LLM 风险分析请求"""
    text: str
    context: Optional[Dict[str, Any]] = None


@app.get("/api/v1/llm/status")
async def get_llm_status():
    """获取 LLM 状态"""
    if llm_client is None:
        return {
            "available": False,
            "message": "LLM 未初始化，请设置 DASHSCOPE_API_KEY"
        }

    return {
        "available": llm_client.is_available,
        "model": llm_client.config.model,
        "message": "通义千问 LLM 已就绪" if llm_client.is_available else "LLM 初始化失败"
    }


@app.post("/api/v1/llm/chat")
async def llm_chat(request: LLMChatRequest):
    """LLM 对话接口"""
    if not llm_client or not llm_client.is_available:
        raise HTTPException(status_code=503, detail="LLM 服务不可用")

    messages = [{"role": "user", "content": request.message}]

    kwargs = {}
    if request.temperature:
        kwargs["temperature"] = request.temperature

    try:
        response = await llm_client.chat(
            messages,
            system_prompt=request.system_prompt,
            **kwargs
        )
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/llm/analyze-risk")
async def llm_analyze_risk(request: LLMAnalysisRequest):
    """LLM 风险分析"""
    if not llm_client or not llm_client.is_available:
        raise HTTPException(status_code=503, detail="LLM 服务不可用")

    try:
        result = await llm_client.analyze_risk(request.text, request.context)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 进化服务接口 ====================

@app.get("/api/v1/evolution/stats")
async def get_evolution_stats(current_user: UserInfo = Depends(get_current_user)):
    """获取进化统计"""
    from src.services.evolution_service import get_evolution_service
    service = get_evolution_service()
    return service.get_evolution_stats()


@app.get("/api/v1/evolution/knowledge")
async def get_learned_knowledge(
    scam_type: Optional[str] = None,
    current_user: UserInfo = Depends(get_current_user)
):
    """获取学习到的知识"""
    from src.services.evolution_service import get_evolution_service
    service = get_evolution_service()
    return service.get_learned_knowledge(scam_type)


@app.post("/api/v1/evolution/evolve")
async def trigger_evolution(current_user: UserInfo = Depends(get_current_user)):
    """手动触发一次进化学习"""
    from src.services.evolution_service import get_evolution_service
    service = get_evolution_service()
    result = await service.auto_evolve()
    return result


@app.post("/api/v1/evolution/manual-learn")
async def manual_learn_cases(
    cases: List[Dict[str, Any]],
    current_user: UserInfo = Depends(get_current_user)
):
    """手动导入案例学习"""
    from src.services.evolution_service import get_evolution_service
    service = get_evolution_service()
    result = await service.manual_learn(cases)
    return result


# ==================== 启动服务 ====================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
