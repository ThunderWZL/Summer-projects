## 2026-08-06

### 当日目标

* 提交项目协作规则、施工 PPE 设计和可运行的前后端与视觉骨架。

### 开发记录

* 20:58 `chore(repo): 完善协作和忽略规则`
  * 完成：建立 Agent 协作、分支、提交、日志和验证规则，完善项目忽略范围。
  * 实现：保留仓库级 `AGENTS.md`，忽略数据集、模型、视频、密钥、缓存、构建和训练产物。
  * 验证：`git diff --check -- .gitignore AGENTS.md docs/development-logs/Thunder.md`，通过。
* 20:59 `docs(project): 确定施工PPE项目设计`
  * 完成：将项目方向更新为 SitePPE Agent，明确三人分工、主流程、状态机、模块、接口、部署和验收标准。
  * 实现：整合 YOLO 数据集、VLM 复核、DeepSeek Agent、权威 RAG、SQLite 和人工审核闭环，删除旧方向的设计与验证文档。
  * 验证：`git diff --check -- project-design.md course-code-reuse-map.md course-tech-coverage-map.md external-reference-map.md project-design-change-notes.md teacher-project-guidance.md validation-report.md docs/development-logs/Thunder.md`，通过；项目未配置文档自动化测试。
* 21:02 `feat(scaffold): 初始化项目核心骨架`
  * 完成：建立 FastAPI 健康接口与共享契约、React/Vite 入口和 YOLO 训练配置。
  * 实现：定义 PPE 候选、VLM 复核、调查结果、事件快照和 WebSocket 事件契约，为 VLM 保留 adapter 接口。
  * 验证：`cd frontend && npm run build`，通过；`cd backend && python -m pytest`，首次因系统没有 `python` 命令失败；将声明的开发依赖安装到 `/tmp` 后执行 `PYTHONPATH=/tmp/siteppe-backend-deps-20260806-2102 python3 -m pytest`，2 项测试通过；ML 未配置全局检查且尚未下载数据集，未运行训练。

### 问题与处理

* GitHub HTTPS 无凭据导致首次推送失败；确认现有 SSH 密钥已授权后，将 `origin` 切换为 SSH 地址并成功推送。
* 本机未配置后端项目环境，且系统 Python 缺少 pytest；临时将声明依赖安装到 `/tmp` 完成本次验证，后续仍需建立正式项目环境。

### 后续计划

* 开始共享契约评审，并在后续本机开发前建立正式项目环境。
