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
* 修复事件 API 黑盒验收发现的责任主体校验、演示证据链与 OpenAPI 错误响应声明问题。

### 开发记录

* 13:35 `feat(vlm): 实现VLM复核解析、固定适配器与配置`
  * 完成：新增 VLM 复核核心三个模块——严格解析器、固定答案适配器与集中配置，并补齐对应测试。
  * 实现：`parser` 将模型输出严格校验为 `VlmReviewResult`，模型身份字段一律由请求上下文回填、不信任模型自报；`FixedVlmAdapter` 确定性输出结论，AUTO 按候选证据充分性决策，confirm/reject/uncertain 场景强制复现；`config` 集中 `VLM_*` 环境变量并保留 `.env.example`。
  * 验证：`cd backend && .venv/bin/python -m pytest tests/modules/vlm_review/test_parser.py tests/modules/vlm_review/test_fixed_adapter.py tests/modules/vlm_review/test_config.py`，14 项通过；`git diff --check`，通过。

* 13:38 `feat(domain): CaseStorePort 支持按候选查询事件`
  * 完成：为 `CaseStorePort` 追加只读方法 `find_by_candidate`，用于按候选定位事件，作为 VLM 复核服务的数据入口。
  * 实现：在 `case_workflow.py` 的端口协议上增加一个查询方法，纯加法不影响既有 `get`/`commit` 行为；该接口为公共接口，独立提交并通知郝欣冉在数据库仓储实现中同步该方法。
  * 验证：`cd backend && .venv/bin/python -m pytest tests/domain/test_case_workflow.py`，20 项通过；`git diff --check`，通过。
* 13:42 `feat(vlm): 实现VLM复核编排服务`
  * 完成：新增 `VlmReviewService`，串起"按候选找事件 → 构造请求 → 模型复核 → 严格解析 → 状态机"，并补齐服务测试。
  * 实现：service 只依赖 `VlmModelPort` 协议，换真实模型不改 service 与状态机；解析失败统一落成 UNCERTAIN 复核走 `VLM_REJECTED`，不让脏输出进入事件状态；候选无事件抛 `CandidateNotFound`。
  * 验证：`cd backend && .venv/bin/python -m pytest`，87 项通过；`git diff --check`，通过。
* 13:49 `fix(vlm): 复核解析拒绝负数播放位置`
  * 完成：为 `VlmReviewResult.evidence_timestamps_ms` 增加非负兜底校验，阻塞负数毫秒进入状态机。
  * 实现：冻结契约未对该字段约束非负，解析层显式检查负数即抛 `VlmParseError`，由 service 统一落成 UNCERTAIN → VLM_REJECTED；不修改 contracts.py。
  * 验证：`cd backend && .venv/bin/python -m pytest`，88 项通过；`git diff --check`，通过。

* 14:14 `feat(domain): 定义业务上下文端口与共享值模型`
  * 完成：新增业务上下文只读端口与七类共享值模型，作为 Agent 调查工具与 `/api/v1/demo/*` 的数据来源，也是郝欣冉 X-01 种子数据必须产出的值模型集合。
  * 实现：`site_context.py` 定义 `ZoneInfo/CameraInfo/VideoInfo/WorkPermit/TaskPpeMatrix/ResponsibleParty/DemoUser`（全部 `extra="forbid"` 严格校验，字段语义对齐设计文档 §6.2），端口 `SiteContextPort`（get_zone_at / find_active_work_permits / get_task_ppe_matrix / list_eligible_responsible_parties / list_videos / get_video）与 `UserDirectoryPort.get`；端口只读，禁止通过端口写入业务数据。
  * 验证：`cd backend && .venv/bin/python -m pytest`，88 项通过；`git diff --check`，通过。
* 14:16 `feat(domain): 六路通道内存种子与演示用户目录`
  * 完成：新增设计文档 §8.1 六路通道的内存种子化业务上下文与演示用户目录，并补齐 13 项领域测试。
  * 实现：`inmemory/site_context.py` 种子六路 `camera→zone→task`（CAM-01 脚手架区无许可、CAM-02 切割+眼部危害、CAM-03 搬运钢筋+手部危害、CAM-04 旋转设备+卷入风险→矩阵注明不简单要求戴手套、CAM-05 车辆区、CAM-06 普通许可）；许可窗口 08:00–18:00，`find_active_work_permits` 按区域+窗口过滤；`inmemory/actor_roles.py` 提供 `officer-01` 安全员、`reviewer-01` 审核人，同时满足角色与用户目录端口。
  * 验证：`cd backend && .venv/bin/python -m pytest`，101 项通过；`git diff --check`，通过。
