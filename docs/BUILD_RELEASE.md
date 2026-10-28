# 构建 Windows CPU 免安装包

构建环境必须与训练环境隔离，使用 Windows x64 / Python 3.11。不要把含 CUDA 的训练环境整体打进发布包。

```powershell
python -m venv reference_run/.release-venv
reference_run/.release-venv/Scripts/python.exe -m pip install -r reference_run/requirements-build.txt
reference_run/.release-venv/Scripts/python.exe reference_run/build_windows_release.py
```

构建前需要准备经过核验的两个训练结果和 YuNet：

- reference_run/artifacts/model_finetuned.pt
- reference_run/artifacts/generation/joint/model.pt
- reference_run/artifacts/generation/joint/READY.json
- reference_run/weights/face_detection_yunet_2023mar.onnx
- reference_run/weights/YuNet-LICENSE.txt

脚本使用 PyInstaller 单文件夹模式，运行目录基于 EXE 所在位置，而不是开发机路径；模型和就绪标记按白名单复制。打包结果包含运行资源 SHA256 清单、构建信息、源码版本、模型说明和第三方版权通知，不包含训练数据、个人样本或开发虚拟环境。

输出：reference_run/release-output/FaceGuard-v0.1.0-windows-x64-cpu.zip 与 SHA256SUMS.txt。

已有 EXE 而只更新模型和说明时，可以加 `--skip-freeze`；修改运行时代码后必须重新完整构建。Windows 便携包没有包含系统 Python 的绝对路径依赖。

## 打包后验证

使用本地已知来源的样本，不把样本打入发布包：

```powershell
reference_run/.release-venv/Scripts/python.exe reference_run/check_portable_release.py `
  --zip reference_run/release-output/FaceGuard-v0.1.0-windows-x64-cpu.zip `
  --generation-photo 'D:/你的生成照片.png' `
  --real-photo 'D:/你的真实照片.jpg' `
  --fake-video 'D:/你的篡改视频.mp4'
```

验证脚本在新目录解压，并移除 PATH 上的 Python、禁用有效网络代理，检查启动、真假照片、篡改视频、无脸输入和损坏资源拒绝。它是在构建主机上的隔离目录检查，不能代替真实队友电脑验收。

`publish_github_release.py` 使用 Git 已配置的 GitHub 凭据，凭据只在内存中，不打印、不写入发布文件。它先创建预发布草稿，上传并核对附件大小及校验值，最后发布。草稿上传失败可根据本地草稿记录恢复，已公开的同名版本不会自动覆盖。

若 Python 上传遇到连接中断，可传 `--transport curl` 使用 Windows 原生 curl；认证头经 stdin 提供，不出现在进程命令行。草稿附件会按校验值去重，失败的同名附件可在重试时替换。发布后使用正式标签的附件地址，不能沿用草稿阶段的 untagged 地址。

官方参考：[PyInstaller 使用说明](https://pyinstaller.org/en/stable/usage.html)、[运行时资源路径](https://pyinstaller.org/en/stable/runtime-information.html)、[GitHub Release API](https://docs.github.com/en/rest/releases/releases)。

<a id="v010"></a>

## v0.1.0 发布记录

### 队友如何使用

1. 下载附件 **FaceGuard-v0.1.0-windows-x64-cpu.zip**，不要下载 Source code。
2. 完整解压，打开 FaceGuard 文件夹，双击 **FaceGuard.exe**。
3. 选择自己的照片或视频，点击蓝色「开始检测」。

不需要 Python、CUDA、独立显卡或训练数据。适用 Windows 10/11 x64 Intel/AMD 电脑；目前没有 macOS、Linux 或 ARM 原生包。首次加载模型需等待，视频处理速度取决于长度和电脑性能。

### 包含功能

- 照片默认检测 AI 整脸生成；视频默认检测换脸/面部篡改。
- 照片要查换脸时，可切换顶部「检测项目」。
- 中文步骤引导、照片/视频首帧预览、真实读取进度、结果解释和报告保存。
- 运行时、两份检测模型与 YuNet 随包提供，资源缺失或损坏会给出说明。
- 文件在本机处理，不上传网络。个人照片、训练数据与数据集示例未包含在发布包中。
- ZIP 校验值见 SHA256SUMS.txt；资源与构建信息见包内 runtime_manifest.json / BUILD_INFO.json。

### 已做检查

新目录解压并从 PATH 移除 Python 后，检查启动、生成照片、真实照片、篡改视频、无脸输入、资源损坏拦截。尚未在每位队友的实际电脑上验收。

### 当前能力边界

这是实验预览版。生成模型主要训练于 FLUX 和 SD3.5，陌生生成工具仍可能判断错误；分数不是真实性概率。视频最多采样16帧，每帧看最大人脸，未提供整段 AI 生成视频检测。代码的 MIT 许可证不替代模型训练素材或第三方组件的适用条款。

详细的大白话解释：[项目不足与改进](https://github.com/pocket996/faceguard/blob/v0.1.0/docs/PROJECT_LIMITATIONS_PLAIN.md)。
