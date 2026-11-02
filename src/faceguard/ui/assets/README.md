# 谛听角色展示资产

## 当前版本：全屏湖面与 23 骨骼角色（2026-11-01）

工作台背景已从中央画框扩展为全窗口水墨湖面，延伸到左右面板后方。用户确认保留谛听端坐造型；移除石台，以脚掌接触暗部、脚边涟漪和实时淡倒影衔接水面。背景绘画不包含角色，水岸抬高到画面上半部，保证角色脚下为连续水面。导航与操作区使用浅色遮罩保持文字可读；桌宠使用同一骨骼角色，隐藏水面效果。

正式背景为 `ink-lake-v2.png`（1672 × 941，2,620,768 字节，SHA-256 `3be9f5ad76375341dea92d8671c1f2c6fe0c3cf7e0713ce3ab8ff3be4302aeed`），使用内置 **imagegen** 在旧庭景上非破坏编辑两轮，原始生成文件保留，正式副本位于本目录。无需生成服务或本机 outputs 即可运行。

最终一轮提示词（上一轮将中央石地改为水面，本轮调整水岸构图）：

```text
Use case: precise-object-edit. Edit this existing garden artwork to fix its composition for a fullscreen app with a character placed at 60 percent image height.
Keep the same pavilion, moon gate, mountains, pine, warm ivory/celadon palette and painterly detail.
CRITICAL COMPOSITION CHANGE: the unobstructed lake water MUST begin at 48 percent of image height and fill the ENTIRE BOTTOM HALF from the center to both sides. The mountains, central shoreline, island rocks, garden walls, pavilion and moon gate must ALL move into the TOP HALF of the image; scale them down vertically/recede them into the distance as necessary. No rocks, trees, islands or shore objects anywhere in the central 65 percent of the lower half. The central foreground should be clean continuous still pale celadon water from halfway down all the way to the bottom edge. Only a few very small bamboo leaves may frame the very bottom extreme corners. Preserve fine ink-wash reflections and horizontal ripples in the water. No added character, no animals, no pedestal, no land under the character, no text, no UI, no logo, no borders. Full landscape artwork edge to edge.
```

`scripts/complete_diting_acting.py` 在 v5 场景上增加双眉和下颌三根骨骼，局部平滑蒙皮并重新限定每顶点最多四个归一权重；保留原网格、材质、双眼和眼睑，强化头颈低垂 / 侧耳的倾听动作。v6 共 23 根骨骼，三组 30 fps 动作分别为 Idle 181 帧、Respond 73 帧、Listen 121 帧。Blender 对全部 375 帧检查：脚掌位移最大为 0，起止几何差为 0，局部边长比第 99 百分位最大约 1.214；三个闭眼峰值的双眼瞳孔均被眼睑遮挡。这些是固定坐姿的形变检查，不等于所有自交或电影级外观验收。

可编辑场景、GLB 和逐帧审计保存于 `outputs/diting-3d/animation-v6/`；GLB SHA-256 为 `cfca3f6e88687804608a49d7f3c701bc3c2949024012c7cc47ea55b97eb58222`。运行资源已导入 `diting-motion-v6/`，工作台、桌宠、设置立体预览都使用这组真实蒙皮。工作台由 `../DitingPerformance.qml` 保存打断瞬间的骨骼姿态，插值 340 ms 后进入目标动作；检测中先进入倾听，再在中段保持细微耳尾活动与呼吸，结束 / 失败 / 取消后平滑返回待机。这里是姿态过渡与片段播放，没有宣称速度连续的全身动作混合系统。

`../DitingAvatar.qml` 使用 Qt Quick 3D 透明场景绘制角色；`ShaderEffectSource` 直接复用同帧渲染，由 `water-reflection.frag` / `.qsb` 生成压缩、衰减、微扰的倒影，未另起角色动画时钟。脚边接触暗部与低对比涟漪由 Canvas 绘制；这些为面向主视角的水面融合效果，不是完整物理水体或三维反射追踪。减少动态效果时骨骼、水纹、倒影扰动和背景视差全部静止，检测继续；离开工作台暂停角色并卸载背景，透明桌宠不显示水面。

制作与验证命令（在仓库根目录）：

