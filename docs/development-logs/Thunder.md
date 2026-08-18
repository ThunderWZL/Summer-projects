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
* 补齐视频实时推理的组合回归测试，锁定迟到节拍、分析结果复用与异常资源释放行为。

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
* 21:52 `test(ml): 覆盖实时迟到后的节拍恢复`
  * 完成：增加慢推理组合回归，验证播放流一次迟到后不会连续追帧，并保持全部源帧顺序输出和资源释放。
  * 实现：通过 `VideoInferenceRunner.iter_video()` 公共生成器注入可控时钟，在播放中制造 350ms 迟到，直接断言下一帧恢复 100ms 正向等待；临时恢复旧 deadline 累加逻辑确认测试可复现零等待 burst 后再恢复正确实现。
  * 验证：`/home/thunder/workspace/Innovative\ Integrated\ Application\ Training/backend/.venv/bin/python -m pytest ml/tests/test_video_inference.py -q`，17 项通过；`git diff --check`，通过；ML 未配置全局 lint 或构建命令，未运行。
* 21:54 `test(ml): 验证最新标注的复用与更新`
  * 完成：强化慢 AI 组合回归，验证完整十帧播放流持续复用最近分析，并在后台新结果到达后更新检测与标注像素。
  * 实现：分阶段阻塞和释放 2、6、8 号采样帧，确认 4 号旧待处理样本被替换；通过公共输出同时断言人员轨迹 ID 和标注像素从 100 更新到 102、106，且帧序与时间戳完整。
  * 验证：`/home/thunder/workspace/Innovative\ Integrated\ Application\ Training/backend/.venv/bin/python -m pytest ml/tests/test_video_inference.py -q`，17 项通过；`git diff --check`，通过；ML 未配置全局 lint 或构建命令，未运行。
* 21:57 `fix(ml): 释放启动失败的视频资源`
  * 完成：修复后台推理线程启动异常时视频捕获句柄未释放的问题，并增加公共生成器级回归测试。
  * 实现：将 worker 启动纳入 `iter_video()` 资源保护范围，仅对成功启动的线程执行关闭；线程启动失败时保留原始异常并在外层 `finally` 释放 capture。
  * 验证：`/home/thunder/workspace/Innovative\ Integrated\ Application\ Training/backend/.venv/bin/python -m pytest ml/tests/test_video_inference.py -q`，18 项通过；`/home/thunder/workspace/Innovative\ Integrated\ Application\ Training/backend/.venv/bin/python -m py_compile ml/video_inference.py`，通过；`git diff --check`，通过；ML 未配置全局 lint 或构建命令，未运行。

### 问题与处理

* `worker.start()` 原位于 capture 资源保护范围外，线程创建失败会泄漏视频句柄；通过启动状态标记与外层 `finally` 修复，并保留原始启动异常。

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

* 20:02 `fix(domain): 补充索引语料指纹参数`
  * 完成：公开 `IndexerPort.index` 的可选 `corpus_fingerprint` 参数，使调用方能够显式传递实际规范化语料指纹。
  * 实现：保持 manifest 指纹与内容指纹分离，未来 Agent 仅消费检索端口，不接触存储实现。
  * 验证：`git diff --check`，通过；后端全量测试在后续 RAG 修复提交中统一运行。

* 20:11 `fix(rag): 校正官方来源状态与检查脚本`
  * 完成：将五来源状态、发布机关、77号文发布日期/生效日和 HTML 正文节点 hash 策略改为官方可核验值，并保持 Python 常量与随仓 JSON 完全一致。
  * 实现：Top-K 检查从仓库 manifest 验证语料，缺密钥、未准备语料或空 citation 均以 NOT RUN/非零退出，不再把离线空库当真实 RAG 成功。
  * 验证：`cd backend && /home/thunder/workspace/Innovative\\ Integrated\\ Application\\ Training/backend/.venv/bin/python -m pytest -q`，155 项通过、1 项 `real_rag` 跳过；真实 RAG 未运行。

* 20:19 `fix(rag): 提供默认来源清单与语料未就绪别名`
  * 完成：`load_manifest()` 可直接加载随仓五来源清单，并公开 `CorpusNotReadyError` 兼容名称，便于验收和上层明确报告未准备语料。
  * 实现：默认路径固定在 requirements_rag manifests 目录，不引入下载文件或索引产物。
  * 验证：`cd backend && /home/thunder/workspace/Innovative\\ Integrated\\ Application\\ Training/backend/.venv/bin/python -m pytest tests/modules/requirements_rag/test_acceptance_regressions.py -q`，3 项通过；`git diff --check`，通过。

* 20:36 `fix(rag): 下推检索过滤并支持来源 artifact`
  * 完成：将 as_of/source_level 过滤下推 JSON 与 Chroma 存储层，新增通用 `source_artifact_sha256`，HTML 正文可在人工复核后入库并保留 PDF 来源追踪。
  * 实现：检索不再使用固定候选上限；冷启动 Chroma metadata 主动连接现有 collection，恢复 embedding model、维度、manifest 与 corpus 校验。
  * 验证：`cd backend && /home/thunder/workspace/Innovative\\ Integrated\\ Application\\ Training/backend/.venv/bin/python -m pytest tests/modules/requirements_rag/test_embedding_service.py tests/modules/requirements_rag/test_html_artifact.py tests/modules/requirements_rag/test_chroma_lazy.py -q`，12 项通过；`git diff --check`，通过。

* 20:49 `chore(env): 补充后端测试环境安装入口`
  * 完成：新增后端测试环境 requirements 入口，缺少 pytest 的环境可一次安装项目运行依赖和 `dev` 测试依赖。
  * 实现：`requirements-dev.txt` 通过 `.[dev]` 复用 `pyproject.toml` 的版本声明，避免维护两份依赖版本；确认 `AGENTS.md` 当前没有自动安装 requirements 的指令。
  * 验证：`python3 -m pip install --dry-run --break-system-packages -r requirements-dev.txt`，成功解析包括 pytest 8.4.2 和 HTTPX 0.28.1 在内的完整环境且未实际安装；`cd backend && /home/thunder/workspace/Innovative\\ Integrated\\ Application\\ Training/backend/.venv/bin/python -m pytest`，160 项通过、1 项真实 RAG 因无密钥跳过；后端未配置 lint 和类型检查，前端与 ML 未受影响。

* 20:51 `fix(rag): 修复 Chroma 全量候选过滤`
  * 完成：Chroma 检索先以 collection.count() 请求完整候选集，再按生效日期、来源级别过滤和 top_k 截断；空 collection 直接返回空结果。
  * 实现：消除 Chroma 路径中 `n_results=top_k` 的预截断，确保第 21 条有效主证据不会被前 20 条未来/背景条款遮蔽。
  * 验证：`cd backend && /home/thunder/workspace/Innovative\\ Integrated\\ Application\\ Training/backend/.venv/bin/python -m pytest tests/modules/requirements_rag/test_chroma_lazy.py::test_chroma_search_queries_all_rows_before_filtering_top_k tests/modules/requirements_rag/test_chroma_lazy.py::test_chroma_search_empty_collection_returns_without_querying -q`，2 项通过；`git diff --check`，通过。

* 子 agent 独立审查发现 `evidence_timestamps_ms` 无非负约束、解析层未兜底，与契约评审稿全局规则不一致；已在解析层补齐显式校验并增加回归测试，低严重度，不影响其他契约遵守。
* 切片 2 的值模型与端口属于共享接口，已按规范拆成独立提交，需在合并 dev 前通知郝欣冉按该值模型产出 X-01 种子数据。
* 事件 API 黑盒验收发现不存在的责任主体可推进状态、公开种子存在跨场景事实与审计缺口、人工命令未公开错误响应；已通过公共 ASGI/OpenAPI 回归逐项复现并修复，未修改冻结契约。

### 后续计划

* 将修复后的 `feat/api-composition` 提交给项目负责人复验；不在任务分支内合并 `dev` 或 `main`。

## 2026-08-12

### 当日目标

* 更新 Agent 协作规则，使契约、设计文档、固定负责人和项目检查命令与重构后的开发方案一致。
* 修复 VLM 技术失败被伪装成语义结论的问题，确保失败不触发 Case 状态迁移。

### 开发记录

