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
│  │  • FAISS 索引    │  │  • 文档加载器   │  │  • SQLite/Pickle │          │
│  │  • 向量嵌入存储  │  │  • 文本/JSON解析│  │  • 用户对话持久化│          │
│  │  • LocalEmbeddings│  │  • 分块处理     │  │  • 预警记录存储 │          │
│  │  • 启动时预加载 │  │                  │  │                  │          │
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
│   │   └── vector_store.py             # 向量存储（RAG语义检索+FAISS索引加速+TF-IDF备选）
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
| 向量存储 | FAISS IndexFlatIP + 本地Pickle缓存 | RAG语义检索，搜索从 O(n) 暴力匹配加速到 O(1) 精确搜索 |
| 文本嵌入备选 | TF-IDF | 无 FAISS 时的关键词检索降级方案 |
| 缓存持久化 | index.pkl + faiss_index.bin | 文档索引 + FAISS 索引双缓存，启动时自动加载预建索引 |
| 数据库 | SQLite / Pickle | 轻量级持久化，用户对话/预警/配置存储 |
| 异步任务 | asyncio | 异步处理，邮件轮询等后台任务 |
| 环境配置 | python-dotenv | .env 文件管理 API Key 等配置 |
| CORS | FastAPI CORSMiddleware | 前端跨域访问支持 |

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

本地反诈知识库通过 **向量化 RAG + FAISS 索引加速 + TF-IDF 备选** 三轨方案保障检索能力：

- **语义嵌入**：使用 `shibing624/text2vec-base-chinese` 中文语义嵌入模型，将诈骗案例文档分块（500字符/块，50字符重叠）后向量化
- **FAISS 索引加速**：使用 FAISS IndexFlatIP 索引，搜索复杂度从 O(n) 暴力匹配降为 O(1) 精确搜索，支持 26万+ chunks 高效检索
- **启动时预加载**：服务器启动时自动加载 `data/vector_store_shared/index.pkl` 和 `faiss_index.bin`，首次启动如无索引则自动构建
- **多源检索**：感知描述 + 原始文本 + 用户画像关键词 三路拼接后作为检索 query
- **GPU自动检测**：自动检测 CUDA 可用性，GPU 可用时使用 GPU 加速嵌入

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
