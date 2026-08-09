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

* 完成 `W-02` YOLO11n 训练评估，并实现 `W-03` 限速视频推理、ByteTrack 匿名跟踪和叠加画面。

### 开发记录

* 17:36 `feat(ml): 完成YOLO训练评估`
  * 完成：在物理 GPU 5 上完成 YOLO11n 80 epochs 训练，以最佳权重评估官方固定测试集，并生成 12 个高错误量失败样例；测试集总体 Precision 为 0.590、Recall 为 0.541、mAP50 为 0.537、mAP50-95 为 0.264。
  * 实现：增加按类别和 IoU 一对一匹配的失败分析命令，记录 FP、FN、排序失败样例和渲染图；生成包含环境、配置、训练指标、逐类测试指标、权重哈希与产物索引的结构化报告，并将视频、权重和运行产物保留在 Git 忽略目录。
  * 验证：`CUDA_VISIBLE_DEVICES=5 yolo detect train model=yolo11n.pt data=work3-dataset.yaml epochs=80 imgsz=640 batch=16 device=0 workers=8 project=outputs/training name=construction-ppe-baseline seed=42 deterministic=True`，80 epochs 完成；`CUDA_VISIBLE_DEVICES=5 yolo detect val model=outputs/training/construction-ppe-baseline/weights/best.pt data=work3-dataset.yaml split=test imgsz=640 batch=16 device=0 workers=8 plots=True project=outputs/evaluation name=construction-ppe-test`，固定测试集 141 张图片、1251 个实例评估完成；`.\ml\.venv\Scripts\python.exe -m unittest discover -s ml/tests -v`，5 项测试通过；`Get-FileHash -Algorithm SHA256 ml\data\w02-artifacts\outputs\training\construction-ppe-baseline\weights\best.pt`，哈希与报告一致且 12 张失败样例完整。ML 全局 lint 和构建命令未配置，未运行。
* 22:00 `feat(ml): 实现视频推理与匿名跟踪`
  * 完成：实现按目标帧率稳定采样的视频推理器，使用 YOLO11n 和 ByteTrack 输出原始像素坐标检测、匿名人员轨迹 ID 和叠加画面。
  * 实现：使用无累积舍入误差的时间戳采样，以 `persist=True` 保留 ByteTrack 状态，支持运行时选择 GPU、推理帧率、播放倍速、置信度和最大推理帧数；补充 `lap` 跟踪依赖。
  * 验证：`.\ml\.venv\Scripts\python.exe -m unittest discover -s ml\tests -v`，10 项测试通过；`.\ml\.venv\Scripts\python.exe -m py_compile ml\video_inference.py`，通过；`python -m pytest tests\test_contracts.py tests\domain\test_case_workflow.py`，65 项后端契约与状态机测试通过；`CUDA_VISIBLE_DEVICES=1 ./conda/bin/python video_inference.py 'How many OSHA violations_ _ r_funny.mp4' --weights outputs/training/construction-ppe-baseline/weights/best.pt --fps 5 --device 0`，服务器 GPU 完整处理 12.4 秒、372 帧公开视频，实际推理 62 个采样帧通过，30 FPS 源视频每 6 帧采样且连续保留匿名轨迹 ID。完整后端 `python -m pytest` 因本机 Python 3.13 环境缺少 `fastapi` 而在健康接口测试收集阶段停止；ML 全局 lint 和构建命令未配置，未运行。

### 问题与处理

* Ultralytics 在线 AMP 探测因服务器访问 GitHub 时证书主机名不匹配而跳过；框架按离线模式继续启用 AMP，训练损失和指标正常，无 NaN 或 OOM。
* `no_boots` 在固定测试集仅有 23 个实例且 mAP50-95 为 0.00708；在后续视频候选中保留该类别，但必须采用保守阈值并交由下游复核。
* ByteTrack 首次运行发现 work3 隔离环境缺少 `lap`，且服务器 PyPI 证书主机名不匹配；从开发机下载 CPython 3.10 Linux wheel，上传后在 work3 环境离线安装，实际跟踪验证通过。

### 后续计划

* 待项目负责人将 `feat/video-inference-tracking` 合并至 `dev` 并完成集成测试后，从最新 `dev` 创建新分支进入 `W-04` 候选聚合。

## 2026-08-09

### 当日目标

* 修复 `W-03` 实时播放追帧和仅输出 AI 采样帧的问题，保证完整视频流畅输出并叠加最新分析结果。

### 开发记录

* 14:14 `fix(ml): 修复实时推理播放节拍`
  * 完成：将完整源视频帧与 5 FPS AI 采样解耦，每张原视频帧均叠加最新可用检测结果，并将 `annotated_frame` 收紧为 NumPy `uint8` OpenCV 帧类型。
  * 实现：新增无追帧的实时节拍器；使用单槽后台队列异步推理，超载时丢弃旧待处理样本；增加首帧模型和跟踪器预热、分析时间戳与更新标记，并将后台推理异常回传播放侧。
  * 验证：`.\ml\.venv\Scripts\python.exe -m unittest discover -s ml\tests -v`，15 项测试通过；`.\ml\.venv\Scripts\python.exe -m py_compile ml\video_inference.py`，通过；`CUDA_VISIBLE_DEVICES=0 ./conda/bin/python video_inference.py 'How many OSHA violations_ _ r_funny.mp4' --weights outputs/training/construction-ppe-baseline/weights/best.pt --fps 5 --device 0 --realtime`，服务器完整输出 372 帧、AI 更新 62 次、最大分析滞后 267 ms；首帧预热进程用时 5.067 秒，完整流进程用时 18.069 秒，扣除启动后的播放和收尾约 13 秒，与 12.4 秒视频节拍一致。本次未修改后端，未运行后端测试；ML 全局 lint 和构建命令未配置，未运行。
