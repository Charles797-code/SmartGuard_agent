# SmartGuard 多模态反诈智能助手

## 项目概述

SmartGuard 是一款基于多模态大模型技术的智能反诈助手，为滨江区浙工大网络空间安全创新研究院提供智能化反诈解决方案。系统具备"感知-决策-干预-进化"四大核心能力，支持文本、语音、图像、视频四种模态的联合分析与风险识别。

### 核心目标

- 多模态融合识别准确率 > 90%
- 误报率 < 5%
- 覆盖 12 种以上主流诈骗类型
- 支持实时风险预警与监护人联动

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                      前端（React + Ant Design + Capacitor）                        │
│         Web / Android / iOS 三端统一，覆盖移动端和桌面端                      │
└────────────────────────┬──────────────────────────────────────────────────┘
                         │ HTTP API（FastAPI）
┌────────────────────────▼──────────────────────────────────────────────────┐
│                        API 网关层（FastAPI）                                   │
│  ┌─────────┐ ┌─────────┐ ┌──────────┐ ┌────────┐ ┌─────────────┐       │
│  │ 认证API │ │画像API  │ │对话API  │ │预警API │ │知识百科API │       │
│  └─────────┘ └─────────┘ └──────────┘ └────────┘ └─────────────┘       │
│  ┌──────────┐ ┌──────────┐ ┌───────────┐ ┌────────────────┐              │
│  │邮件监控API│ │举报API   │ │进化服务API│ │管理后台API    │              │
│  └──────────┘ └──────────┘ └───────────┘ └────────────────┘              │
└────────────────────────┬──────────────────────────────────────────────────┘
                         │
┌────────────────────────▼──────────────────────────────────────────────────┐
│                       核心业务逻辑层                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │ AntiFraud   │  │ PromptEngine │  │Conversation │  │RiskDecision │    │
│  │   Agent     │  │（提示词工程） │  │  Memory     │  │   Engine     │    │
│  │（智能体编排）│  │              │  │（对话记忆）  │  │（决策引擎）  │    │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │MultiModal   │  │ Guardian     │  │ Alert       │  │ Evolution    │    │
│  │  Fusion     │  │  Notifier   │  │  Manager    │  │  Service     │    │
│  │（多模态融合）│  │（监护人通知）│  │（预警管理）  │  │（进化服务）  │    │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘    │
└────────────────────────┬──────────────────────────────────────────────────┘
                         │
┌────────────────────────▼──────────────────────────────────────────────────┐
│                      大模型服务层                                           │
│  ┌─────────────────────────────────────────────────────────────────┐         │
│  │   通义千问 DashScope API — qwen-plus 文本推理                     │         │
│  └─────────────────────────────────────────────────────────────────┘         │
└─────────────────────────────────────────────────────────────────────────────┘
                         │
┌────────────────────────▼──────────────────────────────────────────────────┐
│                      数据与知识层                                           │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐          │
│  │  VectorStore     │  │  KnowledgeBase   │  │   Database       │          │
│  │  • ChromaDB      │  │  • 文档加载器   │  │  • SQLite/Pickle │          │
│  │  • FAISS/HNSW   │  │  • 文本/JSON解析│  │  • 用户对话持久化│          │
│  │  • 向量嵌入存储  │  │  • 分块处理     │  │  • 预警记录存储 │          │
│  │  • 本地嵌入模型  │  │                  │  │                  │          │
│  │  • TF-IDF 备选  │  │                  │  │                  │          │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘          │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 目录结构

```
agent/
├── src/
│   ├── core/                          # 核心模块
│   │   ├── agent.py                    # 智能体主逻辑（感知-决策-干预-进化）
│   │   ├── prompts.py                  # 提示词工程（多模态专用提示词）
│   │   ├── memory.py                   # 长短期记忆（用户画像+对话历史）
│   │   ├── decision.py                # 风险决策引擎（关键词+模式匹配+上下文）
│   │   ├── knowledge_base.py          # 知识库加载器（txt/json多格式支持）
│   │   └── vector_store.py             # 向量存储（ChromaDB+RAG语义检索+FAISS/HNSW+TF-IDF备选）
│   │
│   ├── modules/                        # 功能模块
│   │   ├── input_handler/              # 多模态输入处理
│   │   │   ├── text.py                 # 文本输入处理器
│   │   │   ├── audio.py                # 音频输入处理器（ASR占位/Whisper可选）
│   │   │   └── visual.py              # 视觉输入处理器（OCR占位/Qwen-VL可选）
│   │   │
│   │   ├── recognizer/                # 识别引擎
│   │   │   ├── fusion.py              # 多模态融合判别（加权融合+交叉验证+时序融合）
│   │   │   ├── intent.py              # 意图识别
│   │   │   └── knowledge.py          # 知识检索
│   │   │
│   │   ├── intervention/               # 干预模块
│   │   │   ├── alert.py               # 分级预警管理（5级预警体系）
│   │   │   ├── guardian.py            # 监护人联动（短信/微信/APP推送）
│   │   │   └── report.py              # 报告生成
│   │   │
│   │   ├── evolution/                 # 进化模块
│   │   │   ├── learner.py             # 知识学习器（关键词+模式自动提取）
│   │   │   ├── updater.py             # 知识更新器（数据清洗+标准化+增量入库）
│   │   │   └── report_integration.py   # 举报与进化的联动
│   │   │
│   │   ├── encyclopedia.py           # 诈骗手法百科全书（12种诈骗类型完整数据）
│   │   ├── user_profile.py            # 用户画像管理
│   │   └── llm/
│   │       └── qwen_client.py         # 通义千问客户端（QwenLLM）
│   │
│   ├── api/                           # API路由层
│   │   ├── main.py                    # FastAPI主应用（8类路由注册）
│   │   ├── auth.py                    # JWT认证
│   │   ├── profile.py                 # 用户画像
│   │   ├── conversations.py            # 对话管理
│   │   ├── guardians.py              # 监护人管理
│   │   ├── reports.py                # 报告查询
│   │   ├── encyclopedia.py          # 知识百科API
│   │   ├── report_submit.py          # 举报提交
│   │   ├── admin_*.py               # 管理后台API（用户/举报/日志）
│   │   └── email_monitor.py          # 邮件监控API
│   │
│   ├── services/                      # 业务服务层
│   │   ├── conversation_service.py    # 对话持久化服务
│   │   ├── guardian_service.py       # 监护人通知服务
│   │   ├── evolution_service.py       # 智能进化服务（自动+手动学习）
│   │   ├── email_monitor_service.py   # 邮箱监控服务（IMAP轮询+LLM分析）
│   │   └── admin_*.py               # 管理后台服务
│   │
│   └── data/                          # 数据层
│       ├── database.py               # 数据库访问（SQLite/Pickle持久化）
│       ├── vector_store.py           # 向量存储（见 core/vector_store.py）
│       └── test_cases/               # 测试数据集
│
├── web/                               # 前端（React + Vite + Ant Design + Capacitor）
│   ├── src/                          # React 源代码
│   ├── android/                     # Android 原生壳（Capacitor）
│   └── package.json
│
└── docs/                             # 项目文档
    └── evaluation.md                  # 性能评估报告
```

