# Toyota 样车 · 直柱平窗与车头修整

本文保留第三轮修整与当时的验证结果；当前样车见 [大轮胎与悬挂精修](TOYOTA-ALL-TERRAIN.md)。

当前版本为 `03-flat-glazing`。车柱、窗框和前门分隔条恢复第一版的直线结构，保留 A 柱倾角与车顶收分；取消柱体及玻璃中段的弯曲。引擎盖的双向拱度、压筋、下翻前缘和车顶曲面继续保留。

[同机位实机对照](toyota-trail/03-flat-glazing/index.html) · [车柱近景](toyota-trail/03-flat-glazing/20260926-proof-02/sample-pillar.png) · [引擎盖与车头](toyota-trail/03-flat-glazing/20260926-proof-02/sample-hood.png)

## 车头与原型

原型仍为 Toyota Land Cruiser FJ60。查阅 [Toyota 官方 FJ60 档案](https://www.toyota-global.com/company/history_of_toyota/75years/vehicle_lineage/car/id60013889/)和 [Toyota UK 的 60 系官方照片](https://media.toyota.co.uk/vehicles/land-cruiser-series-60-archive-1985/)，日期为 2026-09-26。

从照片观察，前端适合轻微内收并以圆角收边，整体仍保持宽而方正。基于这一视觉判断，模型从导水板向前逐渐收窄，机盖及车头前缘宽度缩小约 3%（车身每侧约 2.7 cm）。这是游戏模型的调整幅度，不是从照片推算出的原厂尺寸。格栅、侧灯及大灯位置配合移动；圆灯的直径和圆形截面保持原样。改装保险杠与车轮位置不受此收窄影响。

## 验证

- 直接读取最终 GLB 的玻璃顶点与三角面，识别八块车窗，确认每块均共面；最大平面偏差小于 `0.000001 m`。见 [玻璃平面检查](toyota-trail/03-flat-glazing/20260926-proof-02/glazing-check.json)。
- `npm run test:rig`：9 / 9 资产与物理检查通过。原尺寸网格的九种极限装配姿态通过。
- 生产构建通过；八组实机对照、夜间灯光、LOD 切换与交叉轴行驶检查通过。见 [实机记录](toyota-trail/03-flat-glazing/20260926-proof-02/browser-report.json)。
- 近景完整装配 143,046 三角面，远景 59,261。驾驶、悬挂与碰撞调校沿用现有配置。

当前交付对照绑定 `20260926-proof-02`，在同一场景、机位、光照和姿态中对比弯窗版本与本次修正。早先的图片、日志与模型快照保留在原路径。

## 文件

- [当前 Blender 文件](../art/blender/vehicle_toyota_trail.blend) / [生成脚本](../art/blender/vehicle_toyota_trail.py) / [游戏 GLB](../public/assets/models/vehicle_toyota_trail.glb)
- [修改前的模型与源码快照](../art/studies/toyota-trail/03-flat-glazing/baseline.json)
- [交付哈希](toyota-trail/03-flat-glazing/manifest.json)

运行 `npm run assets:toyota` 重新生成模型，再运行 `npm run test:rig`、`npm run build`、`npm run test:toyota:browser`。每次生成与实机采集使用新目录。试玩 URL 加 `?play&vehicle=toyota`。