* 00:18 `docs(workflow): 更新契约与设计文档指引`
  * 完成：补充设计文档权威顺序，要求共享契约任务优先读取项目负责人私发的 AI 开发版契约，并同步冻结边界、目录负责人、检查命令与禁止提交项。
  * 实现：以触发式文档指针连接总体设计、AI 共享契约、版本化共享契约、`contracts.py` 和运行时 Schema；数据库 schema 按 D-09 冻结，OpenAPI、ML、RAG 检查与跨模块交付要求分别落入对应工作流。
  * 验证：`git diff --check -- AGENTS.md docs/development-logs/Thunder.md`，通过；`rg -n "共享契约（给ai）|D-09|\.venv/bin/python -m pytest|npm run generate:contracts|python -m pytest ml/tests|check_rag_topk|reports/generated/" AGENTS.md`，确认关键规则已写入；本次只修改 Agent 规则和开发日志，未运行代码测试或构建。

* 00:41 `fix(vlm): 区分复核技术失败与语义结论`
  * 完成：移除解析失败伪造 `UNCERTAIN` 的降级路径，合法不确定结论仍进入 `VLM_REJECTED`，技术失败重试耗尽后保持候选状态。
  * 实现：新增带 `retryable` 和尝试次数的 `VlmProcessingFailed`；VLM 服务支持配置化重试次数与间隔，永久失败立即透传且不调用状态机；示例环境补齐对应配置。
  * 验证：`cd backend && /home/thunder/workspace/Innovative\ Integrated\ Application\ Training/backend/.venv/bin/python -m pytest tests/modules/vlm_review/`，23 项通过；`cd backend && /home/thunder/workspace/Innovative\ Integrated\ Application\ Training/backend/.venv/bin/python -m pytest`，163 项通过、1 项真实 RAG 条件测试跳过；后端未配置 lint 和类型检查，前端与 ML 未受影响。

### 问题与处理

* 当前主工作区存在其他成员或任务的未提交修改；使用基于最新 `origin/dev` 的独立 worktree 完成本次文档提交，未切换、覆盖或暂存原工作区内容。
* 切片 1 工作树未包含被忽略的虚拟环境；改用主项目 `backend/.venv` 在修复分支目录运行测试，未修改环境或依赖。

### 后续计划

* 推送 `fix/vlm-failure-split` 任务分支，交由项目负责人复验并合入 `dev`。

## 2026-08-13

### 当日目标

* 完成切片五的配置化业务上下文、确定性 PPE 解析和受控 Agent 调查能力。

### 开发记录

* 23:50 `feat(context): 支持配置化演示作业规则`
  * 完成：将五类演示任务规则和六路场景分配迁移到受校验的 JSON 配置，支持更换场景任务映射而无需修改 Python 代码。
  * 实现：内存现场上下文从包内资源构造视频、区域、许可、责任主体和任务矩阵；校验任务、摄像头与视频唯一性、PPE 枚举、任务引用及正数整改窗口。
  * 验证：`cd backend && /home/thunder/workspace/Innovative\ Integrated\ Application\ Training/backend/.venv/bin/python -m pytest tests/domain/test_site_context.py -q`，15 项通过；后端未配置 lint 和类型检查，前端与 ML 未受影响。

### 问题与处理

* 主工作区存在其他任务的未提交修改；本任务使用基于最新 `origin/dev` 的独立 worktree，未切换、暂存或覆盖原工作区内容。

### 后续计划

* 实现 resolver、受控 DeepSeek Agent、确定性假实现和调查组装服务，并运行后端全量测试。

## 2026-08-14

### 当日目标

* 完成确定性调查解析、受控 DeepSeek 工具调用和调查服务组装，并验证切片五语义。

### 开发记录

* 00:03 `feat(investigation): 实现确定性调查与受控Agent`
  * 完成：实现 resolver 优先的调查上下文、仅允许两类只读工具的 Agent 循环、确定性假实现和调查结果持久化组装。
  * 实现：依据 DeepSeek 与 LangChain 最新官方文档绑定工具 schema、透传 `tool_call_id`、显式使用官方 API 地址，并通过 `extra_body` 关闭思考模式；提示词冻结 resolver 事实并声明最终 JSON 字段。
  * 验证：`cd backend && /home/thunder/workspace/Innovative\ Integrated\ Application\ Training/backend/.venv/bin/python -m pytest tests/domain/ tests/modules/investigation/ -q`，116 项通过；`cd backend && /home/thunder/workspace/Innovative\ Integrated\ Application\ Training/backend/.venv/bin/python -m pytest -ra`，在首个既有 API 用例长时间无输出，且主工作区可独立复现同一阻塞，未记为通过；后端未配置 lint 和类型检查，前端与 ML 未受影响。

* 20:51 `feat(video-analysis): 定义视频分析会话端口`
  * 完成：冻结分析会话值对象及开始、停止、画面流和事件订阅四个端口方法。
  * 实现：端口复用共享 `AnalysisStage` 与 `AnalysisEvent` 契约，并提供稳定的视频和会话不存在领域错误。
  * 验证：`cd backend && /home/thunder/workspace/Innovative\ Integrated\ Application\ Training/backend/.venv/bin/python -m pytest tests/domain/test_video_analysis.py::test_analysis_session_and_port_expose_the_frozen_contract -q`，1 项通过；`git diff --check`，通过。

* 20:51 `feat(analysis-session): 实现单路分析与实时事件`
  * 完成：提供分析会话启动/幂等停止 REST、有限 MJPEG 占位流和 WebSocket 实时事件，并在换路时等待旧 runner 完成资源释放。
  * 实现：EventHub 按会话递增 sequence 并实时扇出；会话编排映射 `VlmProcessingFailed`；确定性假实现只引用已有 Case，且仅演示 `helmet/gloves/vest` 候选；断开 WebSocket 时主动清理订阅。
  * 验证：`cd backend && /home/thunder/workspace/Innovative\ Integrated\ Application\ Training/backend/.venv/bin/python -m pytest tests/domain/test_video_analysis.py tests/services/test_event_hub.py tests/services/test_session_manager.py tests/api/test_analysis_sessions.py tests/api/test_analysis_sessions_ws.py -q`，22 项通过；`cd backend && /home/thunder/workspace/Innovative\ Integrated\ Application\ Training/backend/.venv/bin/python -m pytest tests/domain tests/modules tests/services -q`，202 项通过、1 项跳过；后端全量测试在既有 `tests/api/test_cases_api.py` 处无输出阻塞，未记为通过；后端未配置 lint 和类型检查，前端与 ML 未受影响；`git diff --check`，通过。

* 20:51 `fix(analysis-session): 串行化换路并阻止停止后取流`
  * 完成：并发切换请求严格串行，旧 runner 完成清理后才启动下一路；停止或自然结束的会话不再创建新 MJPEG 流。
  * 实现：会话生命周期增加异步互斥并复用内部停止路径；非活动流返回稳定的 `ANALYSIS_SESSION_NOT_ACTIVE` 冲突响应；假实现复用视觉模块的三类 PPE 支持集合。
  * 验证：`cd backend && /home/thunder/workspace/Innovative\ Integrated\ Application\ Training/backend/.venv/bin/python -m pytest tests/domain/test_video_analysis.py tests/services/test_event_hub.py tests/services/test_session_manager.py tests/api/test_analysis_sessions.py tests/api/test_analysis_sessions_ws.py -q`，25 项通过；`cd backend && /home/thunder/workspace/Innovative\ Integrated\ Application\ Training/backend/.venv/bin/python -m pytest tests/domain tests/modules tests/services -q`，204 项通过、1 项跳过；`git diff --check`，通过。

* 20:51 `fix(analysis-session): 保留已完成会话的演示流`
  * 完成：假分析快速完成后仍可读取有限 MJPEG 结果，显式停止或 VLM 失败后继续拒绝取流。
  * 实现：将 runner 活动状态与流可读状态分离，避免 POST 后稍迟请求流时因自然完成返回 409，同时保持停止释放资源语义。
  * 验证：`cd backend && /home/thunder/workspace/Innovative\ Integrated\ Application\ Training/backend/.venv/bin/python -m pytest tests/domain/test_video_analysis.py tests/services/test_event_hub.py tests/services/test_session_manager.py tests/api/test_analysis_sessions.py tests/api/test_analysis_sessions_ws.py -q`，26 项通过；`cd backend && /home/thunder/workspace/Innovative\ Integrated\ Application\ Training/backend/.venv/bin/python -m pytest tests/domain tests/modules tests/services -q`，204 项通过、1 项跳过；`git diff --check`，通过。

