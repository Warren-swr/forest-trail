# Scout / Kestrel：基于正式版的精修

2026-09-26 · 修订 `03-release-refinement` · 本地游戏资产与验证已更新

本轮直接以正式发布的 Scout 和 Kestrel 为基础重新精修。保留原有车身轮廓、分段车窗、双色装饰和整套可见探险装备；结合真实 Defender / 1979 Hilux 照片，改善面板、轮胎、固定支架、灯具及悬挂。精修风格对照已完成的 Toyota FJ60 样车。

- [正式版 / 本次精修交互对照](trail-companions/index.html)：两车各 10 个相同机位，含整体、车门、机盖、轮拱、货物及夜景。
- [两车总览](trail-companions/20260926-proof-03-release-refinement/release-refinement-comparison.jpg) · [Toyota 同机位风格对照](trail-companions/20260926-proof-03-release-refinement/style-lineup.jpg)。
- [Scout 悬挂视频](trail-companions/20260926-proof-03-release-refinement/scout-suspension.mp4) · [Kestrel 悬挂视频](trail-companions/20260926-proof-03-release-refinement/ranger-suspension.mp4)。
- [实拍来源、逐图观察与保留清单](../art/studies/trail-companions/03-release-refinement/reference/NOTES.md)。

## 正式版来源

