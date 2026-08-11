# Mandatory project instructions

These instructions apply to every request and every turn in this Codex session.

- Before responding or modifying files, check these instructions.
- Before finishing, verify that all applicable instructions were followed.

## 任务工作流

### 启动检查

开始任务前执行：

```bash
git status --short
git branch --show-current
```

* 识别当前分支和工作区中的已有修改。
* 将已有修改区分为“当前任务改动”和“无关改动”。
* 保留所有无关改动，并禁止清理、覆盖、暂存或提交这些改动。
* 开始编码前确认任务负责人、任务目标、验收条件和预计修改路径。

### 创建任务分支

* 每个线下分配的任务使用一个独立的短期任务分支。
* `dev` 是团队集成测试分支，`main` 是测试通过后的稳定发布分支。
* 禁止直接在 `dev` 或 `main` 上开发。
* 从最新的远程 `dev` 创建任务分支。

依次执行：

```bash
git fetch origin
git switch dev
git pull --ff-only origin dev
git switch -c <type>/<slug>
```

* 创建任务分支前确认 `origin/dev` 已存在。
* `origin/dev` 不存在时停止创建任务分支，并联系项目负责人从最新的 `main` 初始化 `dev`。
* 根据任务类型使用 `feat`、`fix` 或 `chore` 作为 `<type>`。
* 使用简短的小写英文和连字符编写 `<slug>`。
* 创建或切换分支前确认工作区没有未提交修改。
* 工作区存在无关修改时停止切换分支，并联系相关成员处理。
* 禁止使用 `git stash` 隐藏或搬运无法确认归属的修改。
* 分支名称采用下列格式：

```text
feat/<slug>
fix/<slug>
chore/<slug>
```

根据任务内容选择分支类型：

| 任务内容 | 分支类型 |
| -------- | -------- |
| 增加或扩展功能 | `feat/<slug>` |
| 修复错误或回归 | `fix/<slug>` |
| 仅修改测试、重构、文档或维护配置 | `chore/<slug>` |

### 控制范围与协作

* 严格限制修改范围，只处理当前任务要求的内容。
* 禁止顺手重构、格式化、移动或重命名无关代码。
* 发现当前任务与队友修改同一公共接口、数据表或文件时，先同步分工，再继续修改。
* 已冻结的共享契约、状态枚举和数据库 schema 默认保持不变；只有当前任务明确要求修正契约差距时才允许修改。
* 经明确授权的共享接口变更必须先对齐共享契约，作为独立 commit 提交并推送，再通知依赖方开始实现。
* 初始数据库 schema 评审合入 `dev` 后按 D-09 冻结；本轮禁止继续增加表或数据库迁移。
* 按固定范围分工：Wuweizhe 负责 `ml/` 和 `backend/app/modules/video_analysis/`；Thxnks 负责 `backend/app/repositories/`、`backend/app/adapters/database/`、`frontend/src/features/cases/` 和 `frontend/src/features/review/`；Thunder 负责 `backend/app/domain/`、`backend/app/api/`、其他后端模块及 `frontend/src/features/monitor/`。
* `backend/app/contracts.py`、`backend/app/main.py`、`frontend/src/App.tsx` 和 `frontend/src/shared/` 由 Thunder 统一整合；其他负责人通过冻结契约交接，不直接维护第二份实现。
* 只执行线下明确分配的任务。
* 未经明确要求，禁止创建 Issue。
* 未经明确要求，禁止创建 Pull Request。
* 未经明确要求，禁止创建额外的任务跟踪文件。

## 开发执行

### 文档权威

