# SitePPE Agent

SitePPE Agent 是一个施工现场 PPE（个体防护装备）智能监管演示系统。系统通过六路施工视频发现安全帽、手套和安全背心缺失问题，并将模型复核、法规查询、人工审核、整改提交和复查关闭串联成完整案件闭环。

## 主要功能

- 六路施工视频同时循环播放，点击后一次分析一路视频。
- 检测安全帽、手套和安全背心缺失情况，生成关键证据帧。
- 使用多模态模型复核检测结果，减少误报。
- 使用调查 Agent 结合 RAG 法规依据生成调查结论和整改建议。
- 支持现场安全员补充事实、提交整改说明和整改照片。
- 支持项目安全审核人审核案件、查看整改信息并完成复查关闭。
- 在案件时间线中保留检测、复核、调查、审核和整改记录。

## 六路演示场景

| 通道 | 视频 | 演示内容 |
| --- | --- | --- |
| CAM-01 | `安全1.mp4` | 切割物料，安全帽、手套和背心齐全 |
| CAM-02 | `无背心2.mp4` | 切割物料，缺少安全背心 |
| CAM-03 | `无手套1.mp4` | 装订木板，缺少手套 |
| CAM-04 | `无背心无手套2.mp4` | 攀爬作业，缺少背心和手套 |
| CAM-05 | `无头盔无手套无背心.mp4` | 组装木料，三类 PPE 均缺失 |
| CAM-06 | `符合.mp4` | 多人场景：两人只穿背心，一人未穿戴 PPE |

## 快速开始

### 1. 安装环境

需要 Python 3.10 至 3.12、Node.js 和 npm。

安装后端：

```bash
cd backend
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e '.[ai,vision,dev]'
cp .env.example .env
cd ..
```

安装前端：

```bash
cd frontend
npm ci
cd ..
```

### 2. 放置演示资源

将表格中的六个视频放入项目的 `data/demo` 目录，然后在项目根目录执行以下命令，让后端可以通过 `/data/demo` 读取：

```bash
sudo mkdir -p /data
sudo ln -s "$(pwd)/data/demo" /data/demo
```

执行链接命令前，请确认 `/data/demo` 尚不存在。真实 YOLO 推理还需将 `best.pt` 放在项目根目录。

### 3. 配置服务

在 `backend/.env` 中填写本机实际使用的模型和密钥。完整演示需要配置：

- YOLO：`VISION_PROVIDER`、`YOLO_WEIGHTS_PATH` 和 `VISION_DEVICE`；根目录下的 `best.pt` 对应路径为 `../best.pt`。
- 多模态复核：`VLM_PROVIDER`、接口地址、API Key 和模型名称。
- 调查 Agent：DeepSeek API Key 和模型名称。
- RAG：Embedding API Key、接口地址和构建索引时使用的同一模型。

不调用真实视觉和多模态模型时，可使用固定演示模式：

```env
VISION_PROVIDER=fixture
VLM_PROVIDER=fixed
```

### 4. 启动系统

终端一启动后端：

```bash
cd backend
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

终端二启动前端：

```bash
cd frontend
npm run dev
```

浏览器打开 <http://localhost:5173>。

## 使用方法

1. 进入“监控台”，确认六路视频正在循环播放。
2. 选择一路视频并点击“开始分析”；系统同一时间只分析一路。
3. 分析完成后进入“案件中心”，打开生成的案件。
4. 需要补充信息时，以“现场安全员”身份提交现场事实。
5. 切换为“项目安全审核人”，审核调查结果并批准整改。
6. 切换回“现场安全员”，填写整改说明并上传整改照片。
7. 再次切换为“项目安全审核人”，查看整改信息并复查关闭案件。
8. 确认案件状态为“已关闭”，并检查完整时间线。

## 演示角色

| 角色 | 账号 | 主要操作 |
| --- | --- | --- |
| 现场安全员 | `officer-01` | 补充事实、提交整改说明和照片 |
| 项目安全审核人 | `reviewer-01` | 审核案件、批准整改、复查关闭 |

## 本地文件说明

API Key、`.env`、视频、模型权重、数据库、向量索引和运行生成的证据文件仅保存在本地，不要提交到 Git。