* 17:12 `feat(domain): 提取完整事件仓储协议`
  * 完成：将事件仓储端口提取为独立公共模块，补齐创建、查询、筛选分页、乐观锁提交、候选反查和人工提交记录接口。
  * 实现：以 `CaseQuery` 明确状态、PPE、摄像头、责任主体、时间、逾期、关键词和分页语义，以 `CasePage` 返回分页数据与筛选总数；状态机与 VLM 服务改为从新模块依赖协议，既有行为不变。
  * 验证：`cd backend && /home/thunder/workspace/Innovative\ Integrated\ Application\ Training/backend/.venv/bin/python -m pytest tests/domain/test_case_store_port.py tests/domain/test_case_workflow.py tests/modules/vlm_review/test_service.py`，27 项通过；`git diff --check`，通过；后端未配置 lint 和类型检查，前端与 ML 未受影响，未运行构建或训练。
* 17:16 `feat(store): 实现内存事件仓储`
  * 完成：实现事件快照创建、查询、候选反查、乐观锁提交、人工提交历史与列表筛选分页，并隔离仓储内部可变状态。
  * 实现：成功提交原子完成版本递增、更新时间和状态时间线追加；列表支持状态、PPE、摄像头、责任主体、发生时间、逾期和关键词筛选，按“逾期、待人工、较早发生”排序后分页，并返回分页前总数。
  * 验证：`cd backend && /home/thunder/workspace/Innovative\ Integrated\ Application\ Training/backend/.venv/bin/python -m pytest tests/domain/test_inmemory_case_store.py tests/domain/test_case_workflow.py tests/modules/vlm_review/test_service.py`，31 项通过；`git diff --check`，通过；后端未配置 lint 和类型检查，前端与 ML 未受影响，未运行构建或训练。
* 17:30 `feat(api): 实现事件查询与人工命令闭环`
  * 完成：挂载六路演示视频与业务上下文、事件列表与详情、四个人工命令和当前阶段依据检索 REST 接口，提供可直接演示的完整事件种子。
  * 实现：`deps.py` 统一组合内存上下文、仓储、用户目录、时钟和状态机；列表后端计算筛选分页、统计、逾期、紧急度与重复风险；详情聚合引用、人工提交和完整来源时间线；所有状态变化仅经 `CaseWorkflow.apply`，状态机异常稳定映射为冻结 `ErrorResponse`，版本冲突携带当前版本；视频内容使用支持范围请求的文件响应且不泄露本地路径。
  * 验证：`cd backend && /home/thunder/workspace/Innovative\ Integrated\ Application\ Training/backend/.venv/bin/python -m pytest`，124 项通过；`git diff --check`，通过；后端未配置 lint 和类型检查，前端与 ML 未受影响，未运行构建或训练。
* 17:32 `test(api): 固定事件接口业务时钟`
  * 完成：让事件 API 测试固定使用带时区的业务时间，避免未来日期变化导致期限与逾期断言漂移。
  * 实现：通过 FastAPI 公共依赖覆盖替换时钟系统边界，每项测试结束后恢复应用依赖，不修改生产时钟行为。
  * 验证：`cd backend && /home/thunder/workspace/Innovative\ Integrated\ Application\ Training/backend/.venv/bin/python -m pytest tests/api/test_cases_api.py`，10 项通过；`cd backend && /home/thunder/workspace/Innovative\ Integrated\ Application\ Training/backend/.venv/bin/python -m pytest`，124 项通过；`git diff --check`，通过；后端未配置 lint 和类型检查。
* 18:03 `fix(api): 修复事件命令与演示审计一致性`
  * 完成：拒绝案件范围外的整改责任主体且保持事件与提交历史不变；修复车辆区结案、待复查及已进展案件的机器结果、调查事实、整改证据和人工提交审计；为四个人工命令公开统一错误响应。
  * 实现：状态机通过业务上下文校验责任主体资格并稳定返回 400；演示种子按摄像头、区域、任务、PPE、责任主体和引用构建自洽证据链；组合根同时装载人工提交；OpenAPI 显式声明冻结 `ErrorResponse` 的 400、403、404、409 响应。
  * 验证：`cd backend && /home/thunder/workspace/Innovative\ Integrated\ Application\ Training/backend/.venv/bin/python -m pytest -q tests/api/test_cases_api.py tests/api/test_error_mapping.py tests/domain/test_case_workflow.py tests/modules/vlm_review/test_service.py`，46 项通过；`cd backend && /home/thunder/workspace/Innovative\ Integrated\ Application\ Training/backend/.venv/bin/python -m pytest`，134 项通过；`git diff --check`，通过；后端未配置 lint 和类型检查，前端与 ML 未受影响，未运行构建或训练。

### 问题与处理

* 18:52 `feat(domain): 定义权威依据检索公共端口`
  * 完成：新增严格 Pydantic 的 `RequirementQuery`、`RequirementChunk`、`IndexMetadata`、`IndexReport` 与来源清单模型，并公开 `RequirementRetrieverPort.search`、`IndexerPort.index` 协议。
  * 实现：契约拒绝额外字段、空查询和越界 Top-K；chunk 保留页码与内容哈希，索引元数据固定嵌入模型、向量维度和语料指纹，为后续切片 5 Agent 提供只读检索入口。
  * 验证：`cd backend && /home/thunder/workspace/Innovative\\ Integrated\\ Application\\ Training/backend/.venv/bin/python -m pytest tests/domain/test_requirements_rag_port.py -q`，2 项通过；`git diff --check`，通过。

