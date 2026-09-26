# Toyota 样车 · 轮眉与车身姿态调整

当前版本为 `06-wheel-arch-balance`。本轮判断是不协调主要来自过厚的轮眉与较大的胎顶留白，横向轮距不是主要原因。收窄轮眉并增加静载下沉，让车身与大轮胎的比例更紧凑。

[同机位对照](toyota-trail/06-wheel-arch-balance/index.html) · [侧面](toyota-trail/06-wheel-arch-balance/20260926-proof-02/sample-side.png) · [前侧](toyota-trail/06-wheel-arch-balance/20260926-proof-02/sample-front.png) · [悬挂实机视频](toyota-trail/06-wheel-arch-balance/20260926-proof-02/suspension.mp4)

| 项目 | 上一版 | 本轮 |
| --- | ---: | ---: |
| 轮眉沿圆弧的带宽 | 10 cm | 5.5 cm |
| 平地静载车身原点高度 | 44.9 cm | 39.0 cm |
| 胎顶至轮拱上缘空隙 | 约 28 cm | 约 22 cm |
| 轮胎直径 | 88 cm | 88 cm |
| 横向轮距 | 176 cm | 176 cm |
| 正常悬挂总行程 | 38 cm | 38 cm |
| 静载后的正常上压 / 下垂余量 | 约 20 / 18 cm | 约 14 / 24 cm |

轮眉从等厚的宽环改为贴着车身逐渐外展的窄翻边，内侧完整回接轮拱，遮住裸露的车身切口。轮拱开口、88 cm 轮胎和满舵范围沿用现有尺寸。

弹簧刚度由 26,500 调至 20,000 N/m，增加静载下沉，实测车身降低 **5.88 cm**。压缩与下垂端点、限位缓冲区、阻尼和防倾参数保持原值；38 cm 正常行程内的静态上压与下垂余量重新分配。车身和车轮渲染使用实际物理状态。受控单轮平台试验中，四轮保持承重的抬升高度从 41.1 cm 增至 47.7 cm，见 [测量记录](toyota-trail/06-wheel-arch-balance/20260926-proof-02/suspension-study.json)。

## 验证

- 满舵、全压缩、全下垂及交叉轴的九种装配姿态通过；最终 GLB 的资产与物理回归 9 / 9 通过。
- Toyota 驾驶测试 15 / 15 通过。过坎侧倾峰值 2.4°，后轮离开障碍后约 0.22 s 收稳。
- 含场景碰撞的完整路线行驶 1667 / 1671 m，326 s，零复位，最低直立度 0.96。
- 近景、远景的共面检查与尾灯可见性检查通过；上一轮尾灯修正继续有效。八块玻璃仍为平面且与上一版顶点一致。
- 生产构建、13 组实机对照、灯光状态、LOD 往返及实际交叉轴行驶通过，无浏览器错误。对照图固定世界机位，各版本按自身弹簧参数静置落地。
- 当前完整近景装配 192,626 三角面，远景 67,389；GLB 约 4.29 MB。

[装配检查](toyota-trail/06-wheel-arch-balance/20260926-proof-02/clearance.json) · [驾驶测试](toyota-trail/06-wheel-arch-balance/20260926-proof-02/proving.log) · [完整路线](toyota-trail/06-wheel-arch-balance/20260926-proof-02/lap.log) · [实机记录](toyota-trail/06-wheel-arch-balance/20260926-proof-02/browser-report.json)

本轮对照绑定 `20260926-proof-02`。Blender 静态装配预览使用建模原点姿态；实机截图和测量反映弹簧在车重作用下的落地姿态。上一版与早期试做媒体分别保留，文件哈希和源码快照见 [交付清单](toyota-trail/06-wheel-arch-balance/manifest.json)。

[Blender 文件](../art/blender/vehicle_toyota_trail.blend) · [生成脚本](../art/blender/vehicle_toyota_trail.py) · [游戏模型](../public/assets/models/vehicle_toyota_trail.glb)

```bash
npm run assets:toyota
npm run test:rig
npx tsx tools/proving.ts toyota
VEH=toyota FULL=1 npx tsx tools/sim-test.ts lap
npx tsx tools/toyota-suspension-study.ts /tmp/toyota-suspension-NEW.json
python tools/toyota-geometry-check.py /tmp/toyota-geometry-NEW.json
blender --background --python-exit-code 1 --python tools/toyota-surface-check.py -- public/assets/models/vehicle_toyota_trail.glb /tmp/toyota-surfaces-NEW.json --require-clean
npm run build
npm run test:toyota:browser
```

测量与媒体采集使用新路径，避免覆盖原始结果。
