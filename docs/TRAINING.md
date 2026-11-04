# 训练与实验复现

本文件是当前训练说明的唯一维护入口；实验结论见 [实验记录](EXPERIMENTS.md)，过程与进展见 [项目日志](../LOG.md)，用户约定见 [AGENTS.md](../AGENTS.md)。

正式应用使用根目录 `run_app.cmd` / `run_app.py`，推理代码在 `src/faceguard/inference/`，运行资源在 `weights/runtime/`，无需依赖参考目录。`reference_run` 已封存为只读历史实现：部分既有训练 / 审计脚本仍读取其中的源码，因此暂时保留；这不表示所有训练代码已迁出。

## 当前训练入口

先按 [环境说明](TEAM_ENV_SETUP.md) 和 [数据准备](data-setup.md) 核对环境、数据及初始权重。当前流程从仓库根目录调用 `scripts/`，新训练结果只写 `outputs/`，数据与清单统一保存在 `D:\datasets\faceguard`。每次复现使用全新输出目录，不能覆盖已冻结作业，也不并行开启多项完整训练。

```powershell
# 已准备好本机冻结数据与父权重时，在仓库根目录复现低误报训练
.\.venv\Scripts\python.exe scripts/run_generation_low_fpr.py --output outputs/low-fpr-fresh
```

该入口显式把训练和评测输出写到 `outputs/`，内部仍会只读调用归档训练源码。后续新增训练逻辑在正式项目或 `scripts/` 中开发，不向参考目录追加源码、文档、数据、模型或实验结果。