* 21:29 `fix(api): 统一分析接口错误与OpenAPI契约`
  * 完成：请求字段校验统一返回冻结的 `ErrorResponse`，分析会话端点在 OpenAPI 中声明实际成功和错误响应。
  * 实现：注册 `RequestValidationError` 映射为 `VALIDATION_ERROR`；启动、停止和取流接口声明 404/409/422 模型，MJPEG 200 响应声明为二进制 `multipart/x-mixed-replace`。
  * 验证：`cd backend && /home/thunder/workspace/Innovative\ Integrated\ Application\ Training/backend/.venv/bin/python -m pytest tests/api/test_analysis_sessions.py tests/api/test_analysis_sessions_ws.py tests/domain/test_video_analysis.py tests/services/test_event_hub.py tests/services/test_session_manager.py -q`，27 项通过；`cd backend && /home/thunder/workspace/Innovative\ Integrated\ Application\ Training/backend/.venv/bin/python -m pytest tests/api/test_error_mapping.py::test_human_command_openapi_declares_all_workflow_error_responses tests/domain tests/modules tests/services -q`，205 项通过、1 项跳过；后端未配置 lint 和类型检查，前端与 ML 未受影响；`git diff --check`，通过。

### 问题与处理

* 新增回归测试首次运行 15 项失败、21 项通过；补齐工具绑定、工具调用标识、冻结事实提示词及 DeepSeek V4 配置后，相关测试全部通过。
* 后端全量套件在既有 API 测试发生环境性阻塞；中断后用主工作区单测复现，确认并非本任务分支引入。
* 切片六测试发现运行时类型别名导入失败、同步依赖挂起、WebSocket 断开不清理、runner 技术异常未映射、停止返回早于资源释放及未启用 PPE 被演示；均已补回归测试并修复。
* 双轴复审发现并发换路可产生重叠 runner、停止后仍可重新取流；已增加生命周期互斥、活动状态校验和回归测试。
* 修复后复审发现假 runner 过快完成会使首次 MJPEG 请求返回 409；已分离流可读状态并覆盖完成后读取、停止后拒绝两种行为。
* 契约复审发现请求校验错误仍泄露 FastAPI `detail`，且分析接口 OpenAPI 未声明实际错误模型和 MJPEG 媒体类型；已通过 ASGI 与 OpenAPI 回归测试修复。

### 后续计划

* 推送 `feat/analysis-sessions` 任务分支，交由项目负责人验收；真实视频推理接线等待对应模块交付。

## 2026-08-15

### 当日目标

* 完成切片七六路实时监控台、分析通道切换、实时事件计数和连接失败重试，并验证前后端共享契约。
* 完成切片八确定性案件流水线与六路演示闭环，验证候选、复核、调查、人工处置和关闭链路。

### 开发记录

* 00:53 `feat(frontend): 实现六路实时监控台`
  * 完成：实现响应式 2×3 视频墙、六路预览、单活动分析会话、换路确认、MJPEG 标注画面、角色切换及显式断线重试。
  * 实现：封装演示目录与会话 REST、严格校验并按 sequence 去重 WebSocket 事件；候选数仅采用 `SESSION_PROGRESS` 和 `SESSION_FINISHED` 权威计数；状态机隔离过期会话事件，并处理 StrictMode 加载、重复启动和终态连接释放。
  * 验证：`cd frontend && npm run test`，7 个测试文件共 33 项通过；`cd frontend && npm run build`，类型检查和生产构建通过；`cd backend && /home/thunder/workspace/Innovative\ Integrated\ Application\ Training/backend/.venv/bin/python -m pytest tests/api/test_demo_api.py tests/api/test_analysis_sessions.py`，11 项通过；`git diff --check`，通过；前端未配置 lint，未运行。

* 02:11 `feat(pipeline): 实现确定性案件闭环`
  * 完成：实现候选建案、VLM 复核、确定性调查、人工补事实后自动重调查，以及六路演示从候选到关闭的后端闭环。
  * 实现：增加三帧候选夹具和幂等流水线；按冻结契约区分语义拒绝与技术失败，复用 resolver 生成 PPE 适用性，落实不适用审批守卫、统计过滤和会话权威计数。
  * 验证：`cd backend && PYTHONPATH=/tmp/siteppe-case-pipeline/backend /home/thunder/workspace/Innovative\ Integrated\ Application\ Training/backend/.venv/bin/python -m pytest`，313 项通过、1 项跳过；`git diff --check`，通过；后端未配置 lint 和类型检查，未运行。

* 02:12 `feat(frontend): 串联监控与案件闭环`
  * 完成：在统一应用壳内串联监控台、案件列表和案件详情，并由顶层统一维护演示角色和案件路由。
  * 实现：采用 Hash 路由保持静态部署兼容，监控与案件工作区常驻挂载以保留分析状态；复用共享 API 类型和演示上下文，移除重复导航、角色选择与演示上下文请求实现。
  * 验证：`cd frontend && npm run test`，9 个测试文件共 42 项通过；`cd frontend && npm run build`，类型检查和生产构建通过；`node /home/thunder/.agents/skills/impeccable/scripts/detect.mjs --json src/App.tsx src/styles.css src/features/cases/CasesWorkspace.tsx src/features/cases/case-center.css src/features/review/case-detail.css`，无前端反模式发现；`git diff --check`，通过；前端未配置 lint，未运行。

* 02:22 `fix(integration): 对齐切片八冻结契约`
  * 完成：修正 CAM-02 六路语义，补发 VLM 与 Case 状态实时事件，并用独立事实上下文验证版本 1 至 10 的完整关闭链路。
  * 实现：移除非白名单 `site_note` 特判；按实际迁移发布 `VLM_REVIEWED` 和 `CASE_UPDATED` 摘要；更新 OpenAPI 生成类型及前端测试命令说明。
  * 验证：`cd backend && PYTHONPATH=/tmp/siteppe-case-pipeline/backend /home/thunder/workspace/Innovative\ Integrated\ Application\ Training/backend/.venv/bin/python -m pytest`，313 项通过、1 项跳过；`cd frontend && npm run generate:contracts`，生成成功；`cd frontend && npm run test`，9 个测试文件共 42 项通过；`cd frontend && npm run build`，类型检查和生产构建通过；`git diff --check`，通过；前后端均未配置 lint，未运行。

### 问题与处理

* 回归测试发现 StrictMode 首次加载失效、首次启动失败无提示、重复 POST 和会话终态未关闭 WebSocket；已修复并增加对应行为测试。
* `npm audit` 报告 3 个既有开发依赖链 high 漏洞，来自 `js-yaml 4.3.0` 和 `nanoid 3.3.17`；`npm audit --omit=dev` 确认生产依赖 0 个漏洞，本切片未越界升级既有依赖。
* 切片八首轮回归发现 `VLM_REJECTED` 被计入高频风险、CAM-04 遗留整改提交、离线调查缺少引用导致 CAM-02 无法闭环；已分别修正统计口径、夹具状态和离线权威引用，并补充回归测试。
* 双轴审查发现 CAM-02 被错误强制进入补事实状态、流水线未发送状态事件、OpenAPI 类型未生成和项目命令说明过期；已逐项修正。首次契约生成因沙箱禁止访问本机端口失败，授权本机访问后同一命令成功。

### 后续计划

* 推送审查修正后的 `feat/case-pipeline`，交由项目负责人进行集成验收。

## 2026-08-16

### 当日目标

* 将案例 API 与分析流程接入 SQLAlchemy 仓储，保证分析会话先于案例持久化并支持进程内仓储重建后读取。
* 接入 5 个 RAG 权威来源的抽取语料与复核签核，并修复真实嵌入端点批量限制，使需求检索可返回权威引用。

### 开发记录

* 00:48 `fix(store): 接入SQL案例仓储运行时`
  * 完成：运行时案例仓储由内存实现切换为 `SqlAlchemyCaseStore`，正式启动不再预载案例夹具；分析任务启动前先持久化 `analysis_sessions`，消除案例外键失败。
  * 实现：新增数据库 URL 与 SQL 回显配置、FastAPI 数据库启动和释放生命周期、分析会话 SQL 保存适配器；保留站点上下文种子，并将案例 API 的 demo 数据改为显式测试依赖。
  * 验证：`cd backend && /home/thunder/workspace/Innovative\ Integrated\ Application\ Training/backend/.venv/bin/python -m pytest`，339 项通过、1 项跳过；`cd frontend && npm run build`，失败，当前 `node_modules` 缺少已声明的 `vitest` 与 `@testing-library/react` 等开发依赖；`git diff --check`，通过；后端未配置 lint 和类型检查，前端未配置 lint。