```powershell
& 'D:/tools/blender/blender-4.5.15-windows-x64/blender.exe' -b --python-exit-code 1 --python scripts/complete_diting_acting.py -- --scene outputs/diting-3d/animation-v5/expressive/diting-expressive-v5.blend --face-report outputs/diting-3d/animation-v5/face-accepted/face-report.json --output outputs/diting-3d/animation-v6
.venv/Scripts/python.exe scripts/import_diting_animation.py --asset outputs/diting-3d/animation-v6/DitingActingV6.glb --balsam .venv/Lib/site-packages/PySide6/balsam.exe --output src/faceguard/ui/assets/diting-motion-v6
.venv/Scripts/pyside6-qsb.exe --glsl "100 es,120,150" --hlsl 50 --msl 12 -o src/faceguard/ui/shaders/water-reflection.frag.qsb src/faceguard/ui/shaders/water-reflection.frag
.venv/Scripts/python.exe scripts/check_courtyard_ui.py --record
.venv/Scripts/python.exe scripts/check_diting_motion_ui.py
```

截图、窗口检查与按真实时间录制的连续动作 GIF 位于 `outputs/ink-lake-v6-20261101/`，预览专项报告位于 `outputs/diting-3d/animation-v6/ui-check/`。建模与绑定已能支持当前坐姿交互，但张嘴 / 舌牙、完整面部表演、四足站立 / 行走 / IK 与跨窗口移动未完成；口鼻、折耳、闭眼褶皱和材质接缝仍需精修。其他电脑性能及用户外观验收不能由本机程序检查替代。以下为保留的历史制作记录，当前运行行为以本节为准。


## 历史：石台水墨庭院（2026-11-01，已由湖面替换）

正式工作台由 `../InkCourtyard.qml` 组合水墨庭景远景图、Qt Quick 3D 实时三层石台、石纹材质与接触阴影。保留原谛听形象与检测时的俯耳动作；角色继续使用现有 2.5D，古建 / 远山为绘制的远景，不据此称完整古建筑三维建模或完整 3D 角色已完成。视差联动鼠标注视方向，减少动效时固定相机；进入结果 / 历史页或收为桌宠后卸载庭院，返回工作台重新加载。两侧操作区保留可读背景。

两份素材均使用 **内置 imagegen** 生成，原输出保留在 Codex 的 generated_images 中，以下正式副本已经复制到项目，运行不依赖生成缓存、outputs 或外部 API。

| 正式资源（相对本目录） | 尺寸 | 字节 | SHA-256 |
| --- | --- | --- | --- |
| `ink-courtyard-v1.png` | 1672 × 941 | 2,958,640 | `7de290870faf779e767eb0e58a828c91764a8cb7f217b50c1e1ee4c559f31f2f` |
| `ink-courtyard-stone-v1.png` | 1254 × 1254 | 3,988,501 | `077fb7ae76c7b5c1c1ce2732be8101a34a7c30cb8b832b8dd5543112fabb47f3` |

庭景最终提示词：

```text
Use case: historical-scene. Asset type: finished landscape background artwork for a Chinese desktop application's CENTRAL character stage, not a UI mockup. Create a wide 16:9 ancient Chinese ink-wash courtyard garden with a convincing sculptural, three-dimensional diorama sense of depth, as if soft ink painting were built into real stone, architecture and mist. Elegant Song-dynasty literati garden, misty layered limestone mountains in the distance, an understated timber pavilion and curved tiled eaves in the left middle distance, pale garden walls and a moon gate at the right rear, sparse dark pine and bamboo framing the outer edges, a few weathered rocks, soft shallow reflections. Muted warm rice-paper ivory, celadon grey-green, charcoal ink, tiny aged bronze accents; match warm ivory desktop UI. Viewpoint: slightly elevated frontal perspective, soft morning light and ambient occlusion, distant mountains very pale, foreground ink details crisp. COMPOSITION CRITICAL: leave the central 45 percent of the frame OPEN and calm for a separately rendered large mythical guardian character. In the bottom-center foreground leave an empty flat pale-grey stone courtyard surface for an actual 3D circular stone plinth added later in code. Architectural scenery should frame the character from behind, not fill the central empty space. Foreground dark bamboo leaf clusters only at outer lower corners. Topmost and side edges fade naturally into warm off-white mist, no hard rectangular frame. Landscape artwork fills image, no white margins, no text, no calligraphy, no seals, no logos, no people, no animals, no guardian, no modern objects, no user interface, no drawn pedestal in the central landing area. Painterly ink textures and spatial depth rather than a flat ornamental wallpaper; quiet, refined, readable silhouette space, not oversaturated fantasy.
```

