"""
向量存储模块
基于 ChromaDB 实现文档向量化存储和相似度检索
支持多种嵌入后端：OpenAI、本地模型
"""

import json
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

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
            import os
            os.environ["HF_HUB_OFFLINE"] = "1"
            os.environ["TRANSFORMERS_OFFLINE"] = "1"
            
            try:
                from sentence_transformers import SentenceTransformer
                model_path = self._resolve_model_path()
                print(f"[Embedding] 使用模型路径: {model_path}")
                self._model = SentenceTransformer(
                    str(model_path),
                    device=self.device
                )
            except ImportError:
                raise ImportError("请安装 sentence-transformers: pip install sentence-transformers")
        return self._model
    
    def _resolve_model_path(self) -> Path:
        """解析模型路径"""
        if self.local_model_path:
            path = Path(self.local_model_path)
            if path.exists():
                if path.name == "snapshots":
                    snapshot_dirs = list(path.iterdir())
                    if snapshot_dirs:
                        return snapshot_dirs[0]
                elif any(f.name in ['config.json', 'pytorch_model.bin', 'model.safetensors'] for f in path.iterdir() if f.is_file()):
                    return path
                else:
                    snapshots = path / "snapshots"
                    if snapshots.exists():
                        snapshot_dirs = list(snapshots.iterdir())
                        if snapshot_dirs:
                            return snapshot_dirs[0]
                    return path
        
        for base_dir in [Path("D:\\agent\\models"), Path("models"), Path.cwd() / "models"]:
            if base_dir.exists():
                project_models = base_dir / f"models--{self.model_name.replace('/', '--')}"
                if project_models.exists():
                    snapshots = project_models / "snapshots"
                    if snapshots.exists():
                        snapshot_dirs = list(snapshots.iterdir())
                        if snapshot_dirs:
                            return snapshot_dirs[0]
        
        print("[Embedding] 警告: 未找到本地模型，将尝试使用默认方式加载")
        return Path(self.model_name)
    
    def embed(self, texts: List[str]) -> List[List[float]]:
        """使用本地模型获取嵌入"""
        model = self._load_model()
        embeddings = model.encode(texts, convert_to_numpy=True)
        return embeddings.tolist()


