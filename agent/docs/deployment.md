# 部署文档

## 环境要求

- Python 3.10+
- Node.js 18+
- CUDA 11.8+ (GPU支持，可选)

## 依赖安装

### FAISS 向量索引（推荐安装）

```bash
# CPU 版本（推荐，体积小、安装快）
pip install faiss-cpu

# GPU 版本（如需加速嵌入，且有 CUDA 环境）
pip install faiss-gpu
```

> **说明**：FAISS 索引可将知识库搜索速度提升 50-100 倍。未安装时系统自动降级为暴力搜索，功能不受影响。

## 部署方式

### 方式一：本地部署

#### 1. 克隆项目

```bash
git clone <project-url>
cd anti-fraud-assistant
```

#### 2. 创建虚拟环境

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows
```

#### 3. 安装依赖

```bash
# 后端依赖
pip install -r requirements.txt

# 前端依赖 (可选)
cd web
npm install
```

#### 4. 配置环境变量

创建 `.env` 文件:

```env
# API配置
API_HOST=0.0.0.0
API_PORT=8000

# LLM配置 (必填)
LLM_PROVIDER=qwen
DASHSCOPE_API_KEY=your_api_key_here

# 向量存储
VECTOR_STORE_TYPE=faiss  # FAISS 索引加速（需 pip install faiss-cpu）
VECTOR_STORE_PATH=./data/vector_store_shared

# 知识库路径
KNOWLEDGE_BASE_PATH=D:\agent\knowledge_base
LOCAL_MODEL_PATH=D:\agent\models\models--shibing624--text2vec-base-chinese

# 数据库
DATABASE_PATH=./data/anti_fraud.db

# 日志
LOG_LEVEL=INFO
```

> **首次启动说明**：服务器启动时会自动加载知识库向量索引（`index.pkl`）。如无缓存则自动构建 FAISS 索引（首次约需 1-2 分钟），之后启动秒级加载。

#### 5. 启动服务

```bash
# 方式一：使用main.py
python main.py api --host 0.0.0.0 --port 8000

# 方式二：直接使用uvicorn
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```

#### 6. 访问服务

- API文档: http://localhost:8000/docs
- Web界面: http://localhost:8000/web (需启动前端)
- 或直接打开 web/index.html

---

### 方式二：Docker部署

#### 1. 构建镜像

```bash
docker build -t smartguard:latest .
```

#### 2. 运行容器

```bash
# 运行API服务
docker run -d \
  --name smartguard-api \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  smartguard:latest

# 运行前端
docker run -d \
  --name smartguard-web \
  -p 3000:80 \
  -v $(pwd)/web/dist:/usr/share/nginx/html \
  nginx:alpine
```

---

### 方式三：Docker Compose部署

```bash
# 启动所有服务
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f
```

---

## 生产环境部署

### 1. Nginx反向代理配置

```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    # API服务
    location /api/ {
        proxy_pass http://localhost:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    # Web静态文件
    location / {
        root /var/www/smartguard;
        index index.html;
        try_files $uri $uri/ /index.html;
    }
}
```

### 2. HTTPS配置

使用Let's Encrypt免费证书:

```bash
certbot --nginx -d your-domain.com
```

### 3. 系统服务配置

创建systemd服务文件 `/etc/systemd/system/smartguard.service`:

```ini
[Unit]
Description=SmartGuard Anti-Fraud Assistant
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/smartguard
ExecStart=/opt/smartguard/venv/bin/python main.py api --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启用服务:

```bash
sudo systemctl enable smartguard
sudo systemctl start smartguard
sudo systemctl status smartguard
```

---

## 性能优化

### 1. GPU加速 (可选)

确保安装了CUDA和cuDNN, 然后:

```bash
pip install torch torchvision --extra-index-url https://download.pytorch.org/whl/cu118
```

### 2. FAISS 向量索引优化

向量索引已内置于 `src/core/vector_store.py`：

- **索引文件位置**：`data/vector_store_shared/`
  - `index.pkl` — 文档向量数据
  - `faiss_index.bin` — FAISS 索引文件

- **索引构建时机**：
  - 服务器首次启动时自动构建（约 1-2 分钟）
  - 之后启动时自动加载（秒级）
  - 新增文档后自动重建

- **搜索性能**：
  | 文档数量 | 暴力搜索 | FAISS IndexFlatIP |
  |---------|----------|-------------------|
  | 264,927 chunks | ~5000ms | ~50-100ms |
  | 10万+ chunks | ~2000ms | ~10-50ms |

- **手动重建索引**：
  ```python
  from src.core.vector_store import VectorStore
  vs = VectorStore(embedding_model=...)
  vs.load()
  vs.rebuild_index()  # 手动触发
  ```

### 3. 数据库优化

对于生产环境, 建议使用PostgreSQL:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/smartguard
```

### 3. 缓存配置

向量索引缓存路径配置（已在 `.env` 中设置）：

```env
VECTOR_STORE_PATH=./data/vector_store_shared
```

> **说明**：向量索引在首次启动后会自动缓存到指定目录，后续启动无需重新构建。

---

## 监控与日志

### 日志配置

日志默认输出到控制台和文件:

```env
LOG_LEVEL=INFO
LOG_FILE=./logs/smartguard.log
LOG_MAX_SIZE=100MB
LOG_BACKUP_COUNT=10
```

### 健康检查

```bash
curl http://localhost:8000/health
```

---

## 常见问题

### Q: 启动报错 "ModuleNotFoundError"

```bash
pip install -r requirements.txt
```

### Q: API响应慢

1. 检查是否启用GPU
2. 优化模型加载
3. 增加缓存

### Q: 前端无法连接API

检查CORS配置和网络连接。

---

## 技术支持

如有问题，请联系开发团队。
