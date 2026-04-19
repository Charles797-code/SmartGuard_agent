"""
音频输入处理模块
使用 SenseVoice 进行 ASR + 情感识别 + 音频事件检测
使用 librosa 提取声学特征用于风险分析
"""

# 确保 FFmpeg 在 PATH 中（Windows 便携版安装路径）
import os
_ffmpeg_path = r"C:\Users\Charles\AppData\Local\ffmpeg\bin"
if os.path.exists(_ffmpeg_path) and _ffmpeg_path not in os.environ.get("PATH", ""):
    os.environ["PATH"] = _ffmpeg_path + os.pathsep + os.environ.get("PATH", "")

import base64
import io
import re
import tempfile
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import numpy as np


def _clean_sensevoice_transcription(text: str) -> str:
    """清理 SenseVoice 输出中的语言/情感标签，返回纯文本"""
    if not text:
        return ""
    text = re.sub(r'<\|[^|]*\|>', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


class EmotionLabel(Enum):
    """SenseVoice 情感标签"""
    HAPPY = "happy"          # 高兴
    SAD = "sad"              # 悲伤
    ANGRY = "angry"          # 愤怒
    NEUTRAL = "neutral"      # 中性
    UNKNOWN = "unknown"      # 未知


class AudioEventType(Enum):
    """音频事件类型"""
    MUSIC = "music"          # 音乐
    APPLAUSE = "applause"    # 掌声
    LAUGHTER = "laughter"    # 笑声
    CRYING = "crying"        # 哭声
    COUGH = "cough"          # 咳嗽
    SNEEZE = "sneeze"        # 喷嚏
    SPEECH = "speech"        # 正常语音
    SILENCE = "silence"      # 静音


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
class AudioEvent:
    """检测到的音频事件"""
    event_type: AudioEventType
    start_time: float = 0.0
    end_time: float = 0.0
    confidence: float = 0.0


@dataclass 
class AcousticFeatures:
    """声学特征"""
    # 频谱特征
    spectral_centroid_mean: float = 0.0     # 频谱质心
    spectral_bandwidth_mean: float = 0.0   # 频谱带宽
    spectral_contrast_mean: float = 0.0    # 频谱对比度
    spectral_rolloff_mean: float = 0.0     # 频谱衰减点
    
    # MFCC 特征
    mfcc_mean: List[float] = field(default_factory=list)  # 13维 MFCC 均值
    mfcc_std: List[float] = field(default_factory=list)   # 13维 MFCC 标准差
    delta_mfcc_mean: List[float] = field(default_factory=list)
    
    # 基频/音调特征
    pitch_mean: float = 0.0      # 平均基频 (Hz)
    pitch_std: float = 0.0       # 基频标准差
    pitch_max: float = 0.0       # 最大基频
    pitch_min: float = 0.0      # 最小基频
    
    # 能量/响度特征
    rms_energy_mean: float = 0.0     # 平均 RMS 能量
    rms_energy_std: float = 0.0      # 能量标准差
    zero_crossing_rate_mean: float = 0.0  # 零交叉率均值
    
    # 语速估计
    speech_rate: float = 0.0     # 字/秒
    pause_ratio: float = 0.0    # 停顿比例
    avg_speech_segment_duration: float = 0.0  # 平均语音片段时长
    
    # 风险指标
    pitch_anomaly_score: float = 0.0    # 音调异常分数
    energy_anomaly_score: float = 0.0   # 能量异常分数
    speech_rate_anomaly_score: float = 0.0  # 语速异常分数
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "spectral": {
                "centroid": self.spectral_centroid_mean,
                "bandwidth": self.spectral_bandwidth_mean,
                "contrast": self.spectral_contrast_mean,
                "rolloff": self.spectral_rolloff_mean
            },
            "mfcc": {
                "mean": self.mfcc_mean,
                "std": self.mfcc_std,
                "delta_mean": self.delta_mfcc_mean
            },
            "pitch": {
                "mean": self.pitch_mean,
                "std": self.pitch_std,
                "max": self.pitch_max,
                "min": self.pitch_min,
                "anomaly_score": self.pitch_anomaly_score
            },
            "energy": {
                "rms_mean": self.rms_energy_mean,
                "rms_std": self.rms_energy_std,
                "anomaly_score": self.energy_anomaly_score
            },
            "speech_rate": {
                "chars_per_second": self.speech_rate,
                "pause_ratio": self.pause_ratio,
                "avg_segment_duration": self.avg_speech_segment_duration,
                "anomaly_score": self.speech_rate_anomaly_score
            }
        }


