"""
向量存储模块
基于嵌入模型实现文档向量化存储和相似度检索
支持多种嵌入后端：OpenAI、本地模型
"""

import json
import os
import pickle
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
import numpy as np

from .knowledge_base import KnowledgeDocument


@dataclass
class EmbeddedDocument:
    """嵌入后的文档"""
    content: str
    embedding: List[float]
    source: str
    doc_type: str
    title: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    chunk_id: Optional[int] = None
    
    def to_dict(self) -> Dict:
        return {
            "content": self.content,
            "embedding": self.embedding,
            "source": self.source,
            "doc_type": self.doc_type,
            "title": self.title,
            "metadata": self.metadata,
            "chunk_id": self.chunk_id
        }


class EmbeddingModel:
    """嵌入模型基类"""
    
    def __init__(self, model_name: str = "text-embedding-ada-002"):
        self.model_name = model_name
    
    def embed(self, texts: List[str]) -> List[List[float]]:
        """将文本列表转换为嵌入向量"""
        raise NotImplementedError


class OpenAIEmbeddings(EmbeddingModel):
    """OpenAI 嵌入模型"""
    
    def __init__(
        self,
        model_name: str = "text-embedding-ada-002",
        api_key: Optional[str] = None,
        api_base: Optional[str] = None
    ):
        super().__init__(model_name)
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.api_base = api_base or os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
        
        if not self.api_key:
            raise ValueError("需要设置 OPENAI_API_KEY 环境变量")
    
    def embed(self, texts: List[str]) -> List[List[float]]:
        """调用 OpenAI API 获取嵌入"""
        try:
            import openai
        except ImportError:
            raise ImportError("请安装 openai 包: pip install openai")
        
        # 配置 API
        if self.api_base != "https://api.openai.com/v1":
            openai.api_base = self.api_base
        openai.api_key = self.api_key
        
        response = openai.Embedding.create(
            model=self.model_name,
            input=texts
        )
        
        return [item["embedding"] for item in response["data"]]


class LocalEmbeddings(EmbeddingModel):
    """本地嵌入模型（使用 sentence-transformers）"""
    
    def __init__(
        self,
        model_name: str = "shibing624/text2vec-base-chinese",
        device: str = "cpu",
        local_model_path: Optional[str] = None
    ):
        super().__init__(model_name)
        self.device = device
        self._model = None
        self.local_model_path = local_model_path
    
    def _load_model(self):
        if self._model is None:
            # 在导入之前设置离线模式，防止联网
            import os
            os.environ["HF_HUB_OFFLINE"] = "1"
            os.environ["TRANSFORMERS_OFFLINE"] = "1"
            
            try:
                from sentence_transformers import SentenceTransformer
                
                # 确定模型路径
                model_path = self._resolve_model_path()
                
                print(f"[Embedding] 使用模型路径: {model_path}")
                
                # 直接使用本地路径加载
                self._model = SentenceTransformer(
                    str(model_path),
                    device=self.device
                )
            except ImportError:
                raise ImportError("请安装 sentence-transformers: pip install sentence-transformers")
        return self._model
    
    def _resolve_model_path(self) -> Path:
        """解析模型路径"""
        # 1. 如果指定了本地模型路径，直接使用
        if self.local_model_path:
            path = Path(self.local_model_path)
            if path.exists():
                # 如果是 snapshots 目录，进去找子目录
                if path.name == "snapshots":
                    snapshot_dirs = list(path.iterdir())
                    if snapshot_dirs:
                        return snapshot_dirs[0]
                # 如果是模型快照目录本身
                elif any(f.name in ['config.json', 'pytorch_model.bin', 'model.safetensors'] for f in path.iterdir() if f.is_file()):
                    return path
                else:
                    # 检查是否有 snapshots 子目录
                    snapshots = path / "snapshots"
                    if snapshots.exists():
                        snapshot_dirs = list(snapshots.iterdir())
                        if snapshot_dirs:
                            return snapshot_dirs[0]
                    return path
        
        # 2. 检查项目本地的 models 目录
        for base_dir in [Path("D:\\agent\\models"), Path("models"), Path.cwd() / "models"]:
            if base_dir.exists():
                project_models = base_dir / f"models--{self.model_name.replace('/', '--')}"
                if project_models.exists():
                    snapshots = project_models / "snapshots"
                    if snapshots.exists():
                        snapshot_dirs = list(snapshots.iterdir())
                        if snapshot_dirs:
                            return snapshot_dirs[0]
        
        # 3. 回退到模型名称
        print("[Embedding] 警告: 未找到本地模型，将尝试使用默认方式加载")
        return Path(self.model_name)
    
    def embed(self, texts: List[str]) -> List[List[float]]:
        """使用本地模型获取嵌入"""
        model = self._load_model()
        embeddings = model.encode(texts, convert_to_numpy=True)
        return embeddings.tolist()


