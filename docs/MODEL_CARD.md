# FaceGuard 模型说明

## v0.2.0-rc.1 内测安装包（2026-11-04）

本版为 Windows 10/11 Intel / AMD x64 CPU 安装包，正式源码为 `src/faceguard/`，不依赖参考归档、系统 Python、CUDA 或训练集。软件版本升级没有重新训练检测模型：稳定生成 / 篡改权重仍为下方原有模型，四个已安装生成候选随包保留为高级选项，阈值及 manifest 原始字节保持一致；CPU-only 仅指部署运行时，不代表新模型或更高准确率。

照片逐脸分别检查生成 / 篡改，视频分别输出生成采样人脸线索与原篡改 16 帧基线 / 局部复核。视频生成项使用照片训练模型及照片阈值，未建立视频级准确率 / 误报保证，不检查音频或整幅场景。热力图支持两个方向与梯度 / 遮挡对照，仅作辅助解释；已有开发质量诊断未证明正类红区可靠定位，红色不是修改边界。模型对陌生 GPT 来源、StyleGAN 等仍有明显漏检，历史结果及范围见 `EXPERIMENTS.md`。

本包包含稳定与候选模型、YuNet、配置、manifest、许可证和运行 UI；不包含数据集、用户照片 / 视频或训练中间产物。逐资源哈希、依赖版本、冻结源码指纹及构建提交记录在包内 `BUILD_INFO.json`，独立干净电脑验收仍待用户完成。代码采用 MIT，第三方依赖 / 图像 / 训练数据各自的条款继续适用，商用适用性尚未完成完整核查。

<a id="official-20261031"></a>

## 2026-10-31 正式项目沿用的稳定模型

此次迁移保留旧模型、预处理和验证阈值，未训练或升级权重。正式推理代码为 `src/faceguard/inference/`，独立资源在 `weights/runtime/`，运行不导入 `reference_run`。`manifest.json` 记录完整 SHA-256、来源和训练元数据；`scripts/migrate_reference_models.py` 检查生成模型 READY 哈希、YuNet 预处理与视频 policy 对应关系，复制后逐文件复核，遇到已有不同文件则停止。

| 资源 | 选择及阈值 |
| --- | --- |
| `generation.pt` | 原 FLUX / SD3.5 联合版；阈值 `0.7077365219593048`；YuNet 256px 裁脸 → 128px / JPEG90 → 224px / ImageNet 归一化 |
| `manipulation.pt` | 原 FF++ c23 全网微调；照片帧阈值 `0.6040773391723633`、视频均值阈值 `0.49754807935096323`；256px 裁脸 → 224px / ImageNet 归一化 |
| `video_policy.json` | 与该篡改权重绑定；相邻临时轨迹帧均分，阈值 `0.9978253841400148`；沿用原验证规则 |
| `yunet.onnx` | 原 YuNet，置信度 0.8、扩大 1.3 倍、检测长边限制 640；保留裁剪取整方式 |

生成模型 SHA-256：`9717cf846c62846331061158c42173ada9ff1d105b8239b507cfe41679565a29`。篡改模型 SHA-256：`53c0edb0ceb076e23aa1d738b549e111176a5ddf1e89fa1cd21c9262381c3b7b`。10 月 26 日的生成 / 照片监督实验候选仍单独保留，未自动提升为正式模型；盘点在 `outputs/model-migration-20261031/model-inventory.json`。

照片默认逐脸双项检查；多脸保持各脸分数与阈值，不提供合并概率。普通照片的篡改分支仍是视频帧模型，未建立广泛普通照片验证。视频保留原 16 帧整段基线，另做有预算上限的覆盖 / 局部采样及片段复核；短暂事件仍会漏检，临时空间轨迹不是人物身份识别。真实关注热力图与像素定位本轮均未实现。

迁移验收：6 个 CPU 对照输入（真 / 生成 / 多脸 / 无脸照片、原规则与自适应视频）的旧字段、分数与判定一致，最大数值差 0；这属于功能一致性检查，不是新准确率。正式窗口已检查照片 / 视频后台推理、取消、逐脸与采样帧预览、JSON / 文本报告及历史恢复。检查产物在 `outputs/model-migration-20261031/`；新数据成绩单独记录在 [实验记录](EXPERIMENTS.md)，不与迁移验收混为一谈。

## v0.1.0 发布包历史说明

本发布版包含两个独立模型：

| 分支 | 训练与用途 | 没有证明的能力 |
| --- | --- | --- |
| AI 整脸生成 | LFW、FFHQ-256 镜像真实照片与 FairFaceGen 的 FLUX.1-dev、SD3.5；照片中的最大人脸 | 所有 GPT 版本、所有生成器、普通无脸 AI 图片 |
| 换脸/面部篡改 | FF++ c23 四种已知篡改方法；视频均匀采样最多16帧，每帧最大人脸 | 所有网络视频、短暂局部篡改、整段 AI 生成视频 |

两者都是 ImageNet ResNet18 骨干微调而来。生成分支统一裁脸到128像素并做JPEG90标准化，再送入224像素网络。它没有通过时序模型连续观看视频，也不会对所有人脸逐一追踪。

阈值仅从各自验证集确定。分数是未经概率校准的模型输出，不能按真实性概率解释。没有检测到脸时返回无法判断。

当前生成模型的已见来源测试分数很高，但只反映本次划分：FFHQ 镜像缺少完整身份标签，未完成跨来源人物与近重复审计，来源差异仍可能被模型当成捷径。第一版仅训练 FLUX 时，未见 SD3.5 的召回率只有18.03%；该失败实验保留在源仓库。后来的联合训练将两种生成器都纳入，因此 SD3.5 不再算当前版本的未见生成器。

一个用户提供的 GPT 肖像曾被联合模型识别为生成，分数约99.8/100；它没有用于训练或阈值选择，但也不能替代多版本、成规模的 GPT 测试。个人原图不包含在发布包中。

模型、就绪标记与 YuNet 文件校验值见 runtime_manifest.json。源代码、版本与构建依赖见 BUILD_INFO.json。构建包只包含推理需要的文件，不包含训练数据或个人回归图片。

自有代码按仓库 MIT 许可证提供；第三方程序与 YuNet 的版权和许可证随包保留在 THIRD_PARTY_LICENSES 与 weights 中。模型训练来源及其素材条款不因代码采用 MIT 而被替代；本项目尚未完成训练素材的完整许可与商用适用性核查。

来源：

- FF++：https://github.com/ondyari/FaceForensics
- FairFaceGen：https://zenodo.org/records/17062365
- FFHQ 官方：https://github.com/NVlabs/ffhq-dataset
- 使用的 FFHQ 镜像：https://huggingface.co/datasets/bitmind/ffhq-256
- LFW 下载校验配置：https://github.com/scikit-learn/scikit-learn/blob/1.6.1/sklearn/datasets/_lfw.py
- YuNet：https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet
- Torchvision：https://github.com/pytorch/vision
