# SmartGuard - 全民反诈智能助手

基于大语言模型（LLM）和多模态大模型（VLM）的智能反欺诈助手，具备"感知-决策-干预-进化"四大核心能力。

## 特性

- **多模态感知**：支持文本、语音、图像、视频等多种输入形式
- **智能风险识别**：基于关键词权重和模式匹配的精准风险评估
- **用户画像适配**：根据用户特征自动调整风险评估策略
- **监护人联动**：高风险场景自动通知监护人
- **自动进化学习**：从举报案例中自动学习新型诈骗手法
- **邮件监控**：自动检测邮箱中的可疑邮件

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

## 技术栈

- **后端**：FastAPI + SQLite
- **前端**：原生 HTML + CSS + JavaScript + Ant Design
- **AI**：通义千问（阿里云）
- **向量数据库**：本地嵌入模型

## 许可证

MIT License
