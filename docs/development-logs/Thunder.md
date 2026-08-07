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
* 21:25 `chore(repo): 停止跟踪项目设计文档`
  * 完成：将项目设计改为团队私下阅读的本地文档，不再上传仓库。
  * 实现：在根目录忽略 `/project-design.md`，并从 Git 索引移除该文件，本地文件保留。
  * 验证：`git check-ignore -v --no-index project-design.md`，命中根目录忽略规则；`git diff --check -- .gitignore docs/development-logs/Thunder.md`，通过；本提交仅修改仓库配置和文档跟踪状态，未运行代码测试。

### 问题与处理

* GitHub HTTPS 无凭据导致首次推送失败；确认现有 SSH 密钥已授权后，将 `origin` 切换为 SSH 地址并成功推送。
* 本机未配置后端项目环境，且系统 Python 缺少 pytest；临时将声明依赖安装到 `/tmp` 完成本次验证，后续仍需建立正式项目环境。

### 后续计划

* 在本地完善项目设计文档，然后开始共享契约评审。

## 2026-08-07

### 当日目标

* 完成项目骨架分支验收收尾，开始共享契约与状态机任务，并完善 `dev` 集成验收流程。

### 开发记录

* 15:14 `chore(repo): 忽略本地基线脚本`
  * 完成：将本地 CrossGuard 快速基线脚本排除在版本控制之外，避免误提交无关实验文件。
  * 实现：仅忽略 `scripts/crossguard_quick_baseline.py`，保留项目后续纳入其他脚本的能力。
  * 验证：`git check-ignore -v --no-index scripts/crossguard_quick_baseline.py`，通过；`git diff --check -- .gitignore`，通过；本次仅修改忽略配置，未运行代码测试或构建。
* 16:17 `docs(workflow): 改用dev分支集成验收`
  * 完成：将任务分支交付流程调整为先进入 `dev` 集成测试，再由项目负责人验收并发布到 `main`。
  * 实现：统一任务分支基线、合并前同步、集成测试和正式发布规则，限制 Agent 合并或推送 `main`。
  * 验证：`git diff --check -- AGENTS.md docs/development-logs/Thunder.md`，通过；本次仅修改协作规则和开发日志，未运行代码测试或构建。

### 问题与处理

* 远端尚无 `dev` 分支；规则要求缺失时停止创建任务分支，并由项目负责人从最新 `main` 初始化。

### 后续计划

* 由项目负责人初始化远端 `dev`；后续任务从最新 `dev` 创建分支并先进入 `dev` 集成测试。