* 涉及产品范围、关键决策或成功标准时，先读 `项目设计文档/项目总体设计.md`，再按其文档地图读取当前负责人的设计文档。
* 涉及 `CandidateEvidence`、VLM、调查、Case 工作流与读模型、人工命令、实时事件、REST、错误或六路演示上下文时，优先读取项目负责人提供的当前 `reports/generated/共享契约（给ai）.md`，并遵循其中的权威顺序。
* `reports/generated/共享契约（给ai）.md` 未提供时，回退读取 `项目设计文档/共享契约与集成验收.md`；缺少当前 AI 契约副本时不得自行改变冻结契约。
* 使用 `backend/app/contracts.py` 核对字段、JSON 类型、枚举、必填性、默认值和可执行校验；需要字段级自动校验时使用 `GET /api/v1/contracts/schema`。
* 文档与实现不一致时，不得静默选择或建立兼容双轨；按文档权威顺序确认目标，并在同一任务中同步直接调用方和契约测试。

### 获取上下文

* 只读取当前任务直接涉及的源码、测试、配置和接口定义。
* 优先使用 `rg` 和 `rg --files` 定位文件与引用。
* 禁止无目的地遍历或读取整个仓库。
* 修改前先查找现有实现、测试和命名方式。
* 任务信息已经明确时，禁止重复询问已给出的内容。
* 只有在仓库内无法确认且不同选择会改变实现结果时，才向任务负责人提问。

### 实施修改

* 遵循当前目录已有的结构、命名和代码风格。
* 优先复用现有模块、函数、类型和工具。
* 禁止为单一调用点增加无实际变化需求的抽象层。
* 禁止添加与当前任务无关的兼容层、降级路径或扩展点。
* 只有现有依赖无法满足任务时才添加新依赖。
* 添加或升级依赖时，在同一 commit 中更新依赖声明。
* 修改前端依赖时同步更新 `frontend/package-lock.json`。
* 后端采用锁文件后，修改后端依赖时同步更新该锁文件。
* 修改公共接口时，同步更新所有直接调用方和相关测试。
* 使用项目已有生成命令更新生成文件，禁止手工修改生成文件。
* 只提交项目明确纳入版本控制的生成源码或生成契约。
* 未经明确要求，禁止创建额外的设计、总结或说明文档。

### 验证修改

* 先运行覆盖当前改动的最小检查，再运行受影响范围内的其他检查。
* 修复缺陷时，在已有测试体系中增加能够复现该缺陷的回归测试。
* 运行测试、静态检查或构建前，确认使用的是项目环境和项目命令。
* 禁止声称未实际运行的检查已经通过。
* 检查失败时，记录失败命令和失败原因。
* 发现与当前任务无关的已有失败时，保留现场并向任务负责人说明。
* 提交前执行 `git diff --check`。

## 项目命令

### 后端检查

运行后端测试：

```bash
cd backend
.venv/bin/python -m pytest
```

* 当前未配置后端 lint 和类型检查命令。
* 禁止自行虚构或替换未配置的检查命令。

### 前端检查

运行前端类型检查和生产构建：

```bash
cd frontend
npm run build
```

* 当前未配置前端测试和 lint 命令。
* 禁止自行虚构或替换未配置的检查命令。
* 修改 OpenAPI 或前端共享请求响应契约时，先启动后端，再执行 `cd frontend && npm run generate:contracts`，随后运行生产构建。

### ML 检查

运行 ML 单元测试：

```bash
backend/.venv/bin/python -m pytest ml/tests
```

* 当前未配置 ML lint、构建或全局训练验收命令。
* 修改 ML 代码时运行当前任务指定的训练、评估或推理命令。
* 在开发日志和完成汇报中记录实际执行的 ML 命令和结果。
* 项目新增或修改标准检查命令时，同步更新本节。

### RAG 检查

修改真实 RAG 索引、检索或来源语料时运行：

```bash
cd backend
.venv/bin/python scripts/check_rag_topk.py
```

* 未配置真实密钥或未准备已复核语料时，记录脚本为未运行或失败及其原因，禁止把空索引或 fixture 结果声明为真实 RAG 验收通过。

## 开发日志

### 日志文件