---

## 技术栈

### 后端

| 层级 | 技术选型 | 说明 |
|------|---------|------|
| 语言 | Python 3.10+ | |
| Web框架 | FastAPI | 异步API框架，支持自动文档 |
| LLM底座 | 通义千问 DashScope API | qwen-plus 文本推理 |
| 感知方案 | 本地 OCR + Whisper（可选） | 图片/音频转文字描述 |
| 嵌入模型 | shibing624/text2vec-base-chinese | 本地中文语义嵌入模型（sentence-transformers） |
| 向量存储 | ChromaDB (FAISS/HNSW 自动选择) | RAG语义检索，ChromaDB 内置 FAISS 加速搜索 |
| 文本嵌入备选 | TF-IDF | ChromaDB 不可用时的关键词检索降级方案 |
| 缓存持久化 | index.pkl + faiss_index.bin | 文档索引 + FAISS 索引双缓存，启动时自动加载预建索引 |
| 数据库 | SQLite / Pickle | 轻量级持久化，用户对话/预警/配置存储 |
| 异步任务 | asyncio | 异步处理，邮件轮询等后台任务 |
| 环境配置 | python-dotenv | .env 文件管理 API Key 等配置 |
| CORS | FastAPI CORSMiddleware | 前端跨域访问支持 |

#### ChromaDB 向量存储详解

系统使用 **ChromaDB** 作为向量数据库，提供高性能的语义检索能力：

##### 架构特点

```
用户查询
    │
    ▼
┌─────────────────────────────────────────┐
│            ChromaDB Client              │
│                                         │
│  ┌─────────────┐  ┌─────────────────┐   │
│  │ 本地嵌入模型 │→│ 向量索引引擎     │   │
│  │ text2vec    │  │ FAISS / HNSW    │   │
│  └─────────────┘  └────────┬────────┘   │
│                           │            │
│  ┌─────────────┐  ┌────────▼────────┐   │
│  │ 元数据存储  │←│ 相似度搜索      │   │
│  │ SQLite      │  │ top-k 返回      │   │
│  └─────────────┘  └─────────────────┘   │
└─────────────────────────────────────────┘
```

##### 自动索引选择

ChromaDB 根据数据量自动选择最优索引策略：

| 数据量 | 索引类型 | 特点 | 适用场景 |
|--------|----------|------|----------|
| < 10万 | HNSW | 内存索引，搜索极快，精度高 | 小型知识库 |
| 10万-100万 | IVF (FAISS) | 聚类索引，平衡速度与精度 | 中型知识库 |
| > 100万 | IVF + HNSW | 复合索引，兼顾大规模检索 | 大型知识库 |

##### 核心优势

- **零配置**：ChromaDB 自动管理索引，无需手动选择和调优
- **持久化**：自动保存向量和元数据到本地目录
- **增量更新**：支持动态添加新文档，自动重建索引
- **元数据过滤**：支持在检索时按元数据（如诈骗类型、来源）过滤结果

##### 代码示例

```python
from chromadb import Client
from chromadb.utils import embedding_functions

# 使用本地嵌入模型
embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="shibing624/text2vec-base-chinese"
)

# 创建 ChromaDB 客户端
client = Client()
collection = client.create_collection(
    name="anti_fraud_kb",
    embedding_function=embedding_fn
)

# 添加文档
collection.add(
    documents=["文档内容1", "文档内容2"],
    metadatas=[{"source": "official"}, {"source": "teleantifraud"}],
    ids=["doc1", "doc2"]
)

# 相似度检索
results = collection.query(
    query_texts=["用户查询内容"],
    n_results=3
)
```

### 前端

| 类别 | 技术选型 | 说明 |
|------|---------|------|
| 框架 | React 18.2 | 函数式组件 + Hooks |
| 构建 | Vite 5.0 | 快速开发服务器与生产构建 |
| UI库 | Ant Design 5.12 | 企业级React组件库 |
| 状态 | Zustand 4.4 | 轻量全局状态管理 |
| HTTP | Axios 1.6 | API 请求库 |
| 移动端 | Capacitor 8.3 | Web应用打包为Android/iOS原生App |
| 图表 | Ant Design Charts | 预警统计可视化 |

### 部署

| 组件 | 说明 |
|------|------|
| 后端服务 | `python src/api/main.py` 或 `uvicorn` |
| API端口 | 8000（`0.0.0.0:8000`） |
| 前端端口 | Vite Dev Server（5173）或生产构建到 `web/dist` |
| 知识库路径 | `D:\agent\knowledge_base` |
| 本地模型路径 | `D:\agent\models\models--shibing624--text2vec-base-chinese` |

---

## 核心创新点

### 1. 两阶段多模态分析架构

**不同于"各模态独立分析后简单拼接"的方案**，本系统设计了**两阶段多模态分析架构**：

```
阶段1（感知层 — 本地感知）
    图片 ──► 本地OCR ──► 文字描述
    音频 ──► Whisper（占位）──► 文字描述
                    ↓
阶段2（推理层 — RAG + qwen-plus）
    文字描述 ──┬──► 向量检索（RAG）──► 相似案例
              │
              └──► qwen-plus 推理 ──► 风险评估 + 回复生成
```

