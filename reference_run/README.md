# 训练与实验复现

先完成 [环境安装](../docs/TEAM_ENV_SETUP.md)、[数据准备](../docs/data-setup.md) 和根目录 README 中的模型资源准备。以下基线和生成训练命令均在 reference_run 目录执行，使用根目录 .venv；新候选一节的命令在仓库根目录执行。

- [FF++ 换脸训练](#ffpp-training)
- [整脸生成训练](#generation)
- [10 月 26 日候选复查](#candidate)
- [实验结果与能力限制](../docs/EXPERIMENTS.md)

<a id="ffpp-training"></a>

## 3. 从头复现模型训练

前置数据已经完成：5,000 段 FF++ c23 视频 → 统一 YuNet 裁脸 → 79,994 张 PNG。原项目 `scripts/prepare_ffpp_manifest.py`、`scripts/prepare_ffpp_faces.py` 以及 `../docs/data-setup.md#ffpp` 记录下载、官方划分和裁脸过程。这次读取其真实产物，未重新下载或重做裁脸。

```powershell
..\.venv\Scripts\python.exe train.py
..\.venv\Scripts\python.exe holdout.py
..\.venv\Scripts\python.exe finetune.py
..\.venv\Scripts\python.exe verify.py
..\.venv\Scripts\python.exe verify.py --variant finetuned
..\.venv\Scripts\python.exe make_report.py
```

`train.py` 首次下载约 45 MB 官方 ImageNet 权重到本目录；随后遍历所有图片，核对路径、来源分组、重复编号，并计算解码后像素的 SHA256，遇到跨划分的精确重复会停止。它不能检测近重复、同人不同照或跨库身份泄漏。特征为冻结网络的 FP32 输出，保存在 `artifacts/features.npy`，约 156 MiB。

流程：

1. **train** 拟合特征标准化器，并训练分类层；每个视频在其类别内权重相同，真假两类总权重相同。
2. **val** 比较四个正则化参数 `C = 0.001, 0.01, 0.1, 1`，按视频 AUC 选择；最大化验证集 balanced accuracy 选择阈值。
3. 锁定模型、参数和阈值。
4. **test** 只做最终测试：先取一个视频内各帧分数均值，再计算视频指标。另报告帧指标和每种篡改方法对比真实视频的指标。
5. 将标准化器精确折叠进 PyTorch 线性层，检查 sklearn 与导出模型数值一致。

然后 `finetune.py` 用同一个 ImageNet 骨干重新初始化分类层，训练全部网络参数，使用 AdamW、水平翻转和 CUDA 混合精度。固定运行 4 轮，每轮每段训练视频取 4 张交错帧，四轮合计覆盖所有现有训练帧；这不等于每轮使用全部 16 帧。每轮都在完整验证集评估，按视频 AUC 保存最佳轮次，再确定阈值，最后评估测试集。骨干学习率 1e-4、分类层 3e-4，余弦调度；真假损失按类别数量平衡。

微调模型为 `artifacts/model_finetuned.pt`，其结果文件以 `finetuned_` 开头；视频和指定篡改任务默认优先用它。若比较冻结骨干对照，给 `predict.py` 加 `--task manipulation --checkpoint artifacts/model.pt`。该历史FF++微调没有使用FairFaceGen、来源不明数据或外部测试库。

官方划分：train 3,600 段、val 700 段、test 700 段，按 500 对来源编号分组。类别是真实 1,000 段、四类篡改各 1,000 段。因此“全部预测为假”也能拿到 80% accuracy；阅读结果时应同时看 AUC、balanced accuracy、混淆矩阵和真实类误报。

再次运行会复用清单哈希匹配的特征缓存，重新训练分类层。若修改了骨干权重、图像变换或特征提取实现，应先将 `artifacts/features.npy` 和 `features.json` 改名保存，再重新提取；不要复用旧缓存。当前代码检查清单哈希，不会自动检查每个源文件是否在上次运行后被篡改。

训练后生成 `model.pt`（骨干 + 分类层 + 两种阈值 + 预处理信息），推理时不需要 sklearn 或特征缓存。`verify.py` 在 CPU/GPU 比较分数，并直接读取测试原始视频，验证重新裁脸后的推理与测试清单输出一致。批量 GPU 卷积与单图推理存在浮点差异，图片/视频分数比较容差为 0.001，实际偏差记录在 verification 文件里；接近阈值的输入判定可能随数值扰动变化。相关机制见 [PyTorch 数值精度说明](https://docs.pytorch.org/docs/stable/notes/numerical_accuracy.html)。

## 4. 未见方法测试

`holdout.py` 排除 train 和 val 中所有 NeuralTextures 视频，只在其余三种伪造和真实视频上训练/调参。最后测试集仅取 NeuralTextures 和真实视频，各 140 段。

结果保存在 `holdout_metrics.json`，另存 `model_holdout.pt`，不替换主模型。这是同一个 FF++ 数据集内的方法留出，**不是跨数据集测试**，也不能说明能识别 FLUX、SD3.5 或整段 AI 生成视频。


<a id="generation"></a>

## 整脸生成训练

## 数据、环境与隔离

当前使用父项目根目录 `.venv`，通用依赖已包含 `pyarrow==23.0.1` 读取 Parquet；本目录锁定文件保留历史环境记录，重建方法见 [主环境说明](../docs/TEAM_ENV_SETUP.md)。所有新原始照片、处理结果和清单在 `reference_run/data`；模型与评估在 `artifacts/generation`。父目录的 FairFaceGen ZIP 只读取，原 FF++ 模型没有覆盖。

来源分别为 scikit-learn 固定校验值的 LFW、固定提交和 SHA256 的 FFHQ 公开镜像两个分片、已经下载并校验的官方 FairFaceGen 种子包。下载脚本不需要账户密钥。镜像没有完整身份与逐图许可元数据，未建立商用或图片再分发资格；数据不提交到 Git。

## 从数据到模型

```powershell
..\.venv\Scripts\python.exe download_lfw.py
..\.venv\Scripts\python.exe download_ffhq_subset.py
..\.venv\Scripts\python.exe prepare_generation.py
..\.venv\Scripts\python.exe train_generation.py
..\.venv\Scripts\python.exe calibrate_generation.py
..\.venv\Scripts\python.exe verify_generation.py
..\.venv\Scripts\python.exe report_generation.py
# 覆盖两种已知生成器的联合版；本版本 SD3.5 不再是未见生成器
..\.venv\Scripts\python.exe train_generation.py --include-sd35
..\.venv\Scripts\python.exe calibrate_generation.py --experiment joint
..\.venv\Scripts\python.exe verify_generation.py --experiment joint
..\.venv\Scripts\python.exe activate_generation.py
..\.venv\Scripts\python.exe gui.py --self-test --self-test-task generation
..\.venv\Scripts\python.exe gui.py --self-test --self-test-task manipulation
..\.venv\Scripts\python.exe report_generation_joint.py
```

父项目 `data/raw/fairfacegen` 下需有两个种子包；若缺少，先运行父项目 `scripts/download_fairfacegen.py`。当前已经具备。重跑 `prepare_generation.py` 会在本参考目录重建派生图片与清单，原始数据保留。

整脸生成模型训练 5 轮，每轮遍历全部生成任务的训练图片。ResNet18 从 ImageNet 权重初始化并全网微调，AdamW、骨干学习率 1e-4、分类层 3e-4，余弦调度，批量 48，CUDA 混合精度。损失依次平衡真假类别、真实照片来源和已知分组，避免 LFW 中照片多的人物主导训练。

**第一版单生成器实验**：FLUX 按种子分到 train/val/test；真实照片中 LFW 按人物名称、FFHQ 镜像按图片分组。该版本中 SD3.5 **不参与训练和调参**。只看验证集 AUC 选择轮次，只用验证集 balanced accuracy 选阈值。`calibrate_generation.py` 将阈值放在同一个最优验证决策区间的中点；验证分类保持不变，避免贴在最小生成分数上，整个过程不使用测试集或用户图片选择阈值。保存最终阈值后，再统一计算最终测试、SD3.5 和 JPEG 指标。初始阈值的原始结果保存在 pre_calibration_metrics.json，不隐藏该阶段。SD3.5 测试复用同一真实测试集，不能把这两个指标当成完全独立的实验。

用户提供的 GPT 图片在模型选定后才检查，未用于训练、调参，也没有针对其文件名或标签加规则。它是单张个例，不能用来宣称“支持所有 GPT 生成图”。

第一版发现未见 SD3.5 召回率低，因此追加独立联合版：对 SD3.5 使用同一固定分组哈希建立 train/val/test，与 FLUX 一起训练。原始全部留出实验保留，不把联合版的 SD3.5 测试包装成未见测试。两个版本都不使用用户图片训练或调阈值，但该 GPT 个例在第一版已被观察过，联合版再次检查属于重复回归。

联合版数据清单、权重、指标、阈值及回归结果在 `artifacts/generation/joint`。`activate_generation.py` 只在模型哈希与核验一致、且验证集 balanced accuracy 至少 0.90 时写入 READY.json，随后照片默认路由到联合版。该启用条件不根据测试集或 GPT 个例的结果决定。

## 关键文件

| 文件 | 作用 |
| --- | --- |
| generation_common.py | 训练与推理共用的 128px / JPEG90 标准化 |
| prepare_generation.py | 统一 YuNet 裁脸，分组划分，精确重复隔离，记录未检出人脸 |
| train_generation.py | 独立训练、验证集选模型、正式与未见生成器评估 |
| face_analysis.py | 整脸生成推理，以及照片/视频任务路由 |
| verify_generation.py | 原图与清单分数、CPU/GPU、无脸、跨来源真实帧、用户 GPT 个例检查 |
| artifacts/generation/metrics.json | 各划分指标、真实类误报率、JPEG 重压缩成绩与耗时 |
| artifacts/generation/user_gpt_regression.json | 用户图片的实际输出与原篡改分支对照 |
| data/generation_manifest.csv | 每张图片的原始来源、ZIP 成员、分组、划分、处理图路径和像素 SHA256 |

仍存在数据来源、人物和生成器覆盖限制：FFHQ 镜像无身份标签；未做生物身份或近重复审计。单生成器版本仅用 FLUX，当前联合版本用 FLUX 与 SD3.5，但均没有规模化 GPT 专项训练/测试。统一格式不能完全消除来源差异。高 AUC 和单张 GPT 个例结果都不能替代更广泛的独立测试。

<a id="candidate"></a>

## 10 月 26 日实验候选复查

候选入口为 run_experimental_demo.cmd，依赖本机 outputs 内的选型记录和权重，Git 克隆不包含。稳定模型仍用 run_demo.cmd。

## 结果在哪里

本次固定目录为 `outputs/autonomous-20261026/started-1248`。

| 文件/目录 | 作用 |
| --- | --- |
| source-before | 改动前源码副本 |
| near-duplicate-audit | 43521张外观指纹与142对跨集合候选 |
| clean-generation | 保守隔离清单，含947张隔离记录 |
| openfake-subset / openfake-prepared | 原始下载凭据、固定修订、处理与分组记录 |
| fairface-exam / locked-exam | 仅用于外部考试的真实来源及合并考试清单 |
| generation-selection.json / photo-selection.json | 仅验证集选择的排名、阈值、模型SHA |
| exam-locked-models.json | 看外部结果前冻结的候选 |
| generation-external-* / photo-external-* | 原模型与冻结候选的外部成绩 |
| video-val / video-test / video-policy | 视频记录、验证集阈值与测试成绩 |
| sparse-video | 同编码控制与0.4/0.8秒替换练习，含对齐排除记录 |
| integration.json | 25项测试与界面流程检查记录 |
| user-regression-local.json | 私人样本的本地回归，未上传，不是盲测 |
| original-model-hashes-final.json | 原模型未改变的检查 |
| SUMMARY.json / REPORT_zh.md | 汇总与大白话报告 |

每次作业的`*-args.json`保存实际参数，`*-run`保存输出、失败、温度及资源保护记录。内存不足中止的尝试没有冒充完成的训练。

## 再做一个独立实验，不覆盖稳定模型

以下命令复用本机已经审计的数据清单，输出到新目录。换电脑先按`README.md#generation`和FF++数据说明重新准备合法来源的数据、环境和初始模型。绝对路径清单需要重建，不能盲目照搬。

```powershell
cd D:\faceguard
$sessionRoot = 'outputs/autonomous-20261026/started-1248'
& .\.venv\Scripts\python.exe reference_run\train_generation.py --include-sd35 --manifest "$sessionRoot/openfake-prepared/combined_manifest.csv" --output outputs/my-generation-run --allow-openfake --source-balanced-selection --balanced-sampling --skip-test --epochs 5 --workers 0 --batch-size 32
& .\.venv\Scripts\python.exe reference_run\train_photo_supervision.py --photos "$sessionRoot/photo-supervision-data/manifest.csv" --output outputs/my-photo-run --mask-weight 0.2 --epochs 4 --workers 0 --batch-size 32
```

单独做标签对照时改为`--mask-weight 0`并使用另一个输出目录。除位置监督权重外，数据、种子、批次和训练轮次保持一致。真实伪造掩码未知时，不得把合成练习答案说成真实位置标注。

训练/验证/最终考试保持分离；`--skip-test`让训练阶段不顺手打开考试。看过本轮外部错题后继续改模型，这批数据就属于开发材料，下一轮需要未使用的新考试。不要为了分数好看重复挪本次阈值。

本机临时PowerShell保护器是当日专用，截止16:48；不作为通用调度脚本发布。继续实验应设置新的明确期限、保持资源余量，不同时开多项重训练。此次16GB内存曾因多进程加载不足而停止，单进程串行才完成。无需为复现本轮另装绘图库。
