# Wuweizhe 开发日志

## 2026-08-06

### 当日目标

* 完成 Construction-PPE 官方数据集的可复现审计，确认原始分区、类别统计、数据来源与重复样本风险。

### 开发记录

* 22:30 `feat(ml): 完成施工PPE数据审计`
  * 完成：实现 YOLO 数据集审计命令，记录官方来源、版本、许可、压缩包哈希、类别统计、分区数量和重复检查结果。
  * 实现：校验图片与标签对应关系、YOLO 标签格式和坐标范围，使用 SHA-256 与感知哈希检查重复，并生成确定性的结构化审计报告。
  * 验证：`.\ml\.venv\Scripts\python.exe -m unittest discover -s ml/tests -v`，3 项测试通过；`.\ml\.venv\Scripts\python.exe ml\audit_dataset.py --dataset-root ml\data --source-manifest ml\configs\construction-ppe-source.json --archive ml\data\construction-ppe.zip --output ml\reports\construction-ppe-audit.json`，实际数据审计通过且重复运行报告哈希一致。ML 全局 lint 和构建命令未配置，未运行。

### 问题与处理

* 官方分区中发现 1 组跨训练集与测试集的感知哈希近似样本；按项目要求保留官方分区，不重划分，并在审计报告中记录风险。

### 后续计划

* 领取 `W-02`，基于审计通过的数据集执行 YOLO 训练与固定测试集评估。

## 2026-08-07

### 当日目标

* 完成 `W-02` YOLO11n 训练、固定测试集评估和失败样例分析，形成可复现的结构化训练报告。

### 开发记录

* 17:36 `feat(ml): 完成YOLO训练评估`
  * 完成：在物理 GPU 5 上完成 YOLO11n 80 epochs 训练，以最佳权重评估官方固定测试集，并生成 12 个高错误量失败样例；测试集总体 Precision 为 0.590、Recall 为 0.541、mAP50 为 0.537、mAP50-95 为 0.264。
  * 实现：增加按类别和 IoU 一对一匹配的失败分析命令，记录 FP、FN、排序失败样例和渲染图；生成包含环境、配置、训练指标、逐类测试指标、权重哈希与产物索引的结构化报告，并将视频、权重和运行产物保留在 Git 忽略目录。
  * 验证：`CUDA_VISIBLE_DEVICES=5 yolo detect train model=yolo11n.pt data=work3-dataset.yaml epochs=80 imgsz=640 batch=16 device=0 workers=8 project=outputs/training name=construction-ppe-baseline seed=42 deterministic=True`，80 epochs 完成；`CUDA_VISIBLE_DEVICES=5 yolo detect val model=outputs/training/construction-ppe-baseline/weights/best.pt data=work3-dataset.yaml split=test imgsz=640 batch=16 device=0 workers=8 plots=True project=outputs/evaluation name=construction-ppe-test`，固定测试集 141 张图片、1251 个实例评估完成；`.\ml\.venv\Scripts\python.exe -m unittest discover -s ml/tests -v`，5 项测试通过；`Get-FileHash -Algorithm SHA256 ml\data\w02-artifacts\outputs\training\construction-ppe-baseline\weights\best.pt`，哈希与报告一致且 12 张失败样例完整。ML 全局 lint 和构建命令未配置，未运行。

### 问题与处理

* Ultralytics 在线 AMP 探测因服务器访问 GitHub 时证书主机名不匹配而跳过；框架按离线模式继续启用 AMP，训练损失和指标正常，无 NaN 或 OOM。
* `no_boots` 在固定测试集仅有 23 个实例且 mAP50-95 为 0.00708；在后续视频候选中保留该类别，但必须采用保守阈值并交由下游复核。

### 后续计划

* 进入 `W-03`，使用已下载公开视频实现限速读帧、YOLO 推理、ByteTrack 匿名跟踪和叠加画面。
