"""
视觉输入处理模块
支持图片、视频流的分析和特征提取
"""

import base64
import io
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import asyncio


@dataclass
class VisualInput:
    """视觉输入结构"""
    image_data: Optional[bytes] = None
    image_path: Optional[str] = None
    image_base64: Optional[str] = None
    video_path: Optional[str] = None
    video_frames: Optional[List[bytes]] = None
    source: str = "upload"  # upload, camera, screenshot
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class VisualAnalysis:
    """视觉分析结果"""
    image_description: str
    detected_objects: List[Dict[str, Any]]
    detected_faces: List[Dict[str, Any]]
    text_ocr: List[str]
    suspicious_elements: List[Dict[str, Any]]
    deepfake_indicators: Dict[str, Any]
    scene_type: str
    confidence: float
    metadata: Dict[str, Any]


class VisualInputHandler:
    """视觉输入处理器"""
    
    # 可疑元素检测规则
    SUSPICIOUS_PATTERNS = {
        "fake_qr": {
            "description": "可疑二维码",
            "indicators": ["模糊", "拼接", "异常尺寸"]
        },
        "fake_id": {
            "description": "伪造证件",
            "indicators": ["PS痕迹", "字体异常", "水印缺失"]
        },
        "fake_screenshot": {
            "description": "伪造截图",
            "indicators": ["重复元素", "边缘异常", "文字模糊"]
        },
        "phishing_link": {
            "description": "钓鱼链接",
            "indicators": ["可疑URL", "仿冒网站"]
        }
    }
    
    # 场景类型
    SCENE_TYPES = {
        "chat_screenshot": "聊天截图",
        "transfer_screenshot": "转账截图",
        "id_card": "身份证照片",
        "official_document": "官方文件",
        "webpage": "网页截图",
        "unknown": "其他"
    }
    
    def __init__(self, clip_model: Optional[Any] = None, yolo_model: Optional[Any] = None):
        """
        初始化视觉处理器
        
        Args:
            clip_model: CLIP模型实例（用于图像描述）
            yolo_model: YOLO模型实例（用于目标检测）
        """
        self.clip_model = clip_model
        self.yolo_model = yolo_model
    
    async def process(self, visual_input: VisualInput) -> VisualAnalysis:
        """
        处理视觉输入
        
        Args:
            visual_input: 视觉输入
            
        Returns:
            VisualAnalysis: 视觉分析结果
        """
        # 1. 图像预处理
        image = await self._load_image(visual_input)
        
        # 2. 图像描述生成
        description = await self._generate_description(image, visual_input.source)
        
        # 3. 目标检测
        detected_objects = await self._detect_objects(image)
        
        # 4. 人脸检测
        detected_faces = await self._detect_faces(image)
        
        # 5. OCR文字识别
        ocr_texts = await self._ocr_text(image)
        
        # 6. 可疑元素检测
        suspicious = await self._detect_suspicious(image, detected_objects, ocr_texts)
        
        # 7. 深度伪造检测
        deepfake_indicators = await self._detect_deepfake(image, detected_faces)
        
        # 8. 场景分类
        scene_type = self._classify_scene(detected_objects, ocr_texts)
        
        # 计算总体置信度
        confidence = self._calculate_confidence(
            description, suspicious, deepfake_indicators
        )
        
        return VisualAnalysis(
            image_description=description,
            detected_objects=detected_objects,
            detected_faces=detected_faces,
            text_ocr=ocr_texts,
            suspicious_elements=suspicious,
            deepfake_indicators=deepfake_indicators,
            scene_type=scene_type,
            confidence=confidence,
            metadata={
                "source": visual_input.source,
                "has_video": visual_input.video_path is not None,
                **visual_input.metadata
            }
        )
    
    async def _load_image(self, visual_input: VisualInput):
        """加载图像"""
        if visual_input.image_data:
            return visual_input.image_data
        
        if visual_input.image_path:
            with open(visual_input.image_path, 'rb') as f:
                return f.read()
        
        if visual_input.image_base64:
            # 移除data URI前缀
            if ',' in visual_input.image_base64:
                base64_str = visual_input.image_base64.split(',')[1]
            else:
                base64_str = visual_input.image_base64
            return base64.b64decode(base64_str)
        
        return None
    
    async def _generate_description(self, image: Optional[bytes],
                                     source: str) -> str:
        """生成图像描述"""
        if not image:
            return "[无图像数据]"

        # 如果有CLIP模型，使用它
        if self.clip_model:
            # 实际实现
            # description = self.clip_model.describe(image)
            pass

        # 提取OCR文字
        ocr_texts = await self._ocr_text(image)

        # 提取对象检测
        objects = await self._detect_objects(image)

        # 构建描述
        descriptions = []

        # 基于来源的描述
        source_descriptions = {
            "screenshot": "这是一张屏幕截图",
            "upload": "这是一张上传的图片",
            "camera": "这是一张摄像头拍摄的图片"
        }
        descriptions.append(source_descriptions.get(source, "这是一张图片"))

        # 添加OCR识别的文字
        if ocr_texts:
            valid_texts = [t for t in ocr_texts if not t.startswith("[")]
            if valid_texts:
                descriptions.append(f"图片中包含的文字：{' | '.join(valid_texts[:10])}")
            else:
                descriptions.append(ocr_texts[0])

        # 添加检测到的对象
        if objects:
            obj_names = [o.get('class', '未知') for o in objects[:5]]
            descriptions.append(f"检测到的内容：{', '.join(obj_names)}")

        return "；".join(descriptions) if descriptions else "这是一张图片"
    
    async def _detect_objects(self, image: Optional[bytes]) -> List[Dict[str, Any]]:
        """目标检测"""
        objects = []
        
        if not image:
            return objects
        
        # 如果有YOLO模型，使用它
        if self.yolo_model:
            # 实际实现
            # results = self.yolo_model.detect(image)
            # for r in results:
            #     objects.append({
            #         "class": r.class_name,
            #         "confidence": r.confidence,
            #         "bbox": r.bbox
            #     })
            pass
        
        # 常见检测对象关键词
        common_objects = [
            "身份证", "银行卡", "手机", "电脑",
            "人民币", "美元", "转账界面", "聊天界面",
            "二维码", "条形码", "印章", "签名"
        ]
        
        return objects
    
    async def _detect_faces(self, image: Optional[bytes]) -> List[Dict[str, Any]]:
        """人脸检测"""
        faces = []
        
        if not image:
            return faces
        
        # 实际实现需要使用人脸检测库
        # 使用OpenCV或face_recognition库
        
        return faces
    
    async def _ocr_text(self, image: Optional[bytes]) -> List[str]:
        """OCR文字识别"""
        texts = []

        if not image:
            return texts

        try:
            # 尝试使用Pillow读取图片并尝试简单文字检测
            from PIL import Image
            import io

            img = Image.open(io.BytesIO(image))

            # 尝试使用EasyOCR（如果安装）
            try:
                import torch
                gpu = torch.cuda.is_available()
                import easyocr
                reader = easyocr.Reader(['ch_sim', 'en'], gpu=gpu)
                results = reader.readtext(image)
                for (bbox, text, confidence) in results:
                    if confidence > 0.3 and text.strip():
                        texts.append(text.strip())
            except ImportError:
                # 尝试使用 paddleocr
                try:
                    from paddleocr import PaddleOCR
                    import torch
                    use_gpu = torch.cuda.is_available()
                    ocr = PaddleOCR(use_angle_cls=True, lang='ch', use_gpu=use_gpu)
                    result = ocr.ocr(image, cls=True)
                    if result:
                        for line in result:
                            for item in line:
                                if item and len(item) >= 2:
                                    texts.append(str(item[1]).strip())
                except ImportError:
                    # 简单基于PIL的亮度分析检测文本区域
                    # 适用于明显的大字文本
                    img_gray = img.convert('L')
                    pixels = list(img_gray.getdata())
                    width, height = img.size

                    # 检测是否有高对比度区域（可能是文字）
                    has_text = False
                    for y in range(height):
                        row = pixels[y*width:(y+1)*width]
                        if max(row) - min(row) > 100:  # 高对比度行
                            has_text = True

                    if has_text:
                        texts.append("[图片中可能包含文字，请安装EasyOCR或PaddleOCR以获取完整OCR功能]")

        except Exception as e:
            texts.append(f"[OCR处理失败: {str(e)}]")

        return texts
    
    async def _detect_suspicious(self, image: Optional[bytes],
                                 objects: List[Dict],
                                 ocr_texts: List[str]) -> List[Dict[str, Any]]:
        """检测可疑元素"""
        suspicious = []
        
        if not image:
            return suspicious
        
        # 检测可疑对象
        suspicious_keywords = {
            "qr_code": ["二维码", "扫码", "扫码支付"],
            "fake_document": ["假证件", "伪造", "PS"],
            "suspicious_amount": ["转账", "汇款", "金额"]
        }
        
        # 检测OCR文本中的可疑内容
        for text in ocr_texts:
            for category, keywords in suspicious_keywords.items():
                if any(kw in text for kw in keywords):
                    suspicious.append({
                        "type": category,
                        "text": text,
                        "confidence": 0.7
                    })
        
        return suspicious
    
    async def _detect_deepfake(self, image: Optional[bytes],
                              faces: List[Dict]) -> Dict[str, Any]:
        """深度伪造检测"""
        indicators = {
            "score": 0.0,
            "warnings": [],
            "details": {}
        }
        
        if not image or not faces:
            return indicators
        
        # 实际实现需要使用深度伪造检测模型
        # 可以使用FaceForensics++数据集训练的模型
        
        return indicators
    
    def _classify_scene(self, objects: List[Dict], 
                       ocr_texts: List[str]) -> str:
        """场景分类"""
        # 基于检测到的对象和OCR文本分类场景
        
        all_text = " ".join(ocr_texts)
        
        # 聊天截图
        chat_keywords = ["对方", "我", "说", "吗", "呢"]
        if sum(1 for kw in chat_keywords if kw in all_text) >= 2:
            return self.SCENE_TYPES["chat_screenshot"]
        
        # 转账截图
        transfer_keywords = ["转账", "汇款", "金额", "到账", "交易"]
        if sum(1 for kw in transfer_keywords if kw in all_text) >= 2:
            return self.SCENE_TYPES["transfer_screenshot"]
        
        # 身份证
        id_keywords = ["身份证", "姓名", "性别", "民族", "出生", "住址"]
        if sum(1 for kw in id_keywords if kw in all_text) >= 3:
            return self.SCENE_TYPES["id_card"]
        
        # 官方文件
        official_keywords = ["公章", "印章", "文件", "通知", "决定"]
        if sum(1 for kw in official_keywords if kw in all_text) >= 2:
            return self.SCENE_TYPES["official_document"]
        
        # 网页截图
        web_keywords = ["http", "www", ".com", ".cn", "网站"]
        if any(kw in all_text.lower() for kw in web_keywords):
            return self.SCENE_TYPES["webpage"]
        
        return self.SCENE_TYPES["unknown"]
    
    def _calculate_confidence(self, description: str,
                              suspicious: List[Dict],
                              deepfake: Dict) -> float:
        """计算置信度"""
        confidence = 0.5  # 基础置信度
        
        # 描述完整性
        if description and description != "[无图像数据]":
            confidence += 0.1
        
        # 可疑元素影响
        if suspicious:
            confidence -= 0.1 * len(suspicious)
        
        # 深度伪造分数
        if deepfake.get("score", 0) > 0.5:
            confidence -= 0.2
        
        return max(0.0, min(1.0, confidence))
    
    def process_video_frames(self, frames: List[bytes]) -> List[VisualAnalysis]:
        """处理视频帧序列"""
        results = []
        
        for i, frame in enumerate(frames):
            visual_input = VisualInput(
                image_data=frame,
                metadata={"frame_index": i, "total_frames": len(frames)}
            )
            
            # 同步处理（实际可以是异步）
            result = asyncio.run(self.process(visual_input))
            results.append(result)
        
        return results
    
    def merge_multimodal(self, visual: VisualAnalysis, 
                        text: Optional[str],
                        audio: Optional[str]) -> str:
        """多模态信息融合描述"""
        parts = []
        
        # 图像描述
        if visual.image_description:
            parts.append(f"【图像】{visual.image_description}")
        
        # OCR文字
        if visual.text_ocr:
            ocr_text = "，".join(visual.text_ocr[:10])
            parts.append(f"【文字识别】{ocr_text}")
        
        # 场景类型
        if visual.scene_type != "unknown":
            parts.append(f"【场景】{visual.scene_type}")
        
        # 可疑元素
        if visual.suspicious_elements:
            elements = [e["type"] for e in visual.suspicious_elements]
            parts.append(f"【可疑元素】{', '.join(elements)}")
        
        # 深度伪造警告
        if visual.deepfake_indicators.get("score", 0) > 0.5:
            parts.append("【警告】可能存在深度伪造")
        
        return " | ".join(parts)
