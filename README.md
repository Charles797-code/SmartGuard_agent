# SmartGuard - 全民反诈智能助手

基于大语言模型（LLM）和多模态大模型（VLM）的智能反欺诈助手，具备"感知-决策-干预-进化"四大核心能力。

## 特性

- **多模态感知**：支持文本、语音、图像、视频等多种输入形式
- **智能风险识别**：基于关键词权重和模式匹配的精准风险评估
- **用户画像适配**：根据用户特征自动调整风险评估策略
- **监护人联动**：高风险场景自动通知监护人
- **自动进化学习**：从举报案例中自动学习新型诈骗手法
- **智能邮件监控**：自动检测邮箱中的可疑邮件

## 项目结构

```
SmartGuard/
├── agent/                    # 主后端服务
│   ├── src/
│   │   ├── api/            # API路由
│   │   ├── core/           # 核心模块（Agent、决策、提示词等）
│   │   ├── data/           # 数据库操作
│   │   ├── modules/
│   │   │   ├── llm/        # LLM客户端
│   │   │   ├── recognizer/ # 意图识别、多模态融合
│   │   │   ├── input_handler/ # 输入处理
│   │   │   ├── intervention/ # 预警、监护人、举报
│   │   │   └── evolution/ # 知识学习
│   │   └── services/      # 业务服务
│   ├── web/               # 前端界面
│   └── docs/              # 文档
├── docs/                  # 项目详细文档
└── README.md
```

## 技术架构

### 核心模块

| 模块 | 说明 | 关键文件 |
|------|------|----------|
| Agent核心 | 多模态智能体编排 | `src/core/agent.py` |
| 风险决策引擎 | 关键词权重 + 模式匹配 | `src/core/decision.py` |
| 对话记忆 | 长短期记忆管理 | `src/core/memory.py` |
| 提示词引擎 | 分层提示词工程 | `src/core/prompts.py` |
| 向量存储 | FAISS + 本地嵌入 | `src/core/vector_store.py` |
| 知识库 | 文档加载与检索 | `src/core/knowledge_base.py` |

### AI能力

- **LLM**: 通义千问（阿里云）- 文本理解与生成
- **Embedding**: shibing624/text2vec-base-chinese - 中文语义嵌入
- **ASR**: Whisper - 语音识别
- **VLM**: Qwen-VL - 图像理解

## 快速开始

### 环境要求

- Python 3.9+
- 通义千问 API Key

### 安装

```bash
cd agent
pip install -r requirements.txt
```

### 配置

复制 `.env.example` 为 `.env`，填入必要的配置：

```env
DASHSCOPE_API_KEY=your_api_key_here
QWEN_MODEL=qwen-turbo
DATABASE_PATH=./data/anti_fraud.db
KNOWLEDGE_BASE_PATH=./knowledge_base
LOCAL_MODEL_PATH=./models/text2vec
```

### 启动服务

```bash
python main.py
# 或
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```

### Docker部署

```bash
docker build -t smartguard:latest .
docker run -d -p 8000:8000 \
  -e DASHSCOPE_API_KEY=your_key \
  smartguard:latest
```

## 技术栈

- **后端**：FastAPI + SQLite + SQLAlchemy
- **前端**：原生 HTML + CSS + JavaScript + Ant Design
- **AI**：通义千问（阿里云）+ Whisper + Qwen-VL
- **向量检索**：FAISS + Sentence-Transformers
- **部署**：支持 Docker / K8s / 单机部署

## API接口

### 核心接口

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/v1/chat` | 通用对话接口 |
| POST | `/api/v1/analyze` | 综合分析接口 |
| POST | `/api/v1/auth/login` | 用户登录 |
| GET | `/api/v1/users/{user_id}/profile` | 获取用户画像 |
| POST | `/api/v1/users/{user_id}/guardians` | 添加监护人 |
| GET | `/api/v1/email-monitor/configs` | 邮件监控配置 |

详细API文档请参考 `docs/项目使用指南及详细方案.md`

## 系统架构

```
用户输入 → 感知层解析 → 意图识别路由 → 决策层评分 → 风险分级响应
                                              ↓
                                              触发干预(预警/监护人/举报)
                                              触发进化(案例入库/知识学习)
                                              LLM推理生成回复
```

### 风险等级

| 等级 | 名称 | 响应动作 |
|------|------|----------|
| 0 | 安全 | 正常对话 |
| 1 | 关注 | 温和提醒 |
| 2 | 警告 | 弹窗警告 + APP推送 |
| 3 | 危险 | 强制阻断 + 预警记录 |
| 4 | 紧急 | 全渠道通知监护人 |

### 诈骗类型覆盖

- 冒充公检法诈骗
- 投资理财诈骗
- 兼职刷单诈骗
- 虚假贷款诈骗
- 杀猪盘诈骗
- AI语音合成诈骗
- 虚假征信诈骗
- 购物退款诈骗
- 游戏交易诈骗
- 追星诈骗

## 许可证

MIT License

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=Charles797-code/SmartGuard_agent&type=Date)](https://star-history.com/#Charles797-code/SmartGuard_agent&type=Date)