* 20:16 `fix(rag): 分批嵌入兼容单次请求上限`
  * 完成：OpenAI 兼容嵌入端点按批次发送文本，规避 DashScope 单次请求 input 不超过 20 条的 400 报错，使真实向量索引可正常构建。
  * 实现：`OpenAIEmbeddingClient.embed_documents` 按每批 20 条循环请求并拼接向量，复用懒加载 SDK 与维度回填逻辑。
  * 验证：`cd backend && .venv/bin/python scripts/check_rag_topk.py`，五类 PPE 查询返回真实权威引用；`git diff --check`，通过；后端未配置 lint 和类型检查，未运行。

* 20:22 `chore(rag): 权威来源清单接入抽取元数据与复核签核`
  * 完成：5 个权威来源清单接入抽取元数据并将 extraction_status 置为 ready、human_review_status 置为 reviewed，使 RAG 真实索引可读取完整语料。
  * 实现：补充 5 个来源的 local_path、parser_version 与 derived_text_sha256；GB 39800.1 文本经 OCR 与人工复核校正后重建。
  * 验证：`cd backend && .venv/bin/python scripts/check_rag_topk.py`，五类 PPE 查询命中正确条款；`cd backend && .venv/bin/python -m pytest`，335 项通过、5 项失败（环境原因，见问题与处理）；`git diff --check`，通过；后端未配置 lint 和类型检查，未运行。

* 20:48 `refactor(config): 站点上下文与用户目录改为配置驱动`
  * 完成：站点上下文与用户目录的演示数据全部迁入 JSON 配置，替换代码硬编码；视频路径、时长、场景时间、作业票时间窗与用户列表改为可配置。
  * 实现：新增 `users.json` 并让 `DemoUserDirectory` 从配置加载；扩展 `scene_assignments.json` 与 `_SceneAssignment`/`_SceneAssignments` 模型，`MemorySiteContext` 从配置读取视频与作业票字段；`fixture_candidates` 自持场景起始时间常量。
  * 验证：`cd backend && .venv/bin/python -m pytest`，335 项通过、5 项失败（环境原因，与本次无关）；`git diff --check`，通过；后端未配置 lint 和类型检查，未运行。

* 21:09 `fix(demo): 假分析分阶段延时避免前端错过完成事件`
  * 完成：修复点击「开始分析」后前端卡在「分析中」的问题；fixture 假分析由约 10ms 改为分阶段约 3 秒，使前端 WebSocket 在 SESSION_FINISHED 之前完成订阅。
  * 实现：`InMemoryVideoAnalysis.run_session` 在 STARTING/READING/INFERENCING 阶段间增加 `asyncio.sleep`，进度可视化且规避 EventHub live-only 不重放导致的竞态。
  * 验证：`cd backend && .venv/bin/python -m pytest tests/domain/test_video_analysis.py tests/services/test_session_manager_sql_persistence.py tests/services/test_case_pipeline.py`，13 项通过；实测 POST 会话到生成案例耗时 3.3s；`git diff --check`，通过；后端未配置 lint 和类型检查，未运行。

* 23:29 `feat(investigation): 案件流水线接入真实调查 agent`
  * 完成：案件流水线 `get_case_pipeline` 改用真实调查端口，运行时调查走真实 DeepSeek agent 与真实 RAG 检索，不再使用 fixture 调查。
  * 实现：`build_fixture_case_pipeline` 增加 `investigation` 注入参数，`get_case_pipeline` 传入 `get_investigation_port()`；补充 `requirements-ai.txt` 作为 AI 依赖安装入口（版本仍 single-source 在 pyproject.toml）。
  * 验证：运行时实测 `get_investigation_agent` 返回 `InvestigationAgent`、`get_case_pipeline()._investigation` 为 `InvestigationService`；`git diff --check`，通过；后端未配置 lint 和类型检查，未运行。

* 23:34 `test(investigation): 离线调查测试隔离与断言更新`
  * 完成：新增 conftest.py 强制测试走离线/确定性适配器，避免真实 DeepSeek/embedding 调用；更新受接线影响的两个断言。
  * 实现：conftest.py 置空 DEEPSEEK/EMBEDDING/VLM 相关 key；`test_analysis_sessions` 与 `test_end_to_end` 的 PENDING_REVIEW 断言改为 NEEDS_HUMAN_FACTS（测试环境离线 RAG 引用为空）。
  * 验证：`cd backend && .venv/bin/python -m pytest`，334 项通过、5 项失败（均为环境原因：.env 密钥、chromadb、AGENT_LLM_MODEL=deepseek-v4-pro，非本次回归）；`git diff --check`，通过；后端未配置 lint 和类型检查，未运行。

### 问题与处理

* 原案例 API 测试隐式依赖运行时预载 demo 案例；改为通过依赖覆盖显式注入内存仓储与对应流水线，避免测试夹具进入正式数据库。
* 前端构建失败与本次纯后端接线无关，未修改前端依赖或源码。
* 真实索引构建暴露三个环境问题：DashScope embedding 单次请求 input 上限 20 条，已分批修复；venv 缺少 `openai`、`chromadb`、`socksio`，已安装；后端 pytest 的 5 个失败均为环境原因——`.env` 含真实 VLM/Agent/Embedding 密钥导致配置默认值测试失败，安装 chromadb 后 `test_chroma_lazy` 的「依赖未安装」前提不再成立，均非本次改动回归。

### 后续计划

* 推送 `fix/case-store-runtime-wiring` 任务分支，交由项目负责人在 `dev` 集成验收。
* 推送 `chore/rag-authoritative-index` 任务分支，交由项目负责人在 `dev` 集成验收。
* 推送 `chore/site-context-config-driven` 任务分支，交由项目负责人在 `dev` 集成验收。

## 2026-08-17

### 当日目标

* 将实时视频推理接入后端分析会话，并确保停止会话能够结束正在运行的视频读取和推理。
* 按现有视频素材重编固定六路演示场景，并保持现有前端结构、接口和单 PPE 案件模型不变。
* 提供项目级 README，使新环境能够完成依赖安装、六路配置、服务启动和案件闭环演示。
* 接入真实 OpenAI 兼容多模态复核，使 YOLO 证据帧能够经 Qwen 严格复核后进入案件流水线。
* 补齐 Ultralytics 目标跟踪运行依赖，确保真实 YOLO 视频分析可以启动。
* 修复前端关键证据帧代理，使案件详情能够显示后端生成的证据图片。
* 将前端直接暴露的内部字段、枚举和演示素材名称转换为面向演示的中文表述。
* 支持现场安全员直接上传整改图片，并让审核人在复查区域查看完整整改提交信息。

### 开发记录

* 14:23 `fix(ml): 支持视频推理协作停止`
  * 完成：为视频推理迭代器增加外部停止信号，使停止分析会话后不再继续读取后续视频帧。
  * 实现：在每轮读取源视频前检查调用方提供的停止回调，并继续由原有清理路径关闭后台推理线程和视频捕获句柄。
  * 验证：`backend/.venv/bin/python -m pytest ml/tests/test_video_inference.py -q`，19 项测试通过；ML 全局 lint 和构建命令未配置，未运行。本切片未修改后端和前端，未运行后端完整测试和前端构建。
* 14:24 `docs(log): 更正视觉接线任务负责人`
  * 完成：将本任务开发记录从误写的成员日志移至任务负责人 Thunder 的日志。
  * 实现：删除 Wuweizhe 日志中本任务新增区块，并在 Thunder 日志保留真实提交与验证记录。
  * 验证：`git diff --check`，通过；本提交仅更正日志归属，未运行代码测试。
* 14:48 `feat(video-analysis): 接入真实视觉分析会话`
  * 完成：真实模式下由一次 YOLO 与 ByteTrack 视频推理同时驱动 MJPEG 标注流、PPE 候选聚合、案件流水线和实时事件；停止会话会等待推理线程释放。
  * 实现：增加配置驱动的真实/fixture 适配器选择、会话级候选聚合器、证据 JPEG 持久化与读取接口、模型权重哈希追踪，并将视觉处理异常映射为可重试的 `SESSION_FAILED`。
  * 验证：`cd backend && .venv/bin/python -m pytest tests/modules/video_analysis tests/services/test_session_manager.py tests/api/test_evidence_api.py tests/modules/investigation/test_config.py -q`，63 项测试通过；`cd backend && .venv/bin/python -m compileall -q app`，通过；`git diff --check`，通过；后端未配置 lint 和类型检查，未运行。
