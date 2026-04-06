# 智能计算 - 应用类赛题
# 基于多模态的反诈智能助手

## 赛题概要

本项目旨在构建一个具备"感知-决策-干预-进化"能力的多模态反诈智能助手，为滨江区浙工大网络空间安全创新研究院提供智能化反诈解决方案。

## 目录结构

```
anti-fraud-assistant/
├── src/                    # 源代码
│   ├── core/               # 核心模块
│   │   ├── agent.py        # 智能体主逻辑
│   │   ├── prompts.py      # 提示词工程
│   │   ├── memory.py       # 长短期记忆
│   │   └── decision.py     # 决策引擎
│   ├── modules/            # 功能模块
│   │   ├── input_handler/  # 多模态输入
│   │   ├── recognizer/     # 识别引擎
│   │   ├── intervention/    # 干预模块
│   │   └── evolution/       # 进化模块
│   ├── data/               # 数据处理
│   └── api/                # API服务
├── web/                    # 前端界面
├── tests/                  # 测试
└── docs/                   # 文档
```

## 快速开始

### 环境要求
- Python 3.10+
- Node.js 18+
- CUDA 11.8+ (GPU支持)

### 安装依赖

```bash
# 后端依赖
pip install -r requirements.txt

# 前端依赖
cd web && npm install
```

### 运行服务

```bash
# 启动后端API
python src/api/main.py

# 启动前端
cd web && npm run dev
```

## 核心功能

1. **多模态输入支持** - 文本、音频、视觉三模态输入
2. **智能识别与决策** - 意图识别、知识检索、风险评估
3. **实时干预** - 分级预警、监护人联动、报告生成
4. **自适应进化** - 案例学习、知识库更新

## 技术架构

- **LLM底座**: Qwen-VL / GLM4V
- **Agent框架**: LangGraph
- **向量数据库**: ChromaDB
- **语音处理**: Whisper
- **前端**: React + Ant Design

## 性能指标

- 多模态融合识别准确率 > 90%
- 误报率 < 5%
- 文本/图片响应时间 < 10秒
