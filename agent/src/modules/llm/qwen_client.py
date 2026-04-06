"""
通义千问 (Qwen) LLM 客户端
基于 DashScope API 的 LLM 调用封装
"""

import os
import json
from typing import Optional, List, Dict, Any, AsyncIterator
from dataclasses import dataclass

try:
    import dashscope
    from dashscope import Generation
    DASHSCOPE_AVAILABLE = True
except ImportError:
    DASHSCOPE_AVAILABLE = False


@dataclass
class QwenConfig:
    """通义千问配置"""
    api_key: Optional[str] = None
    model: str = "qwen-turbo"
    temperature: float = 0.7
    max_tokens: int = 2000
    top_p: float = 0.8
    enable_search: bool = False  # 是否启用联网搜索


class QwenLLM:
    """
    通义千问 LLM 客户端
    
    支持模型:
    - qwen-turbo: 快速版，适合简单任务
    - qwen-plus: 增强版，性能更强
    - qwen-max: 最高性能版
    - qwen-max-longcontext: 长上下文版
    """
    
    SUPPORTED_MODELS = [
        "qwen-turbo",
        "qwen-plus", 
        "qwen-max",
        "qwen-max-longcontext"
    ]
    
    def __init__(self, config: Optional[QwenConfig] = None):
        """
        初始化 Qwen 客户端
        
        Args:
            config: 配置对象
        """
        self.config = config or QwenConfig()
        
        # 从环境变量获取 API Key
        if not self.config.api_key:
            self.config.api_key = os.getenv("DASHSCOPE_API_KEY")
        
        # 初始化 dashscope
        if DASHSCOPE_AVAILABLE and self.config.api_key:
            dashscope.api_key = self.config.api_key
            self._initialized = True
        else:
            self._initialized = False
            if not self.config.api_key:
                print("[WARNING] DASHSCOPE_API_KEY not set, using local rule engine")
            elif not DASHSCOPE_AVAILABLE:
                print("[WARNING] dashscope not installed, run: pip install dashscope")
    
    @property
    def is_available(self) -> bool:
        """检查是否可用"""
        return self._initialized and DASHSCOPE_AVAILABLE
    
    def set_api_key(self, api_key: str):
        """设置 API Key"""
        self.config.api_key = api_key
        if DASHSCOPE_AVAILABLE:
            dashscope.api_key = api_key
        self._initialized = True
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        同步对话接口
        
        Args:
            messages: 消息列表，格式 [{"role": "user", "content": "..."}]
            system_prompt: 系统提示词
            **kwargs: 其他参数，会覆盖默认配置
        
        Returns:
            生成的回复文本
        """
        if not self.is_available:
            raise RuntimeError("Qwen LLM 未初始化，请先设置 API Key")
        
        # 合并配置
        params = {
            "model": self.config.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", self.config.temperature),
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "top_p": kwargs.get("top_p", self.config.top_p),
        }

        # 新版 dashscope API: system 要放到 messages 里
        if system_prompt:
            params["messages"] = [{"role": "system", "content": system_prompt}] + messages

        if self.config.enable_search or kwargs.get("enable_search"):
            params["enable_search"] = True
        
        response = Generation.call(**params)
        
        if response.status_code == 200:
            # 新版 dashscope: output.text
            if hasattr(response.output, 'text'):
                text = response.output.text
                if text:
                    print(f"[LLM] Response received: {text[:100]}...")
                else:
                    print("[WARNING] [LLM] Response text is empty")
                return text if text else ""
            # 兼容旧版格式
            elif response.output.choices:
                return response.output.choices[0].message.content
            else:
                return str(response.output)
        else:
            raise RuntimeError(f"Qwen API 错误: {response.code} - {response.message}")
    
    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """
        流式对话接口
        
        Args:
            messages: 消息列表
            system_prompt: 系统提示词
            **kwargs: 其他参数
        
        Yields:
            逐字返回生成的文本
        """
        if not self.is_available:
            raise RuntimeError("Qwen LLM 未初始化，请先设置 API Key")
        
        params = {
            "model": self.config.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", self.config.temperature),
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "top_p": kwargs.get("top_p", self.config.top_p),
            "stream": True,
        }

        # 新版 dashscope API: system 要放到 messages 里
        if system_prompt:
            params["messages"] = [{"role": "system", "content": system_prompt}] + messages

        response = Generation.call(**params)
        
        for chunk in response:
            if chunk.status_code == 200:
                # 新版 dashscope: output.text
                if hasattr(chunk.output, 'text') and chunk.output.text:
                    yield chunk.output.text
                # 兼容旧版格式
                elif chunk.output.choices:
                    content = chunk.output.choices[0].message.content
                    if content:
                        yield content
            else:
                raise RuntimeError(f"Qwen API 流式错误: {chunk.code} - {chunk.message}")
    
    async def analyze_risk(self, text: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        使用 LLM 分析风险
        
        Args:
            text: 待分析文本
            context: 上下文信息
        
        Returns:
            分析结果字典
        """
        system_prompt = """你是一个专业的反诈分析助手。请分析用户输入的对话内容，判断是否存在诈骗风险。

分析维度：
1. 风险等级 (0-5): 0为安全，5为极高风险
2. 风险类型: 仿冒公检法、杀猪盘、刷单诈骗、网购诈骗、冒充客服、投资理财诈骗、贷款诈骗、其他
3. 置信度 (0-1): 分析的可信程度
4. 分析理由: 为什么认为是/不是诈骗
5. 建议措施: 应该采取什么行动

请以JSON格式返回结果。"""
        
        user_content = f"请分析以下对话内容的风险：\n\n{text}"
        if context:
            user_content += f"\n\n背景信息: {json.dumps(context, ensure_ascii=False)}"
        
        messages = [{"role": "user", "content": user_content}]
        
        try:
            response = await self.chat(messages, system_prompt=system_prompt)
            
            # 尝试解析 JSON
            if response and response.strip().startswith("{"):
                result = json.loads(response)
                return result
            else:
                # 如果不是纯JSON，包装一下
                return {
                    "risk_level": 0,
                    "risk_type": "unknown",
                    "confidence": 0.5,
                    "analysis": response if response else "[空响应]",
                    "suggestion": "无法确定风险，请谨慎处理"
                }
        except Exception as e:
            return {
                "risk_level": 0,
                "risk_type": "analysis_error",
                "confidence": 0,
                "analysis": f"LLM分析失败: {str(e)}",
                "suggestion": "使用本地规则引擎进行分析"
            }
    
    async def generate_warning(self, risk_level: int, risk_type: str, text: str) -> str:
        """
        生成警告信息
        
        Args:
            risk_level: 风险等级
            risk_type: 风险类型
            text: 原始文本
        
        Returns:
            警告信息
        """
        if not self.is_available:
            return None
        
        system_prompt = """你是一个反诈提醒助手。根据风险信息生成简洁有力的警告信息。

要求：
1. 语言简洁有力，直击要害
2. 适合在聊天界面展示
3. 长度控制在100字以内
4. 包含具体建议

直接返回警告文本，不要包含其他内容。"""
        
        user_content = f"""风险等级: {risk_level}/5
风险类型: {risk_type}
相关对话: {text}

请生成警告信息："""
        
        messages = [{"role": "user", "content": user_content}]
        
        try:
            return await self.chat(messages, system_prompt=system_prompt)
        except Exception:
            return None
    
    async def enhance_response(self, base_response: str, risk_level: int) -> str:
        """
        增强回复内容
        
        Args:
            base_response: 基础回复
            risk_level: 风险等级
        
        Returns:
            增强后的回复
        """
        if not self.is_available:
            return base_response
        
        system_prompt = """你是一个反诈助手，正在帮助用户分析可疑对话。
请根据基础回复和风险等级，优化回复内容，使其更加清晰、有说服力。

直接返回优化后的回复文本。"""
        
        user_content = f"风险等级: {risk_level}/5\n\n基础回复:\n{base_response}\n\n请优化这个回复："
        
        messages = [{"role": "user", "content": user_content}]
        
        try:
            return await self.chat(messages, system_prompt=system_prompt)
        except Exception:
            return base_response


def create_qwen_client(
    api_key: Optional[str] = None,
    model: str = "qwen-turbo",
    **kwargs
) -> QwenLLM:
    """
    工厂函数：创建 Qwen 客户端
    
    Args:
        api_key: API Key
        model: 模型名称
        **kwargs: 其他配置参数
    
    Returns:
        QwenLLM 实例
    """
    config = QwenConfig(
        api_key=api_key or os.getenv("DASHSCOPE_API_KEY"),
        model=model,
        **kwargs
    )
    return QwenLLM(config)


# 单例模式便捷访问
_llm_client: Optional[QwenLLM] = None


def get_llm_client() -> QwenLLM:
    """获取全局 LLM 客户端"""
    global _llm_client
    if _llm_client is None:
        _llm_client = create_qwen_client()
    return _llm_client


def init_llm_client(api_key: str, model: str = "qwen-turbo", **kwargs) -> QwenLLM:
    """初始化全局 LLM 客户端"""
    global _llm_client
    _llm_client = create_qwen_client(api_key=api_key, model=model, **kwargs)
    return _llm_client
