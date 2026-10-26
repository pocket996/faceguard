# 本机复查与继续实验

这轮是可审计的研究原型，不是所有AI工具的成品检测器。先读[实际结果与不足](AUTONOMOUS_SESSION_2026-10-26.md)。源码在本地分支 `codex/autonomous-20261026`，未推送。数据、模型、环境和个人图片不在Git里；只克隆不能直接重现本机全部训练。

## 本机打开

从项目根目录双击 `reference_run/run_demo.cmd`，仍用稳定权重。明确看新候选则双击 `reference_run/run_experimental_demo.cmd`，启动器会检查所选模型校验值。先选择文件，再开始检测；照片按编号逐脸看，可以放大，检测中可以取消。生成与篡改、视频整段与局部提示分别解释。

PowerShell也可以直接运行：

```powershell
cd D:\deepfake-detection
& .\reference_run\.venv\Scripts\python.exe reference_run\experimental_demo.py
```

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

以下命令复用本机已经审计的数据清单，输出到新目录。换电脑先按`reference_run/GENERATION_README.md`和FF++数据说明重新准备合法来源的数据、环境和初始模型。绝对路径清单需要重建，不能盲目照搬。

```powershell
cd D:\deepfake-detection
$sessionRoot = 'outputs/autonomous-20261026/started-1248'
& .\reference_run\.venv\Scripts\python.exe reference_run\train_generation.py --include-sd35 --manifest "$sessionRoot/openfake-prepared/combined_manifest.csv" --output outputs/my-generation-run --allow-openfake --source-balanced-selection --balanced-sampling --skip-test --epochs 5 --workers 0 --batch-size 32
& .\reference_run\.venv\Scripts\python.exe reference_run\train_photo_supervision.py --photos "$sessionRoot/photo-supervision-data/manifest.csv" --output outputs/my-photo-run --mask-weight 0.2 --epochs 4 --workers 0 --batch-size 32
```

单独做标签对照时改为`--mask-weight 0`并使用另一个输出目录。除位置监督权重外，数据、种子、批次和训练轮次保持一致。真实伪造掩码未知时，不得把合成练习答案说成真实位置标注。

训练/验证/最终考试保持分离；`--skip-test`让训练阶段不顺手打开考试。看过本轮外部错题后继续改模型，这批数据就属于开发材料，下一轮需要未使用的新考试。不要为了分数好看重复挪本次阈值。

本机临时PowerShell保护器是当日专用，截止16:48；不作为通用调度脚本发布。继续实验应设置新的明确期限、保持资源余量，不同时开多项重训练。此次16GB内存曾因多进程加载不足而停止，单进程串行才完成。无需为复现本轮另装绘图库。
