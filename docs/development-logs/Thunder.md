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