- [完整低误报训练复现](#full-low-fpr-20261101)
- [DFF / GPT 数据接入与微调记录](#new-data-20261031)
- [历史 FF++ 训练记录](#ffpp-training)
- [历史整脸生成训练记录](#generation)
- [10 月 26 日候选复查](#candidate)

## 历史命令的阅读范围

以下章节保留原训练过程、参数、文件名和当时的验证范围，方便核对历史模型。以 `..\.venv` 开头的代码块原来在 `reference_run` 中执行，属于历史命令记录；不作为当前向归档目录写入新结果的操作指引。需要重做这些旧流程时，应先将可写输出接入正式训练入口，再在独立输出目录复现。历史 `data` 路径通过代码映射读取，不能重建旧目录或兼容链接。

<a id="ffpp-training"></a>

## 历史 FF++ 模型训练

前置数据已经完成：5,000 段 FF++ c23 视频 → 统一 YuNet 裁脸 → 79,994 张 PNG。原项目 `scripts/prepare_ffpp_manifest.py`、`scripts/prepare_ffpp_faces.py` 以及 `data-setup.md#ffpp` 记录下载、官方划分和裁脸过程。这次读取其真实产物，未重新下载或重做裁脸。

```powershell
..\.venv\Scripts\python.exe train.py
..\.venv\Scripts\python.exe holdout.py
..\.venv\Scripts\python.exe finetune.py
..\.venv\Scripts\python.exe verify.py
..\.venv\Scripts\python.exe verify.py --variant finetuned
..\.venv\Scripts\python.exe make_report.py
```

`train.py` 首次下载约 45 MB 官方 ImageNet 权重到当时的参考目录；随后遍历所有图片，核对路径、来源分组、重复编号，并计算解码后像素的 SHA256，遇到跨划分的精确重复会停止。它不能检测近重复、同人不同照或跨库身份泄漏。特征为冻结网络的 FP32 输出，保存在 `artifacts/features.npy`，约 156 MiB。

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

## 历史 FF++ 未见方法测试

`holdout.py` 排除 train 和 val 中所有 NeuralTextures 视频，只在其余三种伪造和真实视频上训练/调参。最后测试集仅取 NeuralTextures 和真实视频，各 140 段。

结果保存在 `holdout_metrics.json`，另存 `model_holdout.pt`，不替换主模型。这是同一个 FF++ 数据集内的方法留出，**不是跨数据集测试**，也不能说明能识别 FLUX、SD3.5 或整段 AI 生成视频。


<a id="generation"></a>

## 历史整脸生成训练

### 数据、环境与隔离

原实验使用根目录 `.venv` 和 PyArrow 读取 Parquet，历史环境锁定文件保留，当前环境见 [环境说明](TEAM_ENV_SETUP.md)。原 `reference_run/data` 入口已删除；数据与清单现统一到 `D:\datasets\faceguard`，历史模型 / 评估产物只读保留。原 FF++ 模型没有覆盖。

来源分别为 scikit-learn 固定校验值的 LFW、固定提交和 SHA256 的 FFHQ 公开镜像两个分片、已经下载并校验的官方 FairFaceGen 种子包。下载脚本不需要账户密钥。镜像没有完整身份与逐图许可元数据，未建立商用或图片再分发资格；数据不提交到 Git。

### 从数据到模型

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

原 FairFaceGen 种子包现通过 `faceguard.data_locations` 读取统一存储位置。需要补数据时使用根目录 `scripts/` 入口和 [数据准备](data-setup.md)；不按历史路径重建旧文件夹，也不向参考目录生成派生图片或新清单。

整脸生成模型训练 5 轮，每轮遍历全部生成任务的训练图片。ResNet18 从 ImageNet 权重初始化并全网微调，AdamW、骨干学习率 1e-4、分类层 3e-4，余弦调度，批量 48，CUDA 混合精度。损失依次平衡真假类别、真实照片来源和已知分组，避免 LFW 中照片多的人物主导训练。

**第一版单生成器实验**：FLUX 按种子分到 train/val/test；真实照片中 LFW 按人物名称、FFHQ 镜像按图片分组。该版本中 SD3.5 **不参与训练和调参**。只看验证集 AUC 选择轮次，只用验证集 balanced accuracy 选阈值。`calibrate_generation.py` 将阈值放在同一个最优验证决策区间的中点；验证分类保持不变，避免贴在最小生成分数上，整个过程不使用测试集或用户图片选择阈值。保存最终阈值后，再统一计算最终测试、SD3.5 和 JPEG 指标。初始阈值的原始结果保存在 pre_calibration_metrics.json，不隐藏该阶段。SD3.5 测试复用同一真实测试集，不能把这两个指标当成完全独立的实验。

用户提供的 GPT 图片在模型选定后才检查，未用于训练、调参，也没有针对其文件名或标签加规则。它是单张个例，不能用来宣称“支持所有 GPT 生成图”。

第一版发现未见 SD3.5 召回率低，因此追加独立联合版：对 SD3.5 使用同一固定分组哈希建立 train/val/test，与 FLUX 一起训练。原始全部留出实验保留，不把联合版的 SD3.5 测试包装成未见测试。两个版本都不使用用户图片训练或调阈值，但该 GPT 个例在第一版已被观察过，联合版再次检查属于重复回归。

联合版数据清单、权重、指标、阈值及回归结果在 `artifacts/generation/joint`。`activate_generation.py` 只在模型哈希与核验一致、且验证集 balanced accuracy 至少 0.90 时写入 READY.json，随后照片默认路由到联合版。该启用条件不根据测试集或 GPT 个例的结果决定。

### 关键文件

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

<a id="new-data-20261031"></a>

## 10 月 31 日 DFF 微调与 StyleGAN 开发检查

本机数据现统一到 `D:\datasets\faceguard`，新旧素材、裁脸、清单与评测材料的真实位置见 [数据准备](data-setup.md)。旧 `data` / `reference_run/data` 与历史实验数据入口已删除；原清单内容、group / split 和模型绑定哈希保留，更新后的读取函数在代码中映射历史路径，不需要恢复旧目录或链接。

本地规模、来源与划分建议见 [数据准备](data-setup.md#new-data-20261031)。DFF 实体目录为统一根目录的 `01_raw/generation/deepfakeface/{wiki/wiki,text2img/text2img}`；GAN 为 `01_raw/generation/gan140k`，目前只有一个原 validation 分片和每类 1,000 张导出图。新增数据优先服务整脸生成分支。

训练入口现在支持显式 `--allow-dff` 和 `--init-checkpoint`，核对生成任务、ResNet18、128px / JPEG90 和 YuNet 哈希后，从现有生成权重初始化骨干与分类头，再建立新优化器。未传 checkpoint 的旧命令仍从 ImageNet 初始化。StyleGAN 未纳入本轮训练来源；不能直接把原始目录或开发检查清单传给训练器。

本轮数据版本为 `dff-sd15-20261031-v1`。DFF 60,000 张统一裁脸，58,371 张成功、1,629 张未检出人脸；原图未覆盖。处理图在统一根目录 `02_processed/generation/dff-sd15-20261031-v1/`，逐图来源、裁剪框与失败表在 `05_provenance/dff-sd15-20261031-v1/`。

分组使用 [官方 WIKI 元数据](https://data.vision.ee.ethz.ch/cvl/rrothe/imdb-wiki/) 的文件名 / 规范化人名，全部 30,000 对匹配；同一人名及真 / 假家族保持同组，并连接 LFW 已知同名人物（727 个重叠）。对新旧候选和初始模型训练清单逐图核对解码像素 SHA-256，再以 64 位 pHash 距离 ≤ 6 连接相似图。初始模型曾见过但后来从清单删除的 947 行也参与关联审计；与原训练暴露冲突的留出行隔离，不通过删行假定初始模型没有见过。已观察的 DFF 小样家族 / 人名不进入新测试。人名匹配和 pHash 不能证明全部生物身份互斥，FFHQ 无完整身份标注。

最终清单在 `03_manifests/dff-sd15-20261031-v1/`：训练 **70,198**、验证 **14,697**、最终测试 **14,616**，另隔离 1,434 行（原训练暴露 650、跨划分关联 692、精确重复 92）。保留旧清单划分角色，按连接关系保守隔离冲突，不把旧 test 回流训练。`protocol.json` 固定规则、逐来源计数和清单哈希；`train-val.csv` 与 `locked-test.csv` 分开保存。

在项目根目录执行：

```powershell
.\.venv\Scripts\python.exe scripts/prepare_generation_update.py --workers 2
.\.venv\Scripts\python.exe scripts/run_generation_update.py
```

预处理同配置可恢复；冻结清单禁止覆盖。完整流程先保存稳定模型验证基线，再微调 5 轮：batch 32、workers 0、AMP、seed 20261031、骨干学习率 3e-5、分类头 1e-4，按来源 / 方法 / 类别均衡采样。仅按验证集的来源均衡 AUC 选轮次，阈值也仅从验证集选择；训练带 `--skip-test`。候选哈希锁定后才评测试集；原有来源测试属于历史回归，新 DFF 属于同来源分组留出，均不等同未知工具的独立泛化考试。

输出为 `outputs/training-20261031/dff-sd15-update/`，包括配置、逐轮日志、独立 `candidate/model.pt`、新旧模型逐图预测、分来源指标、测试前锁定记录和最终 `completion.json`。完整流程不自动覆盖既有评测输出；复跑应传新的 `--output`，不要并行跑两项训练。稳定 `weights/runtime/` 与参考模型均保留，训练流程不自动启用候选。

本机本轮已完整执行，选中第 5 轮、阈值 0.6774183213710785；候选已通过正式推理模块的原图对照。DFF 测试明显改善，GAN 开发仍全部漏检，旧来源有小幅退化；完整分来源成绩与局限见 [本轮实验](EXPERIMENTS.md#dff-training-20261031)。这些已打开的测试下一轮属于回归材料，不能再称新盲测。

GAN 沿用先前固定的 200 张原 validation 样本，重新使用相同裁脸流程比较新旧权重；未拟合、未重新调阈值，仍标为 `gan_dev` 外部开发检查，不是新盲测。400 张历史开发检查可用以下命令复现，输出目录已有冻结清单时只允许相同配置和文件内容；更换抽样配置请指定新的 `--output`。

```powershell
.\.venv\Scripts\python.exe scripts/check_new_generation_data.py --data-root D:\datasets\faceguard --per-class 100 --device cpu
```

脚本从 DFF 选择 100 对，从 GAN 原 validation 分片选择真 / 假各 100，直接保留 Parquet 原图字节和行号。整理前已观察的固定清单 / 成绩原样保留在 `04_evaluation/new-data-20261031/development-baseline/`；以上新命令默认另写 `04_evaluation/generation-development-current/`，因路径文本不同，不覆盖历史冻结清单。成绩与局限见 [10 月 31 日实验](EXPERIMENTS.md#session-20261031)。两者的样本选择规则相同，换了存储位置不代表新独立考试；清单明确为 `external_dev`，不能直接传给旧训练脚本，也不是训练 / 最终测试划分。

<a id="full-low-fpr-20261101"></a>

### 完整低误报训练已完成（2026-11-01）

上次作业未完成轮次 / 优化器断点，本次从 SD1.5 父权重重新完整训练 3 轮，仍用原冻结数据（train 70,624 / val 14,810），不改旧 split。输出为 `outputs/training-20261101/low-fpr-full/`。每轮权重和验证预测在 `training/epochs/`，六候选排序 / 阈值在回归前锁定。

```powershell
# 本机已完成。需要复现时用新输出目录，不覆盖已有结果，也不要并行重训练
.\.venv\Scripts\python.exe scripts/run_generation_low_fpr.py --output outputs/training-20261101/low-fpr-reproduction
```

最终选新训练第 2 轮，阈值 0.40325649082660675；校验后的候选为 `calibrated/new-epoch-002.pt`，SHA-256 `f387cd1c6613ae0ec74df2791b2c8fbdfc409f33b89dc77eac19da9416240c14`。验证 GPT1 检出 10/25、真图误报 145/7,265；新权重实际历史测试真图误报 161/7,144（约 2.25%），跨版本生成脸 31/158，StyleGAN 开发仍 0/100。老人肖像分 0.4430334 > 锁定阈值，提示疑似生成；未据该图选轮次或调阈值。

正式设置可手动选“GPT联合 · 低误报训练版（11-01）”，CLI 名称为 `gpt-low-fpr-20261101`；默认稳定版和旧候选保留。61 项测试及正式 Qt/CPU 新权重检查通过，6 例 CPU/CUDA 原图对照最大差约 4.57e-7。完整来源计数、实际推理回归与局限见 [11 月 1 日实验](EXPERIMENTS.md#full-low-fpr-20261101)。

### 现有数据低误报流程（2026-10-31）

`src/faceguard/generation_selection.py` 统一实现验证误报预算和排名。训练时显式传 `--selection-metric low_fpr_gpt_recall --max-val-fpr .02 --focus-method gpt-image-1 --save-epoch-checkpoints`，配合独立 `--output`、`--skip-test`；每轮保存权重及验证预测。先按预算内 GPT 各方法组均衡召回排名，再比较所有生成器召回、验证 AUC 和更低误报；精确并列保留较早轮次。旧 AUC 方式仍为默认。

基于现有分数的完整流程：

```powershell
# 现有本机结果已在 low-fpr-existing-models；复跑指定新的输出目录
.\.venv\Scripts\python.exe scripts/benchmark_generation_operating_points.py --output outputs/low-fpr-reproduction
# 本机以下审计 / 复用池已冻结；命令会拒绝覆盖
.\.venv\Scripts\python.exe scripts/audit_current_generation_data.py
.\.venv\Scripts\python.exe scripts/audit_current_generation_data.py --pools-only
# 显卡与内存有余量时，可在新目录执行 3 轮完整低误报选型训练
.\.venv\Scripts\python.exe scripts/run_generation_low_fpr.py --output outputs/low-fpr-full-fresh
```

本轮完整 GPU 作业因资源竞争主动停止，完成轮次为 0，记录在 `outputs/training-20261031/low-fpr-current-data/`。训练器改动已用真实小子集在 CPU 实跑两轮验证；小子集不作为模型成绩。当前有效交付是三套既有模型的验证标定和历史分数重放，另有 6 张原图 CPU 分数核对，不冒充新完整训练 / 新独立考试。

同等整体验证约 2% 误报下，稳定 / SD1.5 / 联合版的 GPT1 检出分别 7/25、5/25、10/25，选中联合权重并标定阈值 0.2556876689195633。历史测试整体误报约 2.34%，用户老人肖像再次漏检。新文件独立安装为 `gpt-low-fpr-v1`，默认稳定版不变；正式设置中可手动选择“GPT联合 · 低误报实验版”。完整结果见 [现有数据低误报报告](EXPERIMENTS.md#current-data-low-fpr-20261031)。

### GPT 漏检后的联合实验（2026-10-31）

用户 GPT 老人肖像在旧稳定、SD1.5 候选与原 GPT 多源候选上均漏检，具体 GPT 版本未知；逐图分数保存在 `outputs/gpt-regression-20261031/comparison.json`。该照片仅作已观察回归，不进入训练 / 验证，也不据此更改阈值。

新版本 `dff-gpt-joint-20261031-v1` 复用 DFF 已冻结的角色和处理图，加上旧 OpenFake 的 GPT1 / 真实来源；沿原 prompt group 保留 train / val / external_test。对新增行重新核对像素 SHA，并对照 DFF 冻结 pHash、原初始权重历史行做距离 ≤ 6 筛查；9 行相关组隔离。实际 train 70,624、val 14,810、旧来源 test 14,616、外部历史回归 168；GPT1 仅 train 93 / val 25，样本量不足风险明确保留。GPT1.5 / GPT2 / nano-banana-pro 均不拟合或选阈值；原测试已经观察，不能再称新盲测。用户图未发现此规则下的近邻，不能据此保证完整身份独立。

```powershell
# 分组清单已冻结时勿重跑第一条；训练输出也禁止覆盖已有作业
.\.venv\Scripts\python.exe scripts/prepare_generation_joint.py --regression-image "D:\table\温暖凝视的老人肖像.png"
.\.venv\Scripts\python.exe scripts/run_generation_joint.py
```

本轮从 DFF 第 5 轮候选初始化，预先固定 3 轮，batch 32 / workers 0，来源 / 方法 / 类别和组均衡采样；骨干 3e-5、分类头 1e-4，seed 20261031。仅按验证集选轮次和阈值，锁定后才打开旧测试、外部回归与用户照片。输出为 `outputs/training-20261031/dff-gpt-joint/`；最后以 `completion.json` 和 [实验记录](EXPERIMENTS.md) 为准，不因启动训练宣称漏检修复。

本机已完成 3 轮与最终回归，验证选第 1 轮，阈值 0.03806435689330101。老人肖像分 0.181338，现提示疑似生成；DFF 真图误报升到 7.42%，外部生成脸仅检出 46/158。联合候选独立安装为 `gpt-sd15-v1`，正式应用重启后在“设置 → 高级选项”手动选择“GPT1 + SD1.5 · 高敏感实验版”；默认稳定模型保持原样。完整取舍与历史候选对照见 [GPT 漏检实验](EXPERIMENTS.md#gpt-feedback-20261031)。

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

以下命令复用本机已经审计的数据清单，输出到新目录。换电脑先按`TRAINING.md#generation`和FF++数据说明重新准备合法来源的数据、环境和初始模型。绝对路径清单需要重建，不能盲目照搬。

```powershell
cd D:\faceguard
$sessionRoot = 'outputs/autonomous-20261026/started-1248'
& .\.venv\Scripts\python.exe reference_run\train_generation.py --include-sd35 --manifest "$sessionRoot/openfake-prepared/combined_manifest.csv" --output outputs/my-generation-run --allow-openfake --source-balanced-selection --balanced-sampling --skip-test --epochs 5 --workers 0 --batch-size 32
& .\.venv\Scripts\python.exe reference_run\train_photo_supervision.py --photos "$sessionRoot/photo-supervision-data/manifest.csv" --output outputs/my-photo-run --mask-weight 0.2 --epochs 4 --workers 0 --batch-size 32
```

单独做标签对照时改为`--mask-weight 0`并使用另一个输出目录。除位置监督权重外，数据、种子、批次和训练轮次保持一致。真实伪造掩码未知时，不得把合成练习答案说成真实位置标注。

训练/验证/最终考试保持分离；`--skip-test`让训练阶段不顺手打开考试。看过本轮外部错题后继续改模型，这批数据就属于开发材料，下一轮需要未使用的新考试。不要为了分数好看重复挪本次阈值。

本机临时PowerShell保护器是当日专用，截止16:48；不作为通用调度脚本发布。继续实验应设置新的明确期限、保持资源余量，不同时开多项重训练。此次16GB内存曾因多进程加载不足而停止，单进程串行才完成。无需为复现本轮另装绘图库。
