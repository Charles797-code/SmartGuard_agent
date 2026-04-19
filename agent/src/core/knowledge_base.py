"""
知识库加载模块
支持从文件夹加载 .txt 和 .json 文件，构建可检索的知识库
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


@dataclass
class KnowledgeDocument:
    """知识文档"""
    content: str
    source: str
    doc_type: str  # txt, json
    title: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "content": self.content,
            "source": self.source,
            "doc_type": self.doc_type,
            "title": self.title,
            "metadata": self.metadata
        }


class KnowledgeBaseLoader:
    """知识库加载器"""
    
    def __init__(self, base_path: str = "knowledge_base"):
        """
        初始化知识库加载器
        
        Args:
            base_path: 知识库根目录路径
        """
        self.base_path = Path(base_path)
        self.documents: List[KnowledgeDocument] = []
        
    def load_folder(self, recursive: bool = True) -> List[KnowledgeDocument]:
        """
        加载文件夹中的所有知识文档

        Args:
            recursive: 是否递归扫描子文件夹

        Returns:
            加载的文档列表
        """
        self.documents = []

        if not self.base_path.exists():
            print(f"警告: 知识库路径不存在: {self.base_path}")
            return self.documents

        # 支持的文件类型
        extensions = ['.txt', '.json', '.jsonl']

        # 遍历目录
        if recursive:
            files = self.base_path.rglob('*')
        else:
            files = self.base_path.glob('*')

        for file in files:
            if file.is_file() and file.suffix.lower() in extensions:
                self._load_file(file)

        # 额外加载 merged_result 目录中的对话数据（config.json）
        self._load_merged_result()

        print(f"知识库加载完成: 共 {len(self.documents)} 个文档")
        return self.documents
    
    def _load_file(self, path: Path):
        """加载单个文件"""
        try:
            if path.suffix.lower() == '.txt':
                self._load_txt(path)
            elif path.suffix.lower() == '.json':
                self._load_json(path)
            elif path.suffix.lower() == '.jsonl':
                self._load_jsonl(path)
        except Exception as e:
            print(f"加载文件失败 {path}: {e}")
    
    def _load_txt(self, path: Path):
        """加载文本文件"""
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        doc = KnowledgeDocument(
            content=content,
            source=str(path.relative_to(self.base_path.parent)),
            doc_type="txt",
            title=path.stem,
            metadata={
                "file_name": path.name,
                "size": path.stat().st_size
            }
        )
        self.documents.append(doc)
    
    def _load_json(self, path: Path):
        """加载 JSON 文件"""
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 处理 JSON 对象或数组
        if isinstance(data, dict):
            self._process_json_dict(data, path)
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    self._process_json_dict(item, path)
    
    def _load_jsonl(self, path: Path):
        """加载 JSONL 文件（支持 TeleAntiFraud-28k 等数据集）"""
        import re
        
        with open(path, 'r', encoding='utf-8') as f:
            for line_idx, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                
                # 处理 messages 格式（TeleAntiFraud-28k）
                if 'messages' in data and isinstance(data['messages'], list):
                    self._process_tele_fraud_record(data, path, line_idx)
                    continue
                
                # 处理普通 JSON 对象
                if isinstance(data, dict):
                    self._process_json_dict(data, path)

    def _load_merged_result(self):
        """加载 merged_result 目录中的对话数据（config.json 格式）"""
        import re

        merged_dir = self.base_path / "merged_result"
        if not merged_dir.exists():
            return

        count = 0
        for subdir in merged_dir.iterdir():
            if not subdir.is_dir():
                continue

            # NEG = 诈骗，POS = 正常
            label_tag = "【诈骗对话】" if "NEG" in subdir.name else "【正常对话】"

            for tts_dir in subdir.iterdir():
                if not tts_dir.is_dir() or not tts_dir.name.startswith("tts_test"):
                    continue

                config_path = tts_dir / "config.json"
                if not config_path.exists():
                    continue

                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)

                    segments = config.get("audio_segments", [])
                    if not segments:
                        continue

                    # 整理对话文本
                    parts = []
                    for seg in segments:
                        role = seg.get("role", "")
                        content = seg.get("content", "")
                        if content and role in ("left", "right"):
                            tag = "骗子" if role == "left" else "客服"
                            parts.append(f"【{tag}】{content}")

                    if not parts:
                        continue

                    # 获取通话终止状态
                    terminated = config.get("terminated_by_manager", False)
                    end_call = config.get("end_call_signal_detected", False)
                    term_reason = config.get("termination_reason", "")

                    lines = [
                        label_tag,
                        f"=== 通话记录 ===",
                        "\n".join(parts),
                    ]
                    if terminated:
                        lines.append(f"=== 通话状态 ===\n被管理员终止，原因：{term_reason}")
                    elif end_call:
                        lines.append("=== 通话状态 ===\n通话异常结束")

                    full_text = "\n\n".join(lines)

                    doc = KnowledgeDocument(
                        content=full_text[:15000],
                        source=str(Path("TeleAntiFraud-28k") / subdir.name / tts_dir.name),
                        doc_type="merged",
                        title=label_tag[1:-1],
                        metadata={
                            "file_name": config_path.name,
                            "is_fraud": "NEG" in subdir.name,
                            "category": subdir.name,
                            "case_id": tts_dir.name,
                        }
                    )
                    self.documents.append(doc)
                    count += 1

                except Exception:
                    continue

        if count > 0:
            print(f"  从 merged_result 加载了 {count} 条对话数据")

    def _process_tele_fraud_record(self, data: Dict, path: Path, line_idx: int):
        """处理电话诈骗记录（TeleAntiFraud-28k 格式）- 保留原始完整数据"""
        import re

        messages = data.get('messages', [])
        audios = data.get('audios', [])

        # 构建完整的原始对话文本，保留给 LLM 做判断
        conversation_parts = []
        label_parts = []

        for msg in messages:
            role = msg.get('role', '')
            content = msg.get('content', '')

            if role == 'user':
                # 保留原始 user 内容（包含 prompt + 通话转录）
                # 提取纯通话内容（去掉 prompt 模板，只留实际对话）
                text = self._extract_user_content(content)
                if text:
                    conversation_parts.append(f"【骗子】{text}")
                else:
                    # 退而求全：保留原始 content（但去掉标签）
                    clean = re.sub(r'<audio>.*?</audio>', '', content, flags=re.DOTALL)
                    clean = re.sub(r'<[^>]+>', '', clean).strip()
                    if clean and len(clean) > 20:
                        conversation_parts.append(f"【骗子】{clean[:800]}")

            elif role == 'assistant':
                # assistant 内容包含分析结果，提取 <answer> 标签
                answer_match = re.search(r'<answer>\s*(.*?)\s*</answer>', content, re.DOTALL)
                if answer_match:
                    answer_text = answer_match.group(1).strip()
                    # 去掉 markdown 代码块
                    answer_text = re.sub(r'```json\s*', '', answer_text)
                    answer_text = re.sub(r'```\s*', '', answer_text).strip()
                    label_parts.append(f"【分析结果】{answer_text}")
                else:
                    # 保留原始
                    clean = re.sub(r'<[^>]+>', '', content).strip()
                    if clean and len(clean) > 10:
                        label_parts.append(f"【分析结果】{clean[:500]}")

        # 组装：对话 + 分析结果 + 元信息
        full_parts = []
        if conversation_parts:
            full_parts.append("=== 通话记录 ===\n" + "\n".join(conversation_parts))
        if label_parts:
            full_parts.append("=== 分析结果 ===\n" + "\n".join(label_parts))
        if audios:
            full_parts.append(f"=== 音频路径 ===\n{audios[0]}")

        if not full_parts:
            return

        full_text = "\n\n".join(full_parts)

        # 生成标题
        title = "电话诈骗案例"
        content_lower = full_text.lower()
        for kw, label in [
            (("公安", "警方", "法院", "报案"), "冒充公检法诈骗"),
            (("投资", "理财", "收益", "本金"), "投资理财诈骗"),
            (("刷单", "兼职", "返利"), "刷单兼职诈骗"),
            (("客服", "退款"), "客服退款诈骗"),
            (("贷款", "征信"), "贷款征信诈骗"),
            (("杀猪", "网恋"), "杀猪盘诈骗"),
            (("中奖", "奖品"), "虚假中奖诈骗"),
        ]:
            if any(k in content_lower for k in kw):
                title = label
                break

        doc = KnowledgeDocument(
            content=full_text[:20000],
            source=str(path.relative_to(self.base_path.parent)),
            doc_type="jsonl",
            title=title,
            metadata={
                "file_name": path.name,
                "line_index": line_idx,
                "num_messages": len(messages),
                "has_audio": bool(audios),
                "audio_path": audios[0] if audios else "",
            }
        )
        self.documents.append(doc)
    
    def _extract_user_content(self, content: str) -> str:
        """从用户消息中提取通话内容"""
        import re
        
        # 方法1: 优先提取 <audio> 标签内的内容（通话转录）
        if '<audio>' in content:
            # 找到 </audio> 之前的部分
            audio_match = re.search(r'<audio>(.*?)</audio>', content, re.DOTALL)
            if audio_match:
                text = audio_match.group(1).strip()
                if text and len(text) > 10:
                    return text
            # 如果有 <audio> 标签但里面是空的或只有占位符，继续往下
            
            # 尝试找 <audio> 后的内容直到下一个标签
            audio_idx = content.find('<audio>')
            remaining = content[audio_idx + len('<audio>'):]
            # 找到下一个标签
            next_tag = re.search(r'<[^>]+>', remaining)
            if next_tag:
                text = remaining[:next_tag.start()].strip()
                if text and len(text) > 10:
                    return text
        
        # 方法2: 移除所有标签后，检查是否包含有效问题
        text = re.sub(r'<[^>]+>', '', content)
        
        # 检查是否包含有效问题内容（不是纯模板）
        if '通话内容' in text or '判断' in text or '是否' in text:
            # 移除模板提示
            lines = text.split('\n')
            valid_lines = []
            for line in lines:
                # 跳过说明性行
                if re.match(r'^(说明|按照|要求|请|以下|输入)', line):
                    continue
                if '```' in line:
                    continue
                if len(line.strip()) > 0:
                    valid_lines.append(line)
            text = '\n'.join(valid_lines)
        
        return text.strip() if text else ""
    
    def _extract_assistant_content(self, content: str) -> str:
        """从助手消息中提取分析结果"""
        import re
        
        # 方法1: 优先提取 <answer> 标签内的 JSON 内容
        if '<answer>' in content:
            answer_match = re.search(r'<answer>(.*?)</answer>', content, re.DOTALL)
            if answer_match:
                text = answer_match.group(1).strip()
                # 移除模板占位符
                text = re.sub(r'<reason_for_judgment>|<confidence_level>|<true/false>', '', text)
                # 检查是否包含有效 JSON
                if 'reason' in text or 'confidence' in text or 'is_fraud' in text:
                    return text.strip()
        
        # 方法2: 检查是否有实际的思考内容（以<think>开头）
        if '<think>' in content:
            # 提取第一个<think>和第二个</think>之间的内容
            think_match = re.search(r'<think>(.*?)</think>', content, re.DOTALL)
            if think_match:
                text = think_match.group(1).strip()
                if text and len(text) > 20:
                    return text
        
        # 备选：清理后返回
        text = re.sub(r'<[^>]+>', '', content)
        text = text.strip()
        return text if len(text) > 10 else ""
    
    def _process_json_dict(self, data: Dict, path: Path):
        """处理 JSON 字典数据"""
        # 尝试提取内容
        content_fields = ['content', 'text', 'description', 'article']
        title_field = 'title'
        
        content = None
        title = None
        
        for field in content_fields:
            if field in data and isinstance(data[field], str):
                content = data[field]
                break
        
        if 'title' in data:
            title = data['title']
        elif 'name' in data:
            title = data['name']
        
        # 如果没有找到标准内容字段，尝试拼接
        if content is None:
            # 提取所有文本字段拼接
            text_parts = []
            for key, value in data.items():
                if isinstance(value, str) and len(value) > 50:
                    text_parts.append(value)
            content = "\n\n".join(text_parts)
        
        if content:
            doc = KnowledgeDocument(
                content=content[:10000],  # 限制长度
                source=str(path.relative_to(self.base_path.parent)),
                doc_type="json",
                title=title,
                metadata={
                    "file_name": path.name,
                    "original_data": {k: v for k, v in data.items() 
                                     if isinstance(v, (str, int, float, bool))}
                }
            )
            self.documents.append(doc)
        
        # 处理 source_data 数组（反诈案例集）
        if 'source_data' in data and isinstance(data['source_data'], list):
            for item in data['source_data']:
                if isinstance(item, dict):
                    item_content = item.get('content', '')
                    item_title = item.get('title', '')
                    
                    if item_content:
                        doc = KnowledgeDocument(
                            content=item_content[:10000],
                            source=str(path.relative_to(self.base_path.parent)),
                            doc_type="json",
                            title=item_title or path.stem,
                            metadata={
                                "file_name": path.name,
                                "parent_title": data.get('website_name', '')
                            }
                        )
                        self.documents.append(doc)
    
    def get_documents(self) -> List[KnowledgeDocument]:
        """获取所有加载的文档"""
        return self.documents
    
    def get_documents_by_type(self, doc_type: str) -> List[KnowledgeDocument]:
        """按类型获取文档"""
        return [doc for doc in self.documents if doc.doc_type == doc_type]
    
    def search_by_keyword(self, keyword: str) -> List[KnowledgeDocument]:
        """按关键词搜索文档"""
        keyword_lower = keyword.lower()
        results = []
        for doc in self.documents:
            if keyword_lower in doc.content.lower():
                results.append(doc)
        return results
    
    def get_stats(self) -> Dict:
        """获取知识库统计信息"""
        txt_count = len(self.get_documents_by_type('txt'))
        json_count = len(self.get_documents_by_type('json'))
        
        total_chars = sum(len(doc.content) for doc in self.documents)
        
        return {
            "total_documents": len(self.documents),
            "txt_documents": txt_count,
            "json_documents": json_count,
            "total_characters": total_chars,
            "base_path": str(self.base_path)
        }


# 便捷函数
def load_knowledge_base(
    path: str = "knowledge_base",
    recursive: bool = True
) -> List[KnowledgeDocument]:
    """
    便捷函数：加载知识库
    
    Args:
        path: 知识库路径
        recursive: 是否递归扫描
        
    Returns:
        文档列表
    """
    loader = KnowledgeBaseLoader(path)
    return loader.load_folder(recursive=recursive)


if __name__ == "__main__":
    # 测试
    loader = KnowledgeBaseLoader("D:\\agent\\knowledge_base")
    docs = loader.load_folder()
    
    stats = loader.get_stats()
    print(f"\n知识库统计:")
    print(f"  总文档数: {stats['total_documents']}")
    print(f"  文本文件: {stats['txt_documents']}")
    print(f"  JSON文件: {stats['json_documents']}")
    print(f"  总字符数: {stats['total_characters']:,}")