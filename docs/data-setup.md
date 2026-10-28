# 数据准备与加载

现有实验已完成 FF++ c23 的 5,000 段视频整理，得到 79,994 张人脸图片；整脸生成分支也已准备 LFW、FFHQ 镜像与 FairFaceGen 数据。这里保留重建步骤，实际模型效果见 [实验记录](EXPERIMENTS.md)。

<a id="ffpp"></a>

## FF++ 下载与预处理

先按 [官方说明](https://github.com/ondyari/FaceForensics/blob/master/dataset/README.md) 申请并取得官方脚本，保存到 tools/download-FaceForensics.py；该脚本、凭据和数据不提交 Git。下载范围为 original、Deepfakes、Face2Face、FaceSwap、NeuralTextures 的 c23，各 1,000 段。

```powershell
.\.venv\Scripts\python.exe scripts/download_ffpp.py --accept-terms --workers 4
```

仅在没有同类下载任务运行时启动或恢复。下载器校验传输长度、MP4 文件头与 SHA256 收据，不代替完整解码；磁盘低于 20 GiB 时停止。官方 train/val/test 为 360/70/70 对来源编号，对应 3,600/700/700 段视频。

## 运行方式

始终在 `D:\faceguard` 的 PowerShell 使用项目虚拟环境。

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

- 当前配套：LFW、FFHQ-256 镜像真实照片，以及 [FairFaceGen](https://zenodo.org/records/17062365) 的 FLUX / SD3.5 种子包。先在根目录运行 scripts/download_fairfacegen.py，再按 [生成检测复现](../reference_run/README.md#generation) 下载真实照片并统一裁脸。
- 新来源实验使用过 OpenFake 与 FairFace 镜像，固定版本、数量、隔离和评测情况见 [实验记录](EXPERIMENTS.md#session-20261026)。
- 后续候选入口：[AI-Face](https://github.com/Purdue-M2/AI-Face-FairnessBench)、[DiFF](https://github.com/iLearn-Lab/MM24-DiFF)、[Community Forensics](https://jespark.net/projects/2024/community_forensics/)。这些是历史候选，不代表已下载或已验证；取得数据前核对条款、实际生成方法与存储需求。

<a id="unverified"></a>

## 来源不明的数据

2026-10-17 检查过用户提供的第三方归档，索引共 116,863 个文件，包含图片和视频，也含非人脸内容。提供方标签、分辨率、帧率与时长差异不能作为可靠真假依据。未获得原始来源、许可和标签依据前，不纳入正式训练或独立测试；本机检查收据为 outputs/local-data-inspection.json，清单为 data/manifests/third-party-unverified.csv。

## 划分原则

训练、验证和最终测试分开；同一人物（已知时）、源视频、原图及其编辑 / 压缩 / 裁剪版本保持同组。跨库检查精确重复与近重复，AI-Face 如包含 FF++ 派生帧需额外排除交叉泄漏。没有找到人脸的输入单独记录，不能标为真实。数据、模型、缓存与个人素材不放入 Git；素材许可不由项目 MIT 许可证代替。