- **阶段1**：本地感知将图片/音频转换为文字描述
- **阶段2**：将描述注入 RAG 检索 + qwen-plus 推理，生成结构化的风险评估和自然语言回复
- **核心优势**：感知与推理分离，避免单模型同时做感知和推理导致的"深度不足"问题

### 2. 本地感知 + qwen-plus 推理架构

系统使用本地感知进行多模态识别，使用 qwen-plus 进行文本推理：

- **图片感知**：本地 OCR（PaddleOCR）识别图片中的文字
- **音频感知**：本地 Whisper 转写音频为文字（可选）
- **RAG检索**：将感知结果与原始文本、用户画像结合进行向量检索
- **推理决策**：qwen-plus 综合所有信息生成风险评估和回复

所有模态统一转换为文本后，由 qwen-plus 进行统一分析。

### 3. RAG 增强的诈骗知识检索

本地反诈知识库通过 **ChromaDB 向量存储 + 本地嵌入模型 + TF-IDF 备选** 三轨方案保障检索能力：

- **ChromaDB 向量存储**：使用 ChromaDB 作为向量数据库，内置 FAISS/HNSW 索引加速搜索
  - 数据量 < 10万：自动使用 HNSW 内存索引，搜索极快
  - 数据量 10万-100万：自动切换为 IVF (FAISS) 聚类索引
  - 数据量 > 100万：自动切换为 IVF + HNSW 复合索引
- **语义嵌入**：使用 `shibing624/text2vec-base-chinese` 中文语义嵌入模型，将诈骗案例文档分块（500字符/块，50字符重叠）后向量化
- **持久化存储**：ChromaDB 自动将向量和元数据持久化到 `data/chroma_db/` 目录
- **多源检索**：感知描述 + 原始文本 + 用户画像关键词 三路拼接后作为检索 query
- **GPU自动检测**：自动检测 CUDA 可用性，GPU 可用时使用 GPU 加速嵌入
- **TF-IDF 备选**：ChromaDB 不可用时使用 TF-IDF 关键词检索降级

#### 知识库数据来源

RAG 知识库的数据来源于以下真实数据集：

**（1）TeleAntiFraud-28k 电信反诈语音数据集**