石纹最终提示词：

```text
Use case: stylized-concept. Asset type: square seamless albedo/base-color texture for the top of a real 3D ancient Chinese courtyard stone terrace, not a scene or object rendering. Orthographic straight overhead texture ONLY, fills the entire square edge to edge. Weathered pale grey limestone with broad irregular stone slabs, thin subtle charcoal fissures, delicate ink-wash cloud mottling, tiny desaturated grey-green moss stains only along a few cracks. Refined Song-dynasty temple courtyard, centuries old but cared for. Neutral cool-warm limestone GREY and ivory, no yellow/gold/olive cast. Physically matte surface with nuanced stone granularity visible at small size, light and understated, antique Chinese ink painting sensibility. Even flat diffuse lighting, NO directional lighting or cast shadows, no perspective, no stone pedestal shape, no side edges, no border, no objects, no people, no text, no symbols, no watermarks. Seamless/tileable appearance, fine believable texture rather than cartoon.
```

验收入口 `scripts/check_courtyard_ui.py`：检查素材读取、真实 3D 石台、倾听、相机 / 像素视差、减少动效、小窗口、页面 / 桌宠切换后的卸载与恢复。截图及详细记录保存在被忽略的 `outputs/ink-courtyard-20261101/`，本机自动验收不代替其他机器或用户的外观确认。

## 谛听角色素材与动态

`diting-v2.png` 使用内置 imagegen，以 `outputs/ui-concepts/2026-10-28/diting/01-character.png` 和 `05-desktop-pet-v2.png` 为身份参考生成透明角色资产。原效果图保留不改。资产已随正式源码保存，不依赖本机 outputs 目录。

本轮提示词：

> 从角色设定图左侧的大幅谛听提取单只完整端坐角色，忠实保留青玉虎首、成熟棕眼、雕刻古金独角、一立一垂的犬耳、细密象牙白云鬃、金边龙鳞、麒麟足与云纹狮尾；保持同一三分之四视角和原有陶玉材质。真实透明背景，无文字、无界面、无场景，不做球体或卡通化重新设计。

历史 2.5D 版本由 `DitingAvatar.qml` 及保留源码的 `shaders/diting.vert` / `diting.frag` 在同一张纹理上进行连续网格形变，实现呼吸、尾摆、点头和轻微侧倾。该版本已由第六轮真实蒙皮替换，旧图与着色器保留供溯源；下面第三至第五轮内容也是对应制作当时的历史记录。

2026-10-30：增加鼠标悬停时的小幅头部回应；减少动态效果时停用回应和连续形变，隐藏角色时暂停计时，重新显示后继续原动画相位。本轮未替换素材或新增 3D 模型。

2026-11-01：移除工作台独立的动作预览按钮，`DitingAvatar.listening` 绑定实际后台检测状态；检测时平滑低头侧倾，局部网格压低竖耳，伴随呼吸与涟漪，结束 / 失败 / 取消完成后回正。减少动态效果时停止这些形变，但检测继续；当前仍为同源 2.5D 网格，不是新增完整骨骼动画。顶点源码及重新编译的 `.qsb` 同步保存。`../brand.svg` 重新设计为青玉底、古金独角与象牙白侧首的矢量徽记，窗口左上角、弹窗和托盘共用此文件，可在小尺寸清晰显示；该徽记为手工矢量绘制，不是角色模型或 imagegen 资产。

## Blender 静态形体小样（2026-10-30）

后续使用 Blender 制作了独立的真实几何小样，构建脚本为根目录 `scripts/build_diting_study.py`。最新本机产物位于 `outputs/diting-3d/v10/`：`diting-static-study.blend`、静态 GLB、主视角 / 正面 / 侧面 PNG 与 `verification.json`。v10 同时保存 `build_source.py`，并把构建源码嵌入 Blender 场景的文本数据，方便核对该轮的实际源码。历史版本保留供对照；这些大型试制文件位于被 Git 忽略的 outputs，源码脚本可复现。

