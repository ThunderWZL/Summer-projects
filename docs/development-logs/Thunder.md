## 2026-08-06

### 当日目标

* 提交项目协作规则、施工 PPE 设计和可运行的前后端与视觉骨架。

### 开发记录

* 20:58 `chore(repo): 完善协作和忽略规则`
  * 完成：建立 Agent 协作、分支、提交、日志和验证规则，完善项目忽略范围。
  * 实现：保留仓库级 `AGENTS.md`，忽略数据集、模型、视频、密钥、缓存、构建和训练产物。
  * 验证：`git diff --check -- .gitignore AGENTS.md docs/development-logs/Thunder.md`，通过。

### 问题与处理

* 无。

### 后续计划

* 提交 SitePPE Agent 项目设计和旧方向文档清理。