* 为每名成员维护一份长期追加的个人开发日志。
* 根据当前任务负责人选择日志文件，禁止根据机器账号或 Git 提交者猜测负责人。
* 每名成员只修改自己的日志文件。
* 使用下列固定映射：

| 任务负责人 | 日志文件 |
| ---------- | -------- |
| Wuweizhe（杨溢鑫） | `docs/development-logs/Wuweizhe.md` |
| Thxnks（郝欣冉） | `docs/development-logs/Thxnks.md` |
| Thunder（汪振龙） | `docs/development-logs/Thunder.md` |

### 记录时机

* 每次创建非 merge commit 前更新当前任务负责人的日志。
* `feat`、`fix`、`test`、`refactor`、`docs` 和 `chore` commit 均必须更新日志。
* 第一次在某个日期提交时创建当天区块。
* 同一天再次提交时更新已有当天区块，禁止重复创建日期标题。
* 合并任务分支产生的 merge commit 不单独增加日志记录。
* 没有实际开发和 commit 的日期禁止创建日志。
* 交付前确保每名成员的日志至少包含 8 个真实开发日期。
* 交付前日志不足 8 个真实开发日期时报告缺口，并禁止补造记录。
* 禁止为满足天数要求伪造日期、任务、结果或工作量。

### 日期格式

* 使用北京时间记录实际开发日期和时间。
* 按时间正序追加日期区块和开发记录。
* 日期标题使用 `## YYYY-MM-DD` 格式。
* 单次开发记录以 `- HH:MM` 开头，后接本次提交信息。

### 日志内容

每个日期区块使用：

```markdown
## YYYY-MM-DD

### 当日目标

* <当天要完成的可验收目标>

### 开发记录

* HH:MM `<type>(<scope>): <summary>`
  * 完成：<实际完成的功能或修改>
  * 实现：<关键模块、接口、算法或技术处理>
  * 验证：`<实际命令>`，<通过、失败或未运行及原因>

### 问题与处理

* <遇到的问题、原因和处理结果；没有则写“无”>

### 后续计划

* <下一步具体工作；没有则写“无”>
```

* 只记录当前成员在当前日期实际完成的工作。
* 使用模块、接口和行为描述工作，禁止只罗列文件名。
* 记录关键技术选择、问题原因和处理结果。
* 验证项必须包含实际执行的命令和真实结果。
* 开发记录中的提交信息必须与实际 commit message 完全一致。
* 未运行的测试、静态检查或构建必须写明原因。
* 同一天后续 commit 必须追加开发记录，并按需更新问题、处理结果和后续计划。
* 禁止粘贴大段代码、完整终端输出、聊天记录或重复的项目背景。
* 禁止在日志中记录密钥、Token、密码、服务器凭据或个人隐私信息。

## Git 提交与协作

### Commit

* commit summary用中文写
* 每完成一个可运行、可验证的最小切片就立即 commit。
* 让每个 commit 只表达一个目的。
* 禁止将多个无关修改压入同一 commit。
* 禁止提交已知无法通过测试、静态检查或构建的修改。
* 禁止将未提交的工作区修改交给其他成员继续处理。

提交信息采用：

```text
<type>(<scope>): <summary>
```

仅使用下列 `type`：

| type       | 用途         |
| ---------- | ---------- |
| `feat`     | 增加功能       |
| `fix`      | 修复错误       |
| `test`     | 增加或调整测试    |
| `refactor` | 重构且不改变外部行为 |
| `docs`     | 只修改文档      |
| `chore`    | 处理其他维护工作   |

提交前依次执行：

```bash
git status --short
git diff
<运行相关测试>
<运行静态检查>
<运行构建命令>
<更新当前任务负责人的当天开发日志>
git diff --check
git add <当前任务的具体文件路径>
git add <当前任务负责人的日志文件路径>
git diff --cached
git commit -m "<type>(<scope>): <summary>"
```