* 15:19 `test(rag): 隔离Chroma可选依赖测试`
  * 完成：消除 Chroma 懒加载测试对本机是否安装 `chromadb` 的隐式依赖，使缺失可选依赖的错误路径可稳定复现。
  * 实现：通过测试级导入替身显式触发 `ImportError`，继续断言适配器仅在实际连接时抛出 `ChromaDependencyUnavailable`。
  * 验证：`cd backend && .venv/bin/python -m pytest tests/modules/requirements_rag/test_chroma_lazy.py -q`，4 项通过；`cd backend && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest`，346 项通过、1 项真实 RAG 跳过；`backend/.venv/bin/python -m pytest ml/tests/test_video_inference.py -q`，19 项通过；`cd frontend && npm test`，42 项通过；`cd frontend && npm run build`，通过；`git diff --check`，通过。后端与前端未配置 lint，未运行。
* 16:11 `feat(demo): 按现有视频重编六路演示场景`
  * 完成：将演示固定为安全切割、无背心切割、无手套装订木板、无背心无手套攀爬、三类 PPE 均缺失的木料组装、多人混合穿戴六路；各路候选数固定为 0、1、1、2、3、7。
  * 实现：重配视频、区域、任务和 PPE 规则；夹具分析支持同一路视频生成多个工人和多项 PPE 候选，同一工人的候选共享人员轨迹，现有六路前端、API、数据库结构和单 PPE 案件模型保持不变。
  * 验证：`cd backend && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest tests/adapters/database/test_seed.py tests/api/test_demo_api.py tests/api/test_analysis_sessions.py tests/api/test_cases_api.py tests/domain/test_site_context.py tests/domain/test_video_analysis.py tests/domain/test_resolver.py tests/integration/test_end_to_end.py tests/modules/investigation/test_agent.py tests/modules/investigation/test_config.py tests/modules/investigation/test_fake.py tests/modules/investigation/test_service.py tests/modules/investigation/test_tools.py tests/services/test_session_manager_sql_persistence.py -q -k 'not test_agent_settings_defaults and not test_deepseek_key_selects_real_investigation_agent' --tb=short`，138 项通过、2 项因本地环境配置排除；`cd backend && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q -k 'not test_agent_settings_defaults and not test_deepseek_key_selects_real_investigation_agent and not test_rag_configuration_is_separate_from_vlm_configuration and not test_defaults_are_used_without_vlm_env'`，342 项通过、1 项跳过、4 项因本地环境配置排除；`PYTHONPATH=backend PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 backend/.venv/bin/python -m pytest backend/tests/modules/investigation/test_config.py::test_agent_settings_defaults backend/tests/modules/investigation/test_config.py::test_deepseek_key_selects_real_investigation_agent backend/tests/modules/requirements_rag/test_rag_config.py::test_rag_configuration_is_separate_from_vlm_configuration backend/tests/modules/vlm_review/test_config.py::test_defaults_are_used_without_vlm_env -q`，4 项通过；合计完整后端回归 346 项通过、1 项跳过；`backend/.venv/bin/python -m compileall -q backend/app`，通过；`cd frontend && npm run build`，通过；`git diff --check`，通过。后端未配置 lint 和类型检查，未运行。

* 16:29 `docs(readme): 补充项目安装与闭环演示说明`
  * 完成：新增项目级 README，覆盖六路场景、依赖安装、视频与模型准备、稳定演示和 CPU YOLO 配置、真实 RAG、前后端启动及人工闭环步骤。
  * 实现：以 `pyproject.toml` 的 `ai`、`vision`、`dev` 可选依赖为统一安装入口；明确真实索引查询仍需 Embedding API、媒体和权重不进入 Git，以及 fixture 与真实 YOLO 的结果边界。
  * 验证：`git diff --check`，通过；逐项检查 README 引用的仓库文件路径，均存在。项目未配置 Markdown lint；本提交仅修改文档，未运行代码测试、静态检查和构建。

* 17:28 `feat(vlm): 接入真实多模态复核`
  * 完成：新增 OpenAI 兼容多模态 VLM 适配器，并让案件流水线按 `VLM_PROVIDER` 在固定复核与真实复核之间选择；本地演示环境已启用 CPU YOLO 与 Qwen3.6。
  * 实现：仅允许读取证据根目录内的 JPEG，将证据帧按最大边限制缩放压缩后编码为 Base64；请求关闭 Qwen 思考模式并要求 JSON 对象，响应继续由现有严格解析器校验；密钥只从环境变量读取，错误按是否可重试分类。
  * 验证：`cd backend && .venv/bin/python -m pytest tests/modules/vlm_review tests/modules/video_analysis/test_runtime.py tests/services/test_case_pipeline.py -q`，48 项通过；`cd backend && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest tests/api/test_analysis_sessions.py -q`，9 项通过；`cd backend && .venv/bin/python -m compileall -q app`，通过；`cd backend && pip3 --python .venv/bin/python check`，无损坏依赖；`cd backend && .venv/bin/python -m build --wheel --no-isolation --outdir /tmp/siteppe-build`，构建成功；真实 Qwen3.6 图片调用返回并通过严格解析，CPU YOLO 使用 `best.pt` 单帧推理成功；`git diff --check`，通过。后端未配置 lint 和类型检查，未运行前端构建。

* 18:08 `fix(vision): 补充目标跟踪依赖`
  * 完成：修复真实 YOLO 视频分析启动时报 `No module named 'lap'`，并将缺失依赖纳入视觉环境安装清单。
  * 实现：为 `vision` 可选依赖显式加入 Ultralytics ByteTrack 所需的 `lap>=0.5.12,<1`，本地后端虚拟环境安装 `lap 0.5.13`。
  * 验证：`backend/.venv/bin/python -c "import lap; print(lap.__version__)"`，输出 0.5.13；真实 `YOLO.track()` 使用 `best.pt` 与演示视频单帧运行成功并识别 3 个目标；`backend/.venv/bin/python -m pytest ml/tests/test_video_inference.py -q`，19 项通过；`pip3 --python backend/.venv/bin/python check`，无损坏依赖；`cd backend && .venv/bin/python -m compileall -q app`，通过；`cd backend && .venv/bin/python -m build --wheel --no-isolation --outdir /tmp/siteppe-lap-build`，构建成功；未运行三百余项全量后端测试，原因是本次仅补充跟踪运行依赖并已完成针对性真实推理验证；后端未配置 lint 和类型检查，未运行。

* 18:16 `fix(frontend): 修复关键证据帧代理`
  * 完成：修复案件详情中全部关键证据帧无法显示的问题，前端开发服务器现在会将 `/evidence` 图片请求转发到后端。
  * 实现：Vite 增加 `/evidence` 代理；开发、测试和构建脚本显式指定 `vite.config.ts`，避免被本地遗留且已忽略的 `vite.config.js` 覆盖；新增代理配置回归测试。
  * 验证：`cd frontend && npm test`，43 项通过；`cd frontend && npm run build`，构建成功；临时启动修复后的前端后请求真实证据地址，返回 `200 image/jpeg`、395167 字节；项目未配置独立 lint，未运行。

* 18:53 `fix(frontend): 增加中文展示映射`
  * 完成：建立面向演示的统一中文展示词汇，将作业代码、调查字段、冲突原因、工具名称、模型结论及六路素材派生名称转换为可读文案。
  * 实现：集中维护任务、机位、区域、视频场景、调查字段、规则冲突、调查工具、VLM 结论和模型来源的格式化函数；未知内部值使用保守的通用文案，不直接暴露字段名。
  * 验证：`cd frontend && npm test -- src/features/cases/format.test.ts`，4 项通过；`cd frontend && npm run build`，构建成功；项目未配置独立 lint，未运行。
