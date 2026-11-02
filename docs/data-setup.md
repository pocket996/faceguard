# 数据准备与加载

## 统一数据入口（2026-10-31）

项目采集数据的实体位置统一为 **`D:\datasets\faceguard`**。根目录 `README.md` 用于导航，`DATA_CATALOG.csv` / `DATA_CATALOG.json` 列出原材料及新增版本的来源、用途状态、文件量、实际位置与历史入口。最初整理 27 组材料，共迁入 220,782 个文件 / 44,818,277,130 字节，迁移前后逐文件 SHA-256、同卷文件身份与旧入口全部核对通过；此次迁移未改图片、标签或划分。后续裁脸与冻结清单作为独立条目追加，不覆盖原始材料，具体审计范围见下文。

```text
D:\datasets\faceguard\
├─ 01_raw\              原始数据
│  ├─ generation\       deepfakeface、gan140k、fairfacegen
│  ├─ manipulation\     ffpp
│  ├─ real\             lfw、ffhq256
│  └─ mixed\            openfake-20261026
├─ 02_processed\        裁脸、派生练习、演示素材，按用途 / 版本分组
├─ 03_manifests\        FF++、原生成任务、保守去重清单
├─ 04_evaluation\       FairFace / 冻结历史评测包、新数据开发检查
├─ 05_provenance\       来源说明、U 盘复制收据、此次迁移记录
└─ 90_quarantine\       4 个第三方未核验归档及旧检查预览
```

FairFace 的原 Parquet、裁脸与协议，以及旧冻结考试包作为完整评测包保留在 `04_evaluation`，不拆散其内部关联。其他原始包的内部目录也保留发布结构：例如 DFF 真图为 `01_raw/generation/deepfakeface/wiki/wiki`，假图为同层 `text2img/text2img`。GAN 原 Parquet 与旧的每类 1,000 张重编码导出同放其来源目录，并在总表注明不能重复计样。

**旧数据目录与链接已按用户要求删除。** 仓库 `data`、`reference_run/data`、原 `D:\datasets\dff` / `gan140k`、旧实验数据入口及旧单文件硬链接均已移除；统一目录中的 220,782 个原有文件身份、大小和修改时间保持不变。`reference_run` 的源码、模型和其他实验输出保留。当前数据总表的 `directory` 是实际位置，`legacy_entry` 只记录历史路径，`legacy_status=removed` 表示旧磁盘入口已删除。

新代码从 `src/faceguard/data_locations.py` 的 `data_location(name)` 获取位置，可用 `FACEGUARD_DATA_ROOT` 指定统一根目录；读取历史 CSV / 协议中的路径时使用 `resolve_data_path(value, base)`。映射只在代码中进行，不建立链接，也不改写原 CSV、标签、split 或冻结清单哈希。下载、预处理、训练和评测读取已适配，正式应用也可重开历史数据文件记录。后续不再重建旧数据文件夹。

新增来源放对应 `01_raw` 来源子目录，处理结果另建 `02_processed` 版本，清单保留同源 group / 划分；来源不明的先放 `90_quarantine`，并更新同一份根目录数据总表。模型权重、训练特征缓存、角色工程与界面截图按原有项目用途保存。

复核入口：根目录运行 `scripts/check_data_store.py`。全文件迁移凭据在 `05_provenance/consolidation-20261031/`（原路径映射、逐文件 SHA-256、操作日志与 verification.json）；复核读取报告在仓库被忽略的 `outputs/data-consolidation-20261031/`。本次另核对 7 份主要清单共 171,301 条文件引用，全部可读且均落在统一目录；FF++ train / val / test 实际批次通过，冻结开发清单哈希不变，47 项现有及路径读取测试通过。删除旧入口后的复核与删除日志位于 `outputs/data-cleanup-20261031/`；历史路径在更新后的项目读取函数中映射，直接用系统文件管理器访问旧目录将不再存在。

现有实验已完成 FF++ c23 的 5,000 段视频整理，得到 79,994 张人脸图片；整脸生成分支也已准备 LFW、FFHQ 镜像与 FairFaceGen 数据。这里保留重建步骤，实际模型效果见 [实验记录](EXPERIMENTS.md)。

<a id="ffpp"></a>

## FF++ 下载与预处理

