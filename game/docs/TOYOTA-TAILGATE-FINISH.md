# Toyota 样车 · 尾灯闪烁修复与细节打磨

本文保留第五轮修整与当时的验证结果；当前样车见 [轮眉与车身姿态调整](TOYOTA-ARCH-BALANCE.md)。

当前版本为 `05-tailgate-finish`。修正尾灯与旧尾门铰链重叠产生的闪烁，并处理备胎遮灯、重复挡泥板和附件连接不完整的问题。沿用上一版的直柱、平窗、88 cm 轮胎和 38 cm 正常悬挂行程。

[同机位对照与移动镜头视频](toyota-trail/05-tailgate-finish/index.html) · [尾灯近景](toyota-trail/05-tailgate-finish/20260926-proof-02/sample-tail-detail.png) · [正后方](toyota-trail/05-tailgate-finish/20260926-proof-02/sample-rear-flat.png)

## 找到的问题与修正

| 问题 | 原因与处理 |
| --- | --- |
| 尾灯下端、倒车灯与尾门连接处闪烁 | 旧铰链和灯罩的部分外表面同处游戏坐标 `Z=2.15 m`，相机移动时发生深度冲突。移除旧铰链，重新布置尾门铰链；灯座、橡胶垫和三段灯罩各有厚度与间距。 |
| 大备胎遮住右尾灯 | 88 cm 备胎沿用了较小轮胎的外侧安装点。备胎中心向内移动 20 cm、向上移动 12 cm，保持完整轮胎尺寸，配套调整支架并留出拖车口空间。 |
| 部分倒车灯被后保险杠遮住 | 重排灯组高度，使倒车灯位于保险杠上方；车灯挂点同步到实际灯罩位置。 |
| 尾门上的悬空铰链和附件 | 尾门改为上舱门、下尾门的结构，铰链落在实体边框上；备胎架补充保险杠转轴、锁扣、支撑杆与安装板。 |
| 后挡泥板重复 | 原尾部函数和侧面函数各生成了一套，尺寸和深度不同。统一为一套，并增加顶部压条与螺钉。 |
| 侧踏板支架未接到车架 | 延长横向支架并增加与纵梁接合的安装块。 |
| 爬梯、排气管的接续粗糙 | 爬梯弯折上端接入行李架并补夹箍，下端增加安装板；排气管接到底盘原有管路，从保险杠下方出管，避开牌照。 |

新增浅灯罩纹路、灯组固定螺钉、后雨刷、尾门把手、牌照与小牌照灯、空心拖车接口和排气尾管卷边。牌照灯与车灯开关联动；刹车灯、倒车灯保留各自状态。

尾门形式参考 Toyota 官方资料中介绍的 60 系上下分体式尾门配置，检索日期为 2026-09-26；资料也提及其他后门形式，因此本次选择用于这辆探险改装样车，不把它表述为所有 60 系的唯一结构。[Toyota 官方介绍](https://mag.toyota.co.uk/60-series-land-cruiser-next-big-thing/)

## 验证

在最终导出的 GLB 上执行检测，并保留旧模型作为对照：

- **共面表面检查：**近景模型从 7 对可见重叠三角面降为 0，远景从 6 对降为 0，车轮为 0。检查覆盖朝向一致、不同材质的轴向平面，并通过向外射线排除埋在内部的接合面。这项检查有明确范围，曲面穿插另由装配姿态与实机视角检查补充。
- **车灯遮挡检查：**近景与远景分别检查左右尾灯和倒车灯，每盏灯取 9 个位置，从正后方与固定跟车机位发射射线，144 次采样全部首先命中对应灯罩。旧模型能复现右尾灯及倒车灯被遮挡。
- **装配检查：**满舵、全压缩、全下垂、交叉轴等九种姿态通过；`npm run test:rig` 的 9 / 9 资产与物理回归检查通过。
- **形状保持：**八块玻璃仍共面，顶点与上一版一致；轮胎、轮圈、悬挂尺寸一致。驾驶物理源码和车辆参数与上一版逐字节相同。
- **实机检查：**12 组同机位截图、远近 LOD 往返、关闭 / 尾灯 / 刹车 / 倒车状态、牌照灯联动，以及新旧模型各 8 秒的尾灯移动镜头录制通过。另录制 12 秒实际交叉轴行驶，左右悬挂长度差达到 33.8 cm，最低直立度 0.969；无浏览器错误。
- **生产构建通过。**完整近景装配 192,834 三角面，远景 67,481；GLB 约 4.28 MB。

[修改前表面与灯组检查](toyota-trail/05-tailgate-finish/20260926-proof-02/surfaces-before.json) · [最终表面与灯组检查](toyota-trail/05-tailgate-finish/20260926-proof-02/surfaces-after.json) · [几何检查](toyota-trail/05-tailgate-finish/20260926-proof-02/geometry-check.json) · [实机记录](toyota-trail/05-tailgate-finish/20260926-proof-02/browser-report.json)

本轮交付绑定 `20260926-proof-02`。早期试做记录留在独立目录。上一轮媒体与模型快照保留原路径；当前模型、源码快照和哈希见 [交付清单](toyota-trail/05-tailgate-finish/manifest.json)。

## 文件与复验

[Blender 文件](../art/blender/vehicle_toyota_trail.blend) · [模型生成脚本](../art/blender/vehicle_toyota_trail.py) · [游戏 GLB](../public/assets/models/vehicle_toyota_trail.glb)

```bash
npm run assets:toyota
npm run test:rig
python tools/toyota-geometry-check.py /tmp/toyota-geometry-NEW.json
blender --background --python-exit-code 1 --python tools/toyota-surface-check.py -- public/assets/models/vehicle_toyota_trail.glb /tmp/toyota-surfaces-NEW.json --require-clean
npm run build
npm run test:toyota:browser
```

检查输出需使用新文件路径；构建与实机媒体采集使用新目录。试玩 URL 加 `?play&vehicle=toyota`。