* 19:04 `fix(frontend): 接入演示友好文案`
  * 完成：监控台、案件中心、案件详情和人工操作区域不再直接展示后端字段、枚举、模型标识、责任主体 ID 或演示视频文件派生名称。
  * 实现：六路机位与区域统一显示业务名称；案件状态、作业、调查事实、冲突、工具、模型结论及时间线均转换为中文表述；事实补充改为中文作业下拉框，完整案件 ID 仅保留为辅助标题信息。
  * 验证：`cd frontend && npm test`，12 个测试文件共 49 项通过；`cd frontend && npm run build`，构建成功；`node /home/thunder/.agents/skills/impeccable/scripts/detect.mjs --json frontend/src/features/cases/format.ts frontend/src/features/cases/CaseCenterPage.tsx frontend/src/features/cases/CasesWorkspace.tsx frontend/src/features/monitor/ChannelCard.tsx frontend/src/features/review/CaseActionPanel.tsx frontend/src/features/review/CaseDetailPage.tsx`，未发现问题；项目未配置独立 lint，未运行。
* 20:16 `fix(vlm): 阻止语义矛盾复核入库`
  * 完成：修复“理由确认未佩戴防护装备，但结论却排除违规”的语义矛盾；矛盾结果不会进入案件状态机，重试耗尽时保持候选待复核状态。
  * 实现：统一 `CONFIRMED`、`REJECTED`、`UNCERTAIN` 的违规语义、人员关联含义、证据充分性和理由前缀；真实模型提示明确人员框不是防护装备框；解析层校验结论、关联、证据标记与理由一致性，并在重试提示中反馈具体语义错误；固定适配器同步将证据不足归为 `UNCERTAIN`。
  * 验证：`cd backend && .venv/bin/python -m pytest tests/modules/vlm_review tests/services/test_case_pipeline.py tests/modules/video_analysis/test_runtime.py -q`，54 项通过；`cd backend && .venv/bin/python -m compileall -q app`，通过；`cd backend && pip3 --python .venv/bin/python check`，无损坏依赖；`cd backend && .venv/bin/python -m build --wheel --no-isolation --outdir /tmp/siteppe-vlm-semantics-build`，构建成功；`cd backend && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest tests/api/test_analysis_sessions.py tests/integration/test_end_to_end.py -q` 输出 10 个通过标记但未返回最终汇总和退出码，未计为通过；后端未配置独立 lint 和类型检查，未运行。
* 20:26 `fix(vlm): 校验复核理由语义方向`
  * 完成：阻止模型通过正确结论前缀包装相反理由正文；“排除违规”不能再描述未佩戴、裸露或装备缺失，“确认违规”不能描述装备已经佩戴。
  * 实现：为三类结论规定可机器校验的理由开头，继续保留后续中文说明；解析层检查理由正文的装备缺失与佩戴方向，真实提示禁止双重否定并要求正文不得反转开头结论；固定适配器同步输出相同格式。
  * 验证：`cd backend && .venv/bin/python -m pytest tests/modules/vlm_review tests/services/test_case_pipeline.py tests/modules/video_analysis/test_runtime.py -q`，57 项通过；`cd backend && .venv/bin/python -m compileall -q app`，通过；`cd backend && .venv/bin/python -m build --wheel --no-isolation --outdir /tmp/siteppe-vlm-reason-semantics-build`，构建成功；真实 CAM-04 复核返回 `CONFIRMED`、`MATCHED`、证据充分及“确认违规：目标装备缺失；”，未再产生反向结论；后端未配置独立 lint 和类型检查，未运行。
* 20:52 `fix(agent): 强制DeepSeek结构化输出`
  * 完成：调查 Agent 按 DeepSeek 官方 JSON Output 要求返回严格 JSON，非 JSON 最终回答会携带固定结构自动纠正后重试。
  * 实现：DeepSeek 请求启用 `response_format=json_object`、1024 Token 输出上限和显式 strict 工具定义；调查提示包含完整 JSON 字段示例，解析失败最多自动纠正两次。
  * 验证：`backend/.venv/bin/python -m pytest backend/tests/modules/investigation backend/tests/services/test_case_pipeline.py -q`，72 项通过；`backend/.venv/bin/python -m compileall -q backend/app`，通过；`pip --python backend/.venv/bin/python check`，无损坏依赖；`backend/.venv/bin/python -m build backend --wheel --no-isolation --outdir /tmp/siteppe-agent-json-build`，构建成功；真实 DeepSeek 合成调查完成责任人与 RAG 工具调用，并返回可解析的建议、整改责任人、期限和法规引用；`git diff --check`，通过；后端未配置独立 lint 和类型检查，未运行。
* 20:58 `fix(agent): 防止调查异常遗留中间状态`
  * 完成：DeepSeek 请求、输出或工具调用失败时，案件不再停留于假的“调查中”，分析会话会明确返回可重试失败。
  * 实现：首次调查改为 Agent 成功后再连续写入启动与结果迁移；DeepSeek 传输异常统一转换为调查域错误，会话管理器发布 `INVESTIGATION_PROCESSING_FAILED`。已处于旧 `INVESTIGATING` 状态的案件仍可通过原候选证据恢复调查。
  * 验证：`backend/.venv/bin/python -m pytest backend/tests/modules/investigation backend/tests/services/test_case_pipeline.py backend/tests/services/test_session_manager.py backend/tests/modules/video_analysis/test_video_analysis.py -q`，86 项通过；`backend/.venv/bin/python -m compileall -q backend/app`，通过；`pip --python backend/.venv/bin/python check`，无损坏依赖；`backend/.venv/bin/python -m build backend --wheel --no-isolation --outdir /tmp/siteppe-agent-failure-build`，构建成功；`git diff --check`，通过；后端未配置独立 lint 和类型检查，未运行。
* 22:13 `feat(rectification): 支持整改图片上传与审核展示`
  * 完成：现场安全员可选择本地 JPEG、PNG 或 WebP 图片作为整改证据；审核人在复查操作区直接查看提交人、时间、理由、整改说明和证据图片，人工提交历史同步展示图片。
  * 实现：新增带角色、案件状态、5 MB 大小、媒体类型与文件签名校验的同源图片上传和读取接口；图片原子写入证据目录并返回稳定地址；详情页在角色切换和窗口重新聚焦时重新读取最新案件。
  * 验证：`cd backend && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q tests/modules/video_analysis/test_evidence_store.py tests/api/test_evidence_api.py tests/api/test_cases_api.py`，33 项通过；`cd backend && .venv/bin/python -m compileall -q app`，通过；`cd frontend && npm test`，12 个测试文件共 52 项通过；`cd frontend && npm run build`，构建成功；`git diff --check`，通过；后端与前端未配置独立 lint，未运行。

### 问题与处理

* 首次提交时错误按模块归属推断负责人并写入 Wuweizhe 日志；任务负责人已明确为 Thunder，本提交完成更正。首次提交已推送，遵守禁止改写共享历史要求，未执行 amend 或强制推送。
* 当前后端虚拟环境的 `asyncio` 默认线程池即使执行空函数也无法退出；真实视觉适配器改用会话受控线程并通过停止回归测试，避免会话和测试进程被默认线程池阻塞。
* 当前虚拟环境自动加载第三方 pytest 插件后会使分析会话集成测试中的 AnyIO 工作线程挂起；禁用非项目所需插件后完整回归通过。原 Chroma 测试还错误假设可选依赖未安装，已改为显式模拟缺失依赖。
* 本地 `backend/.env` 会覆盖默认配置并干扰 4 项配置测试；在仓库根目录隔离该环境后补跑，4 项均通过，未修改或提交本地环境文件。
* 前端首次构建因本地缺少已声明的开发依赖失败；执行 `cd frontend && npm ci --include=dev` 后构建通过。安装过程报告 3 个 high 级依赖审计问题，本切片未执行可能改变依赖版本的自动修复。
* 此前当前机器没有 `/data/demo`；用户完成演示视频放置与目录链接后，已使用其中视频执行真实 YOLO 单帧推理和跟踪验证。
* 后端虚拟环境缺少内置 `pip` 与 `ensurepip`；改用系统 `pip3 --python .venv/bin/python` 安装声明依赖，并先从 PyTorch 官方 CPU 源安装 CPU 版本，避免下载无用的 CUDA 组件。依赖检查无损坏项。
* Python SDK 首次受沙箱代理权限限制而超时；用户明确同意发送本地演示证据帧后，以获准网络权限完成真实调用。本地 `.env` 启用真实 YOLO 后曾使离线 MJPEG 测试误走真实推理；测试会话显式固定 `VISION_PROVIDER=fixture` 后 9 项 API 测试全部通过。
* Ultralytics 的基础依赖不包含 ByteTrack 所需的 `lap`，真实视频分析首次调用 `model.track()` 时触发模块缺失；已安装依赖并在项目 `vision` 可选依赖中显式声明，避免新环境再次遗漏。
* 前端目录遗留的忽略文件 `vite.config.js` 被 Vite 优先加载，且其中没有 `/evidence` 代理，导致图片请求返回前端 HTML；各脚本已显式指定 TypeScript 配置并补充证据代理，真实请求验证通过。
* 分析接口与端到端测试完成 10 个用例后未正常退出，未获得可核验的 pytest 汇总与退出码；本次以 VLM、案件流水线和视觉运行时 54 项明确通过的针对性测试作为提交门禁，不声称该组合测试通过。
* 首次真实复跑误连到 18:10 启动且未热更新的宿主旧后端，产生 8 个旧语义案件；停止旧进程并精确清理该会话后，改为仅监听 `127.0.0.1` 的当前代码完成复验。第一层修复仍允许模型用正确前缀包装相反正文，已由第二层理由方向校验阻断。复验停止时真实调查 Agent 另有一次非 JSON 输出错误，本次未扩展到调查模块。
* DeepSeek JSON 模式与工具调用组合时，LangChain 不会为已是 OpenAI 格式的工具字典自动补入 `strict: true`；适配器改为显式标记每个函数工具后，真实调用通过。虚拟环境缺少内置 `pip`，依赖检查改用系统 `pip --python backend/.venv/bin/python check` 完成。
* 本地数据库存在 3 个旧 `INVESTIGATING` 案件，已备份至 `/tmp/siteppe-before-agent-recovery-20260817-205600.db`；恢复操作需将这 3 个具体案件的作业、风险与 PPE 上下文发送给 DeepSeek，当前受数据外发授权拦截，未写回数据库。

