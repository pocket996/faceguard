# 慧眼辨伪 · FaceGuard

## 正式项目：谛听 · 青玉守真

本机数据统一入口为 **`D:\datasets\faceguard`**：原始素材、裁脸、清单、评测包、来源凭据与待核验数据分层保存。进入该目录先看 `README.md` 和 `DATA_CATALOG.csv`；旧数据文件夹和兼容链接已清理；历史清单通过代码中的路径映射读取。完整位置与维护规则见 [数据准备](docs/data-setup.md)。

从 2026-10-29 起，正式桌面应用以根目录 **`run_app.cmd` / `run_app.py`** 为入口，源码位于 **`src/faceguard/`**。界面沿用上次确定的第二版“谛听”：暖玉白、青玉与古金，左侧媒体、中央角色、右侧独立结果；可收起为透明桌宠。水墨远山、廊亭、月门和湖面现铺满工作台窗口，延伸到左右操作区后方；端坐谛听以脚边涟漪、接触暗部和同步淡倒影贴合水面，支持轻微背景视差；减少动效时固定，离开工作台时卸载背景并暂停角色。素材、生成提示词与实现边界见 [资源说明](src/faceguard/ui/assets/README.md)。`reference_run` 已封存为只读历史归档，当前训练说明统一维护在 `docs/TRAINING.md`，进展记入 `LOG.md`。2026-10-31 已将稳定推理迁入 `src/faceguard/inference/`，权重复制到 `weights/runtime/`；正式程序运行不依赖参考目录。

```powershell
# 在仓库根目录安装一次界面依赖，然后启动
.\.venv\Scripts\python.exe -m pip install -r requirements-ui.txt
.\.venv\Scripts\python.exe run_app.py
# 也可双击 run_app.cmd；直接启动桌宠使用 run_app.py --pet
```

**正式项目已接入原稳定双模型，支持照片双项检测、视频篡改采样、取消、逐脸 / 帧查看与报告。** 已提供本机照片 / 视频导入、预览、照片放大、透明桌宠、位置记忆、置顶和减少动效设置。工作台、桌宠与 **设置 → 角色立体预览** 均已接入同一形象的 **23 骨骼真实 3D 蒙皮角色**，包含呼吸、摆尾、眨眼、双眉 / 下颌轻微表情、点头与低头侧耳倾听。工作台动作保存当前姿态后平滑衔接；检测超过单次动作时持续倾听，结束 / 失败 / 取消后回待机。立体预览支持暂停 / 继续、拖动 / 滚轮旋转和恢复朝向。减少动态效果时角色、水纹和倒影均静止。保留原端坐造型；四足站立 / 行走、张嘴 / 舌牙和完整面部表演及跨窗口移动仍未完成，局部重建与材质接缝仍需精修，未称电影级成品。资产和制作说明随源码保存于 `src/faceguard/ui/assets/`。

点击“开始检测”后在后台加载并校验模型；照片分别输出整脸生成和面部篡改结果，视频分别显示原 16 帧整段基线和有采样上限的片段复核。检测期间谛听自动俯耳倾听，结束后平滑回正，开启减少动效时保持静止；已移除独立动作预览按钮。检测完成后停留工作台，右侧用大字、加粗与分级配色展示结果概览；点击“查看结果与热力图”才进入详情。结果页可选择人脸、查看视频采样帧与人脸放大图，右侧摘要支持较大字号与滚动，报告默认保存为 PDF，也可选择 TXT。多脸不混成一个真假概率，普通照片的篡改结果仍受视频帧模型适用范围限制。

