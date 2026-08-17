# SitePPE Agent

SitePPE Agent 是面向施工现场的 PPE（个体防护装备）合规调查与整改演示系统。系统将六路施工视频、YOLO 检测、VLM 复核、任务规则、RAG 权威依据和人工审核串联为可追溯的案件闭环。

## 功能范围

- 六路固定施工视频监控与分析
- 安全帽、手套、安全背心缺失候选生成
- 视频、摄像头、区域、作业许可和责任班组关联
- VLM 语义复核与案件调查 Agent
- 基于权威规范语料的 RAG 检索与引用
- 人工补充事实、审核、整改证据和复查关闭
- REST、WebSocket 和 MJPEG 实时分析接口

## 六路演示编排

| 通道 | 视频 | 作业 | 预期 PPE 候选数 |
| --- | --- | --- | ---: |
| CAM-01 | `安全1.mp4` | 切割物料，防护齐全 | 0 |
| CAM-02 | `无背心2.mp4` | 切割物料，缺少安全背心 | 1 |
| CAM-03 | `无手套1.mp4` | 装订木板，缺少手套 | 1 |
| CAM-04 | `无背心无手套2.mp4` | 攀爬作业，缺少背心和手套 | 2 |
| CAM-05 | `无头盔无手套无背心.mp4` | 组装木料，三类 PPE 均缺失 | 3 |
| CAM-06 | `符合.mp4` | 多人混合穿戴：两人只穿背心，一人无 PPE | 7 |

上述数量是 `VISION_PROVIDER=fixture` 下的确定性演示结果。切换到真实 YOLO 后，结果取决于模型和视频实际推理输出。

`复合.mp4` 是工人娱乐素材，当前系统不包含行为识别，因此不在六路 PPE 演示中使用。

## 环境要求

- Python 3.10、3.11 或 3.12
- Node.js 与 npm
- SQLite（Python 自带驱动即可）
- 真实 RAG：可访问 OpenAI 兼容的 Embedding API
- 真实调查 Agent：可访问 DeepSeek API
- 真实 YOLO：CPU 即可，GPU 非必需

本项目的 Python 依赖统一维护在 `backend/pyproject.toml`：

- `ai`：Chroma、Embedding、DeepSeek Agent
- `vision`：Ultralytics、OpenCV、YOLO 视频推理
- `dev`：pytest、HTTP 测试工具

## 准备视频和模型

演示视频不进入 Git。后端当前从 `/data/demo` 读取以下文件：

```text
/data/demo/安全1.mp4
/data/demo/无背心2.mp4
/data/demo/无手套1.mp4
/data/demo/无背心无手套2.mp4
/data/demo/无头盔无手套无背心.mp4
/data/demo/符合.mp4
```

如果视频保存在仓库的 `data/demo`，可以在项目根目录将其链接到约定路径：

```bash
sudo mkdir -p /data
sudo ln -s "$(pwd)/data/demo" /data/demo
```

执行前确认 `/data/demo` 尚不存在。也可以直接将视频放到 `/data/demo`。

真实 YOLO 使用的权重文件同样不进入 Git。若 `best.pt` 位于项目根目录，从 `backend` 目录启动服务时配置为 `../best.pt`。

## 后端安装

在项目根目录执行：

```bash
cd backend
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e '.[ai,vision,dev]'
cp .env.example .env
```

真实密钥只写入本地 `backend/.env`，禁止提交到 Git。

### 稳定演示模式

稳定演示使用固定视觉候选和固定 VLM 复核，确保六路案件数量可重复：

```env
VISION_PROVIDER=fixture
VLM_PROVIDER=fixed
```

### CPU YOLO 模式

CPU 可以运行真实 YOLO。项目一次只分析一路视频，并按目标帧率抽帧推理：

```env
VISION_PROVIDER=yolo
YOLO_WEIGHTS_PATH=../best.pt
VISION_DEVICE=cpu
VISION_TARGET_FPS=5
VISION_IMAGE_SIZE=640
```

