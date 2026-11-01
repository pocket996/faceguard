"""Generate a plain Chinese report from frozen experiment results, without fitting anything."""
import argparse
import json
from pathlib import Path

from project_io import HERE,save_json,resolve_data_path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session',type=Path,required=True)
    args=parser.parse_args();base=args.session
    def read(name):return json.loads(resolve_data_path(base/name).read_text(encoding='utf-8-sig'))
    old=read('generation-external-original/metrics.json');new=read('generation-external-selected/metrics.json')
    a,b=old['results']['clean'],new['results']['clean']
    photo_old=read('photo-external-original/metrics.json');photo_new=read('photo-external-selected/metrics.json')
    map_probe=read('photo-map-validation/metrics.json')['controlled_mask_probe']
    label_probe=read('photo-label-validation/metrics.json')['controlled_mask_probe']
    video=read('video-policy/metrics.json');sparse=read('sparse-video/summary.json')['results']
    real_clips=[r for r in sparse if not r['label']];fake_clips=[r for r in sparse if r['label']]
    sparse_counts=dict(real_controls=len(real_clips),short_fake_clips=len(fake_clips),
        baseline_real_alerts=sum(r['legacy_alert'] for r in real_clips),local_real_alerts=sum(r['local_alert'] for r in real_clips),
        baseline_fake_alerts=sum(r['legacy_alert'] for r in fake_clips),local_fake_alerts=sum(r['local_alert'] for r in fake_clips),
        local_true_window_hits=sum(bool(r['local_window_overlaps_planned_event']) for r in fake_clips))
    gen_choice=read('generation-selection.json');photo_choice=read('photo-selection.json')
    summary=dict(generation=dict(original=a,selected=b),photo=dict(original=photo_old,selected=photo_new),
        sparse_video=sparse_counts,controlled_map_probe=map_probe,labels_only_probe=label_probe,
        selected_generation=gen_choice['selected']['name'],selected_photo=photo_choice['selected']['name'],
        test_used_for_reselection=False)
    save_json(base/'SUMMARY.json',summary)
    table=[]
    for source in ['OpenFake:gpt-image-1.5','OpenFake:gpt-image-2','OpenFake:nano-banana-pro']:
        x,y=a['per_source'][source],b['per_source'][source]
        table.append(f"| {source.split(':')[-1]} | {x['fake_images']} | {x['fake_images']-x['false_negatives']} | {y['fake_images']-y['false_negatives']} |")
    source_table='\n'.join(table)
    choices='\n'.join(f"| {r['name']} | {r['source_group_balanced_auc']:.4f} | {r['source_group_balanced_accuracy']:.4f} |" for r in gen_choice['candidates'])
    sparse_text=f"真实对照{len(real_clips)}段，原整段规则提示{sum(r['legacy_alert'] for r in real_clips)}段，局部规则提示{sum(r['local_alert'] for r in real_clips)}段；短暂替换片{len(fake_clips)}段，原整段规则提示{sum(r['legacy_alert'] for r in fake_clips)}段，局部规则提示{sum(r['local_alert'] for r in fake_clips)}段，其中提示时间范围碰到预设替换区间{sum(bool(r['local_window_overlaps_planned_event']) for r in fake_clips)}段。"
    text=f'''# 2026年10月26日自主实验：结果与不足（大白话版）

这轮从北京时间12:48开始，截止约16:48。**程序、数据清理和评估已经推进了一轮，但没有把“任意AI图片都能认出来”解决掉。** 稳定模型、原始数据和现有发布包均保留。本轮没有推送GitHub或重新发布Release。

## 先打开哪个

- 本机新源码界面：双击 `reference_run/run_demo.cmd`。仍用原稳定模型，但有逐脸结果、双项照片检查、视频两项结果、人脸放大和取消按钮。
- 本机实验候选：双击 `reference_run/run_experimental_demo.cmd`。窗口明确标注“实验候选”，不会覆盖稳定模型。
- GitHub原v0.1.0免安装包保留原样，不包含这轮开发版改动；兼容性和重新打包按你的要求暂缓。
- VS Code继续打开 `reference-source.code-workspace`。新实验脚本在reference_run，详细结果在outputs/autonomous-20261026/started-1248。

实验版**更容易抓到陌生生成图片，也更容易误伤真图片**，不能只看检出增加就说全面升级。

## 这次真的测到了什么

### 1. 新来源的生成图片

只用GPT1开发样本和原训练来源训练/选型，之后才打开GPT1.5、GPT2、nano-banana-pro及新真实来源考试。考试结果没有用于重新选模型或挪分界线。

| 外部生成来源 | 可分析脸数 | 原模型认出 | 验证集预先选定的候选认出 |
| --- | ---: | ---: | ---: |
{source_table}
| 合计 | 158 | 25 | 82 |

陌生真脸共1002张：原模型误报15张，新候选误报57张。分别约1.5%和5.7%。其中FairFace镜像992张，DOCCI仅10张；不是所有真实照片的误报率。最终考试针对“检出并裁下的最大脸”，不包括未找到脸的图片，也不能直接当成整张多人照片的成绩。

| 外部检查 | 原模型 | 验证选定的候选 |
| --- | ---: | ---: |
| 认出生成脸 | 25/158（15.8%） | 82/158（51.9%） |
| 误报真脸 | 15/1002（1.5%） | 57/1002（5.7%） |

新候选来自验证集选择的 **{gen_choice['selected']['name']}**，并非看完考试才选它。真实/生成数量差很多，因此没有只报一个“总准确率”来掩盖漏检。

### 2. 照片篡改

原视频帧模型直接用到普通照片，有较明显误报。先在300张来源标为真实的原图上复查，篡改分支提示37张，生成分支提示9张；两项直接合并判假会更糟。

补入真实照片、可控局部修改后，验证集选出的照片候选为 **{photo_choice['selected']['name']}**。外部FairFace真脸误报从225/992降到126/992，仍约12.7%，依然不适合当鉴定工具。DOCCI的10张真脸两者都未误报，样本太少不能据此放心。

照片候选的正例主要还是FF++视频帧与程序制造的局部修改，**缺少足够多真正被改过的普通照片、截图、美颜及局部AI编辑的独立考试**。降低真图误报，不等于这些新篡改已经都会识别。

### 3. 视频

先覆盖全段取样，再在可疑点附近补取，最多96个覆盖点和48个加密点；保留原来16帧规则做整段判断，另给短片段复核提示。不是把所有帧平均，也不是“有一帧高分就判假”。

后者在验证集140段真实视频中会误报86段，所以被弃用。仅用验证数据锁定“同一临时空间轨迹的相邻两帧均分”保守提示阈值，再看固定测试子集：

- 原整段规则：真实视频2/140触发，伪造视频134/140触发。
- 保守局部规则：真实视频0/140触发，伪造视频107/140触发。

局部规则在完整伪造片上检出更少，所以**没有替换整段规则**。0/140只是本次观察，不能说以后误报为零。该测试仍来自原FF++，不代表所有网络视频。

另造了同编码的真实对照与0.4/0.8秒替换片，用来检查平均分是否冲淡短暂问题。{sparse_text}

原计划8组，2组原片与伪造片无法可靠对齐，明确排除，最终6组18段。这个小练习有新编码和对齐假设，只是构造的压力检查，不能冒充全新视频数据集。时间范围是建议复核的邻域，不是精确证明篡改从哪一帧开始。

局部提示在12段短暂替换片中也只抓到3段，**短片段漏检还很明显，没有解决完**。这也是保留原整段结果、把新增能力称为复核提示的原因。

### 4. 你之前提供的GPT图片

修正了启动器中文路径编码后，已真正读入原图复查：实验生成分支返回“疑似生成”，分数约99.91/100；照片篡改分支返回“未检出明显篡改”。原文件校验值不变，标准化后的像素未出现在本轮训练或验证中。它是以前看过的用户回归图片，不是新盲测，也不能代替上面158张外部生成脸的成绩。没有上传或把原图放进仓库。

## 对你之前8个问题的回答，用这次结果来说

**1，数据少吗？** 不只是总数少。原来FLUX/SD3.5已足以把同来源分数练得很好，新GPT1验证样本却只认出6/25。加多来源后有进步，但陌生工具考试仍只认出82/158，还增加误报。同一个工具再加一万张，不保证补上这个缺口。

**2，能教它真正的破绽吗？** 做了一个可复查的尝试：从真图制造轻微错位、颜色和混合边界，并把已知修改区域的答案交给它。另做完全相同数据、只给真假标签的对照。两者验证分类指标约0.9401和0.9399，差距很小，不能宣称位置监督更好。

已知练习区域的像素排序指标约{map_probe['pixel_auc']:.3f}，无位置监督约{label_probe['pixel_auc']:.3f}，说明存在一些位置学习信号；但区域重合度约{map_probe['synthetic_proxy_iou']:.3f}，仍低，也没有真实伪造区域的人工答案。因此不把热区显示成“这里就是破绽”。这只是参考SBI/Face X-Ray思想的简化原创实验，不是论文复现，更不能用混合边界识别所有整脸生成。

**3，数据重复靠加量能解决吗？** 不能。43,521张图片筛出142对跨集合相似候选，查看前40对时发现至少一对明显同源照片，文件的人物标签却不同。142对不全是重复。为新实验保守隔离相关整组947张，原数据不动；老模型不会因为改了清单就自动变干净。还没有证明跨来源人物完全互斥，外观指纹也查不出所有变体。

**4，要给它考试纠正吗？** 训练像练习，验证像模拟考，用来选模型和分界线；最终考试只报成绩。看了最终错题再改模型，那份考试就成了开发材料，下一次需要新考试。本轮已经把这些顺序和文件分开，没有追着最终成绩改阈值。

**5，视频先统一抽帧再加密吗？** 已接入并实际检查。但抽得更多会增加误报，必须一起测。现在分别保留整段基线与短片段提示，给出可疑时间范围和最大采样间隔；采样间隙仍会漏，临时轨迹可能在人物交叉、切镜时串线，也没有真正学习连续动作。

**6，多人照片加训练就行吗？** 先修了只看最大脸的程序限制：对检出的脸逐一给结果，预览编号，可放大核对；一次最多32张，超额会说明。也补了一些真实照片的多脸裁剪。但小脸可能根本没被找到，真假混合的多人篡改照片考试仍缺；生成分支128像素输入也没凭空恢复细节。

**7，方案落地了吗？** 照片默认分别跑生成和篡改，两项、每张脸分别给分，不合成“真假概率”；还新增坏文件、无脸、部分失败和取消处理。新候选可单独打开，稳定权重不覆盖。分支之间会交叉触发，不能据此认定具体是哪种制作方式。

**8，兼容性呢？** 按你的要求暂缓新发布包、跨系统和其他电脑验收。本轮测的是这台机器源码环境，不能说所有队友电脑都已验收。

## 数据、环境、时间与保护

- 原43,521张生成分支数据做相似检查，新清单保留42,574张，隔离947张。隔离是保守处理，不是142对全部被证实有问题。
- OpenFake限量下载1805张，约1.595GB；716张可用，1080张无脸，9张相似组隔离。GPT1训练96张、验证25张，这个数量仍小。源标签为整图标签，对最大脸的适用性是一项研究假设。
- 新真实来源FairFace镜像仅下载一个约237MB验证分片；固定哈希选1000张，7张无脸、1张相似隔离，992张入外部考试。没有使用其人口属性做判断或人物识别。
- 本机RTX 5070 Laptop / 8GB显存、16GB内存完成；未租云服务器，未安装新Python依赖，未改系统电源、驱动或安全设置。仅额外取得官方ViT预训练权重作对照。
- 完成清理后重训5轮、多来源5轮、强化扰动5轮、位置监督4轮、标签对照4轮，以及冻结ViT特征的线性分类对照。不同模型使用同一验证人口排名，不按考试重排。
- 内存低于2GB保留线时，准备作业和一次训练被保护器停止；后改为串行、单进程加载完成。失败日志保留，没有关闭其他应用。GPU85℃、磁盘低于30GB、放电电池低于15%以及截止时间也会停止本次作业。
- 25项测试通过；真实模型双脸、无脸、坏文件、照片双项、放大、取消、视频两项流程均有记录。电脑锁屏期间没有完成界面外观人工验收，不能把自动流程检查当成视觉验收。

## 选型不是“模型越大就越好”

下表是开发验证集的来源/分组均衡指标：让少量新来源不会被几千张熟悉图片淹没；数值不是使用成功率，也不是最终考试成绩。

| 生成候选 | 排序指标AUC（越高越好） | 均衡判对指标 |
| --- | ---: | ---: |
{choices}

冻结ViT约330MB，比原ResNet18大很多，但这轮没胜出；强化压缩/模糊也没有胜出。它们都没有被硬塞进默认检测。

## 下一步优先做什么

1. 增加新工具和真正局部AI编辑的独立资料，同时补真实相机、截图、美颜、压缩等来源；保留后续新考试，别继续拿这次考试调参后仍叫盲测。
2. 先降低陌生真图误报，明确选择“宁可漏一些”还是“多提醒人工复核”；需要新的验证证据，不能拿本次外部57个误报直接挪线。
3. 给真实篡改区域补人工标注，检查位置监督是否在新来源有效；当前合成练习的地图不作为证据。
4. 多人真假组合、人物交叉、短片段、变帧率和长视频继续做独立检查。最后再按你确定的版本重新打包。

## 结果和复查入口

完整本机结果：`outputs/autonomous-20261026/started-1248/SUMMARY.json`。训练配置、来源/划分、模型校验值、验证排名、外部结果、失败和保护日志均在同目录；这些大文件不在Git中。

主要源码：`media_faces.py`逐脸裁剪；`face_analysis.py`两类任务；`video_analysis.py`采样/复核；`audit_near_duplicates.py`与`quarantine_similar_groups.py`查重隔离；`train_generation.py`多来源训练；`local_edit_supervision.py`、`train_photo_supervision.py`已知区域练习；`run_session_evaluations.py`先锁定后考试；`verify_session_integration.py`界面流程检查。

来源：[OpenFake固定版本与研究许可](https://huggingface.co/datasets/ComplexDataLab/OpenFake/blob/3247b942f18d39d1fd476b1077852af033d35d8c/README.md)、[FairFace原作者](https://github.com/joojs/fairface)、[FairFace镜像固定版本](https://huggingface.co/datasets/HuggingFaceM4/FairFace/tree/54d573cdb8b5af490ba8da9da2799628f6e5c496)、[SBI论文](https://arxiv.org/abs/2204.08376)、[Face X-Ray论文](https://arxiv.org/abs/1912.13458)。素材和模型权利不因自有代码采用MIT而改变；本轮不再分发数据或新模型。
'''
    (base/'REPORT_zh.md').write_text(text,encoding='utf-8')
    print('Generated report and SUMMARY.json in the session output directory.',flush=True)


if __name__=='__main__':main()