* 使用明确的文件路径执行 `git add`。
* 将当前任务修改和对应的个人开发日志放入同一个 commit。
* 禁止使用 `git add -A`、`git add .` 或通配符暂存文件。
* 检查 `git diff --cached` 的全部内容，确认暂存区只包含当前任务的修改。
* 项目未配置某项检查时，明确记录该检查未配置或未运行。

### 推送任务分支

每次 commit 后立即推送当前任务分支：

```bash
git push -u origin <task-branch>
```

已设置上游分支后执行：

```bash
git push origin <task-branch>
```

* 只推送当前任务分支。
* 推送被拒绝时，重新获取远程修改并逐项解决冲突。
* 禁止通过强制推送覆盖远程提交。

### 合并前同步

合并前执行：

```bash
git fetch origin
```

* 检查 `origin/dev` 是否已经前进。
* 当 `origin/dev` 包含新提交时，将其合并到当前任务分支。
* 解决冲突后重新运行相关测试、静态检查和构建命令。
* 无法判断冲突处理方式时停止合并，并联系相关成员确认。

### 集成验收与发布

* 任务分支开发完成后先合并到 `dev`，用于项目负责人集成测试。
* 合并到 `dev` 不代表最终验收通过，也不授权合并到 `main`。
* 合并前在已经同步 `origin/dev` 的任务分支上运行完整测试和构建。
* 合并前确认任务分支已经推送。

任务分支完整检查通过后执行：

```bash
git switch dev
git pull --ff-only origin dev
git merge --no-ff <task-branch>
git push origin dev
```

* 推送 `dev` 被拒绝时，重新获取远程修改并逐项解决冲突。
* 项目负责人在 `dev` 完成测试并明确确认验收后，由项目负责人将 `dev` 合并到 `main`。
* Agent 禁止合并或推送 `main`；只有项目负责人执行正式发布操作。

项目负责人验收通过后执行：

```bash
git switch main
git pull --ff-only origin main
git merge --no-ff dev
git push origin main
```

* 推送 `main` 被拒绝时，由项目负责人重新拉取远程修改并解决冲突。
* 禁止通过强制推送覆盖远程 `dev` 或 `main`。

### 禁止操作

禁止执行：

```bash
git reset --hard
git clean
git push --force
git push --force-with-lease
```

* 禁止删除其他成员的分支。
* 禁止清理、覆盖或丢弃其他成员的修改。
* 禁止改写已经共享的提交历史。

### 禁止提交的文件

禁止提交：

* 数据集和数据导出文件。
* 模型权重和模型缓存。
* 演示视频和其他大型媒体文件。
* 运行数据库、向量索引和可重建 RAG artifact，包括 `.data/`、`chroma_db/`、SQLite 文件和 Chroma 持久化目录。
* 运行日志和调试输出。
* 缓存文件和临时文件。
* 构建产物和未明确纳入版本控制的生成文件。
* `reports/generated/` 下由项目负责人私下分发的 AI 契约；以当前副本为准，禁止修改 `.gitignore`、强制暂存或另建契约版本。
* 包含真实环境值的 `.env` 和本地环境配置文件。
* 真实密钥、Token、密码或其他敏感信息。

允许提交：

* 允许提交不含真实密钥和环境值的 `.env.example`。
* 允许提交项目运行所需的非敏感配置文件。

## Agent 沟通

### 过程沟通

* 禁止重复复述已经确认的项目背景、任务要求和开发规范。
* 只在出现重要决策、风险、阻塞或验证结果时发送过程更新。
* 提问前先使用现有代码、配置、测试和文档自行查证。
* 每次只提出会阻塞当前实现的最少问题。

### 完成汇报

* 使用简短列表汇报已完成修改、验证结果和遗留问题。
* 对每个未运行或未通过的检查给出明确说明。
* 仅在有助于继续开发时提供文件路径和后续操作。
* 跨模块交付还必须包含调用入口、合法输入输出样例、至少一个非法输入及预期错误、实际验证命令和已知限制。
* 禁止生成重复的总结、复盘或长篇实现说明。
