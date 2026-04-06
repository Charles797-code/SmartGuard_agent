"""
智能体主逻辑模块
基于LangGraph的智能体编排，实现"感知-决策-干预-进化"能力
"""

import json
import time
import asyncio
import os
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from enum import Enum

# 导入核心模块
from .prompts import PromptEngine
from .memory import ConversationMemory
from .decision import RiskDecisionEngine, RiskAssessment


# ==================== 全局共享知识库 ====================
_shared_vector_store = None
_shared_embedding_model = None
_shared_knowledge_loaded = False


def get_shared_vector_store():
    """获取全局共享的向量存储"""
    global _shared_vector_store, _shared_embedding_model, _shared_knowledge_loaded
    return _shared_vector_store


def init_shared_knowledge_base(knowledge_base_path: str, local_model_path: str):
    """初始化全局共享的知识库（只调用一次）"""
    global _shared_vector_store, _shared_embedding_model, _shared_knowledge_loaded
    
    if _shared_knowledge_loaded:
        return _shared_vector_store
    
    from .knowledge_base import KnowledgeBaseLoader
    from .vector_store import VectorStore, LocalEmbeddings
    
    print(f"[RAG] Initializing global shared knowledge base...")
    
    # 加载文档
    loader = KnowledgeBaseLoader(knowledge_base_path)
    documents = loader.load_folder()
    
    if not documents:
        print(f"[WARNING] [RAG] Knowledge base is empty")
        return None
    
    print(f"[RAG] Knowledge base contains {len(documents)} documents")
    
    # 自动检测 GPU
    try:
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"[RAG] Device: {device}")
    except ImportError:
        device = "cpu"
    
    # 创建嵌入模型
    _shared_embedding_model = LocalEmbeddings(
        model_name="shibing624/text2vec-base-chinese",
        local_model_path=local_model_path,
        device=device
    )
    
    # 创建向量存储（使用固定路径，不含user_id）
    storage_path = "data/vector_store_shared"
    _shared_vector_store = VectorStore(
        embedding_model=_shared_embedding_model,
        storage_path=storage_path
    )
    
    # 尝试加载缓存
    if _shared_vector_store.load():
        _shared_knowledge_loaded = True
        stats = _shared_vector_store.get_stats()
        print(f"[OK] [RAG] Loaded shared vector index from cache: {stats['count']} chunks")
        return _shared_vector_store
    
    # 需要重新嵌入
    print(f"[RAG] Building shared vector index...")
    count = _shared_vector_store.add_documents(documents)
    _shared_vector_store.save()
    _shared_knowledge_loaded = True
    print(f"[OK] [RAG] Shared knowledge base loaded: {len(documents)} docs, {count} chunks")
    
    return _shared_vector_store


class AgentState(Enum):
    """智能体状态"""
    IDLE = "idle"
    RECEIVING = "receiving"
    ANALYZING = "analyzing"
    REASONING = "reasoning"
    WARNING = "warning"
    ACTING = "acting"
    RESPONDING = "responding"
    EVOLVING = "evolving"


class InputModality(Enum):
    """输入模态"""
    TEXT = "text"
    AUDIO = "audio"
    IMAGE = "image"
    VIDEO = "video"
    MULTIMODAL = "multimodal"


@dataclass
class AgentInput:
    """智能体输入"""
    text: Optional[str] = None
    audio_path: Optional[str] = None
    audio_text: Optional[str] = None
    image_path: Optional[str] = None
    image_desc: Optional[str] = None
    video_path: Optional[str] = None
    modality: str = InputModality.TEXT.value
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentOutput:
    """智能体输出"""
    response: str
    risk_assessment: Dict
    actions_taken: List[str]
    state: str
    suggestions: List[str]
    guardian_notified: bool = False
    warning_displayed: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


