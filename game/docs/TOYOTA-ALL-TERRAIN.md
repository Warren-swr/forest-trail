# Toyota 样车 · 大轮胎与悬挂配套精修

本文保留第四轮调整与当时的验证结果；当前样车见 [尾灯闪烁修复与细节打磨](TOYOTA-TAILGATE-FINISH.md)。

当前版本为 `04-all-terrain`，基于上一轮直柱平窗样车继续打磨。采用直径 88 cm 的轮胎，保留原钢轮圈尺寸和旧版的方正车身、深色玻璃及哑光材质。胎壁变厚，轮拱、轮距和悬挂同步调整。以下尺寸与测试均指游戏模型和物理配置。

[同机位实机对照](toyota-trail/04-all-terrain/index.html) · [轮胎近景](toyota-trail/04-all-terrain/20260926-proof-01/sample-wheel.png) · [悬挂实机视频](toyota-trail/04-all-terrain/20260926-proof-01/suspension.mp4)

## 比例与细节

| 项目 | 上一版 | 本轮 |
| --- | ---: | ---: |
| 轮胎直径 | 80 cm | 88 cm |
| 名义胎宽 | 30 cm | 30 cm |
| 轮距 | 172 cm | 176 cm |
| 正常悬挂行程 | 32 cm | 38 cm |
| 车轴最大下垂（相对建模原点） | 13 cm | 19 cm |
| 轮拱开口圆弧半径 | 50 cm | 53 cm |
| 平地静置车身原点高度 | 39.7 cm | 44.9 cm |

正常行程不包含已有的 6 cm 限位缓冲区。额外空间主要分配给下垂，保留全压缩时的轮胎间隙；车身实测抬高 5.2 cm。原钢轮圈的几何直径保持不变，轮胎在胎唇以上增长，备胎和远景轮胎同步更新。

胎块增加 2 mm 级倒角，圆周分段适度增加；模制胎壁环与轮圈接合处连续。脚踏补充橡胶防滑垫、横向纹路和端部紧固件。直线倾斜车柱、窗框、八块平面玻璃、机盖压筋和车头轻微内收延续上一轮形状。

## 悬挂与驾驶

弹簧刚度由 36,000 调至 26,500 N/m，使更长的弹簧在静载下仍保持合适的车身与车轴距离。压缩 / 回弹阻尼分别为 4,200 / 5,900 N·s/m，前 / 后防倾刚度为 10,000 / 6,500 N/m。轮胎旋转质量由 26 调至 30 kg。

减振器采用更长的固定筒体和更大的前后倾角，增加与车架连接的双耳支架；伸缩时只改变外露活塞杆长度。Blender 装配、网格检查与游戏运行时读取同一组安装点和筒长。钢板弹簧的固定端、左右独立变形、车桥和传动轴继续随实际物理运动。

单轮平台缓慢抬升对照：同一平地、质量与手刹设置，以 60 Hz 从 0 抬升到 50 cm，四轮均着地且各自承重超过 100 N 的最高平台高度由 **32.7 cm 增至 41.1 cm**。这是受控仿真对照，用于观察悬挂可用范围。见 [原始测量](toyota-trail/04-all-terrain/20260926-proof-01/suspension-study.json)。

## 验证与产物

- 最终导出模型的八块车窗保持共面，玻璃顶点与上一版一致；轮圈尺寸未变，近景 / 远景轮胎半径一致到毫米级。见 [几何检查](toyota-trail/04-all-terrain/20260926-proof-01/geometry-check.json)。
- 原尺寸网格在九种极限姿态中未检出非安装部位穿插，覆盖全压缩、全下垂、交叉轴与满舵组合。见 [装配检查](toyota-trail/04-all-terrain/20260926-proof-01/clearance.json)。
- `npm run test:rig`：9 / 9 通过；Toyota 驾驶测试：15 / 15 通过；含场景碰撞的完整路线行驶 1667 / 1671 m，326 s，无复位，最低直立度 0.96。
- 生产构建、九组实机对照、夜间灯光与 LOD 切换通过。真实交叉轴行驶中左右悬挂长度差达到 33.8 cm，最低直立度 0.969。见 [实机记录](toyota-trail/04-all-terrain/20260926-proof-01/browser-report.json)。
- 当前 GLB 约 4.09 MB，完整近景装配 185,508 三角面，远景 64,258。增加的面数主要来自胎块倒角与匹配的备胎；远景使用简化轮胎。

对照图使用同一世界机位、时间与涂装，两版分别按各自的轮胎和悬挂配置落地静置；未用抬高旧版或整体缩放轮子的方式制作对照。页面绑定 `20260926-proof-01`。其他车型继续使用各自原有参数；共享代码的新安装参数保留原默认值。

[Blender 文件](../art/blender/vehicle_toyota_trail.blend) · [生成脚本](../art/blender/vehicle_toyota_trail.py) · [游戏 GLB](../public/assets/models/vehicle_toyota_trail.glb) · [本轮哈希与快照](toyota-trail/04-all-terrain/manifest.json)

重建与验证：

```bash
npm run assets:toyota
npm run test:rig
npx tsx tools/proving.ts toyota
VEH=toyota FULL=1 npx tsx tools/sim-test.ts lap
python tools/toyota-geometry-check.py /tmp/toyota-geometry-NEW.json
npx tsx tools/toyota-suspension-study.ts /tmp/toyota-suspension-NEW.json
npm run build
npm run test:toyota:browser
```

测量工具的输出路径必须是新文件；实机采集也使用新目录。试玩 URL 加 `?play&vehicle=toyota`。前一版设计与验证保留在 [直柱平窗记录](TOYOTA-FLAT-GLAZING.md)。