* 18:58 `feat(rag): 添加权威来源清单与稳定切分`
  * 完成：登记五个官方来源及职责，新增按标题、条款和语义段落切分的稳定 chunker，固定 chunk id 与 content_hash，并拒绝空文档和无效页码。
  * 实现：manifest 只提交 URL、权威元数据与哈希策略，不包含下载文档；chunk 保留标准、页码、来源和生效日期，供检索结果回映 Citation。
  * 验证：`cd backend && /home/thunder/workspace/Innovative\\ Integrated\\ Application\\ Training/backend/.venv/bin/python -m pytest tests/modules/requirements_rag/test_manifest_chunker.py -q`，3 项通过。

* 19:08 `feat(rag): 实现嵌入索引与权威检索服务`
  * 完成：接入确定性 fake embedder、JSON 持久化索引、惰性 Chroma 适配器、严格 Citation 映射、API 依赖组合根与五类 Top-K 检查脚本。
  * 实现：索引按 content_hash 幂等，嵌入模型/维度/manifest 指纹变化受控重建；真实 embedding 仅读取 `EMBEDDING_*`，无密钥时 API 稳定返回空 citations；来源解析状态、来源级别、表项切分和 `as_of` 过滤均有明确边界。
  * 验证：`cd backend && /home/thunder/workspace/Innovative\\ Integrated\\ Application\\ Training/backend/.venv/bin/python -m pytest tests/domain/test_requirements_rag_port.py tests/modules/requirements_rag tests/api/test_requirements_api.py -q`，15 项通过、1 项 `real_rag` 跳过；`git diff --check`，通过。

* 19:14 `fix(rag): 固化来源解析护栏与官方公告链接`
  * 完成：为来源 manifest 增加 main/supplemental/background 级别、解析/OCR 状态与派生文本审计字段，GB55034 使用住建部公告主链接并保留商务部镜像校验。
  * 实现：配置指南生效日保持空值，扫描或乱码正文不进入 chunker；表项逐行切分，查询支持 `as_of`，Citation section 统一包含条款与印刷页/PDF 页定位。
  * 验证：`cd backend && /home/thunder/workspace/Innovative\\ Integrated\\ Application\\ Training/backend/.venv/bin/python -m pytest tests/modules/requirements_rag/test_manifest_chunker.py tests/modules/requirements_rag/test_embedding_service.py -q`，9 项通过；真实 RAG 未运行（未配置密钥与下载语料）。

* 19:28 `fix(domain): 扩展权威语料与页码索引契约`
  * 完成：为公共模型增加 `corpus_fingerprint`、来源级别/角色、实际 PDF 页与可选印刷页、分页输入和显式背景查询模式。
  * 实现：Index metadata/report 现在可审计实际语料指纹；chunk 保留来源 provenance，旧 `page` 输入保持兼容并规范化到 `pdf_page`。
  * 验证：`cd backend && /home/thunder/workspace/Innovative\\ Integrated\\ Application\\ Training/backend/.venv/bin/python -m pytest tests/domain/test_requirements_rag_port.py tests/modules/requirements_rag/test_acceptance_regressions.py -q`，5 项通过；`git diff --check`，通过。

* 19:45 `fix(rag): 修复语料可信度与索引一致性`
  * 完成：补齐五来源发布日期、发布机关、PDF hash 与 JSON/Python manifest 一致性；未准备、未复核、乱码、缺分页或 hash 不一致语料统一拒绝索引。
  * 实现：表格数字行逐行切分并继承页码；语料指纹包含规范化实际内容；来源级别和生效日期在 Top-K 截断前过滤；向量数量、维度、模型不匹配显式失败；真实与离线存储边界分离。
  * 验证：`cd backend && /home/thunder/workspace/Innovative\\ Integrated\\ Application\\ Training/backend/.venv/bin/python -m pytest tests/modules/requirements_rag tests/api/test_requirements_api.py tests/api/test_requirements_composition.py -q`，20 项通过、1 项 `real_rag` 跳过；`git diff --check`，通过。

* 子 agent 独立审查发现 `evidence_timestamps_ms` 无非负约束、解析层未兜底，与契约评审稿全局规则不一致；已在解析层补齐显式校验并增加回归测试，低严重度，不影响其他契约遵守。
* 切片 2 的值模型与端口属于共享接口，已按规范拆成独立提交，需在合并 dev 前通知郝欣冉按该值模型产出 X-01 种子数据。
* 事件 API 黑盒验收发现不存在的责任主体可推进状态、公开种子存在跨场景事实与审计缺口、人工命令未公开错误响应；已通过公共 ASGI/OpenAPI 回归逐项复现并修复，未修改冻结契约。

### 后续计划

* 将修复后的 `feat/api-composition` 提交给项目负责人复验；不在任务分支内合并 `dev` 或 `main`。
