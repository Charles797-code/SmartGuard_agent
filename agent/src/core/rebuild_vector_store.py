"""
重建向量库脚本
将 TeleAntiFraud-28k 全量原始数据向量化存入 ChromaDB
"""

import os
import sys
import json

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def rebuild_vector_store(
    dataset_root: str = None,
    chroma_path: str = None,
    local_model_path: str = None,
    collection_name: str = "smartguard_knowledge",
    chunk_size: int = 600,
    batch_size: int = 32,
):
    """
    重建向量库

    Args:
        dataset_root: TeleAntiFraud-28k 数据集根目录
        chroma_path: ChromaDB 存储路径
        local_model_path: 本地嵌入模型路径
        collection_name: 集合名称
        chunk_size: 文本分块大小
        batch_size: 批处理大小
    """
    from src.core.tele_anti_fraud_parser import TeleAntiFraudExtractor
    from src.core.vector_store import ChromaVectorStore, LocalEmbeddings

    if dataset_root is None:
        dataset_root = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "knowledge_base", "TeleAntiFraud-28k"
        )

    if chroma_path is None:
        chroma_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "chroma_db"
        )

    if local_model_path is None:
        local_model_path = os.environ.get(
            "LOCAL_EMBEDDING_MODEL",
            r"D:\agent\models\snapshots"
        )

    print("=" * 60)
    print("向量库重建")
    print("=" * 60)
    print(f"数据集: {dataset_root}")
    print(f"存储路径: {chroma_path}")
    print(f"模型路径: {local_model_path}")
    print(f"集合名称: {collection_name}")
    print(f"分块大小: {chunk_size}")
    print(f"批处理大小: {batch_size}")
    print("=" * 60)

    # 1. 提取原始数据
    print("\n[1/4] 提取原始数据...")
    extractor = TeleAntiFraudExtractor(dataset_root)
    cases = extractor.load_all()
    stats = extractor.get_stats()
    print(f"\n提取统计:")
    print(f"  总案例数: {stats['total']}")
    for ds, cnt in stats.get('by_dataset', {}).items():
        print(f"  - {ds}: {cnt} 条")
    print(f"  总字符数: {stats['total_chars']:,}")
    print(f"  平均长度: {stats['avg_chars']:.0f} 字符/条")

    if not cases:
        print("没有提取到任何数据，退出")
        return

    # 2. 初始化嵌入模型
    print("\n[2/4] 初始化嵌入模型...")
    embedding_model = LocalEmbeddings(
        model_name="shibing624/text2vec-base-chinese",
        device="cpu",
        local_model_path=local_model_path
    )
    print(f"嵌入模型: {embedding_model.model_name}")

    # 3. 初始化向量存储
    print("\n[3/4] 初始化向量存储...")
    vector_store = ChromaVectorStore(
        embedding_model=embedding_model,
        storage_path=chroma_path,
        collection_name=collection_name
    )

    # 4. 向量化入库
    print("\n[4/4] 向量化入库...")
    count = vector_store.add_labeled_cases(
        cases=cases,
        chunk_size=chunk_size,
        overlap=50,
        batch_size=batch_size,
        show_progress=True,
        clear_existing=True
    )

    print(f"\n向量库重建完成!")
    print(f"  最终文档块数: {count}")
    print(f"  集合名称: {collection_name}")
    print(f"  存储路径: {chroma_path}")

    # 验证
    final_stats = vector_store.get_stats()
    print(f"\n最终统计:")
    print(f"  文档总数: {final_stats['count']}")
    print(f"  集合名: {final_stats['collection_name']}")

    return vector_store


def test_search(
    chroma_path: str = None,
    local_model_path: str = None,
    collection_name: str = "smartguard_knowledge",
):
    """测试检索"""
    from src.core.vector_store import ChromaVectorStore, LocalEmbeddings

    if chroma_path is None:
        chroma_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "chroma_db"
        )

    if local_model_path is None:
        local_model_path = os.environ.get(
            "LOCAL_EMBEDDING_MODEL",
            r"D:\agent\models\snapshots"
        )

    embedding_model = LocalEmbeddings(
        model_name="shibing624/text2vec-base-chinese",
        device="cpu",
        local_model_path=local_model_path
    )

    vector_store = ChromaVectorStore(
        embedding_model=embedding_model,
        storage_path=chroma_path,
        collection_name=collection_name
    )

    print(f"\n当前向量库文档数: {vector_store.count()}")

    # 测试查询
    test_queries = [
        "刷单返利诈骗",
        "冒充客服退款",
        "投资理财诈骗",
        "杀猪盘诈骗",
    ]

    for query in test_queries:
        print(f"\n查询: {query}")
        results = vector_store.search(query, top_k=3)
        print(f"  找到 {len(results)} 条结果")
        for i, r in enumerate(results):
            meta = r.get("metadata", {})
            is_fraud = meta.get("is_fraud", False)
            fraud_type = meta.get("fraud_type", "")
            conf = meta.get("confidence", 0.0)
            print(f"  [{i+1}] 相似度={r['similarity']:.3f} | is_fraud={is_fraud} | fraud_type={fraud_type} | conf={conf}")
            print(f"      内容: {r['content'][:150]}...")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="重建 SmartGuard 向量库")
    parser.add_argument("--dataset", type=str, default=None, help="数据集根目录")
    parser.add_argument("--chroma", type=str, default=None, help="ChromaDB 存储路径")
    parser.add_argument("--model", type=str, default=None, help="本地嵌入模型路径")
    parser.add_argument("--collection", type=str, default="smartguard_knowledge", help="集合名称")
    parser.add_argument("--chunk-size", type=int, default=600, help="文本分块大小")
    parser.add_argument("--batch-size", type=int, default=32, help="批处理大小")
    parser.add_argument("--test", action="store_true", help="仅测试检索")

    args = parser.parse_args()

    if args.test:
        test_search(
            chroma_path=args.chroma,
            local_model_path=args.model,
            collection_name=args.collection
        )
    else:
        rebuild_vector_store(
            dataset_root=args.dataset,
            chroma_path=args.chroma,
            local_model_path=args.model,
            collection_name=args.collection,
            chunk_size=args.chunk_size,
            batch_size=args.batch_size
        )