class VectorStore:
    """向量存储"""
    
    def __init__(
        self,
        embedding_model: Optional[EmbeddingModel] = None,
        storage_path: str = "data/vector_store"
    ):
        """
        初始化向量存储
        
        Args:
            embedding_model: 嵌入模型
            storage_path: 存储路径
        """
        self.embedding_model = embedding_model
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        self.documents: List[EmbeddedDocument] = []
        self.index_path = self.storage_path / "index.pkl"
    
    def _split_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """
        文本分块
        
        Args:
            text: 原始文本
            chunk_size: 块大小（字符）
            overlap: 重叠大小
            
        Returns:
            文本块列表
        """
        if len(text) <= chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            
            # 尝试在句子边界分割
            if end < len(text):
                # 向前查找最后一个句号、问号、感叹号或换行
                for i in range(end, max(start + chunk_size - 100, end - 200), -1):
                    if text[i] in '。！？\n':
                        end = i + 1
                        break
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            start = end - overlap
        
        return chunks
    
    def add_documents(
        self,
        documents: List[KnowledgeDocument],
        chunk_size: int = 500,
        overlap: int = 50,
        batch_size: int = 32,
        show_progress: bool = True
    ) -> int:
        """
        添加文档到向量存储（批量处理）
        
        Args:
            documents: 文档列表
            chunk_size: 分块大小
            overlap: 重叠大小
            batch_size: 批处理大小
            show_progress: 是否显示进度
            
        Returns:
            添加的块数
        """
        if not self.embedding_model:
            raise ValueError("需要先设置 embedding_model")
        
        all_chunks = []
        chunk_sources = []
        
        # 分块
        for doc in documents:
            chunks = self._split_text(doc.content, chunk_size, overlap)
            for i, chunk in enumerate(chunks):
                all_chunks.append(chunk)
                chunk_sources.append({
                    "source": doc.source,
                    "doc_type": doc.doc_type,
                    "title": doc.title,
                    "metadata": doc.metadata,
                    "chunk_id": i,
                    "total_chunks": len(chunks)
                })
        
        if not all_chunks:
            return 0
        
        total_chunks = len(all_chunks)
        print(f"共 {total_chunks} 个文本块，开始嵌入...")
        
        # 批量嵌入
        for i in range(0, total_chunks, batch_size):
            batch_end = min(i + batch_size, total_chunks)
            batch_chunks = all_chunks[i:batch_end]
            batch_sources = chunk_sources[i:batch_end]
            
            # 获取当前批次的嵌入
            embeddings = self.embedding_model.embed(batch_chunks)
            
            # 创建嵌入文档
            for chunk, source_info, embedding in zip(batch_chunks, batch_sources, embeddings):
                embedded_doc = EmbeddedDocument(
                    content=chunk,
                    embedding=embedding,
                    source=source_info["source"],
                    doc_type=source_info["doc_type"],
                    title=source_info["title"],
                    metadata=source_info["metadata"],
                    chunk_id=source_info["chunk_id"]
                )
                self.documents.append(embedded_doc)
            
            # 显示进度
            if show_progress:
                progress = batch_end / total_chunks * 100
                print(f"\r嵌入进度: {batch_end}/{total_chunks} ({progress:.1f}%)", end="", flush=True)
        
        if show_progress:
            print()  # 换行
        
        return total_chunks
    
    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """计算余弦相似度"""
        a = np.array(a)
        b = np.array(b)
        
        dot_product = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return float(dot_product / (norm_a * norm_b))
    
    def search(
        self,
        query: str,
        top_k: int = 5,
        min_similarity: float = 0.3
    ) -> List[Dict[str, Any]]:
        """
        搜索相似文档
        
        Args:
            query: 查询文本
            top_k: 返回数量
            min_similarity: 最小相似度
            
        Returns:
            相似文档列表
        """
        if not self.documents:
            return []
        
        if not self.embedding_model:
            # 简单的关键词匹配
            return self._keyword_search(query, top_k, min_similarity)
        
        # 获取查询嵌入
        query_embedding = self.embedding_model.embed([query])[0]
        
        # 计算相似度
        results = []
        for doc in self.documents:
            similarity = self._cosine_similarity(query_embedding, doc.embedding)
            if similarity >= min_similarity:
                results.append({
                    "content": doc.content,
                    "source": doc.source,
                    "doc_type": doc.doc_type,
                    "title": doc.title,
                    "similarity": similarity,
                    "metadata": doc.metadata
                })
        
        # 排序并返回 top_k
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]
    
    def _keyword_search(
        self,
        query: str,
        top_k: int = 5,
        min_similarity: float = 0.3
    ) -> List[Dict[str, Any]]:
        """简单的关键词搜索"""
        keywords = query.lower().split()
        
        results = []
        for doc in self.documents:
            content_lower = doc.content.lower()
            matches = sum(1 for kw in keywords if kw in content_lower)
            
            if matches > 0:
                # 简单的相似度：匹配关键词数量 / 总关键词数
                similarity = matches / len(keywords)
                
                if similarity >= min_similarity:
                    results.append({
                        "content": doc.content,
                        "source": doc.source,
                        "doc_type": doc.doc_type,
                        "title": doc.title,
                        "similarity": similarity,
                        "metadata": doc.metadata
                    })
        
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]
    
    def save(self):
        """保存索引到磁盘"""
        data = {
            "documents": [doc.to_dict() for doc in self.documents]
        }
        
        with open(self.index_path, 'wb') as f:
            pickle.dump(data, f)
        
        print(f"向量索引已保存: {self.index_path}")
    
    def load(self) -> bool:
        """从磁盘加载索引"""
        if not self.index_path.exists():
            return False
        
        try:
            with open(self.index_path, 'rb') as f:
                data = pickle.load(f)
            
            self.documents = [
                EmbeddedDocument(**doc) for doc in data["documents"]
            ]
            
            print(f"向量索引已加载: {len(self.documents)} 个文档")
            return True
        except Exception as e:
            print(f"加载索引失败: {e}")
            return False
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        if not self.documents:
            return {"count": 0}
        
        avg_length = sum(len(doc.content) for doc in self.documents) / len(self.documents)
        
        return {
            "count": len(self.documents),
            "avg_chunk_length": avg_length,
            "sources": list(set(doc.source for doc in self.documents))
        }


