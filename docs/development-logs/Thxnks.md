# Thxnks 开发日志

## 2026-08-09

### 当日目标

* 建立可初始化的 SQLite 数据结构，并写入与共享业务上下文一致的六路确定性演示数据。

### 开发记录

* 22:34 `feat(database): 建立SitePPE数据库模型`
  * 完成：建立业务上下文、分析会话、整改事件、机器处理链和人工审计所需的 SQLAlchemy 数据模型。
  * 实现：为 SQLite 启用外键约束，使用带时区 ISO 时间类型保留业务时间，并为候选到事件的一对一关系增加唯一约束。
  * 验证：`.venv\Scripts\python.exe -m pytest tests/adapters/database/test_models.py -q`，3 项测试通过。
* 22:36 `feat(seed): 添加六路确定性演示数据`
  * 完成：提供可重复执行的 SQLite 初始化入口，写入六路区域、摄像头、视频、许可、任务矩阵、责任主体和演示用户。
  * 实现：复用冻结的内存业务上下文生成数据库种子，保留 CAM-01 无许可、CAM-03/04 手套要求差异和 CAM-06 无额外 PPE 的演示语义。
  * 验证：`.venv\Scripts\python.exe -m app.adapters.database.seed --database-url sqlite:///:memory:`，成功生成 6 路上下文；`.venv\Scripts\python.exe -m pytest`，167 项通过、1 项因需要真实 RAG 凭据跳过。
* 22:39 `fix(database): 统一SQLite时间比较语义`
  * 完成：修复不同时区偏移的 ISO 时间文本无法可靠排序的问题。
  * 实现：所有带时区时间在写入 SQLite 前统一转换为 UTC，读取后仍返回带时区 `datetime`。
  * 验证：`.venv\Scripts\python.exe -m pytest tests/adapters/database -q`，7 项测试通过；`.venv\Scripts\python.exe -m pytest`，167 项通过、1 项因需要真实 RAG 凭据跳过。

### 问题与处理

* 系统未配置 `python` 命令，标准命令 `python -m pytest` 无法启动；已在项目忽略的 `.venv` 中使用工作区 Python 安装仓库声明的开发依赖，并用该环境执行测试。

### 后续计划

* 等待 X-01 验收；通过后实现 SQLAlchemy `CaseStore` 和事务测试。

## 2026-08-12

### 当日目标

* 补齐 X-01 初始数据库 schema 的映射、约束、失败路径和事务评审项，使其具备合入 `dev` 后冻结的条件。

### 开发记录

* 00:42 `fix(database): 补齐初始Schema评审项`
  * 完成：在不增加表和字段的前提下补齐调查结果持久化往返、数据库写入校验、种子失败路径和事务回滚覆盖。
  * 实现：使用结构化 JSON 容器隔离人工事实与确定性 resolver 结果；为分析会话状态、证据帧角色和引用生效日期增加领域校验；明确初始化、事务和异常传播边界。
  * 验证：`.venv\Scripts\python.exe -m pytest tests/adapters/database -q`，15 项通过；`.venv\Scripts\python.exe -m pytest`，175 项通过、1 项因需要真实 RAG 凭据跳过；`git diff --check`，通过。项目未配置后端 lint 和类型检查命令，未运行。
* 00:57 `fix(database): 对齐共享契约字段约束`
  * 完成：消除数据库层对引用生效日期的额外格式限制，并将分析会话状态统一到共享 `AnalysisStage`。
  * 实现：保留 `Citation.effective_date` 的原文字符串语义，删除自定义会话终态枚举，直接复用共享契约的阶段类型和精确枚举值。
  * 验证：`.venv\Scripts\python.exe -m pytest tests/adapters/database -q`，14 项通过；`.venv\Scripts\python.exe -m pytest`，174 项通过、1 项因需要真实 RAG 凭据跳过；`git diff --check`，通过。项目未配置后端 lint 和类型检查命令，未运行。

### 问题与处理

* 调查结果包含现有专列未覆盖的确定性字段；使用 `facts_json` 内的命名容器保存，避免增加字段且避免人工事实覆盖 `required_ppe`。首次往返测试因多层外键对象一次性 flush 顺序失败，改为按依赖层显式 flush 后通过。
* 代码复审发现日期格式和会话终态枚举收紧了共享契约；按契约权威顺序移除额外限制，并使用中文生效日期原文完成数据库往返验证。

### 后续计划

* 推送 X-01 补充提交并交由项目负责人评审；合入 `dev` 并冻结 schema 后，从最新 `dev` 开始 X-02 `CaseStore`。

## 2026-08-14

### 当日目标

* 增强 X-01 数据唯一约束，并跳过 X-02 完成 X-03 事件中心与 X-04 事件详情，供项目负责人联调。

### 开发记录

* 11:32 `fix(database): 增强调查与证据唯一约束`
  * 完成：限制每个案件仅保存一份当前调查快照，并禁止同一案件出现重复时间戳的证据帧。
  * 实现：使用数据库唯一约束替换仅提供查询优化的普通索引，并增加 schema 反射回归测试。
  * 验证：`D:\24269\coding\Summer-projects\backend\.venv\Scripts\python.exe -m pytest tests/adapters/database/test_models.py -q`，6 项通过；`D:\24269\coding\Summer-projects\backend\.venv\Scripts\python.exe -m pytest`，174 项通过、1 项因需要真实 RAG 凭据跳过；`git diff --check`，通过。
* 12:24 `feat(frontend): 实现事件中心与详情闭环`
  * 完成：实现事件统计、URL 筛选、分页、列表页面状态、证据链、VLM 与调查结果、引用、人工历史、时间线及按角色展示的业务命令表单。
  * 实现：提供 `CasesWorkspace` 独立挂载入口，使用 REST 快照刷新和版本冲突重载；视觉采用低动效、中高密度、深色矿物底与单一警示金色，避免渐变光效和嵌套卡片。
  * 验证：`npm.cmd run build`，通过；Playwright 使用真实 fixture 在 1440×1000 与 390×844 视口检查列表、详情、角色切换及审核/整改表单，通过；`git diff --check`，通过。

### 问题与处理

* 当前主工作区包含其他任务的未提交修改；数据库与前端均使用独立 worktree，未暂存或改动这些文件。
* 最新 `dev` 尚未包含 Thxnks 日志，因此从已推送的 X-01 分支同步真实历史记录后追加本次前端记录；未补造开发日期。
* fixture 证据图片 URL 当前不可访问；详情页保留帧元数据并提供明确的失败和重试状态，未用虚假图片替代。

### 后续计划

* 由 Thunder 在 `frontend/src/App.tsx` 挂载 `CasesWorkspace` 并完成监控台与事件页面整合。