若单帧推理超过 200 ms，可将 `VISION_TARGET_FPS` 调低到 `3` 或 `2`。这只降低 AI 抽帧频率，不影响源视频正常播放。

### 真实 VLM 复核

真实 VLM 使用 OpenAI 兼容多模态接口，将 YOLO 生成的本地证据帧编码后提交给模型：

```env
VLM_PROVIDER=openai_compat
VLM_API_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
VLM_API_KEY=<本地密钥>
VLM_MODEL=qwen3.6-35b-a3b
```

需要安装 `backend[ai]`。密钥仅保存在本地 `backend/.env`，不得提交。

### Agent 与 RAG

```env
DEEPSEEK_API_KEY=<本地密钥>
AGENT_LLM_MODEL=deepseek-v4-flash

EMBEDDING_API_KEY=<本地密钥>
EMBEDDING_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
EMBEDDING_MODEL=<构建现有索引时使用的同一模型>
CHROMA_PATH=chroma_db
```

法规文档向量已经持久化在本地 Chroma 中，不会在每次启动时重新构建。每次检索仍需通过 Embedding API 将当前查询转换为向量，因此演示期间必须保证网络、API Key 和额度可用。查询模型必须与构建索引时使用的模型一致。

检查真实 RAG：

```bash
cd backend
.venv/bin/python scripts/check_rag_topk.py
```

## 启动系统

### 1. 启动后端

```bash
cd backend
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

后端首次启动会创建 SQLite 表并写入六路演示上下文。默认数据库是 `backend/siteppe.db`；需要独立的演示数据库时，可在 `.env` 中设置：

```env
DATABASE_URL=sqlite:///./siteppe-demo.db
```

检查服务：

```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/demo/videos
```

API 文档：<http://localhost:8000/docs>

### 2. 启动前端

另开一个终端：

```bash
cd frontend
npm ci
npm run dev
```

浏览器打开 <http://localhost:5173>。Vite 会将 `/api` 和 `/ws` 请求代理到 `http://localhost:8000`。

## 完整闭环演示

1. 在“监控台”选择一路视频并开始分析。
2. 等待分析会话完成，在“案件中心”打开生成的案件。
3. 案件需要补充事实时，以“现场安全员”身份提交现场事实。
4. 切换到“项目安全审核人”，审核案件并批准进入整改。
5. 切换回“现场安全员”，提交整改说明和可访问的整改后图片 URL。
6. 再次切换到“项目安全审核人”，完成复查并批准关闭。
7. 确认案件状态为“已关闭”，时间线包含检测、复核、调查、审核、整改和复查记录。

演示角色：

| 角色 | ID | 操作 |
| --- | --- | --- |
| 现场安全员 | `officer-01` | 补充事实、提交整改证据 |
| 项目安全审核人 | `reviewer-01` | 审核、批准整改、复查关闭 |

## 常用命令

### 后端测试

```bash
cd backend
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest
```

### ML 测试

```bash
backend/.venv/bin/python -m pytest ml/tests/test_video_inference.py -q
```

### 前端测试和构建

```bash
cd frontend
npm test
npm run build
```

## 项目结构

```text
backend/                 FastAPI、案件工作流、RAG、VLM 与视频分析
frontend/                React 监控台、案件中心和案件详情
ml/                      YOLO 视频推理与跟踪
data/demo/               本地演示视频（Git 忽略）
docs/development-logs/   成员开发日志
backend/chroma_db/       本地 RAG 向量索引（Git 忽略）
```

## 数据与密钥安全

以下内容仅保存在本地，不得提交：

- `.env` 与真实 API Key
- 演示视频、数据集和导出数据
- `best.pt` 等模型权重
- SQLite 数据库和 Chroma 索引
- 推理证据、运行日志和构建产物
