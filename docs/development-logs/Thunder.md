## 2026-07-14

### 当日目标

* 建立项目初始设计、课程要求映射、外部参考和设计验证材料。

### 开发记录

* 20:14 `Initial commit: Project design documentation and validation report`
  * 完成：提交项目设计、设计变更说明、教师要求、课程技术覆盖、课程代码复用、外部参考和验证报告，并建立首版忽略规则。
  * 实现：采用 MVP 优先、受控 Agent、RAG 依据检索和模块解耦方案，形成课程周期内可执行的项目结构。
  * 验证：提交说明记录 6 个 Mermaid 图和 6 个 JSON 示例已通过检查；原始验证命令未留存，本次未补写或声称重新运行。

### 问题与处理

* 当时尚未建立个人开发日志制度；本记录依据提交 `7e9f600` 的真实作者、时间、提交信息和文件内容补录。

### 后续计划

* 根据评审继续调整项目方向并建立可运行的项目骨架。

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

* 完成项目骨架分支验收收尾，开始共享契约与状态机任务，完善 `dev` 集成验收流程并维护真实开发日志。

### 开发记录

* 15:14 `chore(repo): 忽略本地基线脚本`
  * 完成：将本地 CrossGuard 快速基线脚本排除在版本控制之外，避免误提交无关实验文件。
  * 实现：仅忽略 `scripts/crossguard_quick_baseline.py`，保留项目后续纳入其他脚本的能力。
  * 验证：`git check-ignore -v --no-index scripts/crossguard_quick_baseline.py`，通过；`git diff --check -- .gitignore`，通过；本次仅修改忽略配置，未运行代码测试或构建。
* 15:32 `feat(contracts): 冻结共享事件与命令契约`
  * 完成：补齐候选业务时间、VLM 模型追溯信息、事件人工数据与时间线，并定义七种人工命令契约。
  * 实现：为候选时间窗口、跨对象身份、时区和 JSON 消息增加校验，通过契约发现接口公开事件与命令 Schema。
  * 验证：`cd backend && .venv/bin/python -m pytest`，24 项测试通过；`git diff --check`，通过。
* 15:46 `feat(workflow): 实现事件状态机`
  * 完成：实现自动复核调查与人工整改闭环的全部合法状态转换，并拒绝越权、跨状态、旧版本、证据缺失和错误候选复核。
  * 实现：通过 `CaseWorkflow.apply` 统一校验状态、角色和版本，经单次仓储端口调用提交最新快照与审计时间线；系统命令不具备数据库直写能力。
  * 验证：`cd backend && .venv/bin/python -m pytest`，44 项测试通过；`git diff --check`，通过；后端未配置 lint 和类型检查，前端未受本次修改影响，未运行构建。
* 16:17 `docs(workflow): 改用dev分支集成验收`
  * 完成：将任务分支交付流程调整为先进入 `dev` 集成测试，再由项目负责人验收并发布到 `main`。
  * 实现：统一任务分支基线、合并前同步、集成测试和正式发布规则，限制 Agent 合并或推送 `main`。
  * 验证：`git diff --check -- AGENTS.md docs/development-logs/Thunder.md`，通过；本次仅修改协作规则和开发日志，未运行代码测试或构建。
* 20:49 `feat(contracts): 完善视觉候选证据契约`
  * 完成：明确原始帧像素坐标、证据类别、关键帧角色和候选模型聚合追溯字段。
  * 实现：校验检测框几何与图像边界、唯一代表帧和时间顺序，并区分真实负类检测与正类未关联的框和置信度规则。
  * 验证：`cd backend && .venv/bin/python -m pytest tests/test_contracts.py tests/domain/test_case_workflow.py`，50 项测试通过。
* 20:54 `feat(contracts): 补齐页面与事件响应契约`
  * 完成：增加事件列表与详情响应、人工提交历史、统一时间线、六种固定实时事件载荷、错误响应和人工命令响应。
  * 实现：保留领域快照并为页面建立独立读模型，按事件类型校验载荷和案件关联，同时统一时区时间与 JSON-only 字段。
  * 验证：`cd backend && .venv/bin/python -m pytest`，68 项测试通过；`cd frontend && npm run build`，通过；后端未配置 lint 和类型检查，ML 未修改运行代码且未配置全局检查。
* 21:24 `docs(log): 补录Thunder真实开发记录`
  * 完成：根据仓库历史补录 Thunder 在 2026-07-14 的真实初始设计工作，并保持日志按时间正序排列。
  * 实现：以提交作者、北京时间、完整提交信息和变更内容为依据，仅记录可验证事实；未补造不存在的开发日期或验证命令。
  * 验证：`git log --all --no-merges --author='thunder\|Thunder\|汪振龙'`，确认 Thunder 共有 3 个真实开发日期；`git diff --check -- docs/development-logs/Thunder.md`，通过。

### 问题与处理

* 契约评审意见已全部落实，仍需 Wuweizhe 和 Thxnks 基于公开 Schema 做最终字段确认后宣布冻结。
* 远端 `dev` 已由项目负责人从最新 `main` 初始化，任务分支可以按新的集成验收流程同步和交付。
* Thunder 当前只有 3 个真实开发日期，距离最终交付要求的 8 天还差 5 天；按规则不得补造日期，只能在后续真实开发日持续记录。

### 后续计划

* 将任务分支合并到 `dev` 后通知 Wuweizhe 和 Thxnks 同步，并要求两人分别确认 ML 生产字段与数据库、页面消费字段不再缺失。
* 后续每个真实开发日继续按提交追加记录，最终交付前再次检查 8 天要求。

## 2026-08-09

### 当日目标

* 完成 VLM 复核核心（切片 1），打通"候选 → 复核 → 状态机"链路，并补上 `CaseStorePort` 按候选查询能力。

### 开发记录

* 13:35 `feat(vlm): 实现VLM复核解析、固定适配器与配置`
  * 完成：新增 VLM 复核核心三个模块——严格解析器、固定答案适配器与集中配置，并补齐对应测试。
  * 实现：`parser` 将模型输出严格校验为 `VlmReviewResult`，模型身份字段一律由请求上下文回填、不信任模型自报；`FixedVlmAdapter` 确定性输出结论，AUTO 按候选证据充分性决策，confirm/reject/uncertain 场景强制复现；`config` 集中 `VLM_*` 环境变量并保留 `.env.example`。
  * 验证：`cd backend && .venv/bin/python -m pytest tests/modules/vlm_review/test_parser.py tests/modules/vlm_review/test_fixed_adapter.py tests/modules/vlm_review/test_config.py`，14 项通过；`git diff --check`，通过。

### 问题与处理

* 无。

### 后续计划

* 实现 VLM 复核编排服务，并为 `CaseStorePort` 增加按候选查询事件的能力（公共接口变更，独立提交并通知郝欣冉确认仓储实现包含该方法）。