class AntiFraudAgent:
    """
    多模态反诈智能体
    
    具备四大核心能力：
    1. 感知：多模态输入感知（文本、语音、图像、视频）
    2. 决策：智能风险识别与决策
    3. 干预：分级预警与监护人联动
    4. 进化：自适应学习与知识更新
    """
    
    def __init__(
        self,
        user_id: str,
        llm_client: Optional[Any] = None,
        vector_store: Optional[Any] = None,
        enable_guardian: bool = True,
        config: Optional[Dict] = None,
        knowledge_base_path: Optional[str] = None,
        embedding_type: str = "local",
        local_model_path: Optional[str] = None,
        use_shared_knowledge: bool = False
    ):
        """
        初始化智能体

        Args:
            user_id: 用户ID
            llm_client: LLM客户端（可选，用于接入大模型API）
            vector_store: 向量存储（可选，用于知识库检索）
            enable_guardian: 是否启用监护人功能
            config: 配置参数
            knowledge_base_path: 知识库文件夹路径（可选）
            embedding_type: 嵌入类型，"openai" 或 "local"
            local_model_path: 本地嵌入模型路径（可选）
            use_shared_knowledge: 是否使用全局共享知识库（推荐）
        """
        self.user_id = user_id
        self.llm_client = llm_client
        self.vector_store = vector_store
        self.enable_guardian = enable_guardian
        self.knowledge_base_path = knowledge_base_path
        self.local_model_path = local_model_path
        self.use_shared_knowledge = use_shared_knowledge

        # 配置
        self.config = config or self._default_config()

        # 核心组件
        self.prompt_engine = PromptEngine()
        self.memory = ConversationMemory(user_id)
        self.decision_engine = RiskDecisionEngine()

        # 知识库加载
        self._knowledge_loaded = False
        self._knowledge_documents = []
        self._relevant_docs = []

        # 如果提供了知识库路径，自动加载
        if knowledge_base_path:
            print(f"[RAG] Agent {user_id} checking knowledge base path: {knowledge_base_path}")
            if os.path.exists(knowledge_base_path):
                if use_shared_knowledge:
                    # 使用全局共享知识库
                    self.vector_store = get_shared_vector_store()
                    if self.vector_store:
                        self._knowledge_loaded = True
                        stats = self.vector_store.get_stats()
                        print(f"[RAG] Agent {user_id} using shared knowledge base: {stats['count']} chunks")
                    else:
                        print(f"[WARNING] [RAG] Agent {user_id} shared knowledge base not initialized")
                else:
                    # 独立的知识库（每个user_id单独加载）
                    print(f"[OK] [RAG] Agent {user_id} loading private knowledge base...")
                    self._load_knowledge_base(embedding_type)
            else:
                print(f"[ERROR] [RAG] Agent {user_id} knowledge base path does not exist")
        
        # 状态
        self.current_state = AgentState.IDLE
        self.session_start = time.time()
        self.interaction_count = 0
        
        # 干预组件（延迟初始化）
        self._guardian_notifier = None
        self._alert_manager = None
    
    def _load_knowledge_base(self, embedding_type: str = "local"):
        """加载知识库（独立的，非共享模式）"""
        try:
            from .knowledge_base import KnowledgeBaseLoader
            from .vector_store import VectorStore

            # 使用固定存储路径（不带user_id），这样不同user_id可以复用缓存
            storage_path = Path("data/vector_store_default")
            index_file = storage_path / "index.pkl"

            if index_file.exists():
                print(f"发现已缓存的向量索引: {index_file}")

            # 加载文档
            loader = KnowledgeBaseLoader(self.knowledge_base_path)
            documents = loader.load_folder()

            if not documents:
                print(f"知识库为空: {self.knowledge_base_path}")
                return

            # 创建向量存储
            embedding_model = None

            if embedding_type == "openai":
                try:
                    from .vector_store import OpenAIEmbeddings
                    embedding_model = OpenAIEmbeddings()
                    print("使用 OpenAI 嵌入模型")
                except Exception as e:
                    print(f"OpenAI 嵌入模型加载失败: {e}")

            if embedding_model is None:
                try:
                    from .vector_store import LocalEmbeddings
                    # 自动检测 GPU
                    try:
                        import torch
                        device = "cuda" if torch.cuda.is_available() else "cpu"
                    except ImportError:
                        device = "cpu"
                    embedding_model = LocalEmbeddings(
                        model_name="shibing624/text2vec-base-chinese",
                        local_model_path=self.local_model_path,
                        device=device
                    )
                    print(f"使用本地嵌入模型 (device={device})")
                except Exception as e:
                    print(f"本地嵌入模型加载失败: {e}")

            if embedding_model is None:
                # 使用 TF-IDF 备选方案
                print("使用 TF-IDF 备选方案")
                self.vector_store = None
                self._knowledge_documents = documents
                self._knowledge_loaded = True
                print(f"知识库加载完成（TF-IDF模式）: {len(documents)} 文档")
                return

            self.vector_store = VectorStore(
                embedding_model=embedding_model,
                storage_path=str(storage_path)
            )

            # 尝试加载已缓存的索引
            if self.vector_store.load():
                self._knowledge_loaded = True
                stats = self.vector_store.get_stats()
                print(f"从缓存加载向量索引: {stats['count']} 个文档块")
                return

            # 没有缓存，需要重新嵌入
            print(f"正在加载 {len(documents)} 个文档...")

            # 添加文档
            count = self.vector_store.add_documents(documents)
            self._knowledge_loaded = True

            # 保存索引到缓存
            self.vector_store.save()

            print(f"知识库加载完成: {len(documents)} 文档, {count} 文本块")
            
        except Exception as e:
            print(f"知识库加载失败: {e}")
            self._knowledge_loaded = False
            self.vector_store = None
            self._knowledge_documents = []
    
    def _default_config(self) -> Dict:
        """默认配置"""
        return {
            "risk_threshold_emergency": 4,
            "risk_threshold_danger": 3,
            "risk_threshold_warning": 2,
            "auto_notify_guardian": True,
            "guardian_delay_seconds": 3,
            "max_context_messages": 10,
            "enable_voice_processing": True,
            "enable_image_processing": True,
            "confidence_threshold": 0.7,
            "multimodal_fusion": True,
            "response_timeout": 30,
            "max_retry": 3
        }
    
    async def process(
        self,
        input_data: AgentInput,
        context: Optional[Dict] = None
    ) -> AgentOutput:
        """
        处理输入并生成响应
        
        Args:
            input_data: 智能体输入
            context: 上下文信息
            
        Returns:
            AgentOutput: 智能体输出
        """
        start_time = time.time()
        actions_taken = []
        
        try:
            # 1. 状态更新：接收输入
            self.current_state = AgentState.RECEIVING
            self.interaction_count += 1
            
            # 2. 状态更新：分析输入
            self.current_state = AgentState.ANALYZING
            processed_input = await self._preprocess_input(input_data)
            
            # 3. 状态更新：推理决策
            self.current_state = AgentState.REASONING
            risk_assessment = await self._assess_risk(processed_input, context)
            
            # 4. 状态更新：预警干预
            self.current_state = AgentState.WARNING
            if risk_assessment.risk_level >= self.config["risk_threshold_warning"]:
                warning_actions = await self._handle_risk(risk_assessment)
                actions_taken.extend(warning_actions)
            
            # 5. 生成响应
            self.current_state = AgentState.RESPONDING
            response = await self._generate_response(
                processed_input, risk_assessment
            )
            
            # 6. 保存到记忆
            self._save_to_memory(input_data, processed_input, response, risk_assessment)
            
            # 7. 状态更新：知识进化（定期执行）
            if self.interaction_count % 10 == 0:
                asyncio.create_task(self._evolve_knowledge())
            
            self.current_state = AgentState.IDLE
            
            # 构建输出
            return AgentOutput(
                response=response,
                risk_assessment=risk_assessment.to_dict(),
                actions_taken=actions_taken,
                state=self.current_state.value,
                suggestions=risk_assessment.recommended_actions,
                guardian_notified="guardian" in str(actions_taken).lower(),
                warning_displayed=risk_assessment.risk_level >= 2,
                metadata={
                    "processing_time": time.time() - start_time,
                    "modality": input_data.modality,
                    "interaction_count": self.interaction_count
                }
            )
            
        except Exception as e:
            self.current_state = AgentState.IDLE
            return AgentOutput(
                response=f"抱歉，处理您的请求时遇到了一些问题。错误信息：{str(e)}",
                risk_assessment={"error": str(e)},
                actions_taken=[],
                state=self.current_state.value,
                suggestions=["请稍后重试"]
            )
    
    async def _preprocess_input(self, input_data: AgentInput) -> Dict:
        """预处理输入"""
        result = {
            "text": input_data.text or "",
            "audio_text": input_data.audio_text,
            "image_desc": input_data.image_desc,
            "modality": input_data.modality
        }
        
        # 多模态融合描述
        multimodal_parts = []
        
        if result["text"]:
            multimodal_parts.append(f"文本内容：{result['text']}")
        
        if result["audio_text"]:
            multimodal_parts.append(f"语音内容：{result['audio_text']}")
        
        if result["image_desc"]:
            multimodal_parts.append(f"图像描述：{result['image_desc']}")
        
        result["multimodal_description"] = "\n".join(multimodal_parts)
        
        return result
    
    async def _search_knowledge_base(
        self,
        query: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        搜索知识库
        
        Args:
            query: 查询文本
            top_k: 返回数量
            
        Returns:
            相似文档列表
        """
        # 使用统一的检索方法
        return await self._retrieve_similar_cases(query, top_k)
    
    def get_knowledge_context(self, query: str, top_k: int = 3) -> str:
        """
        获取知识库上下文（同步方法）
        
        Args:
            query: 查询文本
            top_k: 返回数量
            
        Returns:
            格式化的上下文字符串
        """
        # 优先使用向量存储
        if self.vector_store:
            try:
                results = self.vector_store.search(query, top_k=top_k)
                
                if not results:
                    return self._get_knowledge_context_fallback(query, top_k)
                
                context_parts = ["【反诈知识库参考】"]
                
                for i, doc in enumerate(results, 1):
                    title = doc.get("title", "未知")
                    source = doc.get("source", "")
                    content = doc.get("content", "")
                    similarity = doc.get("similarity", 0)
                    
                    context_parts.append(
                        f"\n{i}. {title} (匹配度: {similarity:.2f})"
                        f"\n来源: {source}"
                        f"\n内容: {content[:300]}..."
                    )
                
                return "\n".join(context_parts)
                
            except Exception as e:
                print(f"获取知识库上下文失败: {e}")
                return self._get_knowledge_context_fallback(query, top_k)
        
        return self._get_knowledge_context_fallback(query, top_k)
    
    def _get_knowledge_context_fallback(self, query: str, top_k: int = 3) -> str:
        """获取知识库上下文（TF-IDF 备选）"""
        if not hasattr(self, '_knowledge_documents') or not self._knowledge_documents:
            return ""
        
        results = self._tfidf_search(query, top_k)
        
        if not results:
            return ""
        
        context_parts = ["【反诈知识库参考】"]
        
        for i, doc in enumerate(results, 1):
            title = doc.get("title", "未知")
            source = doc.get("source", "")
            content = doc.get("content", "")
            similarity = doc.get("similarity", 0)
            
            context_parts.append(
                f"\n{i}. {title} (匹配度: {similarity:.2f})"
                f"\n来源: {source}"
                f"\n内容: {content[:300]}..."
            )
        
        return "\n".join(context_parts)
    
    async def _assess_risk(
        self,
        processed_input: Dict,
        context: Optional[Dict]
    ) -> RiskAssessment:
        """风险评估"""
        # 获取用户画像上下文
        profile_context = self.memory.get_user_profile_context()
        
        # 获取对话历史上下文
        history_context = {
            "conversation_history": self.memory.get_context_for_llm(
                self.config["max_context_messages"]
            )
        }
        
        # 合并上下文
        full_context = {
            **profile_context,
            **history_context,
            **(context or {})
        }
        
        # 如果有向量存储，检索相关案例
        relevant_cases = []
        # 优先使用向量存储，否则使用 TF-IDF 备选方案
        if self.vector_store and processed_input["text"]:
            relevant_cases = await self._retrieve_similar_cases(
                processed_input["text"]
            )
            if relevant_cases:
                full_context["relevant_cases"] = relevant_cases
        elif self._knowledge_documents and processed_input["text"]:
            # TF-IDF 备选方案
            relevant_cases = self._tfidf_search(processed_input["text"], top_k=3)
            if relevant_cases:
                full_context["relevant_cases"] = relevant_cases
                print(f"[RAG] TF-IDF mode retrieved {len(relevant_cases)} relevant cases")
        
        # 打印 RAG 使用状态
        if self._knowledge_loaded:
            if self.vector_store:
                stats = self.vector_store.get_stats()
                print(f"[RAG] Knowledge base loaded: {stats.get('count', 0)} text chunks")
            else:
                print(f"📚 [RAG] 知识库已加载: {len(self._knowledge_documents)} 文档")
        
        # 整合文本输入
        text_input = processed_input["multimodal_description"]

        # 如果没有LLM客户端，使用规则引擎评估
        if not self.llm_client:
            risk_assessment = self.decision_engine.assess_risk(
                text=text_input,
                user_profile=full_context.get("user_profile"),
                context=full_context
            )
            return risk_assessment

        # 始终使用LLM进行风险分析（让它更充分参与）
        llm_assessment = await self._llm_full_analysis(
            processed_input, full_context
        )

        return llm_assessment
    
    async def _llm_enhance_assessment(
        self,
        processed_input: Dict,
        rule_assessment: RiskAssessment,
        context: Dict
    ) -> RiskAssessment:
        """使用LLM增强评估"""
        try:
            # 构建提示词
            prompt = self.prompt_engine.get_multimodal_analysis_prompt(
                text=processed_input["text"],
                image_desc=processed_input.get("image_desc", ""),
                audio_desc=processed_input.get("audio_text", "")
            )

            # 添加上下文
            if context.get("relevant_cases"):
                cases_text = "\n".join([
                    f"案例{i+1}: {c.get('content', '')[:100]}..."
                    for i, c in enumerate(context["relevant_cases"][:3])
                ])
                prompt += f"\n\n【相似案例参考】\n{cases_text}"

            # 调用LLM (使用chat方法)
            messages = [{"role": "user", "content": prompt}]
            response = await self.llm_client.chat(messages)

            # 解析LLM响应
            if response and response.strip():
                result = json.loads(response)
                return RiskAssessment(
                    risk_level=result.get("risk_level", rule_assessment.risk_level),
                    risk_type=result.get("risk_type", rule_assessment.risk_type),
                    confidence=result.get("confidence", rule_assessment.confidence),
                    analysis=result.get("analysis", rule_assessment.analysis),
                    suggestion=result.get("suggestion", rule_assessment.suggestion),
                    warning_message=result.get("warning_message", rule_assessment.warning_message),
                    triggered_keywords=rule_assessment.triggered_keywords,
                    recommended_actions=result.get("suggestion", "").split("，"),
                    timestamp=time.time()
                )
            else:
                print("[WARNING] [LLM] Empty response received, using rule engine")

        except Exception as e:
            # LLM调用失败，使用规则引擎结果
            pass

        return rule_assessment

    async def _llm_full_analysis(
        self,
        processed_input: Dict,
        context: Dict
    ) -> RiskAssessment:
        """使用LLM进行完整的风险分析（直接生成最终响应）"""
        try:
            # 构建更丰富的提示词
            user_input = processed_input["multimodal_description"]

            # 添加上下文
            context_parts = []
            if context.get("relevant_cases"):
                cases_text = "\n".join([
                    f"案例{i+1}: {c.get('content', '')[:200]}..."
                    for i, c in enumerate(context["relevant_cases"][:3])
                ])
                context_parts.append(f"【相似案例参考】\n{cases_text}")

            # 添加用户画像上下文
            up = context.get("user_profile")
            if up:
                profile_parts = []
                if up.get("age_group"):
                    age_labels = {"18-25": "年轻人", "26-35": "中青年", "36-45": "中年人", "46-55": "中老年", "56+": "老年人"}
                    profile_parts.append(f"年龄群体：{age_labels.get(up['age_group'], '')}")
                if up.get("occupation"):
                    profile_parts.append(f"职业：{up['occupation']}")
                if up.get("experience_level"):
                    level_desc = {"新手": "对诈骗了解较少", "了解": "知道一些常见诈骗", "熟悉": "比较了解各种手法", "专业": "对反诈很有经验"}
                    profile_parts.append(level_desc.get(up['experience_level'], ''))
                if up.get("interested_scam_types") and isinstance(up["interested_scam_types"], list) and up["interested_scam_types"]:
                    profile_parts.append(f"特别关注诈骗类型：{', '.join(up['interested_scam_types'])}")
                if profile_parts:
                    context_parts.append("【用户背景】" + "；".join(profile_parts))

            context_text = "\n\n".join(context_parts) if context_parts else ""

            # 先用规则引擎做关键词检测
            keyword_analysis = self.decision_engine.assess_risk(
                text=user_input,
                user_profile=context.get("user_profile"),
                context=context
            )
            
            # 构建关键词分析结果
            kw_list = [kw[0] if isinstance(kw, tuple) else kw for kw in keyword_analysis.triggered_keywords]
            if kw_list:
                kw_summary = "触发风险词: " + ", ".join(kw_list) + "\n关键词得分: " + str(round(keyword_analysis.confidence, 2))
            else:
                kw_summary = "无明显风险词"

            # 构建提示词
            prompt = f"""你是SmartGuard智能反诈助手。请分析以下内容是否存在诈骗风险：

【用户输入】
{user_input}

【关键词检测结果】
风险等级: {"低" if keyword_analysis.risk_level == 0 else "中" if keyword_analysis.risk_level == 1 else "高"}
{kw_summary}

{context_text}

【分析要求】
1. 准确判断风险等级（0-4）：
   - 0: 安全，无风险
   - 1: 关注，有模糊风险信号
   - 2: 警告，有明显风险特征
   - 3: 危险，高风险
   - 4: 紧急，涉及资金转账

2. 识别诈骗类型（如有）：冒充公检法、投资理财、兼职刷单、杀猪盘、AI诈骗等

3. 输出JSON格式：
{{
    "risk_level": 风险等级(0-4),
    "risk_type": "诈骗类型或normal",
    "confidence": 置信度(0-1),
    "analysis": "详细分析说明",
    "suggestion": "防护建议",
    "warning_message": "警告信息（如有）"
}}"""

            # 调用LLM (使用chat方法)
            messages = [{"role": "user", "content": prompt}]
            response = await self.llm_client.chat(messages)

            if response and response.strip():
                result = json.loads(response)
                return RiskAssessment(
                    risk_level=result.get("risk_level", 0),
                    risk_type=result.get("risk_type", "normal"),
                    confidence=result.get("confidence", 0.5),
                    analysis=result.get("analysis", ""),
                    suggestion=result.get("suggestion", ""),
                    warning_message=result.get("warning_message", ""),
                    triggered_keywords=[],
                    recommended_actions=[result.get("suggestion", "")],
                    timestamp=time.time()
                )
            else:
                print("[WARNING] [LLM] Empty response received")

        except json.JSONDecodeError as e:
            print(f"[WARNING] [LLM] JSON parsing failed: {e}")
        except Exception as e:
            print(f"[WARNING] [LLM] Analysis failed: {e}")

        # 降级：使用规则引擎
        risk_assessment = self.decision_engine.assess_risk(
            text=processed_input["multimodal_description"],
            user_profile=context.get("user_profile"),
            context=context
        )
        return risk_assessment
    
    async def _retrieve_similar_cases(self, query: str, top_k: int = 3) -> List[Dict]:
        """检索相似案例"""
        try:
            # 优先使用向量存储
            if self.vector_store:
                results = self.vector_store.search(
                    query=query,
                    top_k=top_k
                )
                return results
            
            # TF-IDF 备选方案
            if hasattr(self, '_knowledge_documents') and self._knowledge_documents:
                return self._tfidf_search(query, top_k)
            
            return []
        
        except Exception:
            return []
    
    def _tfidf_search(self, query: str, top_k: int = 3) -> List[Dict]:
        """TF-IDF 关键词搜索（备选方案）"""
        try:
            from collections import Counter
            import re
            
            # 分词
            def tokenize(text):
                text = re.sub(r'[^\w\u4e00-\u9fff]', ' ', text.lower())
                return text.split()
            
            query_tokens = set(tokenize(query))
            
            results = []
            for doc in self._knowledge_documents:
                content_tokens = tokenize(doc.content)
                content_token_set = set(content_tokens)
                
                # 计算交集
                matches = query_tokens & content_token_set
                if matches:
                    # 简单相似度：匹配词数 / 查询词数
                    similarity = len(matches) / len(query_tokens)
                    
                    results.append({
                        "content": doc.content[:500],
                        "source": doc.source,
                        "title": doc.title,
                        "similarity": similarity,
                        "doc_type": doc.doc_type
                    })
            
            # 排序
            results.sort(key=lambda x: x["similarity"], reverse=True)
            return results[:top_k]
            
        except Exception:
            return []
    
    async def _handle_risk(self, risk_assessment: RiskAssessment) -> List[str]:
        """处理风险"""
        actions = []
        
        # 记录风险事件
        actions.append(f"风险事件记录：{risk_assessment.risk_type}")
        
        # 根据风险等级采取行动
        if risk_assessment.risk_level >= self.config["risk_threshold_emergency"]:
            # 紧急风险：通知监护人
            if self.enable_guardian and self.config["auto_notify_guardian"]:
                await self._notify_guardian(risk_assessment)
                actions.append("监护人通知已发送")
        
        elif risk_assessment.risk_level >= self.config["risk_threshold_danger"]:
            # 危险风险：强制预警
            actions.append("强制预警已触发")
        
        elif risk_assessment.risk_level >= self.config["risk_threshold_warning"]:
            # 警告风险：普通预警
            actions.append("风险警告已显示")
        
        return actions
    
    async def _notify_guardian(self, risk_assessment: RiskAssessment):
        """通知监护人"""
        guardians = self.memory.user_profile.guardians
        
        if not guardians:
            return
        
        # 构造通知内容
        notification = {
            "user_id": self.user_id,
            "risk_level": risk_assessment.risk_level,
            "risk_type": risk_assessment.risk_type,
            "analysis": risk_assessment.analysis,
            "timestamp": time.time(),
            "message": f"紧急通知：您的家人可能正在遭遇{risk_assessment.risk_type}诈骗，请立即联系确认！"
        }
        
        # 延迟通知
        await asyncio.sleep(self.config["guardian_delay_seconds"])
        
        # 发送通知（实际实现需要接入短信/微信等渠道）
        # 这里只是模拟
        for guardian in guardians:
            # await self._send_notification(guardian, notification)
            pass
    
    async def _generate_response(
        self,
        processed_input: Dict,
        risk_assessment: RiskAssessment
    ) -> str:
        """生成响应 - 智能识别用户意图"""
        
        text = processed_input.get("text", "") or ""
        
        # ==================== 意图识别 ====================
        intent = self._recognize_intent(text, risk_assessment)
        
        if intent == "risk_analysis":
            return await self._generate_risk_analysis_response(text, risk_assessment)
        elif intent == "knowledge_query":
            return await self._generate_knowledge_response(text, risk_assessment)
        elif intent == "learning":
            return self._generate_learning_response(text, risk_assessment)
        else:
            return await self._generate_risk_analysis_response(text, risk_assessment)
    
    def _recognize_intent(self, text: str, risk_assessment: RiskAssessment) -> str:
        """识别用户意图"""
        
        # 定义意图关键词
        learning_patterns = [
            "什么是", "介绍一下", "了解", "学习", "科普",
            "有哪些", "常见", "类型", "手法", "怎么", "如何"
        ]
        
        knowledge_patterns = [
            "杀猪盘", "刷单", "公检法", "冒充", "投资理财", "贷款",
            "退款", "征信", "医保", "游戏", "追星", "AI诈骗",
            "深度伪造", "语音合成", "诈骗"
        ]
        
        # 询问类关键词
        query_patterns = [
            "?", "？", "吗", "呢", "是什么", "为什么", "请问",
            "告诉", "解释", "说说", "介绍一下"
        ]
        
        # 检查是否是学习/了解模式
        is_learning = any(p in text for p in learning_patterns)
        has_knowledge_keyword = any(p in text for p in knowledge_patterns)
        is_query = any(p in text for p in query_patterns)
        
        # 判断逻辑
        # 1. 如果用户问"什么是X"，且X是诈骗类型 → 知识百科模式
        if is_learning and has_knowledge_keyword and risk_assessment.risk_level < 2:
            return "knowledge_query"
        
        # 2. 如果用户询问诈骗类型但没有可疑内容 → 反诈助手模式
        if has_knowledge_keyword and is_query and risk_assessment.risk_level < 2:
            return "knowledge_query"
        
        # 3. 如果文本包含明显的诈骗话术关键词 → 风险分析模式
        if risk_assessment.risk_level >= 2:
            return "risk_analysis"
        
        # 4. 如果是纯询问且无风险 → 反诈助手模式
        if is_query and risk_assessment.risk_level == 0:
            return "knowledge_query"
        
        # 5. 默认风险分析
        return "risk_analysis"
    
    async def _generate_risk_analysis_response(self, text: str, risk_assessment: RiskAssessment) -> str:
        """生成风险分析响应 - 更自然友好的输出"""
        response_parts = []

        # 风险等级对应的自然开头
        if risk_assessment.risk_level == 0:
            response_parts.append("✅ 这条内容看起来是安全的。")
        elif risk_assessment.risk_level == 1:
            response_parts.append("💡 我注意到这里面有一些需要注意的地方：")
        elif risk_assessment.risk_level == 2:
            response_parts.append("⚠️ 提醒一下，这条内容有一些风险信号：")
        elif risk_assessment.risk_level == 3:
            response_parts.append("🚨 这很可能是一个诈骗信息！请仔细看：")
        else:  # risk_level >= 4
            response_parts.append("🆘 紧急！这极有可能是诈骗，而且涉及资金！")

        # 分析说明（自然地融入）
        if risk_assessment.analysis:
            response_parts.append(f"\n\n{risk_assessment.analysis}")

        # 如果是高风险，添加更详细的警告
        if risk_assessment.risk_level >= 2:
            if risk_assessment.risk_type != "normal":
                scam_name = self._get_scam_type_name(risk_assessment.risk_type)
                response_parts.append(f"\n\n📌 这看起来像是「{scam_name}」的典型手法。")

        # 防护建议（口语化）
        if risk_assessment.suggestion:
            response_parts.append(f"\n\n💡 建议：{risk_assessment.suggestion}")

        # 行动建议（如果有）
        if risk_assessment.recommended_actions:
            actions = [a for a in risk_assessment.recommended_actions if a]
            if actions:
                response_parts.append(f"\n\n📋 你可以这样做：")
                for i, action in enumerate(actions[:3], 1):
                    response_parts.append(f"\n{i}. {action}")

        # 高置信度时的额外提醒
        if risk_assessment.confidence >= 0.85 and risk_assessment.risk_level >= 2:
            response_parts.append("\n\n⚠️ 我的判断很有把握，请务必重视！")

        return "".join(response_parts)
    
    async def _generate_knowledge_response(self, text: str, risk_assessment: RiskAssessment) -> str:
        """生成反诈助手/知识百科响应"""
        response_parts = []
        
        # 识别用户询问的具体诈骗类型
        scam_type = self._identify_scam_type_from_text(text)
        
        if scam_type:
            # 针对特定诈骗类型的详细解答
            name = scam_type["name"]
            response_parts.append(f"📚 关于「{name}」，让我来为你详细介绍：\n")
            response_parts.append(f"\n【什么是{name}？】")
            response_parts.append(f"\n{scam_type['description']}")
            response_parts.append(f"\n\n【典型特征】")
            for feature in scam_type.get('features', [])[:4]:
                response_parts.append(f"\n• {feature}")
            response_parts.append(f"\n\n【真实案例】")
            response_parts.append(f"\n{scam_type.get('case', '暂无案例')}")
            response_parts.append(f"\n\n【防范要点】")
            for tip in scam_type.get('tips', [])[:4]:
                response_parts.append(f"\n✅ {tip}")
        else:
            # 通用反诈知识
            response_parts.append("🛡️ 你好！我是SmartGuard，你的反诈小助手！\n")
            response_parts.append("\n【近期高发诈骗类型】")
            
            top_scams = [
                {"name": "冒充公检法诈骗", "desc": "骗子冒充警察/检察院，说你涉嫌犯罪要转账"},
                {"name": "刷单返利诈骗", "desc": "先给甜头，后让你大额充值"},
                {"name": "杀猪盘诈骗", "desc": "网恋对象带你投资，其实是骗局"},
                {"name": "虚假贷款诈骗", "desc": "无抵押贷款，先交各种费用"}
            ]
            
            for i, scam in enumerate(top_scams, 1):
                response_parts.append(f"\n{i}. {scam['name']}")
                response_parts.append(f"\n   {scam['desc']}")
            
            response_parts.append("\n\n【防骗口诀】")
            response_parts.append("\n• 不轻信陌生来电")
            response_parts.append("\n• 不点击陌生链接")
            response_parts.append("\n• 不向陌生人转账")
            response_parts.append("\n• 遇到可疑情况多核实")
        
        response_parts.append("\n\n💬 还有什么想了解的吗？比如：")
        response_parts.append("\n• 「什么是杀猪盘？」")
        response_parts.append("\n• 「如何识别冒充公检法的诈骗？」")
        response_parts.append("\n• 「最近有哪些新型诈骗？」")
        
        return "".join(response_parts)
    
    def _generate_learning_response(self, text: str, risk_assessment: RiskAssessment) -> str:
        """生成学习模式响应"""
        response_parts = []
        
        response_parts.append("📖 好的，让我来教你！\n")
        
        # 根据内容决定教授什么
        if "杀猪盘" in text:
            response_parts.append("\n【杀猪盘诈骗详解】\n")
            response_parts.append("\n🐷 什么是杀猪盘？")
            response_parts.append("\n「杀猪盘」是一种网络交友诈骗，骗子通过婚恋网站、社交平台等寻找目标，")
            response_parts.append("通过长时间聊天建立感情（称为「养猪」），最后诱导受害者参与虚假投资（称为「杀猪」）。")
            response_parts.append("\n\n【骗子常用话术】")
            response_parts.append("\n• 「我发现了一个稳赚不赔的平台」")
            response_parts.append("\n• 「跟着导师下注，保证赚钱」")
            response_parts.append("\n• 「我现在都在这个平台赚了好几十万了」")
            response_parts.append("\n\n【防范方法】")
            response_parts.append("\n✅ 网恋对象突然提到投资、博彩，立刻警惕")
            response_parts.append("\n✅ 不要相信「内幕消息」「导师带单」")
            response_parts.append("\n✅ 未见面就涉及金钱的都是诈骗")
            response_parts.append("\n✅ 发现自己被骗后，第一时间报警")
            
        elif "冒充" in text and ("公检法" in text or "警察" in text):
            response_parts.append("\n【冒充公检法诈骗详解】\n")
            response_parts.append("\n👮 骗子通常怎么骗？")
            response_parts.append("\n1️⃣ 骗子来电自称是公安机关/检察院/法院")
            response_parts.append("\n2️⃣ 说你的身份证被盗用，涉嫌洗钱/贩毒等犯罪")
            response_parts.append("\n3️⃣ 要求你配合调查，不能告诉任何人")
            response_parts.append("\n4️⃣ 要求将资金转入「安全账户」进行核查")
            response_parts.append("\n\n【识别要点】")
            response_parts.append("\n✅ 真正的警方不会通过电话办案")
            response_parts.append("\n✅ 警方不会要求转账到任何账户")
            response_parts.append("\n✅ 警方不会让你卸载通讯软件")
            response_parts.append("\n\n【应对方法】")
            response_parts.append("\n1. 直接挂断电话")
            response_parts.append("\n2. 不要和对方继续通话")
            response_parts.append("\n3. 如有疑问，拨打110核实")
            
        else:
            # 通用学习响应
            response_parts.append("\n【常见诈骗类型一览】\n")
            scam_list = [
                ("👮 冒充公检法", "冒充警察说你违法，要求转账"),
                ("💰 投资理财诈骗", "高收益保本诱惑，诱导充值"),
                ("📦 刷单诈骗", "先小赚后大亏，本金无法提现"),
                ("💔 杀猪盘", "网恋对象带你投资，其实是骗局"),
                ("💳 虚假贷款", "无抵押贷款，先交各种费用"),
                ("🛒 购物退款", "假客服退款，诱导转账"),
                ("📋 虚假征信", "说征信有问题，要「修复」"),
                ("🎙️ AI语音诈骗", "合成子女声音，说出事了要钱")
            ]
            
            for name, desc in scam_list:
                response_parts.append(f"\n{name}")
                response_parts.append(f"\n   {desc}")
        
        response_parts.append("\n\n📝 记住防骗三不：不轻信、不转账、不透露！")
        response_parts.append("\n💬 还想了解哪种诈骗类型？")
        
        return "".join(response_parts)
    
    def _identify_scam_type_from_text(self, text: str) -> Optional[Dict]:
        """从文本中识别诈骗类型"""
        
        scam_profiles = {
            "杀猪盘": {
                "name": "杀猪盘诈骗",
                "description": "杀猪盘是一种网络交友诈骗，骗子通过婚恋网站或社交平台寻找目标，建立感情后诱导投资或转账。",
                "features": [
                    "通过婚恋网站主动搭讪",
                    "聊天几天就建立恋爱关系",
                    "频繁提到投资、博彩、平台",
                    "以家人生病、资金周转等借口借钱",
                    "诱导你下载未知投资App"
                ],
                "case": "王女士在网上认识一名「成功人士」，聊天一个月后对方称有内幕消息，带她在一个虚假平台投资，起初小赚，后加大投入后平台无法登录，被骗28万元。",
                "tips": [
                    "网恋不见面的都是诈骗",
                    "对方提到投资、博彩立刻拉黑",
                    "不下载来历不明的App",
                    "不向未见面的人转账"
                ]
            },
            "刷单": {
                "name": "刷单返利诈骗",
                "description": "骗子以刷单返利为诱饵，先让受害者小赚几笔，等大额充值后，以各种理由拒绝提现。",
                "features": [
                    "招聘兼职点赞员、刷好评",
                    "声称「日赚300-500元」",
                    "需要先垫付资金",
                    "充值金额越来越大",
                    "无法提现，客服失联"
                ],
                "case": "张同学看到「刷单赚佣金」广告，前三单都收到返利，第四单充值5000元后被告知「任务未完成需继续充值」，又转了2万元后被拉黑。",
                "tips": [
                    "刷单本身就是违法行为",
                    "正规兼职不会收任何费用",
                    "前期返利是诈骗分子放长线",
                    "发现被骗立即报警"
                ]
            },
            "公检法": {
                "name": "冒充公检法诈骗",
                "description": "骗子冒充公安机关、检察院、法院工作人员，以涉嫌犯罪为由，要求将资金转入「安全账户」。",
                "features": [
                    "来电显示为境外号码或公安机关号码",
                    "声称你涉嫌洗钱、贩毒等重罪",
                    "语气严厉，制造紧张氛围",
                    "要求保密，不许告诉任何人",
                    "要求将资金转入「安全账户」"
                ],
                "case": "李先生接到「公安局」电话，说他涉嫌一起洗钱案，让他将50万转入「核查账户」。李先生照做后，对方失联。",
                "tips": [
                    "真正的警方不会电话办案",
                    "警方不会要求转账到任何账户",
                    "接到此类电话直接挂断",
                    "有疑问拨打110核实"
                ]
            },
            "投资": {
                "name": "投资理财诈骗",
                "description": "骗子以高收益、低风险为诱饵，诱导受害者下载虚假投资平台，先给甜头后卷款跑路。",
                "features": [
                    "承诺年化收益15%以上",
                    "声称「保本」「零风险」",
                    "有「导师」一对一指导",
                    "需要不断充值才能提现",
                    "平台突然无法登录"
                ],
                "case": "陈女士被拉入股票交流群，跟着「老师」在某平台投资，前两个月确实赚钱，第三个月加大投入后，平台显示「系统维护」再也登不上去。",
                "tips": [
                    "正规理财产品不会承诺保本",
                    "年化收益超过6%就要警惕",
                    "不下载来历不明的投资App",
                    "投资前核实平台资质"
                ]
            },
            "贷款": {
                "name": "虚假贷款诈骗",
                "description": "骗子以无抵押、低利率、快速放款为诱饵，以各种名义收取费用后失联。",
                "features": [
                    "声称「无抵押、无征信」",
                    "利率极低甚至「免息」",
                    "要求先交「手续费」「保证金」",
                    "放款前以各种理由收费",
                    "贷款没下来，钱已经被骗"
                ],
                "case": "赵先生急需用钱，在网上看到「无抵押贷款」，联系后被要求交3000元「验资费」，转账后再联系对方，发现已被拉黑。",
                "tips": [
                    "正规贷款不会放款前收费",
                    "银行贷款都需要审核资质",
                    "急需用钱首选银行或正规机构",
                    "遇到收费要求立刻警惕"
                ]
            },
            "退款": {
                "name": "购物退款诈骗",
                "description": "骗子冒充电商平台或快递客服，以质量问题、双倍赔偿等为由，诱导受害者转账。",
                "features": [
                    "准确说出你的购物信息",
                    "声称商品有质量问题要退款",
                    "要求提供银行验证码",
                    "诱导操作转账或贷款",
                    "提到「备用金」「屏幕共享」"
                ],
                "case": "刘女士接到「客服」电话，说她购买的商品有问题要双倍赔偿，按对方指导操作后，发现自己被贷款了2万元。",
                "tips": [
                    "正规退款原路返回，不需要操作",
                    "不提供银行验证码",
                    "不与对方屏幕共享",
                    "不点对方发的陌生链接"
                ]
            }
        }
        
        for keyword, profile in scam_profiles.items():
            if keyword in text:
                return profile
        
        return None
    
    def _get_scam_type_name(self, scam_type: str) -> str:
        """获取诈骗类型中文名"""
        names = {
            "police_impersonation": "冒充公检法诈骗",
            "investment_fraud": "投资理财诈骗",
            "part_time_fraud": "兼职刷单诈骗",
            "loan_fraud": "虚假贷款诈骗",
            "pig_butchery": "杀猪盘诈骗",
            "ai_voice_fraud": "AI语音合成诈骗",
            "deepfake_fraud": "视频深度伪造诈骗",
            "credit_fraud": "虚假征信诈骗",
            "refund_fraud": "购物退款诈骗",
            "gaming_fraud": "游戏交易诈骗",
            "fan_fraud": "追星诈骗",
            "medical_fraud": "医保诈骗",
            "normal": "正常"
        }
        return names.get(scam_type, "未知诈骗")
    
    def _save_to_memory(
        self,
        input_data: AgentInput,
        processed_input: Dict,
        response: str,
        risk_assessment: RiskAssessment
    ):
        """保存到记忆"""
        # 保存用户消息（使用处理后的多模态描述）
        user_content = processed_input.get("multimodal_description", input_data.text or "")
        self.memory.add_message(
            role="user",
            content=user_content,
            metadata={
                "modality": input_data.modality,
                "risk_level": risk_assessment.risk_level
            }
        )

        # 保存助手响应
        self.memory.add_message(
            role="assistant",
            content=response,
            metadata={
                "risk_level": risk_assessment.risk_level,
                "risk_type": risk_assessment.risk_type,
                "confidence": risk_assessment.confidence
            }
        )
    
    async def _evolve_knowledge(self):
        """进化知识"""
        self.current_state = AgentState.EVOLVING
        
        # 定期更新知识库
        # 实际实现需要：1. 爬取最新诈骗案例 2. 清洗数据 3. 入库
        
        self.current_state = AgentState.IDLE
    
    def get_status(self) -> Dict:
        """获取智能体状态"""
        return {
            "user_id": self.user_id,
            "state": self.current_state.value,
            "interaction_count": self.interaction_count,
            "session_duration": time.time() - self.session_start,
            "user_profile": self.memory.user_profile.to_dict(),
            "recent_risks": len(self.memory.long_term)
        }
    
    def update_profile(self, **kwargs):
        """更新用户画像"""
        self.memory.update_profile(**kwargs)
    
    def add_guardian(self, name: str, phone: str, relationship: str):
        """添加监护人"""
        self.memory.add_guardian(name, phone, relationship)
    
    def reset_session(self):
        """重置会话"""
        self.memory.clear_short_term()
        self.session_start = time.time()
        self.current_state = AgentState.IDLE
    
    def export_memory(self) -> Dict:
        """导出记忆数据"""
        return self.memory.to_dict()
    
    def import_memory(self, data: Dict):
        """导入记忆数据"""
        self.memory = ConversationMemory.from_dict(data)