@dataclass
class AudioAnalysis:
    """音频分析结果"""
    transcription: str
    language: str
    duration: float
    speaker_count: int
    
    # SenseVoice 输出
    emotion: EmotionLabel = EmotionLabel.NEUTRAL
    emotion_confidence: float = 0.0
    audio_events: List[AudioEvent] = field(default_factory=list)
    itn_text: str = ""  # 反向文本标准化后的文本
    
    # 声学分析
    emotion_signals: List[str] = field(default_factory=list)
    risk_signals: List[str] = field(default_factory=list)
    acoustic_features: Optional[AcousticFeatures] = None
    
    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)


class AudioInputHandler:
    """
    音频输入处理器
    
    使用 SenseVoice 进行：
    - ASR 语音识别
    - 情感识别 (SER)
    - 音频事件检测 (AED)
    
    使用 librosa 进行：
    - MFCC/频谱特征提取
    - 基频/音调估计
    - 能量/语速分析
    - 声学风险检测
    """
    
    # SenseVoice 模型标识
    SENSEVOICE_MODEL = "iic/SenseVoiceSmall"
    
    # 风险检测阈值
    RISK_THRESHOLDS = {
        "pitch_high": {"threshold": 350, "weight": 2.0},      # 音调过高 (Hz)
        "pitch_low": {"threshold": 80, "weight": 1.5},       # 音调过低
        "pitch_var": {"threshold": 200, "weight": 1.5},     # 音调变化过大
        "speech_rate_fast": {"threshold": 6.0, "weight": 2.0},  # 语速过快 (字/秒)
        "speech_rate_slow": {"threshold": 2.0, "weight": 1.0},   # 语速过慢
        "pause_ratio_high": {"threshold": 0.4, "weight": 1.5}, # 停顿过多
        "energy_high": {"threshold": 0.5, "weight": 1.0},      # 能量过高
        "energy_low": {"threshold": 0.01, "weight": 1.5},      # 能量过低
    }
    
    # 情感关键词增强映射
    EMOTION_KEYWORDS = {
        "anxiety": ["紧张", "害怕", "担心", "着急", "慌", "心慌", "焦虑"],
        "urgency": ["快点", "赶紧", "马上", "立刻", "快", "立即", "十万火急"],
        "threat": ["威胁", "恐吓", "怎么样", "后果", "抓你", "坐牢", "逮捕"],
        "deception": ["不能说", "保密", "秘密", "别告诉", "只能你知道"],
        "manipulation": ["听话", "配合", "帮我", "相信我", "我是你"]
    }
    
    # 风险关键词
    RISK_KEYWORDS = {
        "转账汇款": {"keywords": ["转账", "汇款", "打钱", "付款", "扫码"], "weight": 3.0},
        "验证码泄露": {"keywords": ["验证码", "码", "密码", "登录", "账号"], "weight": 3.0},
        "冒充身份": {"keywords": ["公安", "警察", "法院", "检察官", "局长"], "weight": 2.5},
        "威胁恐吓": {"keywords": ["抓你", "坐牢", "逮捕", "违法", "犯罪"], "weight": 3.0},
        "高收益诱惑": {"keywords": ["赚钱", "收益", "投资", "分红", "稳赚"], "weight": 2.0},
        "安全账户": {"keywords": ["安全账户", "保证金", "解冻", "核查"], "weight": 3.0},
        "虚假绑架": {"keywords": ["绑架", "出事", "受伤", "住院", "被抓"], "weight": 3.0},
        "屏幕共享": {"keywords": ["共享", "屏幕", "远程", "控制", "看看"], "weight": 2.5}
    }
    
    # 模型缓存
    _sensevoice_model = None
    _sensevoice_kwargs = None
    _sensevoice_initialized = False

    def __init__(self, device: Optional[str] = None):
        """
        初始化音频处理器
        
        Args:
            device: 计算设备，如 "cuda:0" 或 "cpu"，默认自动检测
        """
        self.device = device or self._auto_detect_device()
        self.sample_rate = 16000

    def _auto_detect_device(self) -> str:
        """自动检测可用设备"""
        try:
            import torch
            return "cuda:0" if torch.cuda.is_available() else "cpu"
        except ImportError:
            return "cpu"

    @classmethod
    def _init_sensevoice(cls, device: str = "cpu") -> Tuple[Any, Dict]:
        """
        初始化 SenseVoice 模型
        
        Returns:
            (model, kwargs) 元组
        """
        if cls._sensevoice_initialized and cls._sensevoice_model is not None:
            return cls._sensevoice_model, cls._sensevoice_kwargs
        
        try:
            from funasr import AutoModel
            
            print(f"[SenseVoice] Loading model on {device}...")
            model = AutoModel(
                model=cls.SENSEVOICE_MODEL,
                vad_model="fsmn-vad",
                vad_kwargs={"max_single_segment_time": 30000},
                device=device,
                disable_update=True,
            )
            
            cls._sensevoice_model = model
            cls._sensevoice_kwargs = {}
            cls._sensevoice_initialized = True
            print("[OK] [SenseVoice] Model loaded successfully")
            
            return model, cls._sensevoice_kwargs
            
        except ImportError as e:
            print(f"[WARNING] [SenseVoice] funasr not installed: {e}")
            print("[TIP] Run: pip install funasr")
            cls._sensevoice_model = None
            cls._sensevoice_kwargs = None
            cls._sensevoice_initialized = True  # 标记已尝试，避免重复
            return None, {}
        except Exception as e:
            print(f"[WARNING] [SenseVoice] Model load failed: {e}")
            cls._sensevoice_model = None
            cls._sensevoice_kwargs = None
            cls._sensevoice_initialized = True
            return None, {}

    async def process(self, audio_input: AudioInput) -> AudioAnalysis:
        """
        处理音频输入（完整流程）
        
        流程：
        1. SenseVoice ASR + 情感识别 + 音频事件检测
        2. librosa 声学特征提取
        3. 多维度风险评估
        
        Args:
            audio_input: 音频输入
            
        Returns:
            AudioAnalysis: 音频分析结果
        """
        # 0. 获取音频字节
        audio_bytes = await self._get_audio_bytes(audio_input)
        audio_path = await self._save_temp_audio(audio_bytes, audio_input.format)
        
        try:
            # 1. SenseVoice 多任务处理
            sensevoice_result = await self._sensevoice_inference(audio_path, audio_bytes)
            
            # 2. 声学特征提取
            acoustic_features = await self._extract_acoustic_features(
                audio_bytes, 
                audio_input.duration,
                sensevoice_result.get("text", "")
            )
            
            # 3. 情感信号融合（模型 + 关键词）
            emotion_signals = self._fuse_emotion_signals(
                sensevoice_result.get("emotion"),
                sensevoice_result.get("text", "")
            )
            
            # 4. 风险信号检测（关键词 + 声学异常）
            risk_signals = self._detect_risk_signals(
                sensevoice_result.get("text", ""),
                acoustic_features
            )
            
            # 5. 说话人数量估计（简化版）
            speaker_count = self._estimate_speakers(
                sensevoice_result.get("text", "")
            )
            
            # 6. 解析音频事件
            audio_events = self._parse_audio_events(sensevoice_result)
            
            raw_transcription = sensevoice_result.get("text", "")
            cleaned_transcription = _clean_sensevoice_transcription(raw_transcription)
            itn_text = sensevoice_result.get("itn", "") or cleaned_transcription

            return AudioAnalysis(
                transcription=cleaned_transcription if cleaned_transcription else raw_transcription,
                language=sensevoice_result.get("lang", "zh"),
                duration=audio_input.duration or sensevoice_result.get("duration", 0.0),
                speaker_count=speaker_count,
                emotion=EmotionLabel(sensevoice_result.get("emotion", "neutral")),
                emotion_confidence=sensevoice_result.get("emotion_prob", 0.0),
                audio_events=audio_events,
                itn_text=itn_text,
                emotion_signals=emotion_signals,
                risk_signals=risk_signals,
                acoustic_features=acoustic_features,
                metadata={
                    "sample_rate": audio_input.sample_rate,
                    "format": audio_input.format,
                    "model": "SenseVoice-Small",
                    "has_vad": True,
                    **audio_input.metadata
                }
            )
            
        finally:
            # 清理临时文件
            if audio_path and os.path.exists(audio_path):
                try:
                    os.unlink(audio_path)
                except Exception:
                    pass

    async def _sensevoice_inference(
        self, 
        audio_path: str,
        audio_bytes: bytes
    ) -> Dict[str, Any]:
        """
        SenseVoice 推理
        
        支持：
        - ASR 语音识别
        - 情感识别 (happy/sad/angry/neutral)
        - 音频事件检测
        - 语种识别
        
        Returns:
            包含 text, emotion, emotion_prob, lang, duration 等字段的字典
        """
        # 初始化模型（延迟加载）
        if not self._sensevoice_initialized:
            self._init_sensevoice(self.device)
        
        model = self._sensevoice_model
        
        if model is None:
            # 模型未安装，返回降级结果
            return {
                "text": "[SenseVoice 未安装，请运行: pip install funasr]",
                "emotion": "neutral",
                "emotion_prob": 0.0,
                "lang": "zh",
                "duration": 0.0,
                "events": []
            }
        
        try:
            import os as _os
            print(f"[DEBUG] audio_path='{audio_path}', exists={_os.path.exists(audio_path) if audio_path else False}, audio_bytes_len={len(audio_bytes) if audio_bytes else 0}")
            # 调用 SenseVoice
            result_list = model.generate(
                input=audio_path,
                cache={},
                language="auto",
                use_itn=True,  # 使用反向文本标准化
                batch_size_s=60,
                merge_vad=True,
                merge_length_s=15,
                return_raw_text=True,
                is_final=True
            )
            
            if not result_list or len(result_list) == 0:
                return {
                    "text": "",
                    "emotion": "neutral",
                    "emotion_prob": 0.0,
                    "lang": "zh",
                    "duration": 0.0,
                    "events": []
                }
            
            result = result_list[0]
            
            # 解析结果
            return {
                "text": result.get("text", ""),
                "itn": result.get("itn", ""),  # 反向文本标准化
                "emotion": self._extract_emotion_from_sensevoice(result),
                "emotion_prob": self._extract_emotion_prob(result),
                "lang": result.get("lang", "zh"),
                "duration": result.get("duration", 0.0),
                "events": result.get("events", []),
                "timestamp": result.get("timestamp", [])
            }
            
        except Exception as e:
            print(f"[ERROR] [SenseVoice] Inference failed: {e}")
            return {
                "text": f"[识别失败: {str(e)}]",
                "emotion": "neutral",
                "emotion_prob": 0.0,
                "lang": "zh",
                "duration": 0.0,
                "events": []
            }

    def _extract_emotion_from_sensevoice(self, result: Dict) -> str:
        """从 SenseVoice 结果中提取情感标签"""
        # SenseVoice 可能返回的情感字段
        # 根据官方文档，情感信息可能在不同位置
        if "emotion" in result:
            return result["emotion"]
        if "emotion_label" in result:
            return result["emotion_label"]
        if "sentiment" in result:
            return result["sentiment"]
        
        # 尝试从 text 字段解析情感标签（部分模型会在text中嵌入）
        text = result.get("text", "")
        if "开心" in text or "高兴" in text:
            return "happy"
        if "悲伤" in text or "难过" in text:
            return "sad"
        if "生气" in text or "愤怒" in text:
            return "angry"
        
        return "neutral"

    def _extract_emotion_prob(self, result: Dict) -> float:
        """提取情感置信度"""
        if "emotion_prob" in result:
            return float(result["emotion_prob"])
        if "emotion_confidence" in result:
            return float(result["emotion_confidence"])
        if "sentiment_score" in result:
            return float(result["sentiment_score"])
        return 0.0

    def _parse_audio_events(self, result: Dict) -> List[AudioEvent]:
        """解析音频事件"""
        events = []
        raw_events = result.get("events", [])
        
        if not raw_events:
            return events
        
        for event in raw_events:
            if isinstance(event, dict):
                event_type = event.get("type", "speech")
                events.append(AudioEvent(
                    event_type=AudioEventType(event_type),
                    start_time=event.get("start", 0.0),
                    end_time=event.get("end", 0.0),
                    confidence=event.get("confidence", 0.0)
                ))
            elif isinstance(event, str):
                events.append(AudioEvent(
                    event_type=AudioEventType(event),
                    start_time=0.0,
                    end_time=0.0,
                    confidence=0.0
                ))
        
        return events

    async def _extract_acoustic_features(
        self,
        audio_bytes: bytes,
        duration: Optional[float],
        transcription: str
    ) -> AcousticFeatures:
        """
        提取声学特征
        
        使用 librosa 提取：
        - MFCC 特征（13维 + delta）
        - 频谱特征（质心、带宽、对比度、衰减点）
        - 基频/音调估计
        - RMS 能量
        - 零交叉率
        - 语速/停顿分析
        """
        try:
            import librosa
            import numpy as np
            
            # 加载音频
            audio_array, sr = self._load_audio(audio_bytes, target_sr=self.sample_rate)
            
            if len(audio_array) == 0:
                return AcousticFeatures()
            
            features = AcousticFeatures()
            duration_sec = duration or len(audio_array) / sr
            
            # ========== 1. MFCC 特征 ==========
            mfcc = librosa.feature.mfcc(y=audio_array, sr=sr, n_mfcc=13)
            mfcc_delta = librosa.feature.delta(mfcc)
            
            features.mfcc_mean = mfcc.mean(axis=1).tolist()
            features.mfcc_std = mfcc.std(axis=1).tolist()
            features.delta_mfcc_mean = mfcc_delta.mean(axis=1).tolist()
            
            # ========== 2. 频谱特征 ==========
            spectral_centroid = librosa.feature.spectral_centroid(y=audio_array, sr=sr)
            spectral_bandwidth = librosa.feature.spectral_bandwidth(y=audio_array, sr=sr)
            spectral_contrast = librosa.feature.spectral_contrast(y=audio_array, sr=sr)
            spectral_rolloff = librosa.feature.spectral_rolloff(y=audio_array, sr=sr)
            
            features.spectral_centroid_mean = float(spectral_centroid.mean())
            features.spectral_bandwidth_mean = float(spectral_bandwidth.mean())
            features.spectral_contrast_mean = float(spectral_contrast.mean())
            features.spectral_rolloff_mean = float(spectral_rolloff.mean())
            
            # ========== 3. 基频/音调估计 ==========
            # 使用 pyin 进行基频提取（比praat更稳健）
            try:
                f0, voiced_flag, voiced_probs = librosa.pyin(
                    audio_array,
                    fmin=librosa.note_to_hz('C2'),   # 65 Hz
                    fmax=librosa.note_to_hz('C7'),   # 2093 Hz
                    sr=sr
                )
                
                # 过滤无效值
                valid_f0 = f0[np.isfinite(f0)]
                if len(valid_f0) > 0:
                    features.pitch_mean = float(np.median(valid_f0))
                    features.pitch_std = float(valid_f0.std())
                    features.pitch_max = float(np.max(valid_f0))
                    features.pitch_min = float(np.min(valid_f0))
            except Exception as e:
                print(f"[WARNING] [Pitch extraction] Failed: {e}")
            
            # ========== 4. RMS 能量 ==========
            rms = librosa.feature.rms(y=audio_array)
            features.rms_energy_mean = float(rms.mean())
            features.rms_energy_std = float(rms.std())
            
            # ========== 5. 零交叉率 ==========
            zcr = librosa.feature.zero_crossing_rate(audio_array)
            features.zero_crossing_rate_mean = float(zcr.mean())
            
            # ========== 6. 语速估计 ==========
            speech_rate, pause_ratio = self._estimate_speech_rate(
                audio_array, sr, transcription
            )
            features.speech_rate = speech_rate
            features.pause_ratio = pause_ratio
            
            # ========== 7. 计算风险异常分数 ==========
            features.pitch_anomaly_score = self._calculate_pitch_anomaly(features)
            features.energy_anomaly_score = self._calculate_energy_anomaly(features)
            features.speech_rate_anomaly_score = self._calculate_speech_rate_anomaly(features)
            
            return features
            
        except ImportError as e:
            print(f"[WARNING] [librosa] Not installed: {e}")
            return AcousticFeatures()
        except Exception as e:
            print(f"[ERROR] [Acoustic features] Extraction failed: {e}")
            return AcousticFeatures()

    def _load_audio(
        self, 
        audio_bytes: bytes, 
        target_sr: int = 16000
    ) -> Tuple[np.ndarray, int]:
        """加载并重采样音频"""
        import librosa
        import numpy as np
        
        try:
            # librosa 可以直接从字节加载
            audio_array, sr = librosa.load(
                io.BytesIO(audio_bytes),
                sr=target_sr,
                mono=True
            )
            return audio_array, sr
        except Exception as e:
            print(f"[WARNING] [Audio load] librosa failed, trying soundfile: {e}")
            
            # 备用：使用 soundfile
            try:
                import soundfile as sf
                audio_array, sr = sf.read(io.BytesIO(audio_bytes))
                if len(audio_array.shape) > 1:
                    audio_array = audio_array.mean(axis=1)
                if sr != target_sr:
                    import librosa
                    audio_array = librosa.resample(audio_array, orig_sr=sr, target_sr=target_sr)
                    sr = target_sr
                return audio_array, sr
            except Exception as e2:
                print(f"[ERROR] [Audio load] All methods failed: {e2}")
                return np.array([]), target_sr

    def _estimate_speech_rate(
        self, 
        audio_array, 
        sr: int, 
        transcription: str
    ) -> Tuple[float, float]:
        """
        估计语速和停顿比例
        
        Returns:
            (speech_rate, pause_ratio)
            - speech_rate: 字/秒
            - pause_ratio: 静音帧比例
        """
        import librosa
        import numpy as np
        
        duration = len(audio_array) / sr
        
        # 计算静音比例（基于能量阈值）
        rms = librosa.feature.rms(y=audio_array)
        energy_threshold = rms.mean() * 0.1
        silence_frames = np.sum(rms < energy_threshold)
        pause_ratio = silence_frames / len(rms[0]) if len(rms[0]) > 0 else 0.0
        
        # 基于转写文本估计语速
        if transcription and duration > 0:
            # 粗略估计中文字符数
            chinese_chars = len([c for c in transcription if '\u4e00' <= c <= '\u9fff'])
            speech_rate = chinese_chars / duration
        else:
            # 基于音频能量分布估计
            speech_frames = np.sum(rms >= energy_threshold)
            speech_duration = speech_frames * (len(audio_array) / sr) / len(rms[0])
            speech_rate = speech_duration / duration if duration > 0 else 0.0
        
        return speech_rate, pause_ratio

    def _calculate_pitch_anomaly(self, features: AcousticFeatures) -> float:
        """计算音调异常分数"""
        score = 0.0
        
        # 音调过高
        if features.pitch_mean > self.RISK_THRESHOLDS["pitch_high"]["threshold"]:
            score += self.RISK_THRESHOLDS["pitch_high"]["weight"]
        
        # 音调过低
        if features.pitch_mean < self.RISK_THRESHOLDS["pitch_low"]["threshold"]:
            score += self.RISK_THRESHOLDS["pitch_low"]["weight"]
        
        # 音调变化过大
        if features.pitch_std > self.RISK_THRESHOLDS["pitch_var"]["threshold"]:
            score += self.RISK_THRESHOLDS["pitch_var"]["weight"]
        
        return min(score, 5.0)  # 最高5分

    def _calculate_energy_anomaly(self, features: AcousticFeatures) -> float:
        """计算能量异常分数"""
        score = 0.0
        
        # 能量过高（可能表示喊叫或情绪激动）
        if features.rms_energy_mean > self.RISK_THRESHOLDS["energy_high"]["threshold"]:
            score += self.RISK_THRESHOLDS["energy_high"]["weight"]
        
        # 能量过低（可能表示紧张、压抑）
        if features.rms_energy_mean < self.RISK_THRESHOLDS["energy_low"]["threshold"]:
            score += self.RISK_THRESHOLDS["energy_low"]["weight"]
        
        return min(score, 5.0)

    def _calculate_speech_rate_anomaly(self, features: AcousticFeatures) -> float:
        """计算语速异常分数"""
        score = 0.0
        
        # 语速过快
        if features.speech_rate > self.RISK_THRESHOLDS["speech_rate_fast"]["threshold"]:
            score += self.RISK_THRESHOLDS["speech_rate_fast"]["weight"]
        
        # 语速过慢
        if features.speech_rate < self.RISK_THRESHOLDS["speech_rate_slow"]["threshold"]:
            score += self.RISK_THRESHOLDS["speech_rate_slow"]["weight"]
        
        # 停顿过多
        if features.pause_ratio > self.RISK_THRESHOLDS["pause_ratio_high"]["threshold"]:
            score += self.RISK_THRESHOLDS["pause_ratio_high"]["weight"]
        
        return min(score, 5.0)

    def _fuse_emotion_signals(
        self, 
        model_emotion: str, 
        transcription: str
    ) -> List[str]:
        """
        融合情感信号
        
        结合 SenseVoice 模型输出和关键词匹配
        """
        signals = []
        
        # 1. 模型识别的情感
        emotion_map = {
            "happy": "高兴",
            "sad": "悲伤",
            "angry": "愤怒",
            "neutral": "中性",
            "fear": "恐惧",
            "surprise": "惊讶"
        }
        
        if model_emotion in emotion_map:
            signals.append(emotion_map[model_emotion])
        
        # 2. 关键词匹配增强
        for emotion, keywords in self.EMOTION_KEYWORDS.items():
            if any(kw in transcription for kw in keywords):
                emotion_label_map = {
                    "anxiety": "焦虑",
                    "urgency": "急迫",
                    "threat": "被威胁",
                    "deception": "疑似欺骗",
                    "manipulation": "疑似操控"
                }
                if emotion_label_map.get(emotion) not in signals:
                    signals.append(emotion_label_map.get(emotion, emotion))
        
        return list(set(signals))

    def _detect_risk_signals(
        self,
        transcription: str,
        acoustic_features: AcousticFeatures
    ) -> List[str]:
        """
        检测风险信号
        
        结合：
        1. 文本关键词匹配
        2. 声学异常检测
        """
        signals = []
        
        # 1. 关键词检测
        for category, config in self.RISK_KEYWORDS.items():
            if any(kw in transcription for kw in config["keywords"]):
                signals.append(category)
        
        # 2. 声学异常检测
        if acoustic_features.pitch_anomaly_score > 2.0:
            if "音调异常" not in signals:
                signals.append("声学异常-音调")
        
        if acoustic_features.speech_rate_anomaly_score > 2.0:
            if "语速异常" not in signals:
                signals.append("声学异常-语速")
        
        if acoustic_features.energy_anomaly_score > 2.0:
            if "能量异常" not in signals:
                signals.append("声学异常-能量")
        
        # 3. 组合风险模式检测
        combined_risk = self._detect_combined_patterns(transcription, acoustic_features)
        signals.extend(combined_risk)
        
        return list(set(signals))

    def _detect_combined_patterns(
        self,
        transcription: str,
        acoustic_features: AcousticFeatures
    ) -> List[str]:
        """
        检测组合风险模式
        
        例如：急促+转账 = 高风险
        """
        patterns = []
        
        # 模式1：急迫 + 转账 = 典型诈骗
        has_urgency = any(kw in transcription for kw in 
                         ["快", "马上", "赶紧", "立刻", "快点"])
        has_transfer = any(kw in transcription for kw in 
                          ["转账", "汇款", "打钱", "付款", "扫码"])
        if has_urgency and has_transfer:
            patterns.append("紧急转账诈骗")
        
        # 模式2：威胁 + 安全账户 = 典型公检法诈骗
        has_threat = any(kw in transcription for kw in 
                        ["抓你", "坐牢", "违法", "犯罪", "出事"])
        has_safe_account = any(kw in transcription for kw in 
                               ["安全账户", "保证金", "解冻", "核查"])
        if has_threat and has_safe_account:
            patterns.append("冒充公检法诈骗")
        
        # 模式3：保密 + 屏幕共享 = 电信诈骗特征
        has_secret = any(kw in transcription for kw in 
                        ["保密", "不能说", "秘密", "别告诉"])
        has_screen = any(kw in transcription for kw in 
                        ["屏幕", "共享", "远程", "看看"])
        if has_secret and has_screen:
            patterns.append("电信诈骗特征")
        
        # 模式4：声学异常 + 关键词 = 综合风险
        if acoustic_features.pitch_anomaly_score > 3.0:
            if any(kw in transcription for kw in ["你", "我", "钱", "转"]):
                patterns.append("声学综合风险")
        
        return patterns

    def _estimate_speakers(self, transcription: str) -> int:
        """
        估计说话人数量
        
        简化实现：基于对话标记符
        完整实现需要使用 pyannote-audio 或 NeMo Diarization
        """
        dialogue_markers = ["说", "道", "问", "答", "：", ":", "?", "？", "，", "。"]
        marker_count = sum(transcription.count(m) for m in dialogue_markers)
        
        if marker_count > 5:
            return 2
        return 1

    async def _get_audio_bytes(self, audio_input: AudioInput) -> bytes:
        """获取音频字节数据"""
        if audio_input.audio_data:
            return audio_input.audio_data
        
        if audio_input.audio_path and os.path.exists(audio_input.audio_path):
            with open(audio_input.audio_path, 'rb') as f:
                return f.read()
        
        if audio_input.audio_base64:
            return base64.b64decode(audio_input.audio_base64)
        
        return b""

    async def _save_temp_audio(self, audio_bytes: bytes, format: str) -> str:
        """保存临时音频文件"""
        if not audio_bytes:
            return ""

        suffix_map = {
            "mp3": "mp3", "wav": "wav", "m4a": "m4a",
            "ogg": "ogg", "webm": "webm", "flac": "flac"
        }
        suffix = suffix_map.get(format.lower(), "mp3")

        try:
            # 使用纯 ASCII 路径避免 FFmpeg 中文路径问题
            import tempfile, uuid
            tmp_dir = tempfile.gettempdir()
            ascii_name = f"audio_{uuid.uuid4().hex}.{suffix}"
            tmp_path = os.path.join(tmp_dir, ascii_name)
            with open(tmp_path, 'wb') as f:
                f.write(audio_bytes)
            return tmp_path
        except Exception as e:
            print(f"[WARNING] [Temp audio] Save failed: {e}")
            return ""

    def merge_with_text(
        self, 
        audio_analysis: AudioAnalysis,
        text_analysis: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        与文本分析结果融合
        
        用于多模态融合模块
        """
        merged = {
            "transcription": audio_analysis.transcription,
            "itn_text": audio_analysis.itn_text,
            "language": audio_analysis.language,
            "emotion": audio_analysis.emotion.value,
            "emotion_confidence": audio_analysis.emotion_confidence,
            "emotion_signals": audio_analysis.emotion_signals,
            "risk_signals": audio_analysis.risk_signals,
            "audio_events": [
                {"type": e.event_type.value, "start": e.start_time, "end": e.end_time}
                for e in audio_analysis.audio_events
            ],
            "duration": audio_analysis.duration,
            "speaker_count": audio_analysis.speaker_count,
            "acoustic_features": audio_analysis.acoustic_features.to_dict() 
                                if audio_analysis.acoustic_features else {}
        }
        
        if text_analysis:
            merged["text_entities"] = getattr(text_analysis, "entity_tags", [])
            merged["text_intents"] = getattr(text_analysis, "intent_signals", [])
            merged["text_risk_indicators"] = getattr(text_analysis, "risk_indicators", [])
        
        return merged


# ========== 便捷函数 ==========

async def process_audio(audio_bytes: bytes, format: str = "mp3") -> AudioAnalysis:
    """
    便捷函数：处理音频字节
    
    Args:
        audio_bytes: 音频数据
        format: 音频格式
        
    Returns:
        AudioAnalysis 结果
    """
    handler = AudioInputHandler()
    audio_input = AudioInput(
        audio_data=audio_bytes,
        format=format
    )
    return await handler.process(audio_input)
