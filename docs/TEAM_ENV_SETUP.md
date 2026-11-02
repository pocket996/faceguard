# FaceGuard 队友环境安装指南

本指南用于在自己的 Windows 电脑上运行和修改 FaceGuard（慧眼辨伪）源码，以及准备后续模型训练环境。项目包含 AI 整脸生成与换脸 / 面部篡改检测，仓库名称统一为 `faceguard`。

如果只需要体验照片、视频检测，直接下载 [Windows 免安装预览版](https://github.com/pocket996/faceguard/releases/tag/v0.1.0)，完整解压后运行 `FaceGuard.exe`，不需要完成下面的开发环境安装。

## 1. 先确定安装哪一种环境

| 你的电脑与任务 | 选择 |
| --- | --- |
| Windows 10/11 x64，有兼容的 NVIDIA 显卡，参与模型训练 | GPU 环境 |
| Windows 10/11 x64，没有 NVIDIA 显卡，主要修改代码、运行检测或调试 | CPU 环境 |
| macOS、Windows ARM 或 Linux / AutoDL | 不照搬本指南；参考 本文末尾的云端训练说明，这些平台尚未完成实机验收 |

CPU 和 GPU 使用相同的项目代码与通用依赖，主要区别是 PyTorch 安装包与计算设备。CPU 也可做小规模训练调试，但完整训练速度需要单独评估。

**每个人都在自己的电脑上创建根目录 `.venv`。不要复制其他人的 `.venv` 文件夹，也不要把依赖安装到系统 Python。**

## 2. 安装三个基础工具

### Git：获取和更新代码

从 [Git 官方网站](https://git-scm.com/downloads/win) 安装 Windows 版。安装完成后，重新打开 PowerShell，执行：

```powershell
git --version
```

显示版本号即可。

### Python 3.11：运行项目程序

安装 **Python 3.11、64 位**，保留安装选项中的 **pip、Tcl/Tk 和 Python Launcher**。安装来源及 Windows 配置见 [Python 官方说明](https://docs.python.org/3.11/using/windows.html)。已有其他版本的 Python 可以保留，本项目明确使用 3.11。

重新打开 PowerShell，执行：

```powershell
py -3.11 --version
```

应显示 `Python 3.11.x`。小版本号不必与开发者电脑完全相同，不要因为默认 `python` 指向其他版本就直接使用它。

### FFmpeg：视频处理与环境验收

从 [FFmpeg 官方下载入口](https://ffmpeg.org/download.html) 选择 Windows 构建。解压后找到包含 `ffmpeg.exe` 的 `bin` 文件夹，将该文件夹加入 Windows 的**用户 Path** 环境变量。

例如实际位置是 `D:\tools\ffmpeg\bin\ffmpeg.exe`，应加入 Path 的是 `D:\tools\ffmpeg\bin`。不要将 ZIP 压缩包或 EXE 文件本身加入 Path。

重新打开 PowerShell，执行：

```powershell
ffmpeg -version
```

显示版本信息即可。若使用其他 FFmpeg 发行包，版本号可能与开发者不同，最终以项目的视频读写检查为准。

## 3. 获取源码并创建主环境

下面使用 `D:\faceguard` 举例，可以选择其他磁盘。当前安装指南及配套环境改动发布在 `codex/team-environment-setup` 分支，合并到 `main` 前请明确克隆该分支。先进入准备存放项目的父目录，再执行：

```powershell
git clone --branch codex/team-environment-setup https://github.com/pocket996/faceguard.git
cd faceguard
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe --version
```

后续所有命令都在项目根目录执行。根目录应能看到 `README.md`、`requirements.txt`、`scripts` 和刚创建的 `.venv`。

已有旧名称的仓库时，不必重新下载：先关闭占用项目的程序，根据需要将本地文件夹改名，再在仓库中更新远程地址：

```powershell
git remote set-url origin https://github.com/pocket996/faceguard.git
git remote -v
```

旧目录下的虚拟环境不应直接作为改名后的可迁移环境使用，应在新位置重新创建。环境目录可以重建，源码、数据与模型请保留。

## 4. 安装 PyTorch：CPU / GPU 二选一

### 有 NVIDIA 显卡：GPU 环境

先执行 `nvidia-smi`，确认系统能识别显卡。再运行：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-gpu.txt
```

项目目前对齐 PyTorch 2.9.0、torchvision 0.24.0 和 CUDA 12.8 构建，需要相容的显卡和驱动。不要只因为 NVIDIA 显卡存在就认定该组合一定支持；安装后必须通过下文的 GPU 计算检查。

若官方索引下载发生 TLS / SSL 错误，可使用针对 Windows x64 / Python 3.11 的官方直链备用文件：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-gpu-windows.txt
```

### 没有 NVIDIA 显卡：CPU 环境

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-cpu.txt
```

**CPU 与 GPU 的安装步骤选一个即可。** 不要依次安装两种 PyTorch。

## 5. 安装通用依赖并验收

两类环境都需要执行：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
```

`pip check` 应显示 `No broken requirements found.`。随后根据所选设备执行一条验收命令：

```powershell
# GPU 环境：
.\.venv\Scripts\python.exe scripts/check_environment.py --device cuda

# CPU 环境：
.\.venv\Scripts\python.exe scripts/check_environment.py --device cpu
```

检查包含实际前向 / 反向计算、图片和视频读写、Parquet 数据读写、FFmpeg 与依赖一致性。结果写入 `outputs/environment.json`，最终应为 `"status": "passed"`，且 `checks` 中各项均为 `passed`。

再运行已有代码测试：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

测试应以 `OK` 结束。基础验收与已有测试不需要下载完整训练数据。新电脑尚未通过这些检查前，不应认为开发环境已经安装完成。

## 6. 环境好了，还能不能直接检测和训练？

正式应用的检测入口现为根目录 `run_app.cmd` / `run_app.py`。本次开发分支将 `weights/` 与代码一同提交，完成前述推理依赖安装并拉取后，应具备完整 `weights/runtime/`：`generation.pt`、`manipulation.pt`、`yunet.onnx`、`video_policy.json`、`YuNet-LICENSE.txt`、`manifest.json`。已安装候选及其 manifest 同步位于 `weights/generation-candidates/`。启动界面不等于模型校验已通过，首次检测会核验资源；正式推理不需要训练数据，也不导入参考目录。

队友先拉取当前开发分支（合入主分支后再从 main 拉取），即可同时取得代码与模型。`weights/` 禁止文本换行转换，避免 Windows / Linux 间的许可证或配置字节变化破坏哈希。只需离线补模型时，也可使用配套模型包：先核对 `SHA256SUMS.txt`，再解压到**仓库根目录**，不要解压到已有 `weights/` 内导致 `weights/weights/`。例如在仓库根目录执行：

```powershell
Get-FileHash -LiteralPath "C:\你的下载目录\FaceGuard-models-20261102.zip" -Algorithm SHA256
Expand-Archive -LiteralPath "C:\你的下载目录\FaceGuard-models-20261102.zip" -DestinationPath . -Force
```

解压后应能看到 `weights/runtime/generation.pt`、`weights/runtime/manipulation.pt` 与 `weights/generation-candidates/manifest.json`。模型包只提供推理资源，不含 Python 环境、训练数据或源码；仍需完成本页依赖安装，并使用配套正式源码。模型资源在加载时按 manifest 核验；不要用重命名文件、删除校验或随机初始化来绕过缺失提示。


**运行环境、模型权重和训练数据是三样不同的东西。当前开发分支的 Git 克隆包含源码、依赖说明与 `weights/`，不包含虚拟环境或训练数据。**

| 目标 | 下一步 |
| --- | --- |
| 修改代码、运行已有测试 | 环境验收通过即可开始 |
| 用源码检测自己的照片 / 视频 | 按 [README 的模型准备步骤](../README.md) 安装完整 runtime 资源及 manifest；需要候选时一并安装 generation-candidates |
| 训练换脸 / 篡改模型 | 按 [数据说明](data-setup.md) 和 [FF++ 预处理说明](data-setup.md#ffpp) 准备合法来源的数据与清单 |
| 训练整脸生成模型 | 按 [生成检测复现说明](TRAINING.md#generation) 准备数据 |

正式应用需要完整的 `weights/runtime/`（包括 manifest、生成 / 篡改权重、YuNet、视频 policy 与许可证），准备方法见 [根目录 README](../README.md)。已有完整历史资源时可运行 `scripts/migrate_reference_models.py` 只读导入归档资源；不再按旧方法向 `reference_run` 复制模型或创建环境。

准备完成后，在仓库根目录运行：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-ui.txt
.\.venv\Scripts\python.exe run_app.py
```

也可以双击根目录 `run_app.cmd`。`reference_run` 已归档，旧 GUI 和虚拟环境不作为当前开发入口；训练说明统一见 [TRAINING.md](TRAINING.md)。

已准备好 FF++ 处理后图片与清单时，可进一步检查一次小批量训练及模型读写：

```powershell
# CPU 环境将 cuda 换成 cpu：
.\.venv\Scripts\python.exe scripts/check_environment.py --device cuda --training-smoke
```

这只执行两次优化更新，使用临时模型，不覆盖稳定权重，也不代表正式训练成绩。

## 7. 在 VS Code 选择正确解释器

打开根目录的 `faceguard.code-workspace`，或通过“Python: Select Interpreter”选择项目根目录 `.venv\Scripts\python.exe`。只阅读原型源码时也可打开 `reference-source.code-workspace`，它同样使用主环境。

确认解释器路径属于你自己电脑上的 `faceguard\.venv`。终端命令统一使用本文中的完整解释器相对路径，不需要激活脚本或修改 PowerShell 执行策略。

## 8. 常见错误

| 现象 | 处理方法 |
| --- | --- |
| 找不到 `py` 或提示没有 Python 3.11 | 检查 Python 3.11 与 Launcher 是否安装，重新打开终端 |
| 找不到 `requirements.txt` | 当前不在仓库根目录；先 `cd` 到包含 README 的文件夹 |
| `No module named ...` | 确认使用根目录 `.venv` 的解释器，并用它的 `-m pip` 安装对应依赖 |
| CUDA 不可用 | 检查 `nvidia-smi`、显卡/驱动支持，以及是否误装 CPU 版 PyTorch；无 NVIDIA 显卡应走 CPU 路径 |
| 找不到 FFmpeg | 检查加入用户 Path 的是否为包含 `ffmpeg.exe` 的 bin 目录，并重新打开终端 |
| 模型不存在、就绪标记不存在 | 环境安装不会自动带来模型；按 README 准备资源 |
| 训练验收找不到图片或清单 | 尚未准备本机训练数据；先完成基础验收和代码测试 |
| 下载中断或超时 | 网络恢复后重跑同一条安装命令；GPU 可尝试上述官方直链备用文件 |

反馈问题时，提供出错命令、完整错误文字、CPU/GPU 安装路线和 `outputs/environment.json`。不需要附个人照片或整个 `.venv` 文件夹。



## 主环境补充与云端训练


- Windows x64、Python 3.11.15。
- PyTorch 2.9.0 + CUDA 12.8、torchvision 0.24.0。
- RTX 5070 Laptop，约 8 GB 显存；系统内存约 16 GB。
- 通用依赖包含 NumPy、OpenCV、Pillow、pandas、scikit-learn、tqdm 与 pyarrow。
- 系统 FFmpeg 可在命令行调用；本地桌面界面需要 Python 的 Tk 支持。

根目录 `requirements-lock.txt` 记录本机已安装版本，含 Windows 专用 PyTorch 地址。原型目录的锁定文件作为历史记录保留。


### 小批量训练检查的含义

训练验收从 train 划分取两张真实和两张伪造人脸，执行两次优化更新并临时保存、重新加载模型。它使用随机初始化，不下载预训练权重，不覆盖稳定模型；通过检查不代表模型效果或全量训练性能。



### 何时使用 AutoDL

当前本机已完成现有 ResNet18 级别实验，历史主要训练耗时约 9–13 分钟，日常编写代码、界面开发、推理和小规模实验可继续在本地进行。具体历史范围见 `EXPERIMENTS.md#ffpp` 与 `整脸生成联合模型一节`。

出现以下实际需求时再考虑租服务器：

- 目标模型、输入尺寸或视频序列在合理减小批量后仍超出本机显存。
- 一次完整实验耗时已明显影响进度，需要跑多组参数、随机种子或消融对照。
- 需要长时间连续训练，或本机内存、存储和使用时间成为限制。
- 团队需要共同使用一个训练实例，并明确管理数据、作业与结果。

先在本地跑通小批次，记录显存和单轮耗时，再估算完整实验预算、选择云端资源。服务器主要承担正式训练；代码和界面仍可在本地开发，训练所得权重与模型定义、预处理及配置一同带回验证。

## 为 Linux / AutoDL 保留的安装路径

这是待实机验证的部署说明，当前没有租用服务器，也没有完成 Linux 验收。尽量对齐 Python 3.11、PyTorch 2.9.0、torchvision 0.24.0 与通用依赖；根据 GPU 和驱动选择适用构建，不直接安装本机 Windows 锁定文件。

在提供 Python 3.11、兼容 NVIDIA 驱动的 Linux 环境中，可以从以下流程开始：

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements-gpu.txt
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/check_environment.py --device cuda
```

服务器还需提供 FFmpeg 及 OpenCV 所需系统库，数据和输出路径要按实例目录重新配置。原型的 Windows 启动器不在服务器上使用，训练使用 Python 命令行入口。完整部署仍需训练与保存/加载验收，当前源码并未完成跨平台承诺。

不要复制 `.venv` 文件夹给队友或服务器；共享代码、依赖文件、数据准备步骤与验收命令，在目标机器上重建。参考 [Python 虚拟环境说明](https://docs.python.org/3.11/library/venv.html)、[PyTorch 对应版本安装说明](https://pytorch.org/get-started/previous-versions/)、[AutoDL 快速开始](https://www.autodl.com/docs/quick_start/)。
