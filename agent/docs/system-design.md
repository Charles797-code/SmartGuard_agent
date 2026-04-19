# SmartGuard 多模态反诈智能助手

# 系统详细设计文档（SDD）

| 版本 | 日期 | 作者 | 说明 |
|------|------|------|------|
| v1.0 | 2026-04-15 | SmartGuard Team | 初始版本 |

---

## 目录

1. [系统概述](#1-系统概述)
2. [技术架构](#2-技术架构)
3. [核心模块详细设计](#3-核心模块详细设计)
4. [服务层详细设计](#4-服务层详细设计)
5. [数据库设计](#5-数据库设计)
6. [API 接口详细设计](#6-api-接口详细设计)
7. [多模态融合设计](#7-多模态融合设计)
8. [安全与认证设计](#8-安全与认证设计)
9. [部署架构](#9-部署架构)

---

## 1. 系统概述

### 1.1 项目背景

SmartGuard 是一款基于多模态大模型技术的智能反诈助手，为滨江区浙工大网络空间安全创新研究院提供智能化反诈解决方案。系统以"感知-决策-干预-进化"为核心能力，支持文本、语音、图像、视频四种模态的联合分析与风险识别。

### 1.2 系统目标

| 指标 | 目标值 |
|------|--------|
| 多模态融合识别准确率 | >90% |
| 误报率 | <5% |
| 覆盖诈骗类型 | ≥12种 |
| 文本响应延迟 | <3秒 |
| 覆盖用户 | 老年人、成年人、未成年人 |

### 1.3 核心能力

1. **感知能力**：文本解析、图像 OCR、语音 ASR
2. **决策能力**：规则引擎 + LLM 双轨风险评估
3. **干预能力**：5级预警、监护人联动、举报上报
4. **进化能力**：自动学习新诈骗手法、增量更新知识库

### 1.4 用户角色

| 角色 | 权限说明 |
|------|---------|
| 普通用户 | 风险分析、反诈咨询、查看预警、管理监护人、举报诈骗 |
| 监护人 | 查看被监护人预警、确认预警 |
| 管理员 | 用户管理、举报审核、进化知识管理、操作日志 |

---

## 2. 技术架构

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           前端层（React + Ant Design）                       │
│         Web 浏览器 / Android / iOS 三端统一，通过 Capacitor 打包                    │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │ HTTP/REST API
┌────────────────────────────────────▼────────────────────────────────────┐
│                           API 网关层（FastAPI）                                   │
│  ┌─────────┐ ┌─────────┐ ┌──────────┐ ┌────────┐ ┌─────────────┐       │
│  │ 认证API │ │画像API  │ │对话API  │ │预警API │ │知识百科API │       │
│  └─────────┘ └─────────┘ └──────────┘ └────────┘ └─────────────┘       │
│  ┌──────────┐ ┌──────────┐ ┌───────────┐ ┌────────────────┐              │
│  │邮件监控API│ │举报API   │ │进化服务API│ │管理后台API    │              │
│  └──────────┘ └──────────┘ └───────────┘ └────────────────┘              │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
┌────────────────────────────────────▼────────────────────────────────────┐
│                          核心业务逻辑层                                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │ AntiFraud   │  │ PromptEngine │  │Conversation │  │RiskDecision │    │
│  │   Agent     │  │（提示词工程） │  │  Memory     │  │   Engine     │    │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │MultiModal   │  │ Guardian     │  │ Alert       │  │ Evolution    │    │
│  │  Fusion     │  │  Notifier   │  │  Manager    │  │  Service     │    │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘    │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
┌────────────────────────────────────▼────────────────────────────────────┐
│                         大模型服务层                                          │
│  ┌─────────────────────────────────────────────────────────────────┐         │
│  │   通义千问 DashScope API — qwen-plus 文本推理                     │         │
│  └─────────────────────────────────────────────────────────────────┘         │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
┌────────────────────────────────────▼────────────────────────────────────┐
│                         数据与知识层                                          │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐          │
│  │  VectorStore     │  │  KnowledgeBase   │  │   Database       │          │
│  │  • FAISS 索引    │  │  • 文档加载器   │  │  • SQLite/Pickle │          │
│  │  • 向量嵌入存储  │  │  • 文本/JSON解析│  │  • 用户对话持久化│          │
│  │  • LocalEmbeddings│ │  • 分块处理     │  │  • 预警记录存储 │          │
│  │  • TF-IDF 备选  │  │                  │  │                  │          │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘          │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 技术栈

#### 后端

| 层级 | 技术选型 | 说明 |
|------|---------|------|
| 语言 | Python 3.10+ | |
| Web框架 | FastAPI | 异步 API 框架，支持自动文档 |
| LLM 底座 | 通义千问 DashScope API | qwen-plus 文本推理 |
| 感知方案 | 本地 OCR + Whisper（可选） | 图片/音频转文字描述 |
| 嵌入模型 | shibing624/text2vec-base-chinese | 本地中文语义嵌入模型 |
| 向量存储 | FAISS IndexFlatIP + Pickle | RAG 语义检索，支持 26万+ chunks |
| 文本嵌入备选 | TF-IDF | 无 FAISS 时的关键词检索降级方案 |
| 数据库 | SQLite / Pickle | 轻量级持久化 |
| 异步任务 | asyncio | 异步处理，邮件轮询等后台任务 |
| 环境配置 | python-dotenv | .env 文件管理 |

#### 前端

| 类别 | 技术选型 | 说明 |
|------|---------|------|
| 框架 | React 18.2 | 函数式组件 + Hooks |
| 构建 | Vite 5.0 | 快速开发服务器与生产构建 |
| UI 库 | Ant Design 5.12 | 企业级 React 组件库 |
| 状态 | Zustand 4.4 | 轻量全局状态管理 |
| HTTP | Axios 1.6 | API 请求库 |
| 移动端 | Capacitor 8.3 | Web 应用打包为 Android/iOS 原生 App |
| 图表 | Ant Design Charts | 预警统计可视化 |

### 2.3 目录结构

```
agent/
├── src/
│   ├── core/                          # 核心模块
│   │   ├── agent.py                    # 智能体主逻辑（感知-决策-干预-进化）
│   │   ├── prompts.py                  # 提示词工程（多模态专用提示词）
│   │   ├── memory.py                   # 长短期记忆（用户画像+对话历史）
│   │   ├── decision.py                # 风险决策引擎（关键词+模式匹配+上下文）
│   │   ├── knowledge_base.py          # 知识库加载器（txt/json/jsonl 多格式支持）
│   │   └── vector_store.py             # 向量存储（RAG+FAISS 索引加速+TF-IDF 备选）
│   │
│   ├── modules/                        # 功能模块
│   │   ├── input_handler/              # 多模态输入处理
│   │   │   ├── text.py                 # 文本输入处理器
│   │   │   ├── audio.py                # 音频输入处理器（ASR 占位/Whisper 可选）
│   │   │   └── visual.py              # 视觉输入处理器（OCR 占位/Qwen-VL 可选）
│   │   │
│   │   ├── recognizer/                # 识别引擎
│   │   │   ├── fusion.py              # 多模态融合判别（加权融合+交叉验证+时序融合）
│   │   │   ├── intent.py              # 意图识别
│   │   │   └── knowledge.py          # 知识检索
│   │   │
│   │   ├── intervention/               # 干预模块
│   │   │   ├── alert.py               # 分级预警管理（5级预警体系）
│   │   │   ├── guardian.py            # 监护人联动（短信/微信/APP 推送）
│   │   │   └── report.py              # 报告生成
│   │   │
│   │   ├── evolution/                 # 进化模块
│   │   │   ├── learner.py             # 知识学习器（关键词+模式自动提取）
│   │   │   ├── updater.py             # 知识更新器（数据清洗+标准化+增量入库）
│   │   │   └── report_integration.py  # 举报与进化的联动
│   │   │
│   │   ├── encyclopedia.py           # 诈骗手法百科全书（12种诈骗类型完整数据）
│   │   ├── user_profile.py            # 用户画像管理
│   │   └── llm/
│   │       └── qwen_client.py         # 通义千问客户端（QwenLLM）
│   │
│   ├── api/                           # API 路由层
│   │   ├── main.py                    # FastAPI 主应用（路由注册）
│   │   ├── auth.py                    # JWT 认证
│   │   ├── profile.py                 # 用户画像
│   │   ├── conversations.py           # 对话管理
│   │   ├── guardians.py              # 监护人管理
│   │   ├── reports.py                # 报告查询
│   │   ├── encyclopedia.py          # 知识百科 API
│   │   ├── report_submit.py          # 举报提交
│   │   └── admin_*.py               # 管理后台 API（用户/举报/日志）
│   │
│   ├── services/                      # 业务服务层
│   │   ├── conversation_service.py    # 对话持久化服务
│   │   ├── guardian_service.py       # 监护人通知服务
│   │   ├── evolution_service.py       # 智能进化服务（自动+手动学习）
│   │   ├── email_monitor_service.py   # 邮箱监控服务（IMAP 轮询+LLM 分析）
│   │   └── admin_*.py               # 管理后台服务
│   │
│   └── data/                          # 数据层
│       ├── database.py               # 数据库访问（SQLite/Pickle 持久化）
│       ├── vector_store.py           # 数据层向量存储（ChromaDB/Simple 实现）
│       └── test_cases/               # 测试数据集
│
├── web/                               # 前端（React + Vite + Ant Design + Capacitor）
│   ├── src/                          # React 源代码
│   ├── android/                     # Android 原生壳（Capacitor）
│   └── package.json
│
└── docs/                             # 项目文档
    ├── technical-architecture.md       # 技术架构文档
    ├── user-guide.md                  # 用户手册
    ├── deployment.md                  # 部署指南
    ├── evaluation.md                  # 性能评估报告
    └── system-design.md               # 本文档（系统详细设计）
```

---

## 3. 核心模块详细设计

### 3.1 Agent 模块（agent.py）

#### 3.1.1 模块概述

`AntiFraudAgent` 是系统的核心编排引擎，采用状态机模式实现"感知-决策-干预-进化"四大能力，支持多模态输入（文本、语音、图像、视频）的统一处理。

#### 3.1.2 枚举与数据类型

**枚举类：AgentState**

```python
class AgentState(Enum):
    IDLE = "idle"           # 空闲
    RECEIVING = "receiving" # 接收输入
    ANALYZING = "analyzing" # 分析输入
    REASONING = "reasoning" # 推理决策
    WARNING = "warning"     # 发出预警
    ACTING = "acting"       # 采取行动
    RESPONDING = "responding" # 生成响应
    EVOLVING = "evolving"   # 学习进化
```

**枚举类：InputModality**

```python
class InputModality(Enum):
    TEXT = "text"
    AUDIO = "audio"
    IMAGE = "image"
    VIDEO = "video"
    MULTIMODAL = "multimodal"
```

**数据结构：AgentInput**

```python
@dataclass
class AgentInput:
    text: Optional[str]       # 文本内容
    audio_path: Optional[str] # 音频路径
    audio_text: Optional[str] # 语音转文本
    image_path: Optional[str] # 图像路径
    image_desc: Optional[str]  # 图像描述
    video_path: Optional[str]  # 视频路径
    modality: str              # 输入模态
    metadata: Dict = field(default_factory=dict)  # 元数据
```

**数据结构：AgentOutput**

```python
@dataclass
class AgentOutput:
    response: str                    # 响应内容
    risk_assessment: Dict            # 风险评估结果
    actions_taken: List[str]         # 已采取的行动
    state: str                       # 当前状态
    suggestions: List[str]           # 建议列表
    guardian_notified: bool          # 是否通知监护人
    warning_displayed: bool          # 是否显示警告
```

#### 3.1.3 类设计：AntiFraudAgent

**构造函数参数**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| user_id | str | 必填 | 用户标识 |
| llm_client | Optional[QwenLLM] | None | LLM 客户端 |
| vector_store | Optional | None | 向量存储实例 |
| enable_guardian | bool | True | 是否启用监护人 |
| config | Dict | {} | 配置字典 |
| knowledge_base_path | Optional[str] | None | 知识库路径 |
| embedding_type | str | "local" | 嵌入类型 |
| local_model_path | Optional[str] | None | 本地模型路径 |
| use_shared_knowledge | bool | True | 是否使用共享知识库 |

**核心组件**

| 组件 | 类型 | 说明 |
|------|------|------|
| prompt_engine | PromptEngine | 提示词引擎 |
| memory | ConversationMemory | 对话记忆 |
| decision_engine | RiskDecisionEngine | 风险决策引擎 |

**默认配置**

```python
DEFAULT_CONFIG = {
    "risk_threshold_emergency": 4,
    "risk_threshold_danger": 3,
    "risk_threshold_warning": 2,
    "auto_notify_guardian": True,
    "guardian_delay_seconds": 3,
    "max_context_messages": 10,
    "confidence_threshold": 0.7
}
```

#### 3.1.4 核心方法

**主入口：process**

```python
async def process(
    self,
    input_data: AgentInput,
    context: Optional[Dict] = None
) -> AgentOutput:
```

**处理流程**

```
接收输入 (AgentInput)
    ↓
1. 预处理 (_preprocess_input)
    - 图像 OCR（提取文字描述）
    - 音频 ASR（语音转文本）
    ↓
2. 风险评估 (_assess_risk)
    - 检索相似案例 (VectorStore.search)
    - 规则引擎评估 (RiskDecisionEngine.assess_risk)
    - LLM 增强分析（如可用）
    ↓
3. 风险干预 (_handle_risk)
    - 根据风险等级采取行动
    - 通知监护人（如需要）
    ↓
4. 响应生成 (_generate_response)
    - 意图识别 (_recognize_intent)
    - 内容生成（风险分析/知识问答/学习模式）
    ↓
5. 保存记忆
    ↓
返回输出 (AgentOutput)
```

**意图识别逻辑 (_recognize_intent)**

```
输入文本 + 风险评估结果
    ↓
检测学习类关键词 + 诈骗类型关键词 → knowledge_query
高风险 (level >= 2) → risk_analysis
纯询问且无风险 → knowledge_query
默认 → risk_analysis
```

**响应生成模式**

| 模式 | 方法 | 说明 |
|------|------|------|
| risk_analysis | _generate_risk_analysis_response | 高风险内容详细分析 |
| knowledge_query | _generate_knowledge_response | 反诈助手知识问答 |
| learning | _generate_learning_response | 学习教育内容 |

---

### 3.2 Memory 模块（memory.py）

#### 3.2.1 模块概述

`ConversationMemory` 实现长短期记忆机制，支持用户行为画像构建和上下文管理。

#### 3.2.2 数据结构

**Message**

```python
@dataclass
class Message:
    role: str              # user/assistant/system
    content: str           # 消息内容
    timestamp: float       # 时间戳
    metadata: Dict = field(default_factory=dict)  # 元数据
```

**UserProfile**

```python
@dataclass
class UserProfile:
    user_id: str
    age_group: Optional[str]    # elderly/adult/minor
    gender: Optional[str]
    occupation: Optional[str]
    risk_history_count: int = 0
    risk_preference: str = "normal"
    guardians: List[Dict] = field(default_factory=list)
    conversation_count: int = 0
```

#### 3.2.3 类设计：ConversationMemory

**类属性**

```python
SHORT_TERM_MAX_SIZE = 20      # 短期记忆最大容量
SHORT_TERM_TTL = 86400        # 短期记忆 TTL（24小时）
LONG_TERM_MAX_SIZE = 1000    # 长期记忆最大容量
SUMMARY_INTERVAL = 10         # 摘要生成间隔（每10条消息）
```

**关键方法**

| 方法 | 返回值 | 说明 |
|------|--------|------|
| add_message(role, content, metadata) | Message | 添加消息到短期记忆 |
| get_recent_messages(count) | List[Message] | 获取最近 N 条消息 |
| get_context_for_llm(max_messages) | str | 获取 LLM 上下文 |
| get_user_profile_context() | Dict | 获取用户画像上下文 |
| update_profile(**kwargs) | - | 更新用户画像 |
| add_guardian(name, phone, relationship) | - | 添加监护人（去重） |
| to_dict() | Dict | 序列化记忆数据 |
| from_dict(data) | ConversationMemory | 从字典恢复记忆 |

**记忆流程**

```
新消息 → 短期记忆 (short_term deque)
    ↓
每 10 条消息 → 生成摘要 (_generate_summary)
    ↓
高风险消息 (level >= 2) → 长期记忆 (long_term)
    ↓
更新用户画像 (risk_history_count)
```

---

### 3.3 Decision 模块（decision.py）

#### 3.3.1 模块概述

`RiskDecisionEngine` 实现基于规则和模型的风险评估决策引擎，支持多模态风险融合。

#### 3.3.2 枚举与数据类型

**RiskLevel**

```python
class RiskLevel(Enum):
    SAFE = 0       # 安全
    ATTENTION = 1  # 关注
    WARNING = 2    # 警告
    DANGER = 3     # 危险
    EMERGENCY = 4  # 紧急
```

**ScamType**

```python
class ScamType(Enum):
    NORMAL = "normal"
    POLICE_IMPERSONATION = "police_impersonation"
    INVESTMENT_FRAUD = "investment_fraud"
    PART_TIME_FRAUD = "part_time_fraud"
    LOAN_FRAUD = "loan_fraud"
    PIG_BUTCHERY = "pig_butchery"
    AI_VOICE_FRAUD = "ai_voice_fraud"
    DEEPFAKE_FRAUD = "deepfake_fraud"
    CREDIT_FRAUD = "credit_fraud"
    REFUND_FRAUD = "refund_fraud"
    GAMING_FRAUD = "gaming_fraud"
    FAN_FRAUD = "fan_fraud"
    MEDICAL_FRAUD = "medical_fraud"
    UNKNOWN = "unknown"
```

**RiskAssessment**

```python
@dataclass
class RiskAssessment:
    risk_level: int                # 风险等级 0-4
    risk_type: str                 # 诈骗类型
    confidence: float               # 置信度 0-1
    analysis: str                  # 分析说明
    suggestion: str                 # 防护建议
    warning_message: str           # 警告信息
    triggered_keywords: List[str]  # 触发关键词
    recommended_actions: List[str] # 推荐行动
    timestamp: float               # 时间戳
```

#### 3.3.3 关键词权重配置

```python
KEYWORD_WEIGHTS = {
    # 冒充公检法
    "安全账户": 3.0,
    "资金核查": 2.5,
    "拘捕令": 2.5,
    "资产冻结": 2.0,
    # 投资理财
    "保本": 2.5,
    "稳赚不赔": 3.0,
    "高收益": 2.0,
    "内幕消息": 2.0,
    "导师带单": 2.5,
    # 兼职刷单
    "刷单": 2.5,
    "日结": 1.5,
    "任务单": 1.5,
    # AI诈骗
    "绑架": 3.0,
    "急需用钱": 2.0,
    "汇款": 2.5,
    # ... 共50+ 关键词
}
```

#### 3.3.4 诈骗模式配置

```python
SCAM_PATTERNS = {
    "police_impersonation": {
        "indicators": ["公安", "检察院", "法院", "安全账户", "资金核查"],
        "weight": 2.5
    },
    "investment_fraud": {
        "indicators": ["投资", "高收益", "导师", "内幕", "平台"],
        "weight": 2.0
    },
    # ... 8种诈骗模式
}
```

#### 3.3.5 用户画像调整

```python
PROFILE_ADJUSTMENTS = {
    "elderly": {
        "risk_level_boost": 1,
        "monetary_keywords_multiplier": 2.0,
        "description": "老年人权重：涉钱关键词权重翻倍"
    },
    "minor": {
        "risk_level_boost": 1,
        "monetary_keywords_multiplier": 2.5,
        "description": "未成年人权重：涉钱关键词权重2.5倍"
    },
    "accounting": {
        "risk_level_boost": 1,
        "transaction_keywords_multiplier": 2.0
    }
}
```

#### 3.3.6 核心方法

**assess_risk 评估流程**

```
输入文本 + 用户画像 + 上下文
    ↓
1. 关键词检测 (_detect_keywords)
    → 触发关键词列表 + 分数
    ↓
2. 模式匹配 (_match_scam_patterns)
    → 匹配的模式列表
    ↓
3. 上下文增强 (_analyze_context_boost)
    → 上下文加成分数
    ↓
4. 用户画像调整 (_apply_profile_adjustment)
    → 最终分数
    ↓
5. 分数转等级 (_score_to_level)
    → 确定风险等级
    ↓
6. 生成分析和建议 (_generate_analysis_and_suggestion)
    → RiskAssessment 对象
```

**多模态融合**

```python
def fuse_multimodal_risk(
    self,
    text_risk: RiskAssessment,
    image_risk: Optional[RiskAssessment],
    audio_risk: Optional[RiskAssessment]
) -> RiskAssessment
```

融合权重：文本 50%、音频 25%、图像 25%

---

### 3.4 Prompts 模块（prompts.py）

#### 3.4.1 模块概述

`PromptEngine` 包含系统提示词、任务指令、少样本示例等设计。

#### 3.4.2 诈骗类型定义

```python
SCAM_TYPES = {
    "police_impersonation": {
        "name": "冒充公检法诈骗",
        "keywords": ["涉嫌洗钱", "拘捕令", "资金核查", "安全账户", "银行账户"]
    },
    "investment_fraud": {
        "name": "投资理财诈骗",
        "keywords": ["保本", "高收益", "内幕消息", "导师带单", "稳赚不赔"]
    },
    # ... 共12种诈骗类型
}
```

#### 3.4.3 风险等级定义

```python
RISK_LEVELS = {
    0: {
        "name": "安全",
        "description": "未检测到明显的诈骗特征",
        "actions": ["正常交流", "保持警惕"]
    },
    1: {
        "name": "关注",
        "description": "发现模糊的风险信号",
        "actions": ["保持警惕", "核实对方身份"]
    },
    2: {
        "name": "警告",
        "description": "检测到可疑特征，需要警惕",
        "actions": ["提高警惕", "不要转账", "核实对方身份"]
    },
    3: {
        "name": "危险",
        "description": "高风险诈骗特征明显",
        "actions": ["立即停止操作", "不要转账", "报警处理"]
    },
    4: {
        "name": "紧急",
        "description": "典型诈骗话术，已通知监护人",
        "actions": ["保持冷静", "拨打96110", "联系家人"]
    }
}
```

#### 3.4.4 核心方法

| 方法 | 返回值 | 说明 |
|------|--------|------|
| get_analysis_prompt(user_input, context) | str | 获取分析提示词 |
| get_multimodal_analysis_prompt(text, image_desc, audio_desc) | str | 获取多模态分析提示词 |
| get_risk_assessment_prompt(base_risk, user_profile) | str | 获取风险评估提示词 |
| format_warning_message(risk_level, scam_type, suggestion) | str | 格式化警告信息 |

---

### 3.5 KnowledgeBase 模块（knowledge_base.py）

#### 3.5.1 模块概述

`KnowledgeBaseLoader` 从文件夹加载 .txt 和 .json/.jsonl 文件，构建可检索的知识库。

#### 3.5.2 支持的文件格式

| 格式 | 说明 |
|------|------|
| .txt | 纯文本文件 |
| .json | JSON 对象或数组 |
| .jsonl | JSON Lines（支持 TeleAntiFraud-28k 数据集） |

#### 3.5.3 TeleAntiFraud-28k 数据集支持

```python
# JSONL 文件支持 messages 格式
# 自动提取 user 消息中的 <audio> 标签内容作为通话文本
# 自动提取 assistant 消息中 <answer> 标签内容作为分析结果
# 自动识别诈骗类型作为标题
```

#### 3.5.4 核心方法

| 方法 | 返回值 | 说明 |
|------|--------|------|
| load_folder(recursive) | List[KnowledgeDocument] | 加载文件夹中的所有知识文档 |
| get_documents() | List[KnowledgeDocument] | 获取所有加载的文档 |
| get_documents_by_type(doc_type) | List[KnowledgeDocument] | 按类型获取文档 |
| search_by_keyword(keyword) | List[KnowledgeDocument] | 按关键词搜索文档 |
| get_stats() | Dict | 获取知识库统计信息 |

---

### 3.6 VectorStore 模块（vector_store.py）

#### 3.6.1 模块概述

向量存储模块实现文档向量化存储和相似度检索，支持 FAISS 索引加速。

#### 3.6.2 嵌入模型设计

**基类：EmbeddingModel**

```python
class EmbeddingModel(ABC):
    @abstractmethod
    def embed(self, texts: List[str]) -> List[List[float]]:
        pass
```

**实现类**

| 类名 | 模型 | 设备支持 |
|------|------|---------|
| OpenAIEmbeddings | text-embedding-ada-002 | API 调用 |
| LocalEmbeddings | shibing624/text2vec-base-chinese | GPU/CPU |

**LocalEmbeddings 特性**

```python
- 自动检测 GPU/CPU
- 支持本地模型路径优先
- 离线模式支持（HF_HUB_OFFLINE）
- 自动解析 snapshots 目录
```

#### 3.6.3 向量存储设计

**数据结构：EmbeddedDocument**

```python
@dataclass
class EmbeddedDocument:
    content: str                    # 内容
    embedding: List[float]          # 嵌入向量
    source: str                    # 来源路径
    doc_type: str                  # 文档类型
    title: Optional[str]           # 标题
    metadata: Dict                 # 元数据
    chunk_id: Optional[int]        # 块ID
```

**类：VectorStore**

| 属性 | 类型 | 说明 |
|------|------|------|
| embedding_model | EmbeddingModel | 嵌入模型 |
| storage_path | Path | 存储路径 |
| documents | List[EmbeddedDocument] | 文档列表 |
| _faiss_index | faiss.Index | FAISS 索引对象 |
| _use_faiss | bool | 是否使用 FAISS |
| _embedding_dim | int | 嵌入维度 |

**文本分块策略**

```python
CHUNK_SIZE = 500      # 块大小（字符）
CHUNK_OVERLAP = 50    # 重叠大小（字符）
# 按句子边界（。！？\n）分割
```

**FAISS 索引选择策略**

```python
if doc_count < 100000:
    IndexType = "IndexFlatIP"    # 精确搜索
else:
    IndexType = "IndexIVFFlat"   # 聚类搜索
```

#### 3.6.4 搜索策略优先级

```
1. FAISS 索引（最快，O(1) 精确搜索）
2. 暴力搜索（嵌入模型可用，O(n)）
3. 关键词搜索（无嵌入模型，TF-IDF）
```

#### 3.6.5 启动时索引预加载

```python
# 服务器启动时自动执行
init_shared_knowledge_base(knowledge_base_path, local_model_path)
    ↓
VectorStore.load()
    ↓
加载 index.pkl + faiss_index.bin
    ↓
检查 FAISS 索引是否存在
    ├── 存在 → 跳过
    └── 不存在 → rebuild_index() 构建索引
```

#### 3.6.6 核心方法

| 方法 | 返回值 | 说明 |
|------|--------|------|
| add_documents(documents, chunk_size, overlap, batch_size, show_progress, rebuild_index) | int | 添加文档 |
| search(query, top_k, min_similarity) | List[Dict] | 搜索相似文档 |
| save(save_faiss) | - | 保存索引到磁盘 |
| load(load_faiss) | bool | 从磁盘加载索引 |
| rebuild_index() | - | 重建 FAISS 索引 |
| get_stats() | Dict | 获取统计信息 |

---

### 3.7 Encyclopedia 模块（encyclopedia.py）

#### 3.7.1 模块概述

内置 12 种诈骗类型完整数据，每种类型包含：套路步骤、典型案例、防范技巧、警示信号、关键词。

#### 3.7.2 诈骗类型列表

| ID | 名称 | 风险等级 |
|----|------|---------|
| police_impersonation | 冒充公检法诈骗 | 4（高） |
| investment_fraud | 投资理财诈骗 | 3（中） |
| part_time_fraud | 兼职刷单诈骗 | 3（中） |
| loan_fraud | 虚假贷款诈骗 | 3（中） |
| pig_butchery | 杀猪盘诈骗 | 3（中） |
| ai_voice_fraud | AI 诈骗 | 4（高） |
| refund_fraud | 购物退款诈骗 | 3（中） |
| credit_fraud | 虚假征信诈骗 | 2（低） |
| gaming_fraud | 游戏交易诈骗 | 2（低） |
| fan_fraud | 追星诈骗 | 2（低） |
| medical_fraud | 医保诈骗 | 3（中） |
| deepfake_fraud | 深度伪造诈骗 | 4（高） |

#### 3.7.3 每种诈骗类型的结构

```python
{
    "id": "police_impersonation",
    "name": "冒充公检法诈骗",
    "icon": "🚔",
    "color": "#ef4444",
    "short_desc": "假冒公安局、检察院、法院人员，以涉嫌违法为由要求转账",
    "risk_level": 4,
    "techniques": [
        "声称受害者涉嫌洗钱/贩毒等严重犯罪",
        "出示伪造的通缉令、逮捕令等法律文书",
        "要求受害者将资金转入'安全账户'进行核查",
        "威胁受害者不得与家人联系，否则加重处罚"
    ],
    "typical_cases": ["案例1", "案例2", ...],
    "prevention_tips": [
        "公检法机关不会通过电话要求转账",
        "不要轻信来路不明的法律文书",
        "遇到可疑情况及时报警"
    ],
    "warning_signs": [
        "声称你涉嫌违法",
        "要求转账到安全账户",
        "威胁冻结资产"
    ],
    "keywords": ["涉嫌洗钱", "拘捕令", "资金核查", "安全账户"]
}
```

#### 3.7.4 核心方法

| 方法 | 返回值 | 说明 |
|------|--------|------|
| get_encyclopedia_categories() | List[Dict] | 获取分类 |
| get_all_scam_types() | List[Dict] | 获取所有类型 |
| get_scam_detail(scam_id) | Dict | 获取详情 |
| search_encyclopedia(keyword) | List[Dict] | 搜索 |
| get_prevention_by_risk_level(risk_level) | List[Dict] | 按风险获取防范建议 |
| get_statistics() | Dict | 统计信息 |

---

## 4. 服务层详细设计

### 4.1 ConversationService

#### 4.1.1 模块概述

`ConversationService` 实现对话历史的持久化管理，支持多会话、多模式、跨模式上下文。

#### 4.1.2 设计原则

```
每个用户 → 多个登录会话 (login_session)
    ↓
每个登录会话 → 多个对话会话 (session)
    ↓
每个对话会话 → 可切换模式 (risk/chat/learn)
```

#### 4.1.3 核心常量

```python
MAX_RETAIN_SESSIONS = 10      # 最大保留会话数
MAX_MESSAGES_PER_SESSION = 100 # 每个会话最大消息数
```

#### 4.1.4 核心方法

**会话管理**

| 方法 | 返回值 | 说明 |
|------|--------|------|
| create_session(mode) | Dict | 创建新会话 |
| get_or_create_current_session(mode) | Dict | 获取/创建当前会话 |
| load_sessions(limit, login_session_id) | List[Dict] | 加载会话列表 |
| get_session(session_id) | Dict | 获取指定会话 |
| set_current_session(session_id) | Dict | 切换当前会话 |

**消息读写**

| 方法 | 返回值 | 说明 |
|------|--------|------|
| add_message(role, content, mode, metadata) | Dict | 添加消息 |
| get_messages(session_id, mode, limit) | List[Dict] | 获取消息 |
| get_all_mode_messages(session_id, limit_per_mode, login_session_id) | List[Dict] | 获取各模式消息 |
| clear_session(session_id) | bool | 清空会话 |

---

### 4.2 GuardianService

#### 4.2.1 模块概述

`GuardianService` 实现监护人联动功能，支持风险通知、邀请管理、被监护人预警查看。

#### 4.2.2 风险通知策略

```python
RISK_NOTIFY_STRATEGY = {
    5: {"level": "critical", "channels": ["app", "sms"]},
    4: {"level": "emergency", "channels": ["app", "sms"]},
    3: {"level": "high", "channels": ["app"]},
    2: {"level": "medium", "channels": []},
    1: {"level": "low", "channels": []},
    0: {"level": "safe", "channels": []}
}
```

#### 4.2.3 核心方法

**监护人管理**

| 方法 | 返回值 | 说明 |
|------|--------|------|
| add_guardian(relationship, linked_username, notification_level, auto_notify) | Dict | 添加监护人 |
| remove_guardian(guardian_id) | bool | 删除监护人 |
| update_guardian(guardian_id, **kwargs) | Dict | 更新监护人 |
| get_guardians() | List[Dict] | 获取监护人列表 |

**风险通知**

| 方法 | 返回值 | 说明 |
|------|--------|------|
| trigger_risk_notification(risk_level, risk_type, content, response, alert_id) | Dict | 触发风险通知 |
| get_alerts(limit, unread_only) | List[Dict] | 获取预警历史 |
| acknowledge_alert(alert_id) | bool | 确认预警 |

**邀请管理**

| 方法 | 返回值 | 说明 |
|------|--------|------|
| create_invitation(invitee_username, relationship, notification_level, auto_notify) | Dict | 创建邀请 |
| get_sent_invitations() | List[Dict] | 获取发出的邀请 |
| get_received_invitations() | List[Dict] | 获取收到的邀请 |
| respond_to_invitation(invitation_id, accept) | Dict | 响应邀请 |

**监护人视角**

| 方法 | 返回值 | 说明 |
|------|--------|------|
| get_protected_users() | List[Dict] | 获取被监护人列表 |
| get_protected_user_alerts(protected_user_id, limit, unread_only) | List[Dict] | 获取被监护人预警 |
| get_all_protected_alerts(limit, unread_only) | Dict | 获取所有被监护人预警 |
| acknowledge_alert_for_user(alert_id, protected_user_id) | bool | 监护人确认预警 |

---

### 4.3 EvolutionService

#### 4.3.1 模块概述

`EvolutionService` 实现智能学习进化系统，支持自动进化和手动学习。

#### 4.3.2 学习流程

```
积累风险检测案例（高风险案例）
    ↓
达到阈值（10条）→ 自动触发进化
    ↓
分析案例 → 提取新关键词和新模式
    ↓
更新知识库 → 持久化到数据库
    ↓
后续检测使用更新后的知识
```

#### 4.3.3 核心方法

| 方法 | 返回值 | 说明 |
|------|--------|------|
| record_case(user_id, content, risk_level, risk_type, analysis, response) | Dict | 记录案例 |
| auto_evolve() | Dict | 自动进化 |
| enhance_risk_detection(risk_level, risk_type, content) | Dict | 增强检测 |
| get_learned_knowledge(scam_type) | List[Dict] | 获取学习到的知识 |
| get_evolution_stats() | Dict | 获取进化统计 |
| manual_learn(cases) | Dict | 手动学习 |
| export_knowledge() | Dict | 导出知识库 |
| import_knowledge(knowledge) | bool | 导入知识库 |

#### 4.3.4 进化统计

```python
{
    "total_records": int,           # 总记录数
    "learned_cases": int,          # 已学习案例数
    "new_keywords_added": int,     # 新增关键词数
    "new_patterns_added": int,    # 新增模式数
    "last_evolution": float,       # 最后更新时间
    "accuracy_improvement": float  # 准确率提升
}
```

---

### 4.4 EmailMonitorService

#### 4.4.1 模块概述

`EmailMonitorService` 将防御范围从聊天扩展到邮件，支持主流邮箱的 IMAP 协议轮询和 LLM 智能分析。

#### 4.4.2 支持的邮箱服务器

```python
IMAP_SERVERS = {
    "qq": {"imap": "imap.qq.com", "smtp": "smtp.qq.com"},
    "163": {"imap": "imap.163.com", "smtp": "smtp.163.com"},
    "gmail": {"imap": "imap.gmail.com", "smtp": "smtp.gmail.com"},
    "outlook": {"imap": "imap-mail.outlook.com", "smtp": "smtp-mail.outlook.com"}
}
```

#### 4.4.3 诈骗关键词配置

```python
SCAM_KEYWORDS = {
    "extreme_risk": ["安全账户", "洗钱", "拘捕令", ...],
    "high_risk": ["投资", "高收益", "导师", ...],
    "medium_risk": ["快递", "退款", "中奖", ...]
}
```

#### 4.4.4 诈骗模式配置

```python
SCAM_PATTERNS = {
    "urgency_threat": ["紧急", "立即", "马上", "否则"],
    "authority_impersonation": ["公安局", "检察院", "法院", "银行"],
    "money_request": ["转账", "汇款", "押金", "保证金"],
    "code_request": ["验证码", "密码", "账号"],
    "sweet_first": ["中奖", "返利", "赠送", "免费"]
}
```

#### 4.4.5 核心方法

| 方法 | 返回值 | 说明 |
|------|--------|------|
| add_email_config(user_id, email_address, username, password) | Dict | 添加邮件配置 |
| remove_email_config(config_id, user_id) | bool | 移除邮件配置 |
| get_user_configs(user_id) | List[Dict] | 获取用户配置 |
| start_monitoring(config_id) | bool | 启动监控 |
| stop_monitoring(config_id) | bool | 停止监控 |
| start_all_monitoring() | int | 启动所有监控 |
| stop_all_monitoring() | int | 停止所有监控 |
| get_user_alerts(user_id, limit) | List[Dict] | 获取邮件预警 |
| mark_alert_read(log_id, user_id) | bool | 标记已读 |
| get_unread_alert_count(user_id) | int | 未读数量 |

#### 4.4.6 分析流程

```
IMAP 连接邮箱
    ↓
获取最近 7 天未读邮件
    ↓
优先使用 LLM 分析（qwen-plus）
    ↓
Fallback：规则匹配
    - 关键词检测（三级风险）
    - 模式匹配（5种模式）
    ↓
检测结果存入数据库
```

---

## 5. 数据库设计

### 5.1 数据库概述

| 项目 | 说明 |
|------|------|
| 数据库类型 | SQLite |
| 数据库文件 | `./data/anti_fraud.db` |
| 表数量 | 16 张 |
| 编码 | UTF-8 |

### 5.2 E-R 图

```
┌──────────────┐     1:N      ┌──────────────┐
│  users_auth  │─────────────│ user_profiles │
└──────────────┘             └──────────────┘
       │
       │ 1:N
       ├──────────────┐
       │              │
       ▼              ▼
┌──────────────┐  ┌──────────────┐
│ conversations │  │    alerts    │
└──────────────┘  └──────────────┘
                            │
       1:N                  │
       ├────────────────────┼──────────────────┐
       ▼                    ▼                  ▼
┌──────────────┐      ┌──────────────┐  ┌──────────────┐
│  guardians   │      │scam_reports  │  │guardian_invite│
└──────────────┘      └──────────────┘  └──────────────┘

       ┌──────────────────────────────────────────────┐
       │              email_monitor_configs            │
       │                      │ 1:N                   │
       │                      ▼                        │
       │              email_monitor_logs                │
       └──────────────────────────────────────────────┘

┌──────────────┐       ┌──────────────┐
│evolution_records│    │evolution_knowledge│
└──────────────┘       └──────────────┘
```

### 5.3 表结构详情

#### 5.3.1 users_auth（用户认证表）

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | TEXT | PK | 用户唯一ID（UUID） |
| username | TEXT | UNIQUE, NOT NULL | 用户名 |
| email | TEXT | UNIQUE | 邮箱 |
| phone | TEXT | UNIQUE | 手机号 |
| password_hash | TEXT | NOT NULL | 密码哈希（bcrypt） |
| role | TEXT | DEFAULT 'user' | 角色（user/admin） |
| is_active | INTEGER | DEFAULT 1 | 是否激活 |
| created_at | REAL | NOT NULL | 创建时间戳 |
| updated_at | REAL | | 更新时间戳 |
| last_login | REAL | | 最后登录时间戳 |

**索引**：username, email, phone

---

#### 5.3.2 user_profiles（用户画像表）

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| user_id | TEXT | PK, FK→users_auth | 用户ID |
| nickname | TEXT | | 昵称 |
| avatar_url | TEXT | | 头像URL |
| bio | TEXT | | 个人简介 |
| age_group | TEXT | | 年龄段（elderly/adult/minor） |
| gender | TEXT | | 性别 |
| location | TEXT | | 地区 |
| occupation | TEXT | | 职业 |
| education | TEXT | | 学历 |
| risk_awareness | INTEGER | DEFAULT 50 | 反诈意识（0-100） |
| experience_level | TEXT | | 经验等级 |
| interested_scam_types | TEXT | JSON | 感兴趣的诈骗类型 |
| total_consultations | INTEGER | DEFAULT 0 | 总咨询次数 |
| reported_scams | INTEGER | DEFAULT 0 | 举报的诈骗次数 |
| family_protected | INTEGER | DEFAULT 0 | 受保护的家人数量 |
| learned_topics | TEXT | JSON | 已学习的专题 |
| quiz_scores | TEXT | JSON | 测验分数 |
| consultation_count | INTEGER | DEFAULT 0 | 咨询计数 |
| risk_count | INTEGER | DEFAULT 0 | 风险计数 |
| updated_at | REAL | | 更新时间戳 |

**索引**：user_id (PRIMARY KEY)

---

#### 5.3.3 conversations（对话历史表）

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | TEXT | PK | 对话ID（UUID） |
| user_id | TEXT | FK→users_auth | 用户ID |
| session_id | TEXT | NOT NULL | 会话ID |
| mode | TEXT | DEFAULT 'risk' | 模式（risk/chat/learn） |
| messages | TEXT | JSON | 消息列表 |
| message_count | INTEGER | DEFAULT 0 | 消息数量 |
| created_at | REAL | NOT NULL | 创建时间戳 |
| updated_at | REAL | | 更新时间戳 |
| login_session_id | TEXT | | 登录会话ID |

**索引**：id (PRIMARY KEY), user_id

---

#### 5.3.4 alerts（预警记录表）

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | TEXT | PK | 预警ID（UUID） |
| user_id | TEXT | FK→users_auth | 用户ID |
| level | INTEGER | NOT NULL | 风险等级（0-4） |
| risk_type | TEXT | | 风险类型 |
| message | TEXT | | 预警消息 |
| content | TEXT | | 原始内容 |
| response | TEXT | | 系统响应 |
| acknowledged | INTEGER | DEFAULT 0 | 是否已确认 |
| acknowledged_at | REAL | | 确认时间戳 |
| guardian_notified | INTEGER | DEFAULT 0 | 监护人是否已通知 |
| guardian_notifications | TEXT | JSON | 监护人通知列表 |
| created_at | REAL | NOT NULL | 创建时间戳 |

**索引**：id (PRIMARY KEY), user_id, created_at

---

#### 5.3.5 guardians（监护人表）

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | TEXT | PK | 监护人ID（UUID） |
| user_id | TEXT | FK→users_auth | 被监护用户ID |
| linked_user_id | TEXT | FK→users_auth | 关联用户ID（监护人账户） |
| name | TEXT | NOT NULL | 姓名 |
| phone | TEXT | | 电话 |
| relationship | TEXT | NOT NULL | 关系（父亲/母亲/配偶/子女/其他） |
| notification_level | TEXT | DEFAULT 'emergency' | 通知级别 |
| is_active | INTEGER | DEFAULT 1 | 是否激活 |
| auto_notify | INTEGER | DEFAULT 1 | 自动通知开关 |
| channels | TEXT | JSON | 通知渠道（sms/wechat/app） |
| created_at | REAL | NOT NULL | 创建时间戳 |

**索引**：id (PRIMARY KEY), user_id, linked_user_id

---

#### 5.3.6 guardian_invitations（监护人邀请表）

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | TEXT | PK | 邀请ID（UUID） |
| inviter_id | TEXT | FK→users_auth | 邀请者ID |
| invitee_id | TEXT | FK→users_auth | 被邀请者ID |
| relationship | TEXT | NOT NULL | 关系 |
| status | TEXT | DEFAULT 'pending' | 状态（pending/accepted/rejected） |
| notification_level | TEXT | DEFAULT 'emergency' | 通知级别 |
| auto_notify | INTEGER | DEFAULT 1 | 自动通知开关 |
| created_at | REAL | NOT NULL | 创建时间戳 |
| responded_at | REAL | | 响应时间戳 |

**索引**：id (PRIMARY KEY), inviter_id, invitee_id

---

#### 5.3.7 scam_reports（举报表）

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | TEXT | PK | 举报ID |
| report_id | TEXT | UNIQUE | 举报编号（RC-YYYYMMDD-XXXXX） |
| user_id | TEXT | FK→users_auth | 用户ID |
| scam_type | TEXT | NOT NULL | 诈骗类型 |
| title | TEXT | NOT NULL | 标题 |
| content | TEXT | NOT NULL | 内容 |
| scammer_contact | TEXT | | 骗子联系方式 |
| scammer_account | TEXT | | 骗子账号 |
| platform | TEXT | | 平台 |
| amount | REAL | | 涉及金额 |
| description | TEXT | | 描述 |
| evidence_urls | TEXT | JSON | 证据URL |
| status | TEXT | DEFAULT 'pending' | 状态（pending/verified/rejected） |
| source | TEXT | DEFAULT 'user' | 来源 |
| extracted_keywords | TEXT | JSON | 提取的关键词 |
| extracted_patterns | TEXT | JSON | 提取的模式 |
| learned | INTEGER | DEFAULT 0 | 是否已学习 |
| created_at | REAL | NOT NULL | 创建时间戳 |
| updated_at | REAL | | 更新时间戳 |

**索引**：id (PRIMARY KEY), report_id (UNIQUE), user_id, status

---

#### 5.3.8 evolution_records（学习进化记录表）

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | TEXT | PK | 记录ID |
| record_id | TEXT | UNIQUE | 记录编号 |
| user_id | TEXT | FK→users_auth | 用户ID |
| content | TEXT | NOT NULL | 内容 |
| risk_level | INTEGER | | 风险等级 |
| risk_type | TEXT | | 风险类型 |
| analysis | TEXT | | 分析 |
| response | TEXT | | 响应 |
| learned | INTEGER | DEFAULT 0 | 是否已学习 |
| created_at | REAL | NOT NULL | 创建时间戳 |

**索引**：id (PRIMARY KEY), record_id (UNIQUE)

---

#### 5.3.9 evolution_knowledge（学习进化知识表）

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | TEXT | PK | 知识ID |
| scam_type | TEXT | NOT NULL | 诈骗类型 |
| knowledge_type | TEXT | NOT NULL | 知识类型（keyword/pattern） |
| content | TEXT | NOT NULL | 内容 |
| created_at | REAL | NOT NULL | 创建时间戳 |
| updated_at | REAL | | 更新时间戳 |

**索引**：id (PRIMARY KEY), scam_type, knowledge_type

---

#### 5.3.10 email_monitor_configs（邮件监控配置表）

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | TEXT | PK | 配置ID（UUID） |
| user_id | TEXT | FK→users_auth | 用户ID |
| email_address | TEXT | NOT NULL | 邮件地址 |
| imap_host | TEXT | | IMAP 主机 |
| imap_port | INTEGER | DEFAULT 993 | IMAP 端口 |
| smtp_host | TEXT | | SMTP 主机 |
| smtp_port | INTEGER | DEFAULT 465 | SMTP 端口 |
| username | TEXT | NOT NULL | 用户名 |
| password_encrypted | TEXT | NOT NULL | 加密密码 |
| use_ssl | INTEGER | DEFAULT 1 | 使用SSL |
| check_interval | INTEGER | DEFAULT 300 | 检查间隔（秒） |
| is_active | INTEGER | DEFAULT 1 | 是否激活 |
| last_check_at | REAL | | 最后检查时间戳 |
| last_check_status | TEXT | | 最后检查状态 |
| created_at | REAL | NOT NULL | 创建时间戳 |
| updated_at | REAL | | 更新时间戳 |

**索引**：id (PRIMARY KEY), user_id

---

#### 5.3.11 email_monitor_logs（邮件监控记录表）

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | TEXT | PK | 日志ID |
| config_id | TEXT | FK→email_monitor_configs | 配置ID |
| user_id | TEXT | FK→users_auth | 用户ID |
| email_subject | TEXT | | 邮件主题 |
| email_from | TEXT | | 发件人 |
| email_date | REAL | | 邮件日期 |
| scam_score | REAL | | 诈骗分数 |
| risk_level | TEXT | | 风险等级 |
| detected_keywords | TEXT | JSON | 检测到的关键词 |
| detected_patterns | TEXT | JSON | 检测到的模式 |
| status | TEXT | DEFAULT 'pending' | 状态 |
| is_read | INTEGER | DEFAULT 0 | 是否已读 |
| created_at | REAL | NOT NULL | 创建时间戳 |

**索引**：id (PRIMARY KEY), config_id, user_id

---

#### 5.3.12 其他表

| 表名 | 说明 |
|------|------|
| users | 用户表（兼容性保留） |
| knowledge | 知识库表 |
| test_cases | 测试案例表 |
| admin_operation_logs | 管理员操作日志表 |
| admin_statistics | 管理员统计数据表 |

---

## 6. API 接口详细设计

### 6.1 认证接口（auth.py）

**路由前缀**：`/api/v1/auth`

| 端点 | 方法 | 认证 | 说明 |
|------|------|------|------|
| `/register` | POST | 无 | 用户注册 |
| `/login` | POST | 无 | 用户登录 |
| `/logout` | POST | Token | 退出登录 |
| `/me` | GET | Token | 获取当前用户 |
| `/refresh` | POST | Token | 刷新 Token |
| `/verify` | GET | 可选 | 验证 Token |

**认证方式**：HTTPBearer（Bearer Token）

---

### 6.2 用户画像接口（profile.py）

**路由前缀**：`/api/v1/profile`

| 端点 | 方法 | 认证 | 说明 |
|------|------|------|------|
| `/` | GET | Token | 获取用户画像 |
| `/` | PUT | Token | 更新用户画像 |
| `/complete` | POST | Token | 完善用户画像 |
| `/options` | GET | 无 | 获取选项列表 |
| `/stats` | GET | Token | 获取用户统计 |
| `/increment/consultation` | POST | Token | 增加咨询计数 |

---

### 6.3 对话接口（conversations.py）

**路由前缀**：`/api/v1/conversations`

| 端点 | 方法 | 认证 | 说明 |
|------|------|------|------|
| `/sessions` | GET | Token | 获取会话列表 |
| `/sessions` | POST | Token | 创建新会话 |
| `/sessions/{id}/switch` | POST | Token | 切换会话模式 |
| `/sessions/{id}` | DELETE | Token | 删除会话 |
| `/messages` | GET | Token | 获取消息列表 |
| `/messages` | POST | Token | 发送消息 |
| `/messages/all-modes` | GET | Token | 获取所有模式消息 |
| `/current-session` | GET | Token | 获取当前会话 |

---

### 6.4 监护人接口（guardians.py）

**路由前缀**：`/api/v1/guardians`

| 端点 | 方法 | 认证 | 说明 |
|------|------|------|------|
| `/` | GET | Token | 获取监护人列表 |
| `/` | POST | Token | 添加监护人 |
| `/{guardian_id}` | PUT | Token | 更新监护人 |
| `/{guardian_id}` | DELETE | Token | 删除监护人 |
| `/alerts` | GET | Token | 获取预警历史 |
| `/alerts/{alert_id}/acknowledge` | POST | Token | 确认预警 |
| `/notification-history` | GET | Token | 通知历史 |
| `/available-users` | GET | Token | 可用用户列表 |
| `/invitations` | POST | Token | 创建邀请 |
| `/invitations/sent` | GET | Token | 发出的邀请 |
| `/invitations/received` | GET | Token | 收到的邀请 |
| `/invitations/{id}/accept` | POST | Token | 接受邀请 |
| `/invitations/{id}/reject` | POST | Token | 拒绝邀请 |
| `/protected/users` | GET | Token | 被监护人列表 |
| `/protected/alerts` | GET | Token | 所有被监护人预警 |
| `/protected/{user_id}/alerts` | GET | Token | 指定被监护人预警 |

---

### 6.5 报告接口（reports.py）

**路由前缀**：`/api/v1/reports`

| 端点 | 方法 | 认证 | 说明 |
|------|------|------|------|
| `/generate` | GET | Token | 生成报告 |
| `/summary` | GET | Token | 获取摘要 |
| `/conversation-stats` | GET | Token | 对话统计 |
| `/charts` | GET | Token | 图表数据 |
| `/scam-types` | GET | 无 | 获取诈骗类型 |
| `/submit` | POST | Token | 提交举报 |
| `/my-reports` | GET | Token | 我的举报 |
| `/{report_id}` | GET | Token | 举报详情 |
| `/statistics/summary` | GET | 无 | 统计摘要 |
| `/keywords/dangerous` | GET | Token | 危险关键词 |

---

### 6.6 知识百科接口（encyclopedia.py）

**路由前缀**：`/api/v1/encyclopedia`

| 端点 | 方法 | 认证 | 说明 |
|------|------|------|------|
| `/` | GET | 无 | 获取百科概览 |
| `/categories` | GET | 无 | 获取分类 |
| `/scam-types` | GET | 无 | 获取诈骗类型列表 |
| `/scam-types/{scam_id}` | GET | 无 | 诈骗类型详情 |
| `/search` | GET | 无 | 搜索百科 |
| `/prevention-tips` | GET | 无 | 防范建议 |
| `/statistics` | GET | 无 | 统计信息 |
| `/warnings` | GET | 无 | 预警特征 |
| `/techniques` | GET | 无 | 诈骗手法 |
| `/cases` | GET | 无 | 典型案例 |
| `/by-risk/{level}` | GET | 无 | 按风险等级筛选 |

---

### 6.7 分析接口（main.py）

**路由前缀**：`/api/v1`

| 端点 | 方法 | 认证 | 说明 |
|------|------|------|------|
| `/analyze` | POST | 无 | 通用风险分析 |
| `/analyze/text` | POST | 无 | 文本分析 |
| `/analyze/multimodal` | POST | 无 | 多模态分析 |
| `/chat` | POST | 无 | 通用对话 |
| `/llm/status` | GET | 无 | LLM 状态 |
| `/llm/chat` | POST | 无 | LLM 对话 |
| `/llm/analyze-risk` | POST | 无 | LLM 风险分析 |
| `/evolution/stats` | GET | Token | 进化统计 |
| `/evolution/knowledge` | GET | Token | 进化知识 |
| `/evolution/evolve` | POST | Token | 触发进化 |
| `/evolution/manual-learn` | POST | Token | 手动学习 |

---

### 6.8 请求/响应格式

**AgentOutput 响应格式**

```json
{
  "response": "string",
  "risk_assessment": {
    "risk_level": 0,
    "risk_type": "string",
    "confidence": 0.0,
    "analysis": "string",
    "suggestion": "string"
  },
  "actions_taken": ["string"],
  "state": "string",
  "suggestions": ["string"],
  "guardian_notified": false,
  "warning_displayed": false
}
```

---

## 7. 多模态融合设计

### 7.1 融合算法概述

`MultimodalFusion` 实现加权融合、交叉验证、时序融合三种算法。

### 7.2 权重配置

```python
MODALITY_WEIGHTS = {
    "text": 0.5,   # 文本权重 50%
    "audio": 0.25, # 音频权重 25%
    "image": 0.25  # 图像权重 25%
}
```

### 7.3 置信度阈值

```python
CONFIDENCE_THRESHOLDS = {
    "high": 0.8,    # 高置信度
    "medium": 0.5,  # 中置信度
    "low": 0.3     # 低置信度
}
```

### 7.4 融合流程

```
文本风险分 + 音频风险分 + 图像风险分
    ↓
1. 加权融合（_weighted_fusion）
    → 根据 MODALITY_WEIGHTS 加权求和
    ↓
2. 交叉验证（_cross_validate）
    → 检测模态间差异（阈值 0.3）
    → 差异越大越保守（取高风险）
    ↓
3. 时序融合（_temporal_fusion）
    → 考虑历史对话窗口（默认5轮）
    → 上升趋势自动加权
    ↓
4. 分数转等级（_score_to_level）
    → 0-0.2 → SAFE(0)
    → 0.2-0.4 → ATTENTION(1)
    → 0.4-0.6 → WARNING(2)
    → 0.6-0.8 → DANGER(3)
    → 0.8-1.0 → EMERGENCY(4)
    ↓
5. 置信度计算（_calculate_confidence）
    → 综合各模态置信度
```

### 7.5 注意力融合公式

```
融合分数 = 风险分 × 权重 × (1 + 置信度)

示例：
文本：风险分 0.8，权重 0.5，置信度 0.9
→ 融合分数 = 0.8 × 0.5 × (1 + 0.9) = 0.76
```

---

## 8. 安全与认证设计

### 8.1 认证机制

| 机制 | 说明 |
|------|------|
| 密码哈希 | bcrypt 算法 |
| Token 类型 | JWT（JSON Web Token） |
| Token 有效期 | 默认 7 天 |
| 刷新机制 | 支持 Token 刷新 |

### 8.2 密码安全

```python
# 密码验证要求
MIN_PASSWORD_LENGTH = 6
MAX_PASSWORD_LENGTH = 50

# bcrypt 工作因子
BCRYPT_ROUNDS = 12
```

### 8.3 角色权限

| 角色 | 权限 |
|------|------|
| user | 风险分析、预警管理、监护人管理、举报 |
| admin | 用户管理、举报审核、进化知识管理、日志查看 |

---

## 9. 部署架构

### 9.1 部署模式

```
┌────────────────────────────────────────────────────────────┐
│                      负载均衡层（Nginx）                        │
│              端口 80/443 → 分发到后端服务                       │
└────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│  API Server 1 │    │  API Server 2 │    │  API Server N │
│  (FastAPI)     │    │  (FastAPI)     │    │  (FastAPI)     │
│  Port: 8000    │    │  Port: 8000    │    │  Port: 8000    │
└───────────────┘    └───────────────┘    └───────────────┘
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              ▼
                    ┌─────────────────┐
                    │  共享存储        │
                    │  (向量索引)      │
                    │  data/          │
                    └─────────────────┘
```

### 9.2 环境变量配置

```env
# API 配置
API_HOST=0.0.0.0
API_PORT=8000

# LLM 配置
DASHSCOPE_API_KEY=your_api_key_here
QWEN_MODEL=qwen-plus

# 向量存储
VECTOR_STORE_TYPE=faiss
VECTOR_STORE_PATH=./data/vector_store_shared

# 知识库路径
KNOWLEDGE_BASE_PATH=D:\agent\knowledge_base
LOCAL_MODEL_PATH=D:\agent\models\models--shibing624--text2vec-base-chinese

# 数据库
DATABASE_PATH=./data/anti_fraud.db

# 日志
LOG_LEVEL=INFO
```

### 9.3 FAISS 索引文件

```
data/vector_store_shared/
├── index.pkl           # 文档向量数据
└── faiss_index.bin     # FAISS 索引文件
```

### 9.4 性能优化建议

| 优化项 | 说明 |
|------|------|
| GPU 加速 | 安装 faiss-gpu 可加速嵌入计算 |
| FAISS 索引 | 首次启动后自动缓存，秒级加载 |
| 向量维度 | text2vec-base-chinese 为 768 维 |
| 批量处理 | 添加文档时使用批量嵌入 |

---

## 附录

### A. 配置常量汇总

| 常量 | 值 | 说明 |
|------|------|------|
| SHORT_TERM_MAX_SIZE | 20 | 短期记忆最大容量 |
| SHORT_TERM_TTL | 86400 | 短期记忆 TTL（秒） |
| LONG_TERM_MAX_SIZE | 1000 | 长期记忆最大容量 |
| SUMMARY_INTERVAL | 10 | 摘要生成间隔 |
| CHUNK_SIZE | 500 | 文本分块大小 |
| CHUNK_OVERLAP | 50 | 分块重叠大小 |
| MAX_RETAIN_SESSIONS | 10 | 最大保留会话数 |
| MAX_MESSAGES_PER_SESSION | 100 | 每会话最大消息数 |
| GUARDIAN_DELAY_SECONDS | 3 | 监护人通知延迟 |

### B. 状态码说明

| 状态码 | 说明 |
|--------|------|
| 0 | 安全 |
| 1 | 关注 |
| 2 | 警告 |
| 3 | 危险 |
| 4 | 紧急 |

### C. 诈骗类型 ID 映射

| ID | 名称 |
|----|------|
| police_impersonation | 冒充公检法诈骗 |
| investment_fraud | 投资理财诈骗 |
| part_time_fraud | 兼职刷单诈骗 |
| loan_fraud | 虚假贷款诈骗 |
| pig_butchery | 杀猪盘诈骗 |
| ai_voice_fraud | AI 诈骗 |
| refund_fraud | 购物退款诈骗 |
| credit_fraud | 虚假征信诈骗 |
| gaming_fraud | 游戏交易诈骗 |
| fan_fraud | 追星诈骗 |
| medical_fraud | 医保诈骗 |
| deepfake_fraud | 深度伪造诈骗 |

---

*文档版本：v1.0*
*更新日期：2026-04-15*
