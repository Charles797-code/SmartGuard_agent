"""
音频输入处理模块
支持实时通话、语音消息的ASR转写和特征提取
"""

import base64
import io
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import asyncio


@dataclass
class AudioInput:
    """音频输入结构"""
    audio_data: Optional[bytes] = None
    audio_path: Optional[str] = None
    audio_base64: Optional[str] = None
    duration: Optional[float] = None
    sample_rate: int = 16000
    channels: int = 1
    format: str = "wav"
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class AudioAnalysis:
    """音频分析结果"""
    transcription: str
    language: str
    duration: float
    speaker_count: int
    emotion_signals: List[str]
    risk_signals: List[str]
    audio_features: Dict[str, Any]
    metadata: Dict[str, Any]


class AudioInputHandler:
    """音频输入处理器"""

    # 情感信号关键词
    EMOTION_KEYWORDS = {
        "anxiety": ["紧张", "害怕", "担心", "着急", "慌"],
        "urgency": ["快点", "赶紧", "马上", "立刻", "快"],
        "threat": ["威胁", "恐吓", "怎么样", "后果"],
        "deception": ["不能说", "保密", "秘密", "别告诉"]
    }

    # 风险语音特征
    RISK_AUDIO_FEATURES = {
        "high_pitch": {"threshold": 300, "description": "音调过高"},
        "fast_speech": {"threshold": 5.0, "description": "语速过快"},  # 字/秒
        "trembling": {"description": "声音颤抖"},
        "silence_gaps": {"threshold": 3, "description": "频繁停顿"}
    }

    # Whisper模型缓存
    _whisper_model_cache = None

    def __init__(self, whisper_model: Optional[Any] = None):
        """
        初始化音频处理器

        Args:
            whisper_model: Whisper ASR模型实例（可选，不传则自动加载）
        """
        self.whisper_model = whisper_model
        self.sample_rate = 16000

    @classmethod
    def _get_whisper_model(cls):
        """获取或加载Whisper模型"""
        if cls._whisper_model_cache is None:
            try:
                import whisper
                import torch
                device = "cuda" if torch.cuda.is_available() else "cpu"
                print(f"[Whisper] Loading model (device={device})...")
                # 使用base模型，平衡速度和准确度
                cls._whisper_model_cache = whisper.load_model("base", device=device)
                print("[OK] [Whisper] Model loaded")
            except ImportError:
                print("[WARNING] [Whisper] Not installed, run: pip install openai-whisper")
                cls._whisper_model_cache = False
            except Exception as e:
                print(f"[WARNING] [Whisper] Model load failed: {e}")
                cls._whisper_model_cache = False
        return cls._whisper_model_cache if cls._whisper_model_cache else None
    
    async def process(self, audio_input: AudioInput) -> AudioAnalysis:
        """
        处理音频输入
        
        Args:
            audio_input: 音频输入
            
        Returns:
            AudioAnalysis: 音频分析结果
        """
        # 1. ASR转写
        transcription = await self._transcribe(audio_input)
        
        # 2. 情感分析
        emotion_signals = self._analyze_emotion(transcription)
        
        # 3. 风险信号检测
        risk_signals = self._detect_risk_signals(transcription)
        
        # 4. 音频特征提取
        audio_features = await self._extract_features(audio_input)
        
        # 5. 说话人估计
        speaker_count = self._estimate_speakers(transcription, audio_features)
        
        return AudioAnalysis(
            transcription=transcription,
            language=self._detect_language(transcription),
            duration=audio_input.duration or 0,
            speaker_count=speaker_count,
            emotion_signals=emotion_signals,
            risk_signals=risk_signals,
            audio_features=audio_features,
            metadata={
                "sample_rate": audio_input.sample_rate,
                "format": audio_input.format,
                **audio_input.metadata
            }
        )
    
    async def _transcribe(self, audio_input: AudioInput) -> str:
        """ASR转写"""
        # 如果有Whisper模型，使用它进行转写
        if self.whisper_model:
            audio_bytes = await self._get_audio_bytes(audio_input)
            result = await self._whisper_transcribe(audio_bytes)
            return result

        # 尝试自动加载Whisper模型
        whisper_model = self._get_whisper_model()
        if whisper_model:
            self.whisper_model = whisper_model
            audio_bytes = await self._get_audio_bytes(audio_input)
            result = await self._whisper_transcribe(audio_bytes)
            return result

        # 模拟转写结果
        return "[这是语音转写文本的占位符]"
    
    async def _get_audio_bytes(self, audio_input: AudioInput) -> bytes:
        """获取音频字节数据"""
        if audio_input.audio_data:
            return audio_input.audio_data
        
        if audio_input.audio_path:
            # 读取文件
            with open(audio_input.audio_path, 'rb') as f:
                return f.read()
        
        if audio_input.audio_base64:
            return base64.b64decode(audio_input.audio_base64)
        
        return b""
    
    async def _whisper_transcribe(self, audio_bytes: bytes) -> str:
        """使用Whisper进行转写"""
        try:
            # 尝试导入whisper
            import whisper
            import io
            import tempfile
            import numpy as np

            # 保存临时文件
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as f:
                f.write(audio_bytes)
                temp_path = f.name

            try:
                # 自动检测 GPU
                import torch
                device = "cuda" if torch.cuda.is_available() else "cpu"
                # 加载模型（缓存以提高性能）
                if not hasattr(self, '_whisper_model') or self._whisper_model is None:
                    self._whisper_model = whisper.load_model("base", device=device)

                # 转写
                result = self._whisper_model.transcribe(temp_path, language='zh')
                return result.get("text", "").strip() or "[语音转写结果为空]"

            finally:
                # 清理临时文件
                import os
                if os.path.exists(temp_path):
                    os.unlink(temp_path)

        except ImportError:
            return "[Whisper未安装，无法转写音频]"
        except Exception as e:
            return f"[音频转写失败: {str(e)}]"
    
    def _analyze_emotion(self, transcription: str) -> List[str]:
        """情感分析"""
        signals = []
        
        for emotion, keywords in self.EMOTION_KEYWORDS.items():
            for keyword in keywords:
                if keyword in transcription:
                    emotion_map = {
                        "anxiety": "焦虑",
                        "urgency": "急迫",
                        "threat": "被威胁",
                        "deception": "疑似欺骗"
                    }
                    signals.append(emotion_map.get(emotion, emotion))
                    break
        
        return list(set(signals))
    
    def _detect_risk_signals(self, transcription: str) -> List[str]:
        """检测风险信号"""
        signals = []
        
        # 关键词检测
        risk_keywords = {
            "转账汇款": ["转账", "汇款", "打钱", "付款"],
            "验证码": ["验证码", "码", "密码"],
            "冒充身份": ["公安", "警察", "法院", "检察官"],
            "威胁恐吓": ["抓你", "坐牢", "逮捕", "违法"],
            "高收益诱惑": ["赚钱", "收益", "投资", "分红"],
            "安全账户": ["安全账户", "保证金", "解冻"]
        }
        
        for category, keywords in risk_keywords.items():
            if any(kw in transcription for kw in keywords):
                signals.append(category)
        
        return signals
    
    async def _extract_features(self, audio_input: AudioInput) -> Dict[str, Any]:
        """提取音频特征"""
        features = {
            "duration": audio_input.duration or 0,
            "sample_rate": audio_input.sample_rate,
            "channels": audio_input.channels
        }
        
        # 实际实现需要提取MFCC等特征
        # 伪代码：
        # if audio_bytes:
        #     y, sr = librosa.load(io.BytesIO(audio_bytes), sr=self.sample_rate)
        #     mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
        #     features["mfcc_mean"] = mfcc.mean(axis=1).tolist()
        #     features["speech_rate"] = len([s for s in y if abs(s) > 0.01]) / len(y)
        
        return features
    
    def _estimate_speakers(self, transcription: str, features: Dict) -> int:
        """估计说话人数量"""
        # 简单实现：基于对话轮次估计
        # 实际需要使用说话人分割技术
        
        dialogue_markers = ["说", "道", "问", "答", "：", ":", "?"]
        marker_count = sum(transcription.count(m) for m in dialogue_markers)
        
        if marker_count > 5:
            return 2
        return 1
    
    def _detect_language(self, transcription: str) -> str:
        """检测语言"""
        # 简单实现：基于字符判断
        chinese_chars = len([c for c in transcription if '\u4e00' <= c <= '\u9fff'])
        
        if chinese_chars > len(transcription) * 0.5:
            return "zh"
        return "en"
    
    def merge_with_text(self, audio_analysis: AudioAnalysis, 
                       text_analysis: Optional[Any] = None) -> Dict[str, Any]:
        """与文本分析结果融合"""
        merged = {
            "transcription": audio_analysis.transcription,
            "language": audio_analysis.language,
            "emotion_signals": audio_analysis.emotion_signals,
            "risk_signals": audio_analysis.risk_signals,
            "duration": audio_analysis.duration
        }
        
        if text_analysis:
            merged["text_entities"] = text_analysis.entity_tags
            merged["text_intents"] = text_analysis.intent_signals
            merged["text_risk_indicators"] = text_analysis.risk_indicators
        
        return merged