```powershell
& 'D:\tools\blender\blender-4.5.15-windows-x64\blender.exe' --background --factory-startup --python-exit-code 1 --python scripts/build_diting_study.py -- --output outputs/diting-3d/rebuild --views hero front side
```

小样使用独立网格和曲线制作头身、独角、不对称耳、云鬃、鳞片、麒麟足与狮尾；GLB 结构检查确认有真实几何且不含图片贴板。v4–v7 修正中：加宽并融合口鼻、补下眼睑、改变虹膜占比、修正耳壳法线以减少内耳穿插、压缩下身比例；把空心管状卷毛改为带螺旋凹槽的实体浮雕面，并合并相接云鬃、调整槽宽与平滑程度；主视角朝向和背景也重新对齐参考。v7 已渲染主视角、正面与侧面，并检查 GLB 几何与文件完整性。

v8–v10 进一步修正：通过布尔运算制作凹入头部的眼眶，眉骨 / 眼睑并入头部几何，加入虹膜细节；虎纹通过射线投射贴合头部表面，鼻孔调整到鼻部表面。云鬃改用沿 S 形路径扫掠、两端收尖并有纵向起伏的实体毛束，缩小毛束并打散排列，面颊两侧补细束。v10 三视角渲染、静态 GLB 结构和有限坐标检查完成。

脸部神态仍偏卡通；侧面毛束的厚度与衔接、耳部、独角雕刻及玉质仍未达到原图的精细度。**这是未通过外观验收的静态形体研究，不是精细还原或最终角色。** 当前约 78 万导出顶点、348 个网格，未经实时性能优化；未绑定骨骼、未制作角色动画、未接入正式 UI。程序化材质未做运行时烘焙，GLB 外观尚未与 Blender 渲染逐项核对，结构检查通过不代表实时外观通过。现有 2.5D 资产继续使用。

## 原角色图重建路线（2026-10-30）

用户反馈 v10 仍相差很远后，转为验证原图约束的网格重建，暂停继续累加程序化云鬃 / 脸部参数。输入仍为上面的 `diting-v2.png`，没有另画一个角色来替换目标。