### 后续计划

* 将 `feat/real-vision-wiring` 合并到 `dev`；配置本地模型权重与演示视频后执行真实推理冒烟验证。
* 在演示环境将六个约定视频挂载到 `/data/demo` 后，执行六路播放与案件数量冒烟验收。
* 启动前后端，用真实 CPU YOLO、Qwen VLM、RAG 与调查 Agent 执行一次案件人工整改闭环演示。
* 使用真实整改照片完成一次安全员上传、审核人查看并关闭案件的浏览器验收。

## 2026-08-18

### 当日目标

* 让六路监控默认持续播放，同时保持点击开始后一次只分析一路。
* 将项目 README 收敛为面向使用者的功能介绍和操作指南。
* 支持六路 CAM 在服务运行期间配置场地及三类 PPE 要求。
* 修复新建案件固定显示 8 月 7 日的问题，使候选与案件创建时间遵从系统时间。
* 降低安全帽漏报，使连续未检测到安全帽的人员进入 VLM 复核。
* 移除前端对 YOLO 候选置信度的展示，避免将其误解为装备本身的置信度。
* 按业务处理责任分类事件，并将现场安全员列表限制为待提交整改证据事件。
* 明确 VLM 对安全帽、手套和安全背心的视觉判定边界，降低错误排除违规。
* 关闭千问视觉思考模式，恢复稳定的非思考复核调用。

### 开发记录

* 00:41 `feat(monitor): 支持六路视频实时循环播放`
  * 完成：六路监控卡片在未分析时自动静音循环播放；选中通道继续切换到现有实时标注流，其余通道不中断播放。
  * 实现：仅调整通道卡片的视频播放属性与状态文案，保留单活动会话、点击启动和切换确认逻辑。
  * 验证：`cd frontend && npm test -- --run src/features/monitor/ChannelCard.test.tsx`，2 项通过；`cd frontend && npm test`，12 个测试文件共 52 项通过；`cd frontend && npm run build`，构建成功；项目未配置独立 lint，未运行。
* 12:10 `docs(readme): 聚焦项目功能与使用方法`
  * 完成：README 改为介绍核心功能、六路场景、快速启动和人工闭环用法，删除架构、接口、数据库、依赖分组和测试命令等开发细节。
  * 实现：保留运行所需的视频、模型、密钥配置和双终端启动步骤，并将整改流程更新为直接上传整改照片。
  * 验证：`git diff --check`，通过；`test -f backend/.env.example && test -f frontend/package.json && test -d data/demo && test -f best.pt`，引用的本地路径均存在；项目未配置 Markdown lint，本提交仅修改文档，未运行代码测试和构建。
* 13:01 `feat(rules): 支持运行期场地PPE配置`
  * 完成：新增六路 CAM 场地配置读取与更新接口，支持选择中文预制场地或自定义场地名称及安全帽、手套、安全背心要求；配置仅保存在当前服务内存中。
  * 实现：运行期上下文原子更新对应 CAM 的作业许可与 PPE 矩阵，调查解析器继续通过原有接口读取最新规则；接口通过区分预制与自定义的请求结构限制输入，不向前端暴露内部任务代码。
  * 验证：`cd backend && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest tests/domain/test_site_context.py tests/domain/test_resolver.py tests/api/test_demo_api.py -q`，39 项通过；`cd backend && .venv/bin/python -m compileall -q app`，通过；`cd backend && .venv/bin/python -m build --wheel --no-isolation --outdir /tmp/siteppe-camera-rules-backend`，构建成功；后端未配置独立 lint 和类型检查，未运行。
* 13:08 `feat(frontend): 增加场地配置表单`
  * 完成：新增六路 CAM 场地配置弹窗，可选择中文预制场地，或填写自定义场地名称并勾选安全帽、防护手套和安全背心要求；分析期间表单不可保存。
  * 实现：增加类型化场地配置读取与更新客户端；通道列表和编辑表单分离，使用现有监控台颜色、间距与响应式布局，并提供键盘可访问的原生表单控件及明确的保存状态。
  * 验证：`cd frontend && npm test -- --run src/features/monitor/WorksiteConfigurationDialog.test.tsx src/shared/api.test.ts`，2 个测试文件共 7 项通过；`cd frontend && npm run build`，构建成功；项目未配置独立 lint，未运行。
* 13:14 `feat(monitor): 接入六路场地规则配置`
  * 完成：监控台顶部以配置按钮替换角色切换，案件中心保留角色选择；六路监控卡片以中文展示当前场地和 PPE 要求，保存配置后立即更新。
  * 实现：监控页并行加载视频与运行期场地配置，通过配置接口写回指定 CAM；分析启动或运行期间禁止保存配置，避免当前推理规则中途变化。
  * 验证：`cd frontend && npm test`，13 个测试文件共 56 项通过；`cd frontend && npm test -- --run src/App.test.tsx src/features/monitor/ChannelCard.test.tsx src/features/monitor/MonitorPage.test.tsx`，3 个测试文件共 17 项通过；`cd frontend && npm run build`，构建成功；`PYTHONPATH=backend PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 backend/.venv/bin/python -m pytest backend/tests -q`，382 项通过、1 项跳过、1 项因既有相对路径依赖运行目录而失败；`cd backend && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest tests/modules/requirements_rag/test_acceptance_regressions.py::test_shipped_manifest_loads_with_real_provenance_metadata -q`，该项在后端目录重跑通过；项目未配置独立 lint，未运行。
* 13:43 `fix(frontend): 移除配置重启提示`
  * 完成：删除场地配置页面中后端重启后恢复默认的提示文字，仅保留配置操作说明。
  * 实现：收敛配置弹窗说明文案，并增加该提示不再显示的组件回归断言。
  * 验证：`cd frontend && npm test`，13 个测试文件共 56 项通过；`cd frontend && npm run build`，构建成功；项目未配置独立 lint，未运行。