先按 [官方说明](https://github.com/ondyari/FaceForensics/blob/master/dataset/README.md) 申请并取得官方脚本，保存到 tools/download-FaceForensics.py；该脚本、凭据和数据不提交 Git。下载范围为 original、Deepfakes、Face2Face、FaceSwap、NeuralTextures 的 c23，各 1,000 段。

```powershell
.\.venv\Scripts\python.exe scripts/download_ffpp.py --accept-terms --workers 4
```

仅在没有同类下载任务运行时启动或恢复。下载器校验传输长度、MP4 文件头与 SHA256 收据，不代替完整解码；磁盘低于 20 GiB 时停止。官方 train/val/test 为 360/70/70 对来源编号，对应 3,600/700/700 段视频。

## 运行方式

始终在仓库根目录（当前入口 `D:\deepfake-detection`）的 PowerShell 使用项目虚拟环境。

1. 重建视频清单：

```powershell
.\.venv\Scripts\python.exe scripts/prepare_ffpp_manifest.py
```

2. 重现首批处理：

```powershell
.\.venv\Scripts\python.exe scripts/prepare_ffpp_faces.py --pairs-per-split 1 --frames 16 --size 256 --workers 2
```

3. 验证首批真实/伪造图片均能组成模型输入批次：

```powershell
.\.venv\Scripts\python.exe scripts/check_data_loader.py data/manifests/ffpp-frames-preview-1-93e2b370610e.csv
```

4. 全量处理或中断后的恢复命令（仅在没有同类处理进程运行时执行）：

```powershell
.\.venv\Scripts\python.exe scripts/prepare_ffpp_faces.py --all --frames 16 --size 256 --workers 2
```

处理成功的组有缓存，恢复时跳过；改变抽帧数、裁剪尺寸、边界比例或检测权重会产生独立配置目录，不覆盖原始视频。新配置的清单名会包含新的配置编号。磁盘剩余不足 10 GiB 时停止新的目标组处理并记录错误。

完成后，全量清单为 `data/manifests/ffpp-frames-full-93e2b370610e.csv`。运行同一个 check_data_loader.py 验证它。若进度报告 state=incomplete，先检查 errors，不能把部分输出当成全量成功。

## 裁脸规则与已知限制

- 真实与各类伪造视频均使用相同 YuNet 参数：检测前将长边限制到 640，置信度阈值 0.8，选择最大人脸，扩大到 1.3 倍方框并限制在画面内，输出 256×256 PNG。
- 原始与伪造视频长度可能不同，不假定逐帧对齐，不把原始视频某一帧的框直接套到伪造视频。每个视频独立均匀抽样、检测。
- 没有人脸的采样帧记录在报告中并跳过，不以整张画面冒充人脸样本；多脸视频中最大人脸规则仍可能选错，需抽样查看。
- 顺序遍历所有帧，解码取出的采样帧，并核对帧遍历数与元数据。未转换保存所有原始帧，不将这一检查描述为逐像素完整质量审查。
- 图像帧保留 parent_video_id、source_video、frame_index、timestamp、crop_box、face_score 与来源分组。视频指标应先按 parent_video_id 汇总，再计算，不能把相邻帧当独立视频。
- 官方文件名编号字段保留为 target_id/source_id；这里只用它们隔离相关来源，不据此假定所有伪造方法的逐帧映射相同。

## 统一数据加载

`src/faceguard/data.py` 的 FaceImageDataset 接受相同 CSV 格式的图片清单；来自视频的帧也以图片形式加载。默认返回 RGB、float32、[0,1] 范围、CHW 形式的张量以及标签和来源信息。预训练模型需要的归一化由后续训练 transform 明确配置。

```python
from faceguard.data import FaceImageDataset
from torch.utils.data import DataLoader

dataset = FaceImageDataset(
    'data/manifests/ffpp-frames-preview-1-93e2b370610e.csv',
    split='train',
)
loader = DataLoader(dataset, batch_size=16, shuffle=True, num_workers=0)
batch = next(iter(loader))
images, labels = batch['image'], batch['label']
```

在自建脚本中先将项目 `src` 目录加入 Python 模块路径，方式可参考 scripts/check_data_loader.py。Windows 后续使用多进程 DataLoader 时需将入口放在 `if __name__ == '__main__':` 内；当前验证使用 num_workers=0。

新图片集需提供相同字段：sample_id、path、label（真实0/伪造1）、dataset、task、method、compression、target_id、source_id、group_id、split、media_type=image、provenance_status=verified。没有语义的压缩、视频编号字段可留空。保留可审计的来源后才能标为 verified；这一字段不是自动证明许可或标签准确性的工具。

加载器在过滤划分前检查全清单中的重复路径、编号和来源分组泄漏。派生数据应保留相同的全局 group_id；接入 AI-Face 时需要额外识别它与 FF++ 的重叠，不能只换 dataset 名称绕过分组规则。来源不明的第三方数据仍隔离，不自动进入正式加载器。

验证命令：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## 人脸检测权重

使用 OpenCV Zoo 官方 YuNet 2023mar：
https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet

模型下载到 weights/face_detection_yunet_2023mar.onnx；MIT 许可保存于 weights/YuNet-LICENSE.txt。模型 SHA256 为 `8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4`。

```powershell
Invoke-WebRequest -Uri 'https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx' -OutFile 'weights/face_detection_yunet_2023mar.onnx'
Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/opencv/opencv_zoo/main/models/face_detection_yunet/LICENSE' -OutFile 'weights/YuNet-LICENSE.txt'
```

<a id="sources"></a>

## 整脸生成与新增来源

- 当前配套：LFW、FFHQ-256 镜像真实照片，以及 [FairFaceGen](https://zenodo.org/records/17062365) 的 FLUX / SD3.5 种子包。先在根目录运行 scripts/download_fairfacegen.py，再按 [生成检测复现](TRAINING.md#generation) 下载真实照片并统一裁脸。
- 新来源实验使用过 OpenFake 与 FairFace 镜像，固定版本、数量、隔离和评测情况见 [实验记录](EXPERIMENTS.md#session-20261026)。
- 后续候选入口：[AI-Face](https://github.com/Purdue-M2/AI-Face-FairnessBench)、[DiFF](https://github.com/iLearn-Lab/MM24-DiFF)、[Community Forensics](https://jespark.net/projects/2024/community_forensics/)。这些是历史候选，不代表已下载或已验证；取得数据前核对条款、实际生成方法与存储需求。

<a id="new-data-20261031"></a>

## 2026-10-31 新到 DFF / GAN 数据

已读取 U 盘来源说明，并核对本地文件数量与 Parquet 标签元数据。最初从 U 盘复制 62,005 个文件、6,172,730,809 字节到 D 盘，逐文件 SHA-256 通过，U 盘原件保留；随后纳入上述统一目录。复制收据现为 `05_provenance/import-20261031/{summary.json,files.jsonl}`，来源原文为 `05_provenance/incoming-20261031/SOURCE.md`。归档完整性不等于全量解码、标签人工检查、去重、划分或训练完成。详细初次盘点在 `04_evaluation/new-data-20261031/inventory.json`，旧 outputs 路径仍可访问。

| 实际路径 | 本地内容 | 用途建议 |
| --- | --- | --- |
| `01_raw/generation/deepfakeface/wiki/wiki` | 30,000 张真实照片 | 补真实来源，与对应生成图同组划分 |
| `01_raw/generation/deepfakeface/text2img/text2img` | 30,000 张 SD1.5 生成图 | 整脸生成分支的新开发数据 |
| `01_raw/generation/gan140k/real` / `fake` | 各 1,000 张已导出 JPEG | 先用于数据接入检查，不代表完整 140k |
| `01_raw/generation/gan140k/validation-00000.parquet` | 10,000 条，真实 / StyleGAN 各 5,000 | 保留原发布划分，首轮建议作为外部开发评测 |

DFF 来源为 [OpenRL/DeepFakeFace](https://huggingface.co/datasets/OpenRL/DeepFakeFace)，不是 DiFF；发布说明确认 `text2img.zip` 是 SD1.5，`wiki.zip` 是 IMDB-WIKI 真图。两包本地相对路径一一对应，共 30,000 对；同名只表示来源关联，不能据此当作逐像素对齐图或篡改掩码。`00`–`99` 是目录分片，不能当作 100 位人物。本轮另取得官方 WIKI 元数据，全部 30,000 个真图路径匹配人名；规范化人名与 LFW 连接分组，不等同生物身份验证。

GAN 来源记录为 [TheKernel01/140k-Real-and-Fake-Faces](https://huggingface.co/datasets/TheKernel01/140k-Real-and-Fake-Faces/blob/main/README.md)。本地 Parquet 元数据确认 `label=0/1` 分别为 real/fake，`generator=0/1` 分别为 Real/StyleGAN。现有 `extract.py` 每类只取前 1,000 张，并重新以 JPEG95 保存；不要将这种顺序截取当随机代表样本，也不要把导出 JPEG 和同一 Parquet 原图重复计数。新预处理应直接读取 Parquet 图片字节，保留分片名、行号、原始 image.path、原发布 split、label 和 generator。

### 已完成的预处理与冻结划分

归档与正式推理迁移后，先固定 DFF 100 对、GAN 原 validation 真 / 假各 100 做旧生成模型开发检查，保留原始 Parquet 图片字节和行号。清单与分数在统一目录 `04_evaluation/new-data-20261031/development-baseline/`，成绩集中到 [实验记录](EXPERIMENTS.md#session-20261031)。这些已观察样本属于开发材料。

1. **统一裁脸已完成。** DFF 60,000 张沿用 YuNet 0.8、最大脸、1.3 倍、128px / JPEG90；58,371 张成功，1,629 张未检出人脸并单列。输出在 `02_processed/generation/dff-sd15-20261031-v1/`，框、原图路径、缓存与失败表在同版本 `05_provenance/`；抽看 16 组裁脸，未据此宣称全量人工标签核验。
2. **分组与去重已冻结。** WIKI 元数据在 `05_provenance/imdb-wiki/`，来自 [官方元数据包](https://data.vision.ee.ethz.ch/cvl/rrothe/imdb-wiki/)，有下载范围和成员哈希收据。DFF 真 / 假家族、人名与 LFW 同名（727 个重叠）连接；新旧候选及初始训练历史行逐图核对像素 SHA-256，以 pHash 距离 ≤ 6 连接相似图。与初始权重训练暴露冲突、跨 split 关联及精确重复共隔离 1,434 行。已看过的 DFF 开发家族 / 人名不进入新测试。
3. **实际划分：train 70,198 / val 14,697 / test 14,616。** 清单、分开的 train-val / locked-test 和协议在 `03_manifests/dff-sd15-20261031-v1/`。旧数据保留原划分角色，不把旧 test 回流；初始模型见过但后来删除的行仍参与泄漏检查。FFHQ 身份未知、人名及 pHash 有漏检可能，不能声称全部生物身份互斥。
4. **本轮训练限定 DFF + 旧生成数据。** 来源均衡混合 SD1.5、FLUX、SD3.5 与真实来源；验证集只用于选轮次和阈值，最终测试等候选锁定后再打开。训练配置和执行入口见 [复现说明](TRAINING.md#new-data-20261031)，实际实验结论以 `docs/EXPERIMENTS.md` 为准。
5. **GAN 仍作为外部开发检查。** 原 validation 不进入训练；固定 200 张与旧模型比较，也不称新盲测。需要 GAN 训练时应补原 train，并另保留隔离验证 / 测试。新数据仅补整脸生成，不能替代换脸视频、短暂篡改或真实定位标注；未知生成工具、独立真实来源和团队人工验收仍待补。

U 盘 `SOURCE.md` 原样保存在统一根目录的 `05_provenance/incoming-20261031/SOURCE.md`，原 `D:\datasets\SOURCE.md` 硬链接已删除；旧 `extract.py` 仍限量和重编码，不作为新正式预处理入口。说明中“旧生成数据本体未持有”与本机不符：LFW、FFHQ、FairFaceGen 与原始 / 清洗清单均保留，本轮已按训练历史一起复核。新增产物继续登记同一 DATA_CATALOG，不恢复旧数据目录。

## 现有数据复用与审计（2026-10-31）

`05_provenance/current-data-low-fpr-20261031/` 保存本轮 1,805 份 OpenFake 下载文件 / 收据核对、725 张裁脸像素复核、失败与隔离去向、缓存 metadata 和 FFHQ / GAN 分片盘点。下载字节哈希与发布方哈希分开记录：viewer 可能重编码，不冒充原发布字节；没有新增外部下载。

`03_manifests/current-data-low-fpr-20261031/` 的 `real-training-pool.csv` 从原 train 复用 3,000 张真图（DFF 1,000、FFHQ 1,000、LFW 700、Pexels 150、LAION 150），一行一个已有 component group 和像素哈希；`gpt-development.csv` 保留 GPT1 train 93 / val 25，`gpt-external-regression.csv` 单列 GPT1.5 / GPT2 外部历史回归 145 张。原路径、标签、group 和 split 不改，输出哈希在 `pool-protocol.json`，处理图像素重核 3,263 行。

这些是既有数据的复用子集，不是新增独立素材；GPT 开发部分仍只有 118 张，公开 metadata / 原标签不足以完成逐脸真值、生物身份或老人 / 美颜 / 相机 / 截图场景标注。外部回归不转入训练，原 GAN validation 继续训练外保留。数据总表同步登记新审计与清单目录，详细实验口径见 [现有数据低误报报告](EXPERIMENTS.md#current-data-low-fpr-20261031)。

<a id="unverified"></a>

## 来源不明的数据

2026-10-17 检查过用户提供的第三方归档，索引共 116,863 个文件，包含图片和视频，也含非人脸内容。提供方标签、分辨率、帧率与时长差异不能作为可靠真假依据。未获得原始来源、许可和标签依据前，不纳入正式训练或独立测试；本机检查收据为 outputs/local-data-inspection.json，清单为 data/manifests/third-party-unverified.csv。

## 划分原则

训练、验证和最终测试分开；同一人物（已知时）、源视频、原图及其编辑 / 压缩 / 裁剪版本保持同组。跨库检查精确重复与近重复，AI-Face 如包含 FF++ 派生帧需额外排除交叉泄漏。没有找到人脸的输入单独记录，不能标为真实。数据、模型、缓存与个人素材不放入 Git；素材许可不由项目 MIT 许可证代替。