本机外部工具目录为 `D:\tools\diting-reconstruction\`：独立 `.venv` 安装重建依赖；通过 `.pth` 只读复用根环境已有的 Torch / torchvision / NumPy，未更新根环境这些包。使用 [腾讯官方 Hunyuan3D-2 源码](https://github.com/Tencent-Hunyuan/Hunyuan3D-2)，固定提交 `f8db63096c8282cb27354314d896feba5ba6ff8a`；[官方 Hunyuan3D-2mini 权重](https://huggingface.co/tencent/Hunyuan3D-2mini)固定修订 `f90a0f7df7d5e6f71109cf333f6a95a0ae3194a6`，下载 mini 基础版形体权重，SHA-256 为 `3cc66f3bea33e4062b7dbc875ffe1d70c4888914aec3e91b60f94e9bd01b522b`。官方 LICENSE / NOTICE 随工具保留；本项目不打包这些权重或生成工具。

重建入口为 `scripts/reconstruct_diting.py`。它以 meta 参数构造后直接赋入权重，避开标准 CPU 初始化时出现的本机原生崩溃，并移除官方推理权重本就不包含的点云编码模块；用于图像到形体解码，不用于训练。支持按可用显存选择整模块卸载或 CPU 图像编码加分层 GPU 卸载，使用上游层次表面采样和标准 marching cubes，不安装自定义 CUDA 扩展。固定上游版本的层次采样将浮点网格间距误转为整数，会产生空表面；本机对外部工具源码做了两处 dtype 修正，补丁保存在 `scripts/hunyuan3d_float_coordinates.patch`，未直接修改正式应用或参考检测代码。

```powershell
# 首次检出固定上游源码后应用；已应用时不用重复执行。
git -C D:/tools/diting-reconstruction/source apply D:/faceguard/scripts/hunyuan3d_float_coordinates.patch
& 'D:\tools\diting-reconstruction\.venv\Scripts\python.exe' -u scripts/reconstruct_diting.py --source-root D:/tools/diting-reconstruction/source --model-dir D:/tools/diting-reconstruction/models/hunyuan3d-dit-v2-mini --output outputs/diting-3d/reconstruction-v1 --resolution 384 --chunks 8000
& 'D:\tools\blender\blender-4.5.15-windows-x64\blender.exe' --background --factory-startup --python-exit-code 1 --python scripts/preview_diting_reconstruction.py -- --mesh outputs/diting-3d/reconstruction-v1/diting-reconstructed.ply --output outputs/diting-3d/reconstruction-v1/review
```

第一轮输出约 67 万顶点 / 133 万三角面，真实网格 GLB / PLY、四个泥模视角、`.blend`、中间潜变量、参数、环境与失败尝试保存在被忽略的 `outputs/diting-3d/reconstruction-v1/`。几何坐标有限，但原始网格非封闭，不是适合直接绑定的成品。坐姿、前腿厚度与尾部体积较 v10 改善，脸部及云鬃细节仍模糊，独角 / 折耳 / 尾部存在位置偏差，外观未通过验收。

`scripts/texture_diting_reconstruction.py` 在真实网格上制作原图投影诊断，产物在 `projection/`，参考图已打包进 `.blend`。这是单视角投影，用于暴露形体对不齐、侧转拉伸及未覆盖表面；侧背面保留泥模，不是完整多视角纹理，不导出伪装为成品的纹理 GLB。完整纹理、拓扑整理、绑定动作和 UI 接入仍需另行完成。正式角色继续使用现有 2.5D 资产。

第二轮使用同一官方仓库修订中的 mini-turbo，图像编码为 1022 像素、形体潜变量为 3072 个；该权重 SHA-256 为 `bdbcef30dd0149a281e17d5b5b1fdad1122c904e098a42f3100e04e03c247bc4`。采用官方示例的 5 步生成，512 网格提取，输出在 `outputs/diting-3d/reconstruction-v2/`，约 135 万顶点 / 270 万三角面。实际生成与导出成功，坐标有限；仍为非封闭、未绑定的高面数静态研究，不能因模型生成成功而勾选外观或实时性能验收完成。

```powershell
& 'D:\tools\diting-reconstruction\.venv\Scripts\python.exe' -u scripts/reconstruct_diting.py --source-root D:/tools/diting-reconstruction/source --model-dir D:/tools/diting-reconstruction/models/hunyuan3d-dit-v2-mini-turbo --output outputs/diting-3d/reconstruction-v2 --steps 5 --resolution 512 --chunks 8000 --offload model
```

第二轮进一步使用 `scripts/diting_projection_alignment.json` 中的参考点，在相机平面内连续变形真实网格，保留深度，修正独角、折耳、口鼻与尾端位置；不是平面图片变形。结果在 `reconstruction-v2/aligned/`，两个视角 PNG 与已打包参考图的 `.blend` 均保留。此变形只按当前参考视角校准，不能代替完整雕刻；侧转仍可见投影拉伸、鼻口 / 折耳局部错位及未覆盖表面，开放边界和浮片也待清理。眼部、完整纹理、拓扑、绑定与正式 UI 接入均未完成。

```powershell
& 'D:\tools\blender\blender-4.5.15-windows-x64\blender.exe' --background --factory-startup --python-exit-code 1 --python scripts/texture_diting_reconstruction.py -- --scene outputs/diting-3d/reconstruction-v2/review/diting-reconstructed.blend --reference src/faceguard/ui/assets/diting-v2.png --alignment scripts/diting_projection_alignment.json --output outputs/diting-3d/reconstruction-v2/aligned
```

## 第三轮材质与正式项目立体预览（2026-10-30）

用户认可第二轮主视角方向后，保留同一几何与原图身份，使用 `scripts/refine_diting_surface.py` 清理小于 300 顶点的独立浮片并消除退化边。辅助材质通过内置 imagegen 的 identity-preserve 编辑生成，输入分别为清理后网格的左 / 右 / 背正交泥模，以及上面的 `diting-v2.png` 配色与身份参考；要求保持相机、姿态、轮廓、单角和不对称耳，只补青玉皮肤、象牙云鬃、古金鳞边，背面不出现脸部。生成图复制到项目 `outputs/diting-3d/refinement-v3/textures/`，原始生成文件保留；用途与校验值记录在同目录 `provenance.json`，这些图片是辅助材质参考，不是新的几何模型或最终 3D 渲染。

`scripts/bake_diting_materials.py` 使用参考相机可见性与法线权重优先保留原图正面，用另外三视角补充侧背颜色；透明边缘与未覆盖的深凹 / 底部表面使用象牙基础色。减面后通过 UV 烘焙生成一张 4096×4096 颜色纹理，导出标准材质 GLB，不依赖运行时多相机着色或本机 outputs 目录。完整高面数场景与辅助图打包到 `projected-v2/diting-multiview-high.blend`，减面场景为 `baked/diting-material-study.blend`，都在 `outputs/diting-3d/refinement-v3/` 下。

正式源码新增 **`diting-static-v3.glb`**：300,002 个三角面，149,995 个减面几何顶点；GLB 因 UV / 法线缝拆分为 212,232 个顶点，文件 19,079,884 字节，SHA-256 为 `92c13ace122e68849d7f0c4bc9d3266f15e8dfdd4dd776fcfbf9bfce7dc42450`。包含一张内嵌纹理，无骨骼和动画。`scripts/check_diting_asset.py` 实际回读该文件渲染主 / 背视角，确认坐标与 UV 有限、保持真实深度、没有外部纹理依赖；位置重合顶点焊合审计后开放边 / 非流形边均为 0。报告和回读渲染位于 `refinement-v3/verification/`。

正式应用 **设置 → 查看角色立体预览** 使用 `DitingVolume.qml` / Qt Quick 3D 加载这个 GLB，可拖动、滚轮或按钮旋转和恢复朝向；关闭后卸载场景。实际窗口回归覆盖加载、转动后像素变化、复位和释放，9 项控制器检查通过，截图仍在 `outputs/desktop-ui-check/`。工作台 / 桌宠继续现有 2.5D 动效；立体预览是静态资产交付，口鼻 / 折耳接缝、完整手工材质、适合形变的拓扑、蒙皮和骨骼动作仍待完成，其他机器实时性能尚未验收。

```powershell
& 'D:\tools\blender\blender-4.5.15-windows-x64\blender.exe' --background --factory-startup --python-exit-code 1 --python scripts/bake_diting_materials.py -- --scene outputs/diting-3d/refinement-v3/clean/diting-cleaned.blend --reference src/faceguard/ui/assets/diting-v2.png --materials outputs/diting-3d/refinement-v3/textures --output outputs/diting-3d/refinement-v3/projected --stage project
& 'D:\tools\blender\blender-4.5.15-windows-x64\blender.exe' --background --factory-startup --python-exit-code 1 --python scripts/bake_diting_materials.py -- --scene outputs/diting-3d/refinement-v3/projected/diting-multiview-high.blend --output outputs/diting-3d/refinement-v3/baked --stage bake --faces 300000 --size 4096
```

## 第四轮基础骨骼与动态预览（2026-10-30）

`scripts/rig_diting_character.py` 在第三轮减面场景上建立 14 根坐姿控制骨骼：根部、骨盆、胸部、颈部、头部、双耳、三段尾部及四个固定脚掌控制。原网格、UV 和烘焙材质保留，首轮使用区域平滑权重，每顶点保留最多 4 个骨骼影响；脚掌保持固定，头颈、胸部及尾部有独立权重，不是旋转整只模型来代替动作。该绑定针对小幅坐姿动作，尚无完整四足肢体 / IK 或面部绑定。

制作三组 30 fps 动作：`Idle` 约 4.8 秒，包含胸部呼吸、微点头与轻摆尾；`Respond` 约 1.4 秒，轻点头并回正；`Listen` 约 3.2 秒，侧头 / 侧耳后返回。工程为 `outputs/diting-3d/animation-v4/diting-rig-v4.blend`，带 1 个蒙皮、14 个关节和 3 个动画的交换文件为同目录 `DitingRigV4.glb`（23,370,344 字节；SHA-256 `81955de45a2f01a1d6b941f947cf1e13a23262356766860d6e5b868b1cb0f252`）。作者脚本及姿态报告随工程保留。

本机 Blender 实际评估 3 个动作的起点、峰值和终点：所有坐标有限、脚掌位移保持 0，各动作回到起始姿态；检查局部边长变化以限制首轮拉伸。完整指标见 `animation-v4/rig-report.json`，这不是大幅行走、所有自交或面部变形的完整验收。

运行时采用 [Qt 官方 Balsam 资产转换](https://doc.qt.io/qt-6.8/qtquick3d-tool-balsam.html)，由 `scripts/import_diting_animation.py` 把 GLB 转为 `src/faceguard/ui/assets/diting-motion-v4/` 下的 QML、`.mesh`、纹理和 `.qad` 轨道。生成组件包含真正的 `Skin`、14 个关节与逆绑定矩阵。脚本将三个时间线改成互斥控制，切换前复位绑定姿态，避免骨骼被多个动作同时覆盖。运行无需 Blender、Balsam 或 GLB 解析；静态 v3 文件保留。

`DitingVolume.qml` 已切换到这组蒙皮资源，默认循环待机，动作按钮播放回应 / 倾听后回到待机，支持暂停 / 继续和旋转。减少动效时停止、回正，恢复后从待机开始；关闭预览卸载实例。当前快速打断先复位再开始，尚未做跨动作姿态融合。工作台 / 桌宠仍为原有 2.5D 展示，面部 / 眨眼、四足行走及跨窗口移动继续待办。

本机实际窗口检查 `scripts/check_diting_motion_ui.py` 覆盖骨骼属性及渲染像素变化、固定根部、两个单次姿态、返回待机并继续播放、切换清除胸部缩放、暂停 / 继续、减少动效静止和关闭释放。报告、截图及真实程序录屏位于 `animation-v4/ui-check/`，`motion-demo.mp4` / `.gif` 为实际窗口播放，`nod-demo.gif` 是该录屏的点头片段。口鼻 / 折耳及材质接缝仍需精修，未将本轮写成完整角色或全机器性能验收完成。

```powershell
& 'D:\tools\blender\blender-4.5.15-windows-x64\blender.exe' --background --factory-startup --python-exit-code 1 --python scripts/rig_diting_character.py -- --scene outputs/diting-3d/refinement-v3/baked/diting-material-study.blend --output outputs/diting-3d/animation-v4
.\.venv\Scripts\python.exe scripts/import_diting_animation.py --asset outputs/diting-3d/animation-v4/DitingRigV4.glb --balsam .venv/Lib/site-packages/PySide6/balsam.exe --output src/faceguard/ui/assets/diting-motion-v4
.\.venv\Scripts\python.exe scripts/check_diting_motion_ui.py --record
```

## 第五轮大幅坐姿表演与眼部几何（2026-10-31）

用户明确指出第四轮幅度不足，目标是保持同一形象的 3D 动画电影角色。本轮延续已认可的原图重建形体、青玉 / 象牙 / 古金配色、独角和一立一折耳，未改成另一个卡通角色。它仍是表演原型，不能把增加动作和眼部几何当作电影级角色已完成。

`scripts/build_diting_face.py` 在第三轮材质场景上制作内凹眼窝、有曲率的棕色虹膜 / 瞳孔、上下眼睑和眼线。眼睑边缘采样原脸部颜色并匹配法线，避免独立零件的亮边与反向暗面；清理部分薄胡须碎片，补六根渐细胡须。鼻部覆盖研究会与原纹理错位，默认不启用 `--sculpt-nose`，当前鼻口仍需精修。最终眼部候选在 `outputs/diting-3d/animation-v5/face-matched/`；其他 face / acting 目录只是中间研究，不是新的验收入口。

`scripts/animate_diting_expressive.py` 通过 `create_rig(..., expressive=True)` 重做大幅变形权重，旧脚本默认小幅版本保持可复现。头 / 颈 / 胸连续分配影响，口鼻随头部保持形状；尾部按网格连通分离尾簇，再沿表面扩散权重，修复尾巴同高度区域被颈骨牵动的问题。增加双眼、双眼睑和两根辅助控制，合计 20 根骨骼；每顶点最多 4 个影响。仍是坐姿骨架，四个脚掌保持固定，没有四足行走 / IK。

三组 30 fps 动作重新制作：`Idle` 约 6 秒，包含呼吸、尾摆、耳部轻弹与两次眨眼；`Respond` 约 2.4 秒，先抬头预备，再明显点头、回弹和收住；`Listen` 约 4 秒，头颈胸共同转向并侧倾，耳尾跟随，停留后回正。采样姿态中头部相对绑定姿态的最大角度变化分别约 3° / 20.4° / 36.4°，不是整只模型旋转代替动作。动作切换先以 220 ms 将当前关节姿态平滑回正，再开始新片段；尚非任意两个动作之间的完整混合系统。姿态快照显式复制向量 / 四元数，避免 Qt 值类型引用随关节变化而破坏过渡。

最终工程与交换文件在 `outputs/diting-3d/animation-v5/expressive/`：`diting-expressive-v5.blend`、`DitingExpressiveV5.glb`、`motion-report.json`、姿态 PNG 和构建源码。GLB 为 **23,803,996 字节**，SHA-256 为 `a740ead8439cc21a5ecc831b14a8ff912edf2e988dfe5b2407a717faf3b23743`，含 1 个蒙皮和 3 个片段。各动作抽样的脚掌最大位移为 0，局部边长比第 99 百分位最大约 1.193，坐标有限，起止姿态一致；额外沿主相机射线检查三个闭眼峰值，双眼瞳孔顶点全部被眼睑遮挡。这些检查不能覆盖所有自交、视角或行走形变。

运行资源由同一个 Balsam 转换脚本生成到 `src/faceguard/ui/assets/diting-motion-v5/`，`DitingVolume.qml` 已接入；静态 v3、动态 v4 和 `reference_run` 保留。普通运行无需 Blender、生成模型或本机 outputs。工作台 / 桌宠当前仍为原 2.5D，结果查看 / 真实热力图待接入状态、历史与设置入口保持原有流程。

本机控制器的 9 项检查通过。专项窗口检查覆盖真实蒙皮与像素变形、眼睑位移、大幅姿态、单次动作返回待机、快速切换平滑回正、暂停 / 继续、减少动效与关闭释放。详细报告与 MP4 / GIF 位于 `outputs/diting-3d/animation-v5/ui-check/`，`character-demo.mp4` / `.gif` 是角色区域剪辑；录屏按固定时间逐帧采样真实 Qt 场景，避免显卡繁忙时跳过动作，不是离线替换角色图片。本轮完整界面回归也已通过，记录仍集中在 `outputs/desktop-ui-check/`。

**仍待完善：** 鼻口几何与纹理的错位、折耳和鬃毛接缝、闭眼的自然褶皱 / 表情、眉部与嘴部独立表演、动画电影级材质与光照、完整四足骨架与行走、主工作台 / 桌宠接入和跨窗口移动；其他电脑性能及用户最终外观验收未完成。

```powershell
& 'D:\tools\blender\blender-4.5.15-windows-x64\blender.exe' --background --factory-startup --python-exit-code 1 --python scripts/build_diting_face.py -- --scene outputs/diting-3d/refinement-v3/baked/diting-material-study.blend --output outputs/diting-3d/animation-v5/face-matched
& 'D:\tools\blender\blender-4.5.15-windows-x64\blender.exe' --background --factory-startup --python-exit-code 1 --python scripts/animate_diting_expressive.py -- --scene outputs/diting-3d/animation-v5/face-matched/diting-face-v5.blend --face-report outputs/diting-3d/animation-v5/face-matched/face-report.json --output outputs/diting-3d/animation-v5/expressive
.\.venv\Scripts\python.exe scripts/import_diting_animation.py --asset outputs/diting-3d/animation-v5/expressive/DitingExpressiveV5.glb --balsam .venv/Lib/site-packages/PySide6/balsam.exe --output src/faceguard/ui/assets/diting-motion-v5
.\.venv\Scripts\python.exe scripts/check_diting_motion_ui.py --record
```

修改着色器后需使用已安装 PySide6 提供的 `qsb.exe` 重新编译对应 `.qsb` 文件（Windows 根目录）：

```powershell
.\.venv\Lib\site-packages\PySide6\qsb.exe --glsl "100 es,120,150" --hlsl 50 --msl 12 -o src/faceguard/ui/shaders/diting.vert.qsb src/faceguard/ui/shaders/diting.vert
.\.venv\Lib\site-packages\PySide6\qsb.exe --glsl "100 es,120,150" --hlsl 50 --msl 12 -o src/faceguard/ui/shaders/diting.frag.qsb src/faceguard/ui/shaders/diting.frag
```