* 17:09 `fix(events): 使用系统时间创建案件`
  * 完成：新分析会话产生的候选发生时间和案件创建时间不再继承固定的 2026 年 8 月 7 日；真实 YOLO 与 fixture 路径使用同一系统时间语义。
  * 实现：分析会话记录带时区的启动时间，候选以会话启动时间叠加视频位置，案件通过注入时钟记录实际创建时间；演示作业许可证按事件日期重建当天 08:00—18:00 时间窗，保持 resolver 规则有效。
  * 验证：`cd backend && env VISION_PROVIDER=fixture VLM_PROVIDER=fixed DEEPSEEK_API_KEY= EMBEDDING_API_KEY= EMBEDDING_BASE_URL= VLM_API_KEY= VLM_API_BASE_URL= .venv/bin/pytest -q tests/services/test_case_pipeline.py tests/services/test_session_manager.py tests/services/test_session_manager_sql_persistence.py tests/modules/video_analysis/test_runtime.py tests/modules/video_analysis/test_video_analysis.py tests/domain/test_site_context.py tests/domain/test_video_analysis.py`，49 项通过；`cd backend && timeout 15s env VISION_PROVIDER=fixture VLM_PROVIDER=fixed DEEPSEEK_API_KEY= EMBEDDING_API_KEY= EMBEDDING_BASE_URL= VLM_API_KEY= VLM_API_BASE_URL= .venv/bin/pytest -q tests/integration/test_end_to_end.py::test_new_demo_case_uses_system_time_and_current_permit`，1 项通过；`cd backend && .venv/bin/python -m compileall -q app`，通过；`cd backend && .venv/bin/python -m build --wheel --no-isolation --outdir /tmp/siteppe-event-time-build-29baXn`，构建成功；`git diff --check`，通过；后端未配置独立 lint 和类型检查，未运行。
* 18:49 `fix(events): 修复系统时间边界与测试阻塞`
  * 完成：修复晚于 18:00 分析演示视频时作业许可证失效的问题，并解除后端 ASGI 测试在同步依赖处的阻塞。
  * 实现：案件创建时间继续使用系统当前时间，候选发生时间保留录制场景时刻并同步到分析当天；测试入口在支持的平台使用项目已有 uvloop，并禁止本地 `.env` 改写离线测试配置。
  * 验证：`cd backend && .venv/bin/pytest -q`，388 项通过、1 项跳过；`cd backend && .venv/bin/python -m compileall -q app`，通过；`cd backend && .venv/bin/python -m build --wheel --no-isolation --outdir /tmp/siteppe-event-time-final-build`，构建成功；`git diff --check`，通过；后端未配置独立 lint 和类型检查，未运行。
* 19:12 `feat(vision): 支持安全帽持续缺失候选`
  * 完成：可评估人员连续未检测到安全帽时生成缺失正类关联候选并进入 VLM 复核，同时保留连续 `no_helmet` 检测形成强负类证据的原有路径。
  * 实现：安全帽采用与手套、背心一致的连续缺失聚合；全序列均有合格 `no_helmet` 时保存检测框及其置信度，纯缺失或混合序列使用人员置信度并生成无装备框的三帧证据；检测到 `helmet` 会重置缺失序列。
  * 验证：`cd backend && .venv/bin/python -m pytest -q tests/modules/video_analysis tests/modules/vlm_review tests/services/test_case_pipeline.py tests/services/test_session_manager.py`，105 项通过；`cd backend && .venv/bin/python -m pytest -q`，391 项通过、1 项跳过；`cd backend && .venv/bin/python -m compileall -q app`，通过；`cd backend && pip3 --python .venv/bin/python check`，无损坏依赖；`cd backend && .venv/bin/python -m build --wheel --no-isolation --outdir /tmp/siteppe-helmet-missing.dSMZta`，构建成功；`git diff --check`，通过；后端未配置独立 lint 和类型检查，前端未修改，未运行前端检查。
* 20:14 `fix(frontend): 移除YOLO置信度展示`
  * 完成：事件详情不再展示候选置信度，关键证据帧不再展示观测置信度，避免将 YOLO 检测分数解释为装备本身的可信程度。
  * 实现：保留候选与证据帧的置信度数据契约，仅删除前端可见条目，并将事件摘要和证据说明布局调整为删除后的项目数量。
  * 验证：`cd frontend && npm test -- src/features/review/CaseDetailPage.test.tsx`，3 项通过；`cd frontend && npm test`，13 个测试文件共 57 项通过；`cd frontend && npm run build`，类型检查与生产构建通过；`git diff --check`，通过；项目未配置独立 lint，未运行。
* 20:38 `feat(cases): 按处理责任分类事件队列`
  * 完成：事件列表删除处理状态筛选，按待补现场事实、待项目审核、待提交整改证据、待项目复查、已逾期、系统分析中和已关闭七类展示；现场安全员只看到待提交整改证据的事件。
  * 实现：建立完整的案件状态到业务分类映射，逾期事件优先进入独立分类且不重复展示；列表请求按当前角色限制状态，安全员摘要同步收敛为整改证据与当前页逾期数量。
  * 验证：`cd frontend && npm test -- src/features/cases/CaseCenterPage.test.tsx`，2 项通过；`cd frontend && npm test`，14 个测试文件共 59 项通过；`cd frontend && npm run build`，类型检查与生产构建通过；`git diff --check`，通过；项目未配置独立 lint，当前环境未提供浏览器调试接口，未执行真实浏览器视觉验收。
* 21:03 `fix(vlm): 补充PPE复核判定规则`
  * 完成：明确安全帽、防护手套和安全背心的佩戴判定边界，荧光色普通上衣、安全带和工具带不再作为安全背心依据。
  * 实现：要求模型忽略检测框及类别文字，至少两帧清楚显示正确佩戴才可排除违规；目标部位过小、模糊、遮挡或无法跨帧确认时返回不确定。
  * 验证：`cd backend && .venv/bin/pytest tests/modules/vlm_review/test_openai_compat_adapter.py -q`，7 项通过；`cd backend && .venv/bin/python -m compileall -q app`，通过；`cd backend && .venv/bin/python -m build --wheel --no-isolation --outdir /tmp/siteppe-vlm-prompt-build`，构建成功；后端未配置独立 lint 和类型检查，未运行。
* 21:05 `fix(vlm): 开启千问视觉思考模式`
  * 完成：真实千问 VLM 请求开启思考模式，使 PPE 复核能够执行更充分的视觉推理。
  * 实现：将千问兼容请求的 `enable_thinking` 固定为 `true`，其他模型请求参数与输出解析保持不变。
  * 验证：`cd backend && .venv/bin/pytest tests/modules/vlm_review -q`，48 项通过；`cd backend && .venv/bin/python -m compileall -q app`，通过；`cd backend && .venv/bin/python -m build --wheel --no-isolation --outdir /tmp/siteppe-vlm-thinking-build`，构建成功；后端未配置独立 lint 和类型检查，未运行。
* 22:46 `fix(vlm): 关闭千问视觉思考模式`
  * 完成：关闭真实千问 VLM 的思考模式，避免复核持续失败并恢复非思考调用。
  * 实现：千问兼容请求明确发送 `enable_thinking=false`，移除思考预算参数；保留 90 秒超时和 2048 Token 输出空间。
  * 验证：`cd backend && .venv/bin/pytest tests/modules/vlm_review -q`，48 项通过；`cd backend && .venv/bin/python -m compileall -q app tests`，通过；`cd backend && .venv/bin/python -m build --no-isolation --outdir /tmp/siteppe-vlm-no-thinking-build`，构建成功；全量后端测试运行至约 35% 时执行环境未返回退出码，未计为通过；后端未配置独立 lint 和类型检查，未运行。

### 问题与处理

* 当前环境未提供可用的浏览器调试接口，未执行真实浏览器播放验收；已通过组件测试校验自动播放、循环、静音与内联播放属性。
* 本地 `backend/.env` 中的真实 DeepSeek 密钥和模型覆盖了默认值，导致两项既有默认配置测试失败；本切片未修改本地配置，排除这两项后相关规则、接口和调查解析测试全部通过。
* 后端完整测试从仓库根目录运行时，一项既有 RAG 验收测试使用了相对 `app/` 路径而失败；切换到 `backend` 目录单独重跑后通过。
* ASGI 同步依赖测试阻塞可在未修改的 `origin/dev` 基线上复现，排除系统时间功能引入；测试入口启用项目已有 uvloop 后完整后端测试通过。
* 当前环境未提供可用的浏览器调试接口，本次事件分类改动未执行真实浏览器视觉验收；已通过组件测试和生产构建验证结构、角色过滤与响应式样式编译。
* 本次全量后端测试运行至约 35% 时执行环境提前结束且未返回退出码；VLM 模块 48 项测试和后端构建均已通过。

### 后续计划

* 在演示浏览器中确认六路视频同时循环播放，并点击任一路验证仅该路切换为分析标注流。
* 在 `dev` 集成环境新建一个案件，确认列表与详情显示当前系统日期；历史案件保留原始时间不回填。