class ChromaVectorStore:
    """基于 ChromaDB 的向量存储"""
    
    def __init__(
        self,
        embedding_model: Optional[EmbeddingModel] = None,
        storage_path: str = "data/chroma_db",
        collection_name: str = "smartguard_knowledge"
    ):
        """
        初始化 ChromaDB 向量存储
        
        Args:
            embedding_model: 嵌入模型
            storage_path: ChromaDB 持久化路径
            collection_name: 集合名称
        """
        self.embedding_model = embedding_model
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.collection_name = collection_name
        
        self._client = None
        self._collection = None
        self._connect()
    
    def _connect(self):
        """连接到 ChromaDB"""
        try:
            import chromadb
            from chromadb.config import Settings
        except ImportError:
            raise ImportError("请安装 chromadb: pip install chromadb")
        
        self._client = chromadb.PersistentClient(
            path=str(self.storage_path),
            settings=Settings(anonymized_telemetry=False)
        )
        
        try:
            self._collection = self._client.get_collection(name=self.collection_name)
            print(f"[ChromaDB] 已连接到集合: {self.collection_name}, 文档数: {self._collection.count()}")
        except Exception:
            self._collection = self._client.create_collection(
                name=self.collection_name,
                metadata={"description": "SmartGuard 反诈知识库"}
            )
            print(f"[ChromaDB] 创建新集合: {self.collection_name}")
    
    def _get_embedding_function(self):
        """获取 ChromaDB 的嵌入函数"""
        if isinstance(self.embedding_model, OpenAIEmbeddings):
            from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
            return OpenAIEmbeddingFunction(
                api_key=self.embedding_model.api_key,
                api_base=self.embedding_model.api_base
            )
        else:
            class LocalEmbeddingFunction:
                """本地嵌入函数适配器"""
                def __init__(self, embedding_model: LocalEmbeddings):
                    self._model = embedding_model
                
                def __call__(self, texts: List[str]) -> List[List[float]]:
                    return self._model.embed(texts)
            
            return LocalEmbeddingFunction(self.embedding_model)
    
    def add_documents(
        self,
        documents: List[KnowledgeDocument],
        chunk_size: int = 500,
        overlap: int = 50,
        batch_size: int = 32,
        show_progress: bool = True,
        rebuild_index: bool = True,
        clear_existing: bool = False
    ) -> int:
        """
        添加文档到向量存储
        
        Args:
            documents: 文档列表
            chunk_size: 分块大小
            overlap: 重叠大小
            batch_size: 批处理大小
            show_progress: 是否显示进度
            rebuild_index: 是否重建索引
            clear_existing: 是否清除现有数据
            
        Returns:
            添加的块数
        """
        if clear_existing:
            try:
                self._client.delete_collection(name=self.collection_name)
                self._collection = self._client.create_collection(
                    name=self.collection_name,
                    metadata={"description": "SmartGuard 反诈知识库"}
                )
                print(f"[ChromaDB] 已清空集合: {self.collection_name}")
            except Exception:
                pass
        
        all_chunks = []
        chunk_sources = []
        
        for doc in documents:
            chunks = self._split_text(doc.content, chunk_size, overlap)
            for i, chunk in enumerate(chunks):
                all_chunks.append(chunk)
                chunk_sources.append({
                    "source": doc.source,
                    "doc_type": doc.doc_type,
                    "title": doc.title or "",
                    "metadata": json.dumps(doc.metadata, ensure_ascii=False),
                    "chunk_id": i,
                    "total_chunks": len(chunks)
                })
        
        if not all_chunks:
            return 0
        
        total_chunks = len(all_chunks)
        print(f"[ChromaDB] 共 {total_chunks} 个文本块，开始嵌入...")
        
        for i in range(0, total_chunks, batch_size):
            batch_end = min(i + batch_size, total_chunks)
            batch_chunks = all_chunks[i:batch_end]
            batch_sources = chunk_sources[i:batch_end]
            
            embeddings = self.embedding_model.embed(batch_chunks)
            
            ids = [f"doc_{i+j}" for j in range(len(batch_chunks))]
            metadatas = [self._prepare_metadata(src) for src in batch_sources]
            
            self._collection.add(
                ids=ids,
                documents=batch_chunks,
                embeddings=embeddings,
                metadatas=metadatas
            )
            
            if show_progress:
                progress = batch_end / total_chunks * 100
                print(f"\r嵌入进度: {batch_end}/{total_chunks} ({progress:.1f}%)", end="", flush=True)
        
        if show_progress:
            print()
        
        print(f"[ChromaDB] 已添加 {total_chunks} 个文档块到集合")
        return total_chunks
    
    def _prepare_metadata(self, source_info: Dict) -> Dict:
        """准备元数据"""
        return {
            "source": source_info.get("source", ""),
            "doc_type": source_info.get("doc_type", ""),
            "title": source_info.get("title", ""),
            "chunk_id": source_info.get("chunk_id", 0),
            "total_chunks": source_info.get("total_chunks", 1)
        }
    
    def _split_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """文本分块"""
        if len(text) <= chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            
            if end < len(text):
                for i in range(end, max(start + chunk_size - 100, end - 200), -1):
                    if text[i] in '。！？\n':
                        end = i + 1
                        break
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            start = end - overlap
        
        return chunks
    
    def search(
        self,
        query: str,
        top_k: int = 5,
        min_similarity: float = 0.3,
        where: Optional[Dict] = None,
        where_document: Optional[Dict] = None
    ) -> List[Dict[str, Any]]:
        """
        搜索相似文档
        
        Args:
            query: 查询文本
            top_k: 返回数量
            min_similarity: 最小相似度（转换为 ChromaDB 的 where 过滤）
            where: 元数据过滤条件
            where_document: 文档内容过滤条件
            
        Returns:
            相似文档列表
        """
        start_time = time.time()
        
        try:
            results = self._collection.query(
                query_texts=[query],
                n_results=top_k * 2,
                where=where,
                where_document=where_document,
                include=["documents", "metadatas", "distances"]
            )
        except Exception as e:
            print(f"[ChromaDB] 搜索出错: {e}")
            return []
        
        search_results = []
        if results and results["ids"]:
            for i, doc_id in enumerate(results["ids"][0]):
                distance = results["distances"][0][i]
                similarity = self._distance_to_similarity(distance)
                
                if similarity < min_similarity:
                    continue
                
                metadata = results["metadatas"][0][i] if results.get("metadatas") else {}
                
                search_results.append({
                    "id": doc_id,
                    "content": results["documents"][0][i],
                    "source": metadata.get("source", ""),
                    "doc_type": metadata.get("doc_type", ""),
                    "title": metadata.get("title", ""),
                    "similarity": similarity,
                    "distance": distance,
                    "metadata": metadata
                })
                
                if len(search_results) >= top_k:
                    break
        
        elapsed = time.time() - start_time
        if elapsed > 0.1:
            print(f"[ChromaDB] 搜索耗时: {elapsed*1000:.1f}ms, 返回 {len(search_results)} 个结果")
        
        return search_results
    
    def _distance_to_similarity(self, distance: float) -> float:
        """将 ChromaDB 的距离转换为相似度"""
        return 1.0 - distance
    
    def get_by_id(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """根据 ID 获取文档"""
        try:
            result = self._collection.get(
                ids=[doc_id],
                include=["documents", "metadatas"]
            )
            if result and result["ids"]:
                return {
                    "id": result["ids"][0],
                    "content": result["documents"][0],
                    "metadata": result["metadatas"][0] if result.get("metadatas") else {}
                }
        except Exception as e:
            print(f"[ChromaDB] 获取文档失败: {e}")
        return None
    
    def delete_by_id(self, doc_id: str) -> bool:
        """根据 ID 删除文档"""
        try:
            self._collection.delete(ids=[doc_id])
            return True
        except Exception as e:
            print(f"[ChromaDB] 删除文档失败: {e}")
            return False
    
    def count(self) -> int:
        """获取文档数量"""
        return self._collection.count()
    
    def clear(self):
        """清空集合"""
        try:
            self._client.delete_collection(name=self.collection_name)
            self._collection = self._client.create_collection(
                name=self.collection_name,
                metadata={"description": "SmartGuard 反诈知识库"}
            )
            print(f"[ChromaDB] 已清空集合: {self.collection_name}")
        except Exception as e:
            print(f"[ChromaDB] 清空集合失败: {e}")
    
    def peek(self, limit: int = 10) -> List[Dict[str, Any]]:
        """查看前 N 条文档"""
        try:
            result = self._collection.peek(limit=limit)
            if result and result["ids"]:
                return [
                    {
                        "id": result["ids"][i],
                        "content": result["documents"][i],
                        "metadata": result["metadatas"][i] if result.get("metadatas") else {}
                    }
                    for i in range(len(result["ids"]))
                ]
        except Exception as e:
            print(f"[ChromaDB] 查看文档失败: {e}")
        return []
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        count = self._collection.count()
        
        try:
            result = self._collection.peek(limit=100)
            sources = set()
            if result and result.get("metadatas"):
                for meta in result["metadatas"]:
                    if meta and meta.get("source"):
                        sources.add(meta["source"])
        except Exception:
            sources = set()
        
        return {
            "count": count,
            "collection_name": self.collection_name,
            "storage_path": str(self.storage_path),
            "embedding_model": self.embedding_model.model_name if self.embedding_model else "unknown",
            "sample_sources": list(sources)
        }


VectorStore = ChromaVectorStore


def create_vector_store(
    knowledge_base_path: str = "knowledge_base",
    embedding_type: str = "local",
    model_name: str = "shibing624/text2vec-base-chinese",
    storage_path: str = "data/chroma_db",
    collection_name: str = "smartguard_knowledge",
    local_model_path: Optional[str] = None
) -> ChromaVectorStore:
    """
    创建并初始化向量存储
    
    Args:
        knowledge_base_path: 知识库路径
        embedding_type: 嵌入类型 ("openai" 或 "local")
        model_name: 模型名称
        storage_path: ChromaDB 存储路径
        collection_name: 集合名称
        local_model_path: 本地模型路径（优先使用）
        
    Returns:
        ChromaVectorStore 实例
    """
    from .knowledge_base import KnowledgeBaseLoader
    
    loader = KnowledgeBaseLoader(knowledge_base_path)
    documents = loader.load_folder()
    
    if embedding_type == "openai":
        embedding_model = OpenAIEmbeddings()
    else:
        embedding_model = LocalEmbeddings(
            model_name=model_name,
            local_model_path=local_model_path
        )
    
    vector_store = ChromaVectorStore(
        embedding_model=embedding_model,
        storage_path=storage_path,
        collection_name=collection_name
    )
    
    existing_count = vector_store.count()
    if existing_count > 0:
        print(f"[VectorStore] ChromaDB 已包含 {existing_count} 个文档")
    elif documents:
        count = vector_store.add_documents(documents)
        print(f"[VectorStore] 已添加 {count} 个文档块到 ChromaDB")
    
    return vector_store


if __name__ == "__main__":
    vector_store = create_vector_store(
        knowledge_base_path="D:\\agent\\knowledge_base",
        embedding_type="local"
    )
    
    results = vector_store.search("刷单诈骗", top_k=3)
    
    print(f"\n搜索结果: {len(results)} 个")
    for i, r in enumerate(results, 1):
        print(f"\n--- 结果 {i} (相似度: {r['similarity']:.3f}) ---")
        print(f"来源: {r['source']}")
        print(f"内容: {r['content'][:200]}...")