* 17:04 `fix(ml): 防止推理线程阻塞退出`
  * 完成：增加“慢 AI 与完整帧输出”组合回归测试，确认后台推理阻塞时播放侧仍按顺序输出全部原视频帧。
  * 实现：为推理线程退出增加默认 10 秒的可配置超时，超时时显式报错；使用嵌套 `finally` 保证线程超时或异常时仍释放视频捕获句柄。
  * 验证：`.\ml\.venv\Scripts\python.exe -m unittest discover -s ml\tests -v`，18 项测试通过；`.\ml\.venv\Scripts\python.exe -m py_compile ml\video_inference.py`，通过；`CUDA_VISIBLE_DEVICES=0 ./conda/bin/python video_inference.py 'How many OSHA violations_ _ r_funny.mp4' --weights outputs/training/construction-ppe-baseline/weights/best.pt --fps 5 --device 0 --realtime --shutdown-timeout 10`，服务器完整输出 372 帧、AI 更新 62 次并在超时内正常退出。本次未修改后端，未运行后端测试；ML 全局 lint 和构建命令未配置，未运行。
* 20:40 `feat(ml): 增加标注视频输出验证`
  * 完成：补全实时帧输出节拍、迟到后恢复休眠、慢 AI 仅追踪最新样本、标注像素叠加和完整视频编码输出的回归验证。
  * 实现：增加标注 MP4 输出函数与 `--output-video` 命令行参数，沿用源视频帧率、尺寸和完整播放帧；组合测试直接断言编码器收到的每帧都包含检测框像素，并构造旧采样积压确认中间样本被最新样本替换。
  * 验证：`.\ml\.venv\Scripts\python.exe -m unittest discover -s ml\tests -v`，21 项测试通过；`.\ml\.venv\Scripts\python.exe -m py_compile ml\video_inference.py`，通过；`CUDA_VISIBLE_DEVICES=0 ./conda/bin/python video_inference.py 'How many OSHA violations_ _ r_funny.mp4' --weights outputs/training/construction-ppe-baseline/weights/best.pt --fps 5 --device 0 --realtime --shutdown-timeout 10 --output-video outputs/w03-annotated-review-20260809.mp4`，服务器输出 372 帧、30 FPS、480×854、12.4 秒的 MPEG-4 视频，抽帧确认人员与反光背心标注已写入最终文件。本次未修改后端，未运行后端测试；ML 全局 lint 和构建命令未配置，未运行。
* 20:47 `fix(ml): 保留标注视频原始音轨`
  * 完成：保留源视频 AAC 音轨，并保证音轨短于画面时不截断最后的标注视频帧。
  * 实现：先在输出目录的临时目录编码完整标注画面，再使用 FFmpeg 无重编码合入可选源音轨，成功后原子移动到目标路径；以实际帧数与帧率限定容器时长，保证完整输出不被较短音轨截断，且限帧输出不携带整段音轨。
  * 验证：`.\ml\.venv\Scripts\python.exe -m unittest discover -s ml\tests -v`，21 项测试通过；`.\ml\.venv\Scripts\python.exe -m py_compile ml\video_inference.py`，通过；`CUDA_VISIBLE_DEVICES=0 ./conda/bin/python video_inference.py 'How many OSHA violations_ _ r_funny.mp4' --weights outputs/training/construction-ppe-baseline/weights/best.pt --fps 5 --device 0 --realtime --shutdown-timeout 10 --output-video outputs/w03-annotated-final-20260809.mp4`，服务器输出保留 372/372 帧、30 FPS、12.4 秒画面和 12.20 秒 AAC 音轨；增加 `--max-frames 30` 复验后，输出为 30 帧、1.0 秒画面和 1.003 秒音轨。本次未修改后端，未运行后端测试；ML 全局 lint 和构建命令未配置，未运行。

### 问题与处理

* 首次实时复测虽完整输出 372 帧，但首次模型初始化导致最大分析滞后 1733 ms；将首帧预热移到播放时钟开始前，最大滞后降至 267 ms。
* `InferenceFrame` 与 `annotated_frame` 的全部调用方均在 `ml` 目录，未跨模块传输，因此收紧内部类型而不修改共享 Pydantic 契约。
* 原实现无限期等待推理线程退出，模型或 GPU 调用卡死时会阻塞会话停止；增加退出超时、错误回传和捕获句柄释放测试后解决。
* 原回归测试只证明返回了帧对象，未覆盖迟到后恢复休眠、旧样本替换、标注像素和最终视频文件；补充行为级与服务器端到端验证后解决。
* 首次标注 MP4 只包含视频流；合回源 AAC 音轨后又发现 `-shortest` 会因音轨较短将 372 帧截为 367 帧，移除截断参数后复验同时保留完整画面和音轨。

### 后续计划

* 请项目负责人重新测试并合并修正后的 `feat/video-inference-tracking`；合并后再从最新 `dev` 创建 `W-04` 候选聚合分支。