def create_vector_store(
    knowledge_base_path: str = "knowledge_base",
    embedding_type: str = "local",  # "openai" 或 "local"
    model_name: str = "shibing624/text2vec-base-chinese",
    storage_path: str = "data/vector_store",
    local_model_path: Optional[str] = None
) -> VectorStore:
    """
    创建并初始化向量存储
    
    Args:
        knowledge_base_path: 知识库路径
        embedding_type: 嵌入类型
        model_name: 模型名称
        storage_path: 存储路径
        local_model_path: 本地模型路径（优先使用）
        
    Returns:
        VectorStore 实例
    """
    from .knowledge_base import KnowledgeBaseLoader
    
    # 加载知识库
    loader = KnowledgeBaseLoader(knowledge_base_path)
    documents = loader.load_folder()
    
    # 创建嵌入模型
    if embedding_type == "openai":
        embedding_model = OpenAIEmbeddings()
    else:
        embedding_model = LocalEmbeddings(
            model_name=model_name,
            local_model_path=local_model_path
        )
    
    # 创建向量存储
    vector_store = VectorStore(
        embedding_model=embedding_model,
        storage_path=storage_path
    )
    
    # 添加文档
    if documents:
        count = vector_store.add_documents(documents)
        print(f"已添加 {count} 个文档块到向量存储")
    
    return vector_store


if __name__ == "__main__":
    # 测试
    import sys
    
    # 测试加载
    vector_store = create_vector_store(
        knowledge_base_path="D:\\agent\\knowledge_base",
        embedding_type="local"
    )
    
    # 测试搜索
    results = vector_store.search("刷单诈骗", top_k=3)
    
    print(f"\n搜索结果: {len(results)} 个")
    for i, r in enumerate(results, 1):
        print(f"\n--- 结果 {i} (相似度: {r['similarity']:.3f}) ---")
        print(f"来源: {r['source']}")
        print(f"内容: {r['content'][:200]}...")