> **来源**：[TeleAntiFraud-28k](https://arxiv.org/abs/2503.24115) —— 首个面向电信反诈的**开源**音频-文本慢思考（Slow-Thinking）数据集，由马志明（Zhiming Ma）、王沛东（Peidong Wang）等研究者于 2025 年发布，发表于 **ACM MM '25**（The 31st ACM International Conference on Multimedia），2025年10月27-31日，爱尔兰都柏林。GitHub 地址：[JimmyMa99/TeleAntiFraud](https://github.com/JimmyMa99/TeleAntiFraud)
>
> **引用格式**：```
> @inproceedings{ma2025teleantifraud,
>   title={TeleAntiFraud-28k: An Audio-Text Slow-Thinking Dataset for Telecom Fraud Detection},
>   author={Ma, Zhiming and Wang, Peidong and Huang, Minhua and others},
>   booktitle={Proceedings of the 31st ACM International Conference on Multimedia (MM '25)},
>   pages={7119--7129},
>   year={2025},
>   organization={ACM}
> }
> ```

- **数据规模**：**28,511 条**经过严格处理的语音-文本对（speech-text pairs），完整标注了诈骗推理过程
- **构建策略**：该数据集通过三种策略构建：
  1. **隐私保护的文本真值样本生成**（Privacy-preserved text-truth sample generation）：使用 ASR（自动语音识别）转录真实电话录音（原始音频匿名化处理），通过 TTS（文本转语音）模型重新生成以确保真实世界一致性
  2. **语义增强**（Semantic enhancement via LLM-based self-instruction）：在真实 ASR 输出上通过大语言模型的自指令采样扩展场景覆盖
  3. **多智能体对抗合成**（Multi-agent adversarial synthesis）：通过预定义的通信场景和诈骗类型学模拟新兴诈骗战术
- **三大任务标注**：每条数据均包含以下三个任务的完整标注：
  - **场景分类**（Scenario Classification）：通话属于哪种场景类型（客服咨询、订餐服务、预约服务、日常购物等 7 类）
  - **欺诈检测**（Fraud Detection）：该通话是否涉及诈骗（`is_fraud: true/false`）
  - **诈骗类型分类**（Fraud Type Classification）：具体诈骗类型（银行诈骗、客服诈骗、钓鱼诈骗、投资诈骗、彩票诈骗、绑架诈骗、邮件诈骗等 8 类）
- **本项目中的使用**：位于 `agent/knowledge_base/TeleAntiFraud-28k/` 目录，其中 `total_train_clear.jsonl` 和 `total_test.jsonl` 等文件包含完整的对话内容、场景分类标签、是否涉诈标签和诈骗类型标签。系统通过向量检索匹配历史相似诈骗案例，辅助 LLM 进行风险推理

**（2）官方反诈宣传文档**

- **来源**：位于 `agent/knowledge_base/official_docu/` 目录
- **内容**：官方发布的反诈宣传教育材料（JSON 格式），包括各类诈骗类型的定义、手法分析、典型案例和防范提示
- **覆盖类型**：如"冒充公检法诈骗""网络购物诈骗""刷单诈骗""虚假链接诈骗"等
- **用途**：提供权威的反诈知识背景，增强系统对诈骗手法的识别准确性

**（3）高频关键词库**

- **来源**：位于 `agent/knowledge_base/20key-words.txt` 文件
- **内容**：20 个高频反诈关键词及其详细解释和警方提示，涵盖当前最常见的诈骗话术关键词，包括：屏幕共享、百万保障、安全账户、征信修复、刷单做任务、色情小卡片、未知链接/二维码、境外来电、小众聊天软件、内幕消息、NFC盗刷、积分清零、快递引流、虚拟货币、电诈工具人、帮信行为、两卡、现金黄金、购物卡、刷流水
- **用途**：作为规则匹配层（RiskDecisionEngine）的关键词字典，补充 RAG 语义检索之外的精确匹配能力

> **说明**：上述数据集均为开源/公开资料或官方发布内容，数据集本身的标注（如 `is_fraud` 标签、`fraud_type` 类型）由数据集发布方提供或 LLM 推理生成，用于构建系统的反诈知识背景。系统不会直接输出数据集内容，而是通过 RAG 检索+推理生成的方式，辅助判断用户输入内容的风险等级。

### 4. 多模态融合判别器（MultimodalFusion）

`src/modules/recognizer/fusion.py` 中实现了专业级的多模态融合算法：

- **加权融合**（Weighted Fusion）：文本 50%、音频 25%、图像 25% 的权重分配，结合置信度二次加权
- **交叉验证**（Cross-Validation）：检测不同模态分析结果的差异（阈值 0.3），差异越大越保守（取高风险）
- **时序融合**（Temporal Fusion）：考虑历史对话窗口（默认5轮）中的风险趋势，上升趋势自动加权重
- **注意力融合**（Attention Fusion）：融合分数 = 风险分 × 权重 × (1+置信度)，置信度高的模态获得更高权重

### 5. 多层风险决策引擎

```
输入文本 ──► 关键词检测（加权打分）
          ──► 模式匹配（SCAM_PATTERNS 8类诈骗模式）
          ──► 上下文增强（历史风险+金额+紧迫性）
          ──► 用户画像调整（老年人+1分，未成年人+1分）
          ──► LLM 增强评估（qwen-plus 生成 JSON 结构化结果）
          ──► 多模态融合（MultimodalFusion 加权融合）
          ──► 5级风险等级输出
```

- **规则引擎兜底**：即使 LLM 不可用（API Key 未配置），纯规则引擎也能正常运行
- **LLM 增强**：LLM 可用时，规则引擎结果作为参考，由 qwen-plus 最终决定风险等级
- **多模态分级**：通过 `MultimodalFusion` 对文本+音频+图像三个通道的风险评估做加权融合，输出最终分险等级

### 5.1 规则引擎模式详解

规则引擎是**无需 LLM 调用**的本地风险评估方式，基于关键词匹配、模式识别和规则计算来快速判断风险。

#### 5.1.1 整体架构

```
输入文本
    │
    ▼
┌─────────────────────────────────────────┐
│           RiskDecisionEngine            │
│                                         │
│  ┌───────────┐  ┌───────────┐         │
│  │ 1.关键词检测 │→│2.模式匹配  │         │
│  └─────┬─────┘  └─────┬─────┘         │
│        │              │                │
│        ▼              ▼                │
│  ┌───────────┐  ┌───────────┐         │
│  │3.上下文增强 │→│4.画像调整 │         │
│  └─────┬─────┘  └─────┬─────┘         │
│        │              │                │
│        └──────┬───────┘                │
│               ▼                        │
│        ┌───────────┐                   │
│        │5.分数映射  │                   │
│        └─────┬─────┘                   │
│              ▼                         │
│        ┌───────────┐                   │
│        │6.生成结果  │                   │
│        └───────────┘                   │
└─────────────────────────────────────────┘
    │
    ▼
RiskAssessment 对象
```

#### 5.1.2 关键词检测与评分

`KEYWORD_WEIGHTS` 定义了每种诈骗类型的关键词及其权重：

| 诈骗类型 | 关键词 | 权重 | 说明 |
|---------|--------|------|------|
| 冒充公检法 | 安全账户 | 3.0 | 最高风险 |
| 冒充公检法 | 资金核查 | 2.5 | 高风险 |
| 冒充公检法 | 洗钱 | 2.0 | 中高风险 |
| 投资理财 | 稳赚不赔 | 3.0 | 最高风险 |
| 投资理财 | 保本 | 2.5 | 高风险 |
| 投资理财 | 高收益 | 2.0 | 中高风险 |
| 兼职刷单 | 刷单 | 2.5 | 高风险 |
| AI诈骗 | 绑架 | 3.0 | 最高风险 |
| AI诈骗 | 急需用钱 | 2.0 | 中高风险 |

**检测逻辑**：简单字符串匹配 + 加权求和

```python
# 检测到的关键词列表
triggered = [("安全账户", 3.0), ("转账", 2.0)]

# 分数计算
total = sum(weight for _, weight in triggered)  # 基础分
bonus = 0.5 * (len(triggered) - 1)  # 多重触发奖励
keyword_score = min(total + bonus, 10.0)  # 上限10分
```

#### 5.1.3 模式匹配

每种诈骗类型有**必需关键词组合**，满足以下条件之一即匹配：

- **全部匹配**：包含所有必需关键词 → 直接匹配
- **部分匹配**：包含至少 2 个必需关键词 → 模糊匹配

```python
SCAM_PATTERNS = {
    "police_impersonation": {
        "required_keywords": ["公安", "民警", "警官", "洗钱", "涉嫌"],
        "additional_score": 1.5,
        "context_patterns": ["资金", "账户", "转账", "验证码"]
    },
    "investment_fraud": {
        "required_keywords": ["高收益", "投资", "理财"],
        "additional_score": 1.5,
        "context_patterns": ["保本", "稳赚", "平台", "导师"]
    },
    ...
}
```

#### 5.1.4 用户画像调整（年龄差异化风险调整）

`PROFILE_ADJUSTMENTS` 定义了不同用户群体的风险调整规则：

```python
PROFILE_ADJUSTMENTS = {
    "elderly": {           # 老年人
        "base_adjustment": 1,           # 基础分 +1
        "money_keywords_boost": 2.0,    # 涉钱关键词额外 +2.0
        "description": "老年人风险阈值降低"
    },
    "minor": {             # 未成年人
        "base_adjustment": 1,
        "money_keywords_boost": 2.5,   # 比老年人更严格
        "description": "未成年人更严格评估"
    },
    "accounting": {        # 财会人员
        "base_adjustment": 1,
        "transaction_boost": 2.0,      # 交易关键词额外 +2.0
        "description": "财会人员增加交易验证"
    }
}
```

**调整触发条件**：

| 年龄段 | 触发词 | 额外加分 | 说明 |
|--------|--------|----------|------|
| 老年人 | 转账/汇款/钱/支付 | +2.0 | 涉钱话题权重翻倍 |
| 未成年人 | 转账/汇款/钱/支付 | +2.5 | 比老年人更严格 |
| 财会人员 | 汇款/转账/支付/账户 | +2.0 | 交易验证增强 |

#### 5.1.5 分数转等级

```python
risk_threshold = {
    "safe": 0,        # < 2.0
    "attention": 2.0,  # 2.0 - 4.0
    "warning": 4.0,   # 4.0 - 6.0
    "danger": 6.0,    # 6.0 - 8.0
    "emergency": 8.0  # >= 8.0
}
```

#### 5.1.6 完整计算示例

**场景**：老年人收到短信 "我是民警，你涉嫌洗钱，请转账到安全账户"

```
Step 1: 关键词检测
触发: [("安全账户", 3.0), ("洗钱", 2.0), ("转账", 2.0)]
关键词分数: 3.0 + 2.0 + 2.0 + 0.5(奖励) = 7.5

Step 2: 模式匹配
匹配: ["police_impersonation"]
模式分: 1 × 1.5 = 1.5

Step 3: 上下文增强
boost: 0.0 (无特殊上下文)

Step 4: 基础分数
base = 7.5 + 1.5 + 0.0 = 9.0

Step 5: 用户画像调整
age_group = "elderly"
base_adjustment: +1
money_keywords_boost: +2.0 (包含"转账")
最终分数: 9.0 + 1 + 2.0 = 12.0

Step 6: 分数转等级
12.0 >= 8.0 → 风险等级 = 4 (紧急)
```

#### 5.1.7 性能对比

| 指标 | 规则引擎 | LLM 模式 |
|------|----------|----------|
| 响应速度 | < 10ms | 500-2000ms |
| 依赖 | 无 | 需要 API |
| 可解释性 | 高（逐条规则） | 中（黑盒） |
| 覆盖范围 | 有限（规则库） | 无限（泛化能力） |
| 适用场景 | 简单明确场景 | 复杂模糊场景 |

### 5.2 两种模式如何共同工作

系统采用**规则引擎 + LLM 双轨协作**的架构，根据场景自动选择最优路径。

#### 5.2.1 协作架构图

```
用户输入
    │
    ▼
┌─────────────────────────────────────────────────────┐
│                   _assess_risk()                    │
└────────────────────────┬────────────────────────────┘
                         │
    ┌────────────────────┴────────────────────┐
    ▼                                         ▼
┌─────────────┐                        ┌─────────────┐
│ 无 LLM 客户端 │                        │ 有 LLM 客户端│
│  (规则引擎)   │                        │  (双轨模式)  │
└──────┬──────┘                        └──────┬──────┘
       │                                      │
       ▼                                      ▼
┌─────────────┐                        ┌─────────────┐
│ 直接返回     │                        │ 先用规则引擎 │
│ 规则引擎结果 │                        │ 做关键词检测 │
└─────────────┘                        └──────┬──────┘
                                              │
                                              ▼
                                    ┌─────────────────┐
                                    │ _llm_full_analysis()
                                    │ - 构建 prompt
                                    │ - 调用 qwen-plus
                                    │ - 解析结构化结果
                                    └────────┬────────┘
                                             │
                                             ▼
                                    ┌─────────────────┐
                                    │ 生成自然语言响应 │
                                    │ + RiskAssessment │
                                    └─────────────────┘
```

#### 5.2.2 代码实现位置

**位置 1**：无 LLM 时完全使用规则引擎（`agent.py:567-573`）

```python
# 如果没有LLM客户端，使用规则引擎评估
if not self.llm_client:
    risk_assessment = self.decision_engine.assess_risk(
        text=text_input,
        user_profile=full_context.get("user_profile"),
        context=full_context
    )
    return risk_assessment
```

**位置 2**：有 LLM 时先用规则引擎做关键词检测参考（`agent.py:676-684`）

```python
# 先用规则引擎做关键词检测，作为参考
keyword_analysis = self.decision_engine.assess_risk(
    text=user_input,
    user_profile=context.get("user_profile"),
    context=context
)
kw_list = [kw[0] for kw in keyword_analysis.triggered_keywords]
if kw_list:
    kw_summary = "触发风险词: " + ", ".join(kw_list)
else:
    kw_summary = "无明显风险词"
```

#### 5.2.3 两种模式的分工

| 模式 | 适用场景 | 职责 | 输出 |
|------|----------|------|------|
| 规则引擎 | 无 LLM / 低风险场景 | 快速判断、明确定义场景 | `RiskAssessment` 结构化对象 |
| LLM 分析 | 复杂场景 / 高风险场景 | 深度理解、模糊判断、自然语言生成 | 自然语言回复 + `RiskAssessment` |

#### 5.2.4 工作流程详细说明

**流程 1：规则引擎独立工作（无 LLM）**

```
用户: "我收到一条短信说我中了大奖"
    │
    ▼
RiskDecisionEngine.assess_risk()
    │
    ├── 1. 关键词检测: [("中奖", 1.0)] → 分数 1.0
    ├── 2. 模式匹配: 未匹配
    ├── 3. 上下文增强: boost 0.0
    ├── 4. 用户画像调整: default + 0
    ├── 5. 分数计算: 1.0 < 2.0 → 风险等级 0 (安全)
    │
    ▼
返回 RiskAssessment(risk_level=0, risk_type="normal", ...)
```

**流程 2：双轨协作（有 LLM）**

```
用户: "我是民警，你涉嫌洗钱，请转账到安全账户"
    │
    ▼
Step 1: 规则引擎快速检测
    │
    ├── 关键词: ["安全账户", "洗钱", "转账"]
    ├── 模式匹配: ["police_impersonation"]
    └── 分数: 9.0 �� 高风险标记
    │
    ▼
Step 2: LLM 深度分析
    │
    ├── 构建 prompt（注入关键词检测结果 + 相似案例 + 用户画像）
    ├── 调用 qwen-plus
    └── 解析结构化结果
    │
    ▼
返回: 自然语言回复 + RiskAssessment(risk_level=4, ...)
```

#### 5.2.5 LLM Prompt 中的规则引擎结果注入

在 `_llm_full_analysis()` 方法中，规则引擎的检测结果作为上下文注入到 LLM 的 prompt 中：

```python
# 先用规则引擎做关键词检测，作为参考
keyword_analysis = self.decision_engine.assess_risk(...)

# 构建 prompt 时注入
prompt = f"""...
【系统辅助参考】（你可以参考，但最终判断要以内容本身为准）
关键词检测：{kw_summary}
{context_text}
...
"""
```

这样 LLM 可以参考规则引擎的检测结果，但最终判断由 LLM 自主决定，实现了规则引擎的快速性和 LLM 的智能性的结合。

#### 5.2.6 降级机制

当 LLM 调用失败时，系统自动降级到规则引擎：

```python
async def _llm_full_analysis(...):
    try:
        # LLM 调用
        response = await self.llm_client.chat(messages)
        # 解析响应
        ...
    except Exception as e:
        print(f"[WARNING] [LLM] Analysis failed: {e}")
    
    # 降级：使用规则引擎 + 模板
    risk_assessment = self.decision_engine.assess_risk(...)
    return risk_assessment
```

### 6. 用户画像驱动的个性化风控

`src/core/memory.py` 中的 `UserProfile` 和 `src/modules/user_profile.py` 中的画像体系：

- **人口统计画像**：年龄段（6档）、职业（7类）、学历（5级）
- **反诈专项画像**：防骗意识水平、关注的诈骗类型、是否独居、是否曾有被骗经历、经济状况、理财经验
- **动态画像更新**：每次对话后更新对话计数、风险历史计数、情绪状态
- **画像驱动的风险调整**：老年人/独居老人触发关键词时权重翻倍（`PROFILE_ADJUSTMENTS` 配置）
- **预警风格个性化**：温和/正常/紧急三档预警风格，根据用户画像动态选择

### 7. 智能学习进化系统

`src/services/evolution_service.py` + `src/modules/evolution/` 实现了持续自我进化：

- **自动进化**：每积累 10 条高风险案例自动触发学习，从案例中提取新关键词和新模式
- **手动导入**：支持管理员批量导入案例数据进行强化训练
- **持久化存储**：学习到的关键词和模式存储到数据库，`evolution_knowledge` 表记录每一条新知识
- **增强检测**：历史学习到的知识参与后续风险检测，形成正反馈闭环

### 8. 邮件监控主动防御

`src/services/email_monitor_service.py` 将防御范围从聊天扩展到邮件：

- **IMAP 协议轮询**：支持 QQ/163/Gmail/Outlook 等主流邮箱（自动识别 IMAP 服务器）
- **LLM 智能分析**：使用 qwen-plus 对邮件标题+正文+发件人进行诈骗识别
- **规则引擎兜底**：无 LLM 时使用 3 级关键词库（极高/高/中风险）+ 5 种模式检测
- **定时自动检测**：每 5 分钟轮询一次新邮件，检测结果持久化到数据库

### 9. 全链路闭环：预警 → 监护人通知 → 举报上报

```
风险检测 ──► 5级预警
          ──► 高风险触发监护人通知（短信/微信/APP推送，3秒延迟确认）
          ──► 举报上报（`report_submit_service.py`，提交至反诈中心）
          ──► 全程对话持久化（`conversation_service.py`）
          ──► 进化学习记录（`evolution_service.py`）
```

---

## 功能模块详解

### 智能体编排（agent.py）

`AntiFraudAgent` 是系统的核心编排引擎，7个状态：`IDLE → RECEIVING → ANALYZING → REASONING → WARNING → ACTING → RESPONDING → EVOLVING`

- **核心方法**：`process(input_data)` 异步处理多模态输入
- **感知与推理分离**：本地感知处理多模态输入，qwen-plus 负责推理决策
- **意图识别**（`_recognize_intent`）：自动区分风险分析模式 / 知识百科模式 / 学习模式
- **全局共享知识库**：`init_shared_knowledge_base()` 全局只加载一次，所有 Agent 实例复用，节省内存

### 提示词工程（prompts.py）

系统内置了完整的提示词模板体系：

- **12种诈骗类型的专项提示词**：每种类型包含关键词、高风险人群、典型话术
- **多模态融合提示词**：`MULTIMODAL_FUSION_PROMPT_TEMPLATE`，包含跨模态一致性检测指令
- **AI内容检测专项提示词**：视频换脸检测（面部边缘/眨眼/光照/口型）、语音合成检测（语调/停顿/情感）
- **用户画像上下文注入**：将年龄段、职业、历史风险等画像信息注入 prompt，引导模型个性化输出

### 音频输入处理（audio.py）

`AudioInputHandler` 模块使用 **SenseVoice** 作为核心引擎，实现 ASR + 情感识别 + 音频事件检测一体化处理，并使用 **librosa** 提取声学特征进行风险分析。

#### 核心模型：SenseVoice-Small

| 特性 | 说明 |
|------|------|
| 模型 | `iic/SenseVoiceSmall` (FunAudioLLM) |
| ASR | 多语言语音识别，中文提升 50%+ |
| 情感识别 | happy/sad/angry/neutral/fear/surprise |
| 音频事件 | music/applause/laughter/crying/cough/sneeze |
| 推理速度 | 10秒音频仅需 70ms，比 Whisper 快 15 倍 |
| 部署 | `pip install funasr` |

#### 声学特征提取（librosa）

| 特征类别 | 具体指标 |
|---------|---------|
| MFCC | 13维均值/标准差 + delta |
| 频谱 | 质心、带宽、对比度、衰减点 |
| 基频/音调 | 均值、标准差、最大值、最小值 |
| 能量 | RMS 均值/标准差、零交叉率 |
| 语速 | 字/秒、停顿比例 |

#### 声学风险检测

```python
RISK_THRESHOLDS = {
    "pitch_high": {"threshold": 350, "weight": 2.0},      # 音调过高
    "pitch_low": {"threshold": 80, "weight": 1.5},        # 音调过低
    "pitch_var": {"threshold": 200, "weight": 1.5},      # 音调变化过大
    "speech_rate_fast": {"threshold": 6.0, "weight": 2.0}, # 语速过快
    "speech_rate_slow": {"threshold": 2.0, "weight": 1.0}, # 语速过慢
    "pause_ratio_high": {"threshold": 0.4, "weight": 1.5}  # 停顿过多
}
```

#### 组合风险模式检测

```python
# 模式1：急迫 + 转账 = 典型诈骗
# 模式2：威胁 + 安全账户 = 典型公检法诈骗
# 模式3：保密 + 屏幕共享 = 电信诈骗特征
# 模式4：声学异常 + 关键词 = 综合风险
```

#### 完整处理流程

```
┌─────────────────────────────────────────────────────────────────┐
│                       音频输入 (.mp3/wav/m4a)                      │
└───────────────────────────────┬─────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────┐
│                   SenseVoice 多任务推理                           │
│  ├─ ASR 转写文本                                                 │
│  ├─ 情感标签 (happy/sad/angry/neutral)                           │
│  ├─ 音频事件检测 (laughter/crying/music)                         │
│  └─ 语种识别 (zh/en/yue/ja/ko)                                   │
└───────────────────────────────┬─────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────┐
│                   librosa 声学特征提取                            │
│  ├─ MFCC (13维 + delta)                                        │
│  ├─ 频谱特征 (质心/带宽/对比度/衰减)                               │
│  ├─ 基频/音调 (pyin 算法)                                       │
│  ├─ RMS 能量                                                    │
│  └─ 语速/停顿分析                                               │
└───────────────────────────────┬─────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────┐
│                      风险评估引擎                                 │
│  ├─ 文本关键词匹配 (8类诈骗关键词)                                  │
│  ├─ 声学异常检测 (音调/语速/能量)                                  │
│  ├─ 情感信号融合 (模型 + 关键词)                                   │
│  └─ 组合模式检测 (紧急转账/公检法/电信诈骗)                          │
└───────────────────────────────┬─────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────┐
│                      AudioAnalysis 输出                          │
│  {                                                          │
│    "transcription": "你儿子出事了，急需转账5万",                  │
│    "emotion": "fear",                                        │
│    "audio_events": [],                                       │
│    "emotion_signals": ["恐惧", "急迫", "被威胁"],              │
│    "risk_signals": ["紧急转账诈骗", "虚假绑架"],                │
│    "acoustic_features": { "pitch_anomaly_score": 2.5, ... }  │
│  }                                                          │
└─────────────────────────────────────────────────────────────────┘
```

#### 处理示例

用户发送语音 `"你儿子出事了，急需转账5万"`：

| 阶段 | 结果 |
|------|------|
| ASR | `你儿子出事了，急需转账5万` |
| SenseVoice 情感 | `fear` (恐惧) |
| 关键词情感 | `["被威胁", "急迫"]` |
| 声学检测 | 语速异常 (过快) |
| 文本风险 | `["虚假绑架", "转账汇款"]` |
| 组合模式 | `["紧急转账诈骗"]` |
| 最终输出 | `{emotion_signals: ["恐惧","被威胁","急迫"], risk_signals: ["紧急转账诈骗","虚假绑架","转账汇款"]}` |

#### 与 Agent 集成

```python
# audio.py
merged = handler.merge_with_text(audio_analysis, text_analysis)

# 包含字段
{
    "transcription": "...",
    "emotion": "fear",
    "emotion_confidence": 0.85,
    "emotion_signals": ["恐惧", "被威胁", "急迫"],
    "risk_signals": ["紧急转账诈骗"],
    "audio_events": [...],
    "acoustic_features": {...}
}
```

#### 依赖安装

```bash
pip install funasr>=1.0.0  # SenseVoice 模型
pip install librosa>=0.10.1  # 声学特征提取
```

### 视觉输入处理（visual.py）

`VisualInputHandler` 模块使用多模型组合实现完整的图像分析能力：

#### 核心模型组合

| 模型 | 用途 | 模型名/库 |
|------|------|----------|
| **Qwen2.5-VL** | 图像描述生成 | `Qwen/Qwen2.5-VL-3B-Instruct` |
| **YOLO11** | 目标检测 | `yolo11m.pt` (Ultralytics) |
| **PaddleOCR** | 中文OCR识别 | `paddleocr` |

#### 处理流程

```
┌─────────────────────────────────────────────────────────────────┐
│                       图片输入 (.jpg/.png)                        │
└───────────────────────────────┬─────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────┐
│                   Qwen2.5-VL 图像描述生成                         │
│  ├─ 中文详细描述                                               │
│  ├─ 场景类型识别 (聊天截图/证件/转账界面/网页)                    │
│  └─ 结构化信息提取                                             │
└───────────────────────────────┬─────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────┐
│                     YOLO11 目标检测                               │
│  ├─ 身份证、银行卡、文档                                        │
│  ├─ 手机、电脑、屏幕截图                                        │
│  ├─ 二维码、印章                                               │
│  └─ 聊天界面、转账界面识别                                      │
└───────────────────────────────┬─────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────┐
│                    PaddleOCR 中文OCR识别                         │
│  ├─ 中文、英文、数字混合识别                                     │
│  ├─ 方向检测                                                   │
│  └─ 高精度表格识别                                             │
└───────────────────────────────┬─────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────┐
│                       人脸检测                                      │
│  ├─ face_recognition / Dlib / OpenCV                           │
└───────────────────────────────┬─────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────┐
│                      场景分类 + 可疑元素检测                        │
│  ├─ 聊天截图 / 转账截图 / 身份证 / 银行卡                        │
│  ├─ 伪造证件检测                                                │
│  ├─ 钓鱼链接检测                                                │
│  └─ 伪造转账截图检测                                            │
└───────────────────────────────┬─────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────┐
│                      VisualAnalysis 输出                          │
│  {                                                               │
│    image_description: "这是一张转账截图，显示成功转账5000元",       │
│    detected_objects: [{"class_name": "转账界面", "confidence": 0.9}],│
│    text_ocr: [{"text": "转账成功", "confidence": 0.95}],         │
│    suspicious_elements: [{"type": "fake_transfer", ...}],        │
│    scene_type: "transfer_screenshot",                          │
│    llm_description: "场景类型：转账截图 | 文字内容：转账成功..."   │
│  }                                                               │
└─────────────────────────────────────────────────────────────────┘
```

#### 示例：用户发送转账截图

用户发送一张伪造的"转账成功"截图：

| 阶段 | 结果 |
|------|------|
| Qwen2.5-VL 描述 | `这是一张手机转账截图，显示招商银行转账成功` |
| YOLO11 检测 | `转账界面(0.92), 手机(0.85)` |
| PaddleOCR | `转账金额：5000元，到账时间：实时` |
| 场景分类 | `transfer_screenshot` (置信度 0.85) |
| 可疑元素 | `伪造转账截图(0.75)` |
| 最终输出 | `{suspicious: ["伪造转账截图"], scene: "transfer_screenshot"}` |

#### 依赖安装

```bash
# Qwen2.5-VL
pip install transformers>=4.40.0 qwen-vl-utils torch

# YOLO11
pip install ultralytics>=11.0.0

# PaddleOCR
pip install paddlepaddle-gpu>=3.0.0  # GPU版本
pip install paddleocr>=2.7.0

# 人脸检测 (可选)
pip install face-recognition  # 推荐
# 或
pip install dlib>=19.24.0    # 安装复杂但精度高
```

#### 开源模型选型对比

**图像描述模型对比：**

| 模型 | 参数量 | 中文能力 | 适用场景 | 显存需求 |
|------|--------|---------|---------|---------|
| Qwen2.5-VL-3B | 3B | ★★★★★ | 通用图像理解 | ~6GB |
| Qwen2.5-VL-7B | 7B | ★★★★★ | 精细理解 | ~14GB |
| Florence-2-base | ~200M | ★★★☆☆ | 轻量描述 | ~1GB |
| BLIP-2 | ~1.2B | ★★★☆☆ | 通用 | ~4GB |

**目标检测模型对比：**

| 模型 | mAP@50 | 速度 | 适用场景 |
|------|--------|------|---------|
| YOLO11n | 39.5 | 极快 | 实时 |
| YOLO11m | 51.5 | 快 | 平衡 |
| YOLO11x | 54.7 | 中等 | 高精度 |
| RT-DETR | ~53 | 中等 | 实时高精度 |

**OCR模型对比：**

| 模型 | 中文准确率 | 速度 | 特点 |
|------|-----------|------|------|
| PaddleOCR | 95.2% | 快(GPU) | 中文最优 |
| EasyOCR | 90.5% | 中 | 多语言支持 |
| Tesseract | 75% | 快 | 英文为主 |

### 风险决策引擎（decision.py）

`RiskDecisionEngine` 的核心打分机制：

| 诈骗类型 | 核心关键词 | 权重 |
|---------|-----------|------|
| 冒充公检法 | 安全账户(3.0)、资金核查(2.5)、拘捕令(2.5) | 极高 |
| 投资理财 | 稳赚不赔(3.0)、高收益(2.0)、内幕消息(2.0) | 高 |
| 兼职刷单 | 刷单(2.5)、日结(1.5)、任务单(1.5) | 高 |
| AI诈骗 | 绑架(3.0)、急需用钱(2.0)、汇款(2.5) | 极高 |
| 虚假贷款 | 解冻(2.0)、手续费(1.5)、无抵押(1.5) | 中高 |

### 诈骗手法百科全书（encyclopedia.py）

内置 12 种诈骗类型完整数据（每种类型包含：套路步骤、典型案例、防范技巧、警示信号、关键词）：

1. 冒充公检法诈骗（风险4级）
2. 投资理财诈骗（风险3级）
3. 兼职刷单诈骗（风险3级）
4. 虚假贷款诈骗（风险3级）
5. 杀猪盘诈骗（风险3级）
6. AI诈骗（风险4级）
7. 购物退款诈骗（风险3级）
8. 虚假征信诈骗（风险2级）
9. 游戏交易诈骗（风险2级）
10. 追星诈骗（风险2级）
11. 医保诈骗（风险3级）
12. 深度伪造诈骗（风险4级）

### 数据库持久化（database.py）

系统使用 **SQLite + Pickle** 实现轻量级持久化：

- `user_profiles`：用户画像
- `conversations`：对话历史（按 `login_session_id` 分组）
- `alerts`：预警记录
- `guardian_notifications`：监护人通知记录
- `evolution_records`：进化学习记录
- `evolution_knowledge`：学习到的知识（关键词/模式）
- `email_monitor_configs`：邮件监控配置
- `email_monitor_logs`：邮件检测日志

---

## API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/v1/analyze` | POST | 通用风险分析（文本） |
| `/api/v1/analyze/multimodal` | POST | 多模态分析（图片+音频+文本） |
| `/api/v1/analyze/video` | POST | 视频分析（RAG推理） |
| `/api/v1/analyze/video-url` | POST | 视频URL分析 |
| `/api/v1/chat` | POST | 通用对话（支持文本+图片+音频，可选risk/chat/learn模式） |
| `/api/v1/llm/status` | GET | LLM服务状态查询 |
| `/api/v1/llm/chat` | POST | 直接调用 qwen-plus 对话 |
| `/api/v1/llm/analyze-risk` | POST | 直接调用 qwen-plus 风险分析 |
| `/api/v1/encyclopedia/*` | GET | 诈骗手法百科（分类/详情/搜索/防范建议） |
| `/api/v1/users/{user_id}/profile` | GET/PUT | 用户画像 |
| `/api/v1/users/{user_id}/guardians` | GET/POST | 监护人管理 |
| `/api/v1/users/{user_id}/alerts` | GET | 预警列表 |
| `/api/v1/evolution/*` | GET/POST | 进化服务（统计/知识/手动学习） |
| `/api/v1/email-monitor/*` | GET/POST | 邮件监控配置与预警 |
| `/api/v1/report-submit` | POST | 举报上报 |

---

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- CUDA 11.8+（可选，用于 GPU 加速嵌入）

### 安装依赖

```bash
# 后端依赖
pip install -r requirements.txt

# 前端依赖
cd web && npm install
```

### 配置

在 `agent/` 目录下创建 `.env` 文件：

```env
DASHSCOPE_API_KEY=your_api_key_here
QWEN_MODEL=qwen-plus
```
```

### 启动服务

```bash
# 启动后端 API
python src/api/main.py

# 启动前端（另开终端）
cd web && npm run dev
```

---

## 性能指标

| 指标 | 目标值 | 状态 |
|------|--------|------|
| 多模态融合准确率 | >90% | 待测试 |
| 误报率 | <5% | 待测试 |
| F1-Score | >0.88 | 待测试 |
| 文本响应延迟 | <3秒 | 待测试 |
| 覆盖诈骗类型 | ≥12种 | ✅ 已实现 |

---

*文档版本: v2.1*
*更新日期: 2026-04-15*