基线为发布提交 `33439c37d453c87279797d7365d8874cff5b747a`，对应成功的 [Pages 部署](https://github.com/Warren-swr/forest-trail/actions/runs/36213839010)。此前已从线上下载模型和 sidecar，并与该 Git 版本逐字节核对；本轮继续校验这些冻结文件的 SHA-256。

生成器直接导入以下正式版源文件的不可变副本：

- `art/blender/reference/vehicle_scout_release.py`
- `art/blender/reference/vehicle_ranger_release.py`

它们与 `02-release-baseline/released/` 中的正式版脚本逐字节一致。新的 `art/blender/vehicle_release_refinement.py` 逐组件保留原版内容，只替换需要精修的面板、轮圈、轮眉、灯具、支架和运动部件。当前生产入口和两车包装脚本均指向这个新生成器。

前两轮 `01-balanced-trail` / `02-release-baseline` 及原媒体继续保留，作为已被替代的试作与比较校正记录；前两轮试作模型不参与本次“精修前”的对比，也不是本轮建模的车身基础。旧文件中的 `accepted` 名称是历史命名，不表示当前采用。开始重做时的模型、脚本、配置和报告保存在 `03-release-refinement/superseded/`。

## 实拍如何落实到模型

| 参考 | 实际使用的结构观察 |
| --- | --- |
| [传统 Defender 90 探险车](https://en.wikipedia.org/wiki/File:Defender90.JPG) | 直立平窗、车顶肩部曲面、四盏顶灯、带脚座的行李篮、外露铰链、通气管、窄轮眉与钢轮圈 |
| [NAS Defender 90](https://en.wikipedia.org/wiki/File:NAS_Land_Rover_Defender_90.jpg) | 机盖与翼子板分界、车门铰链、管状护件、脚踏及轮毂结构 |
| [Toyota 官方 1979 Hilux 图集](https://mag.toyota.co.uk/in-focus-1979-toyota-hilux-4wd/) | 单排驾驶室与独立货斗、门后通风片、三角窗、货斗冲压筋/轮罩/挂钩、窄竖尾灯、合页、六螺栓自由轮毂、整体桥与钢板弹簧 |

共下载并逐图查看 13 张实拍。2015 Defender 的后期凸起机盖与展车的现代灯组不移植到 Scout。照片保存在研究目录，未作为游戏贴图或模型资产使用。

## 原有细节的保留与精修

| 部位 | Scout | Kestrel |
| --- | --- | --- |
| 整体轮廓 | 保留 2.50 m 轴距、三段侧窗、橙色/奶油色搭配和双腰线 | 保留 2.62 m 轴距、短驾驶室、独立货斗、浅蓝/奶油色搭配和腰线 |
| 面板与车窗 | 连续起拱机盖、融入面板的压筋、弧顶与收边、平面深色车窗、贴合玻璃的滑窗分隔条 | 连续斜机盖、平面车窗、接入上下窗框的三角窗隔条、后柱通风片、弧顶与雨槽 |
| 原版装备 | 车顶篮架、4 顶灯、2 油桶、2 脱困板、行李、盘绳、千斤顶、铁锹、通气管、天线全部保留 | 双灯货架及斜撑、蓝盖冰箱、卷帐篷、2 行李袋、备胎、盘绳、红油桶全部保留 |
| 近景精修 | 脱困板真实把手开孔、千斤顶真实孔位、油桶压纹与绑带、货架夹具、通气管固定片、天线底座 | 连续弯管货架、脚座螺栓与加强片、货斗连续压筋、轮罩筋、绳钩、冰箱密封条/锁扣与贴合货物的绑带 |
| 车头 | 保留完整绞盘、前防护杠、保险杠、卸扣和号牌，精修灯碗/棱镜、绞盘脚座/卷筒/线束与插销 | 保留圆灯方框、格栅、镀铬保险杠、护块/拖钩和号牌，精修灯碗/棱镜与连接件 |
| 侧面与后部 | 保留加油口、镜子、脚踏、挡泥板、备胎、8 级后梯、尾灯、牵引点；补齐承重支架、踏面、摆臂铰链/锁扣与梯子脚座 | 保留镜子双支架、加油口、天线、挡泥板、尾门文字/把手/链条和拖球；补齐合页、压纹、牌照灯、绑扎锚点 |
| 轮胎与底盘 | 86 cm 胎径、五孔钢轮圈真实通风孔、窄 5.5 cm 轮眉、整体桥螺旋弹簧 | 84 cm 胎径、六孔钢轮圈真实通风孔、窄 4.5 cm 外沿、与车身同色的轮眉肩面、整体桥钢板弹簧 |

统一使用与 Toyota 一致的哑光车漆和不透明深色车窗。胎壁增高时固定轮圈尺寸；高低 LOD 都保留轮胎接地轮廓与轮圈开孔。原版可见装备并非通过增加面数替代。

## 悬挂和装配

| 参数 | Scout 正式版 → 精修 | Kestrel 正式版 → 精修 |
| --- | --- | --- |
| 轴距 | 2.50 → 2.50 m | 2.62 → 2.62 m |
| 轮距 | 1.65 → 1.78 m | 1.58 → 1.75 m |
| 胎径 | 76 → 86 cm | 72 → 84 cm |
| 正常悬挂行程 | 30 → 38 cm | 30 → 35 cm |
| 弹簧刚度 | 30,000 → 16,000 N/m | 25,000 → 15,500 N/m |
| 压缩 / 回弹阻尼 | 3,600 / 5,200 → 3,200 / 4,500 | 2,900 / 4,200 → 2,800 / 3,950 |
| 前 / 后防倾系数 | 9,000 / 6,000 → 7,200 / 4,600 | 7,000 / 4,000 → 6,200 / 3,400 |
| 四轮承重平台高度 | 30.4 → 46.3 cm | 31.8 → 47.9 cm |

正常行程不包含额外的 6 cm 缓冲限位。平台测试中，各版本先在平地静置，再以相同速度将左前轮平台从 0 抬到 50 cm；四轮接地且每轮载荷超过 100 N 才计作承重。正式版运行其冻结的原始物理与参数，精修版运行当前物理与参数。这是完整游戏车辆的对照，不是原厂悬挂参数或 RTI 测量。

Kestrel 的减振器上支点重新布置在正式版低货斗的下方，避免活塞杆穿过货斗地板；没有抬高货斗来躲开冲突。扩大轮距后，交叉轴状态的胎肩仍避开原有轮罩和装载区域。Scout 内轮罩和加油口按新轮胎包络重新布置；备胎架绕开倒车灯，保持实际支撑连接。

螺旋弹簧保持 18 mm 钢丝直径；钢板弹簧两端保持固定。四个弹簧分别形变，减振器筒体保持刚性，轮毂制动件随转向但不随车轮滚转。

## 验证结果与开销

- `npm run build`：类型检查和生产构建通过。
- 两车驾驶验收各 **15/15**：起步/倒车、单轮凸起、交叉轴、坡起/驻停、泥地、侧坡、涉水、绞盘、复位和跨帧率回放。
- 当前三车导出资产与接地回归 **9/9**；几何脚本验证最终 GLB、8 / 4 块主要平面车窗、两级轮胎包络和弹簧形变。
- 当前三车共 **27** 种极限姿态，未缩小网格，轮胎/车桥/弹簧/减振器无不允许的干涉。
- 两车近远 LOD 和车轮无检测到的可见跨材质共面重叠；尾灯与倒车灯的直视和追尾机位采样全部可见。
- 完整场景碰撞开启，约 **1.67 km** 环线均到达终点阈值：Scout **325 s**，Kestrel **322 s**，均 **0 次复位**，最低直立度均约 **0.96**。
- WebGL 实机验证包含两车各 10 组正式版/精修对照、辅助灯/刹车/倒车灯、近远 LOD 往返、三车切换和紧凑界面；无页面错误、请求失败或模型 fallback。
- 两段 12 秒悬挂视频直接录制真实游戏运动。最大左右悬挂差分别约 **38.4 / 35.8 cm**；减振器筒体缩放误差为 **0**。
- Toyota 的 GLB、sidecar、生成器和完整解析配置与已完成样车逐项一致。

| 完整装配三角面 / GLB | Scout | Kestrel |
| --- | ---: | ---: |
| 正式版（无独立 LOD） | 30,353 | 23,320 |
| 精修近景 | 235,196 | 230,803 |
| 精修远景 | 84,778 | 78,211 |
| GLB 文件 | 5.16 MB | 5.33 MB |

面数统计包含 Body、四轮和活动底盘，只用于说明几何开销，不作为精修质量指标。视觉检查以同机位图片、完整装备及装配/运动结果为准。近远 LOD 在 18–23 m 区间切换。本轮增加了细节，相比正式版并非减面优化。

## 复验

在 `game/` 下运行；输出目录应使用新的运行 ID，避免覆盖旧证据。

```bash
npm run assets:companions
npm run build
RIG_OUT=/new/run/rig.json npm run test:rig
PROVING_OUT=/new/run/scout.json npx tsx tools/proving.ts scout
PROVING_OUT=/new/run/ranger.json npx tsx tools/proving.ts ranger
VEH=scout FULL=1 npm run test:lap
VEH=ranger FULL=1 npm run test:lap
blender -b --threads 4 --python-exit-code 1 --python art/blender/verify_vehicles.py -- /new/run/clearance.json
python3 tools/trail-geometry-check.py /new/run/geometry.json
npx tsx tools/trail-suspension-study.ts /new/run/suspension.json
TRAIL_STUDY_OUT=/new/run/browser npm run test:companions:browser
```

浏览器脚本支持 `PLAYWRIGHT_MODULE` 和 `FOREST_CHROMIUM` 指定已有安装。原始运行目录为 `/mnt/runs/forest-trail/release-refinement-20260926-102050`；整理后的报告、视频与文件摘要位于 [本轮证据目录](trail-companions/20260926-proof-03-release-refinement/) 和 [manifest.json](trail-companions/manifest.json)。当前修改已落入本地游戏资源，发布状态由后续部署单独决定。