**真实 Grad-CAM 热力图已接入。** 进入结果页时选择第一条人脸，在后台计算该人脸、该检测项目的关注区域；可切换“热力图叠加 / 并排对比”并调整叠加强度。照片分别解释整脸生成与篡改，视频解释所选采样帧中的人脸，不计算未采样帧。已计算的关注网格随历史结果保存，重开时直接恢复，不依赖临时 PNG。红色表示较强的、支持生成 / 篡改正类的关注响应；即使未检出，也可能存在局部颜色。每张图独立归一化，不能比较颜色来判断真假概率；全零响应保持透明并说明原因。热力图是粗粒度模型解释，不是精确篡改定位，也不提高检测准确率。PDF / TXT 报告目前仍只含文字。计算可取消；模型或原文件不匹配会提示重新检测，详细方法与实测见 [实验记录](docs/EXPERIMENTS.md#heatmaps-20261101)。

正式资源随代码保存在 `weights/`，队友拉取本次开发分支即可取得完整模型；其他电脑按 [环境说明](docs/TEAM_ENV_SETUP.md) 安装 PyTorch / OpenCV 等推理依赖，不需要训练数据。已有完整旧参考资源但需重建正式资源时，可在根目录执行一次：

```powershell
.\.venv\Scripts\python.exe scripts/migrate_reference_models.py
# 纯命令行检测；输出目录自行选择
.\.venv\Scripts\python.exe scripts/predict_official.py "D:\your-photo.jpg" --output outputs/prediction.json
```

运行资源为 `generation.pt`、`manipulation.pt`、`yunet.onnx`、`video_policy.json`、`YuNet-LICENSE.txt` 和 `manifest.json`，全部位于随 Git 跟踪的 `weights/runtime/`；已安装候选及其 manifest 同步位于 `weights/generation-candidates/`。`.gitattributes` 对 `weights/` 禁止文本换行转换，保留哈希所对应的原始字节。迁移脚本只复制稳定权重并检查哈希与预处理，不自动启用实验候选；旧权重和参考源码保留。模型详情见 [模型说明](docs/MODEL_CARD.md#official-20261031)。

**训练完成不等于应用已切换模型。** 设置、说明、技术详情与媒体预览等弹窗统一采用青玉 / 古金圆角卡片，标题栏、开关、模型下拉与操作区使用统一样式；图标已改为独角倾听姿态的矢量徽记。设置常规区域只显示当前模型与说明，技术详情也从设置进入；训练候选集中在默认收起的“设置 → 高级选项”，供对照评测，日常无需切换。初始默认仍为稳定版，已有选择继续保留；结果和历史技术记录保存实际版本与权重哈希，PDF / TXT 提供便于阅读的结论。切换后需重新检测，旧模型缓存和当前结果会清除，历史记录保留。候选独立存放在 `weights/generation-candidates/`（连同其 manifest 一起复制到其他电脑）；不会覆盖稳定资源。SD1.5 候选明显改善 DFF，但不能由此推断 GPT 或 StyleGAN 也能识别；未检出不等于真实。

```powershell
# 显式用已安装的 SD1.5 候选；不修改默认稳定模型
.\.venv\Scripts\python.exe scripts/predict_official.py "D:\your-photo.jpg" --task generation --generation-model dff-sd15-v1 --output outputs/candidate-prediction.json
# 联合实验版更敏感、误报更多，仅用于明确选择的实验对照
.\.venv\Scripts\python.exe scripts/predict_official.py "D:\your-photo.jpg" --task generation --generation-model gpt-sd15-v1 --output outputs/joint-prediction.json
# 验证整体误报目标约 2% 的标定版；仍可能漏检，不改变默认模型
.\.venv\Scripts\python.exe scripts/predict_official.py "D:\your-photo.jpg" --task generation --generation-model gpt-low-fpr-v1 --device cpu --output outputs/low-fpr-prediction.json
# 11 月 1 日完整训练后由验证选出的第 2 轮，仍为明确选择的实验版
.\.venv\Scripts\python.exe scripts/predict_official.py "D:\your-photo.jpg" --task generation --generation-model gpt-low-fpr-20261101 --device cpu --output outputs/low-fpr-trained-prediction.json
```

**2026-11-01 已完成此前中断的完整 3 轮低误报训练。** 验证选出第 2 轮，历史测试真图误报约 2.25%，用户 GPT 老人肖像现提示疑似生成；跨版本生成脸仍仅检出 31/158，不能视为 GPT 泛化问题解决。正式应用重启后，在“设置 → 高级选项”选“GPT联合 · 低误报训练版（11-01）”；默认仍为稳定版，原候选保留。结果与复现见 [完整低误报训练](docs/TRAINING.md#full-low-fpr-20261101)。

本机“GPT联合 · 低误报实验版”与高敏感联合版使用相同权重，只调整验证集标定阈值。验证整体误报约 2%，历史测试约 2.34%，用户 GPT 老人肖像在此阈值下仍漏检；这是检出 / 误报取舍，尚未解决 GPT 泛化。现有数据审计与 3,000 张真图训练复用清单见 [低误报与素材审计](docs/EXPERIMENTS.md#current-data-low-fpr-20261031)。

右上角“历史”与“设置”相邻，支持按名称搜索、照片 / 视频筛选、重新打开、删除与清空。历史元数据保存于系统应用数据目录的 `history.sqlite3`，包含本机路径、名称、媒体类型、大小、北京时间与真实检测结果；不复制原始媒体。导入记录标记“待检测”，完成 / 部分完成 / 取消 / 失败分别保存状态；重新打开可恢复结果且不重复写入，文件大小或修改时间改变后需重新检测，原文件移动 / 删除后会提示无法打开。选脸预览临时裁图在正常退出时清理。桌宠与工作台复用同一角色，展开 / 收起采用柔和淡出淡入，减少动效时立即切换；支持悬停回应与双击切换。结果页并排图同步缩放、拖动并可复位。快捷键见队友说明。骨骼角色当前在立体预览播放，替换主工作台 / 桌宠动效、行走与跨窗口移动仍待实现。

操作与验收见 [队友使用说明](docs/TEAM_QUICKSTART.md)。下文保留的 **v0.1.0 发布包和 `reference_run` 检测流程属于已有参考项目**，与正式应用的源码入口分开。

---

**一个在本机分析人脸照片和视频，提示 AI 整脸生成、换脸及面部篡改风险的检测研究原型。**

选择照片或视频 → 程序检测并裁出人脸 → 模型分析 → 查看检测提示与分数，保存中文报告。项目同时提供 Windows 桌面程序、命令行工具，以及从数据整理到训练、评估的实验源码，供日常体验、团队演示和研究复现使用。

**当前提供 v0.1.0 免安装预览版。检测结果仅供辅助判断，分数不是真假概率；未检出可疑特征也不能证明文件真实。**

[下载 Windows 版](https://github.com/pocket996/faceguard/releases/tag/v0.1.0) · [操作说明](docs/TEAM_QUICKSTART.md) · [队友环境安装](docs/TEAM_ENV_SETUP.md) · [能力与限制](docs/PROJECT_LIMITATIONS_PLAIN.md) · [模型说明](docs/MODEL_CARD.md)

## 能检测什么？

项目将两种问题分开检测：**“这张脸是否由 AI 生成”**与**“这张脸是否被换脸或修改”**。两项结果分别展示，不能据此确定文件使用了哪种制作工具。

| 检测任务 | 输入与例子 | 当前依据与范围 |
| --- | --- | --- |
| AI 整脸生成 | 含人脸的照片，例如 AI 生成的人像 | 发布版主要训练于 FLUX.1-dev、SD3.5 生成脸与真实照片；陌生生成器可能漏检 |
| 换脸 / 面部篡改 | 含人脸的照片或视频，例如视频人物被替换面孔 | 发布版主要训练于 FaceForensics++（FF++）的四类篡改视频帧；对普通照片的泛化仍有限 |

- **照片**：v0.1.0 默认检查整脸生成，也可手动切换到换脸 / 面部篡改；每次分析最大人脸。
- **视频**：v0.1.0 均匀采样最多 16 帧，每帧分析最大人脸，再汇总结果。它没有连续学习整段动作，短暂篡改可能被漏掉。
- **输出**：中文检测提示、模型倾向分数、技术详情及可保存的报告。
- **处理位置**：检测在本机进行，所选照片、视频不上传网络。

当前没有验证对无脸风景、商品图等任意 AI 图片的检测能力，也没有提供整段 AI 生成视频检测。未检测到可分析的人脸时，结果是“无法判断”。

## 直接使用：下载、解压、双击

适用于 **Windows 10/11、64 位 Intel/AMD 电脑**。发布包已包含运行时和推理模型，不需要安装 Python、CUDA、独立显卡或训练数据。

1. 打开 [v0.1.0 发布页](https://github.com/pocket996/faceguard/releases/tag/v0.1.0)，下载 **FaceGuard-v0.1.0-windows-x64-cpu.zip**（约 281 MB）。请选这个附件，GitHub 自动生成的 `Source code` 压缩包是源码。
2. **完整解压**，打开其中的 `FaceGuard` 文件夹，双击 **FaceGuard.exe**。请保留整个文件夹，程序依赖旁边的资源文件。
3. 点击 **选择照片** 或 **选择视频**，确认预览后点击 **开始检测**。照片若要检查换脸，在上方“检测项目”切换任务。
4. 查看右侧结果，需要时点击 **保存检测报告**。首次加载模型需要等待，视频耗时取决于长度与电脑性能。

目前没有 macOS、Linux、Windows ARM 原生发布包。已完成开发机上的解压启动与推理检查，其他电脑的兼容性仍需实际验收。

遇到启动或资源问题请看 [队友操作与排错说明](docs/TEAM_QUICKSTART.md)。发布包的启动日志位于 `%LOCALAPPDATA%\FaceGuard\startup.log`；反馈时提供版本和错误信息即可。

## 检测结果应该怎么看？

| 提示 | 含义 |
| --- | --- |
| 疑似 AI 整脸生成 / 疑似人脸篡改 | 模型分数达到该任务的提示阈值，需要结合来源和原始文件复核 |
| 未检出明显生成 / 篡改特征 | 本模型没有检出足够强的特征，仍可能漏检 |
| 未找到可分析的人脸 / 无法判断 | 没有足够输入供模型分析，不能归为真实 |

例如 **99/100 表示模型倾向分很高，不表示“有 99% 的概率为假”**。压缩、模糊、遮挡、侧脸、小脸和陌生生成工具都可能影响结果；生成与篡改分支也可能交叉触发。

当前不提供经过验证的精确篡改区域定位或生成器归因。开发版中的人脸框与视频复核时间范围用于帮助查看，不能作为伪造证据。更多解释见 [项目不足的大白话说明](docs/PROJECT_LIMITATIONS_PLAIN.md)。

## 发布版、源码开发版和实验模型有什么区别？

以下状态的核对日期为 **2026-10-27**，源码开发版对应本地分支 `codex/autonomous-20261026`。

| 版本 | 使用入口 | 包含内容 |
| --- | --- | --- |
| v0.1.0 发布预览版 | 下载 ZIP，运行 `FaceGuard.exe` | 可直接体验；照片默认整脸生成、视频检查篡改；最大脸 / 最多 16 帧规则 |
| 2026-10-26 源码开发版（历史归档） | 环境和模型准备好后，用根目录 `.venv` 运行 `reference_run/gui.py` | 照片对检出的人脸逐一检查生成与篡改，分别展示结果；支持人脸放大、取消检测；视频保留整段基线并增加局部复核提示 |
| 历史实验候选（归档） | `reference_run/run_experimental_demo.cmd` | 显式加载新生成检测与照片篡改候选；窗口标注“实验候选”，保留原稳定权重 |

**10 月 26 日的开发版功能和候选模型尚未打入 v0.1.0 发布包，也尚未同步到 GitHub `main`。** 克隆 GitHub 主分支得到的是已推送的代码；本地实验入口还依赖未随 Git 分发的模型与选型记录。

本轮开发增加了逐脸分析、视频局部复核、近重复数据审计和跨来源训练评估。实验候选在固定外部生成脸测试中，检出从 **25/158（15.8%）**提高到 **82/158（51.9%）**，同时陌生真实脸误报从 **15/1002（1.5%）**增加到 **57/1002（5.7%）**。这些数值仅针对本轮可检出、可裁剪的人脸样本，不能当成任意照片的准确率。

详细实验条件、照片篡改与短片段漏检情况，以及尚待改进的问题，见 [10 月 26 日结果与不足](docs/EXPERIMENTS.md#session-20261026)；复查步骤见 [本轮复现说明](docs/TRAINING.md#candidate)。

## 从源码运行

**体验当前谛听界面，使用根目录正式入口；v0.1.0 免安装包是历史预览版。** 以下源码安装命令以 Windows x64 / Python 3.11 为例，在仓库根目录执行。

### 1. 准备根目录主开发环境

训练和源码运行统一使用根目录 `.venv`。`reference_run` 只读保留历史实现和环境记录，不再作为日常开发或文档维护入口。

新电脑获取源码后，Windows x64 / Python 3.11 / NVIDIA GPU 的安装步骤为：

```powershell
git clone https://github.com/pocket996/faceguard.git
cd faceguard
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-gpu.txt
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

已有根目录 `.venv` 时先检查并复用现有环境；本机已安装可用的 GPU 版 PyTorch。无 NVIDIA 显卡的 Windows 队友可将 `requirements-gpu.txt` 换为 `requirements-cpu.txt`，用于 CPU 推理与小规模调试。使用完整的虚拟环境解释器路径即可，无需激活环境或更改 PowerShell 执行策略。

通用依赖已包含 Parquet 数据读取所需的 `pyarrow`。主环境配置、CPU/GPU 检查及小批量训练验收步骤见 [环境配置与验收](docs/TEAM_ENV_SETUP.md)。正式应用推理已经独立；部分训练兼容源码仍只读引用参考归档，具体范围见 [训练指南](docs/TRAINING.md)。

### 2. 准备正式模型资源

**本次开发分支已将检测权重与代码一同纳入 Git。** 拉取后核对下列完整正式资源，再安装推理与界面依赖；日常检测无需自行训练或另找模型：

```text
weights/runtime/
├── generation.pt
├── manipulation.pt
├── yunet.onnx
├── video_policy.json
├── YuNet-LICENSE.txt
└── manifest.json
```

已有完整历史资源时，可以在根目录运行 `scripts/migrate_reference_models.py`，只读导入旧资源并核验到 `weights/runtime/`；已有正式资源时直接复用，不向参考归档写入。候选资源独立保存在 `weights/generation-candidates/`。具体要求见 [模型说明](docs/MODEL_CARD.md#official-20261031)。

### 3. 打开正式界面或使用命令行

```powershell
.\.venv\Scripts\python.exe run_app.py
# 或双击 run_app.cmd
```

命令行也使用正式推理入口，结果保存到独立输出目录：

```powershell
# 照片：AI 整脸生成
.\.venv\Scripts\python.exe scripts/predict_official.py "C:\media\photo.jpg" --task generation --device cpu --output outputs/photo-result.json

# 视频：换脸 / 面部篡改
.\.venv\Scripts\python.exe scripts/predict_official.py "C:\media\clip.mp4" --task manipulation --device cpu --output outputs/video-result.json
```

默认视频使用采样复核；仅在复查旧规则时传入 `--sampling legacy`。普通照片由程序自行检测人脸，`--face-crop` 仅用于已经裁好的人脸图片。`reference_run` 的 GUI / CLI 仅保留历史追溯用途，不作为当前使用入口。

## 技术方案、数据与实验复现

推理主流程为 **读取媒体 → YuNet 人脸检测与裁剪 → 两个独立的 ResNet18 检测分支 → 阈值判断与结果展示**。两个分支均基于 ImageNet 预训练骨干微调；视频主要依据采样帧上的人脸外观，当前未训练时序模型。

| 分支 | 主要训练数据 | 可查阅的结果 |
| --- | --- | --- |
| 换脸 / 面部篡改基线 | FF++ c23：真实视频及 Deepfakes、Face2Face、FaceSwap、NeuralTextures；5,000 段视频预处理得到 79,994 张人脸图 | [训练与视频级测试结果](docs/EXPERIMENTS.md#ffpp) |
| 稳定整脸生成模型 | LFW、FFHQ-256 镜像真实照片及 FairFaceGen 的 FLUX / SD3.5；43,521 张可用人脸图 | [联合模型结果与范围](docs/EXPERIMENTS.md#generation-joint) |
| 10 月 26 日实验候选 | 在原数据基础上做相似组隔离，补充 OpenFake 等来源，并保留独立外部检查 | [实验报告](docs/EXPERIMENTS.md#session-20261026) |

训练集用于拟合模型，验证集用于选择模型与阈值，测试集用于锁定方案后报告成绩。**已见来源的高分不能代替跨来源效果**；数据来源、人物分组与近重复检查仍有局限，具体见各实验报告。

## 文档导航

| 需要做什么 | 阅读入口 |
| --- | --- |
| 查看项目进展与历史记录 | [项目日志](LOG.md) |
| 下载版操作与排错 | [使用说明](docs/TEAM_QUICKSTART.md) |
| 配置源码开发环境 | [安装与环境验收](docs/TEAM_ENV_SETUP.md) |
| 准备数据与清单 | [数据准备](docs/data-setup.md) |
| 训练、校准与复现实验 | [训练指南](docs/TRAINING.md) |
| 查看成绩、失败实验与限制 | [实验记录](docs/EXPERIMENTS.md) |
| 理解模型范围 | [模型卡](docs/MODEL_CARD.md) · [大白话限制](docs/PROJECT_LIMITATIONS_PLAIN.md) |
| 查阅旧版 Windows 打包记录 | [历史构建说明](docs/BUILD_RELEASE.md) |



历史实验使用 `reference_run/.venv`，其 `requirements-lock.txt` 保留当时的版本记录；当前主环境为根目录 `.venv`，根目录 `requirements-lock.txt` 记录本机 Windows x64 / Python 3.11 / CUDA 12.8 的完整版本。验收方法及适用范围见 [环境说明](docs/TEAM_ENV_SETUP.md)。

队友或 AutoDL 服务器应根据依赖清单重新创建环境。`.venv` 文件夹不作为跨电脑分发物；`requirements-gpu.txt` 使用官方 CUDA 12.8 索引按平台选择安装包，`requirements-gpu-windows.txt` 则是仅供 Windows x64 / Python 3.11 使用的直链备用方案。两个完整锁定文件含 Windows 地址，不用于 Linux。Linux/AutoDL 尚未实机验收；服务器训练使用命令行入口，桌面界面在本地运行。

## 目录导航

```text
run_app.cmd     正式应用双击启动入口
run_app.py      正式应用 Python 入口
src/faceguard/  正式应用、QML 界面、同源角色动效、历史记录与基础数据模块
reference_run/  只读历史归档；部分训练兼容依赖尚保留，停止新增维护
scripts/        环境检查、数据下载、FF++ 清单与抽帧裁脸
tests/          数据、推理、训练协议、视频采样与审计检查
docs/           使用说明、TRAINING.md 训练步骤、实验报告与限制
LOG.md          唯一项目日志
AGENTS.md       用户要求与持续维护约定
```

`reference-source.code-workspace` 仅用于在 VS Code 中查看历史参考实现，不作为日常维护工作区。`weights/` 中的运行模型、候选及配套文件随 Git 分发；数据集、虚拟环境、特征缓存和本机运行日志继续排除。文档中的 `data/`、`outputs/`、`artifacts/` 路径是历史说明或运行后产生的本机文件。旧 Release 附件另外包含其对应版本的运行时和必要推理模型，不代表当前开发版。

## 许可证与使用范围

自有代码采用 [MIT 许可证](LICENSE)。第三方组件、训练素材和模型的条款分别适用，代码许可证不授予其商用或再分发权利；当前尚未完成训练素材的完整许可与商用适用性核查，详见 [模型说明](docs/MODEL_CARD.md)。

本项目适合学习、实验与辅助复核。检测提示不能单独用于认定某个人或文件造假，也不能替代专业鉴定。
