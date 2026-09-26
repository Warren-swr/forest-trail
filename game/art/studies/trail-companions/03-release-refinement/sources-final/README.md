# Forest Trail · 松溪环线

**[在线试玩](https://warren-swr.github.io/forest-trail/)** · [GitHub 仓库](https://github.com/Warren-swr/forest-trail)

![封面](docs/cover.png)

单人第三人称 3D 森林越野网页游戏。从三辆风格不同的老式四驱车里挑一辆：
- 沿松溪环线记录三处风景（林窗小屋、浅溪石滩、山脊望台），最后回到营地；
- 旅程之外可以继续自由驾驶：去越野训练场挑战弹坑和交叉轴、刷新计时，穿过赤岩峡谷的木板吊桥，或者在夜里开着远光灯探索森林。

技术栈：Vite + React + TypeScript + PlayCanvas 2.22（3D）+ Rapier 3D（刚体与碰撞）+ WebAudio（合成音效与背景音乐）。

演示视频：[docs/demo.mp4](docs/demo.mp4)（126 秒，1080p，由游戏内“录制演示视频”按钮录制）。

## 横版实景图

[查看 5 张原图](docs/screenshots/landscape/README.md)（2560×1440，16:9）：松林小径、湖畔船屋、赤岩峡谷、秋林木屋与星夜营地，均由当前游戏实机取景。

[![横版实景图预览](docs/screenshots/landscape/preview.jpg)](docs/screenshots/landscape/README.md)

## 主要内容

- **三辆车：**
  - **Scout 短轴四驱：**以传统 Defender 为参考的探险车，前后整体桥螺旋弹簧。
  - **TOYOTA Land Cruiser FJ60：**圆灯四门旅行车，前后钢板弹簧，长轴、重、稳，带通气管。
  - **Kestrel 小皮卡：**以 1979 Hilux 为参考的早期四驱单排皮卡，独立冲压货斗和前后钢板弹簧，轻快灵活。

  **Scout 与 Kestrel 已从上一版正式模型重新精修**：保留原有分段车窗、双色腰线、车顶灯与货架，以及油桶、脱困板、工具、行李和备胎等完整可见装备；对照真实 Defender / 1979 Hilux 照片，精修连续面板、开孔钢轮圈、灯具、支架与绑带，向 Toyota 样车对齐风格。胎径为 86 / 84 cm，正常悬挂行程为 38 / 35 cm；驾驶、完整环线、极限装配和实机检查通过。见 [精修说明](docs/VEHICLE-TRAIL-COMPANIONS.md) 和 [正式版对照、Toyota 样车与悬挂视频](docs/trail-companions/index.html)。

  **当前 Toyota 为旧版风格精修样车**：保留方正车身、深色车窗与车顶装备，轮胎直径 88 cm，正常悬挂行程 38 cm。本轮将轮眉带宽从 10 收窄到 5.5 cm，增加弹簧静载下沉，使车身降低约 5.9 cm，胎顶留白更紧凑；轮距与悬挂端点保持原值。尾灯修正、直柱、平窗和机盖曲面继续保留。近景完整装配约 19.3 万三角面，远景约 6.7 万。见 [本轮比例调整](docs/TOYOTA-ARCH-BALANCE.md) 和 [同机位对照](docs/toyota-trail/06-wheel-arch-balance/index.html)。[第一版样车](docs/TOYOTA-TRAIL-STUDY.md)与[上一轮三车记录](docs/VEHICLE-FIDELITY.md)留作历史参考。
- **近景环境与摄影：**风化岩石倒角、细分树皮、树桩年轮与裂纹，8 种环境模型增加距离 LOD。暂停菜单可近距离检视车辆，摄影焦点随镜头距离更新。
- **昼夜与车灯：**
  - 天空是 GPU 程序化生成的，有太阳、云、星空和月亮；白天与夜晚之间平滑过渡。
  - 夜里有篝火、串灯、窗灯，营地和草甸上空有萤火虫。
  - 车灯可以开关，并在近光和远光之间切换：近光带截止线，远光照得更远，并联动灯排和雾灯。
- **颠簸路面与新区域：**
  - 路面：炮弹坑、交叉轴、连续起伏、搓板路、侧倾坡、原木台阶、岩石花园。
  - 越野训练场：7 对旗门计时，保存最佳成绩。
  - 赤岩峡谷：砂岩、天然石拱，还有可以开车通过的吊桥。
  - 秋色林与 A 字木屋、湖畔船屋、营地夜景。
  - 立体雪山和瀑布、风吹植被，以及会被车惊跑的鹿群和盘旋的鹰。
- **背景音乐：**白天、夜晚、标题 / 演示三组歌单，曲目切换时交叉淡入淡出。曲目来自 Kevin MacLeod（incompetech.com，CC BY 4.0），见 [docs/CREDITS.md](docs/CREDITS.md)。
- **现代界面：**磨砂面板风格，包括选车卡片、环形速度表、车灯与档位状态、训练场计时和侧栏式暂停菜单。
- **演示模式：**约 2 分钟的自动运镜展示，可以一键录制成 WebM 下载；还能一键生成 1200×1800 的竖屏封面。

## 启动

需要 Node.js 22.12 或更新版本（已在 22.23 上验证），以及一块支持 WebGL2 的显卡。在 `game/` 目录下运行：

```bash
npm ci
npm run dev      # 开发服务器 http://localhost:5173
npm run build    # 类型检查 + 生产构建，输出到 dist/
npm run preview  # 本地预览 dist/
```

`dist/` 是纯静态文件（`base: './'`），可以直接放到任意静态服务器上。

URL 参数：
- `?play`：跳过标题页；
- `?play&vehicle=toyota`：直接进入 Toyota 样车（也支持 `scout` / `ranger`）；
- `?debug`：显示驾驶遥测（速度、油门、悬挂长度、载荷、地表、安全点、绞盘张力、绘制调用数）。

## 操作

| 动作 | 键鼠 | 标准手柄 |
| --- | --- | --- |
| 油门 | W / ↑ | RT |
| 制动；停稳后倒车 | S / ↓ | LT |
| 转向 | A D / ← → | 左摇杆 |
| 手刹 | Space | B |
| 高 / 低档 | Q | X |
| 大灯开 / 关 | L | 十字键上 |
| 远光 / 近光 | B | 十字键右 |
| 白天 / 夜晚 | N | — |
| 环视（1.5 秒后自动回正） | 按住右键拖动；滚轮调远近 | 右摇杆 |
| 镜头回正 | C | 右摇杆按下 |
| 绞盘：选锚点 / 断开 | E | Y |
| 绞盘：连接；按住收绳 | 左键或 F | A |
| 记录风景点 / 探索点 / 拾取工具箱 | F | A |
| 复位到最近安全点 | 按住 R 1 秒 | 按住 LB+RB 1 秒 |
| 地图 | M | View |
| 摄影模式 | P | — |
| 暂停菜单 | Esc | Menu |

标题页可以选车、切换昼夜、观看或录制演示、生成封面。暂停菜单的“车辆与涂装”里可以随时换车。

## 目录

```
src/game/world/     地图布局（layout.ts）、地形合成与颠簸路面、新区域摆放（areas.ts）、植被与岩石散布
src/game/physics/   Rapier 世界、自写四驱车模型（按 VehicleSpec 参数化）、绞盘
src/game/render/    地形、实例化森林与风动、天空与昼夜、远山与瀑布、车辆视图与泥污、车灯、夜间灯光、野生动物、粒子
src/game/           主循环、旅程规则、训练场计时（park.ts）、演示导演（director.ts）、封面（cover.ts）、镜头、输入、音频、存档
src/ui/             React 界面：标题与选车、HUD、暂停菜单、地图、演示字幕层
art/blender/        全部 3D 资产的 Blender Python 源脚本（车辆共享零件库、三辆车、穿模检测、植被、岩石、道具）和 .blend 文件
public/assets/      导出的 GLB 模型、车辆挂点 JSON、背景音乐
tools/              无头试验场、路线测试、地图预览
docs/               方案文档、验证报告、开发计划、素材来源、截图、封面、演示视频
```

## 测试与工具

```bash
npm run test:proving                # 三辆车依次跑驾驶验收 D01–D12（结果写入 tools/proving-results*.json）
npm run test:rig                    # 最终 GLB、弹簧形变、胎肩接地和车桥碰撞体回归检查
npm run test:toyota:browser         # 当前 Toyota 与修改前版本对照、悬挂录制；写入新目录（需 Playwright）
npm run test:companions:browser     # Scout / Kestrel 同机位对照、灯光、LOD 与真实悬挂录制
npm run test:lap                    # 自动驾驶跑完整条环线；VEH=toyota|ranger 选车，FULL=1 加载全部静态碰撞体
npx tsx tools/sim-test.ts park      # 自动驾驶跑完越野训练场（同样支持 VEH=...）
npx tsx tools/sim-test.ts canyon    # 自动驾驶穿过赤岩峡谷和吊桥
npm run test:drive                  # 起步、制动、驻停、泥地与岩阶数据
npm run map                         # 生成地图预览 docs/map-preview.png 并打印各路段坡度
npm run assets                      # 用 Blender 重新生成全部模型、预览图、车辆 JSON 和 asset-report.json（需安装 Blender 4.x）
npm run assets:toyota                # 只重新生成旧版风格 Toyota 样车及装配检查
npm run assets:companions            # 只重建 Scout / Kestrel，并检查完整悬挂与转向范围
```

## 文档

- [docs/PLAN-v2.md](docs/PLAN-v2.md)：第二版开发计划。
- [docs/DESIGN.md](docs/DESIGN.md)：方案文档，记录所有实现取舍；第二版内容在第 13 节。
- [docs/VERIFICATION.md](docs/VERIFICATION.md)：实际验证过程与结果、性能数据、剩余限制、截图索引。
- [docs/CREDITS.md](docs/CREDITS.md)：背景音乐来源、许可证与署名。
- [docs/TOYOTA-ARCH-BALANCE.md](docs/TOYOTA-ARCH-BALANCE.md)：当前 Toyota 的轮眉与车身姿态调整。
- [docs/VEHICLE-TRAIL-COMPANIONS.md](docs/VEHICLE-TRAIL-COMPANIONS.md)：当前 Scout / Kestrel 的建模、细节与悬挂优化、对照媒体和复验命令。
- [docs/TOYOTA-TAILGATE-FINISH.md](docs/TOYOTA-TAILGATE-FINISH.md)：第五轮尾灯闪烁修复与附件连接打磨记录。
- [docs/TOYOTA-ALL-TERRAIN.md](docs/TOYOTA-ALL-TERRAIN.md)：第四轮大轮胎与悬挂调整记录。
- [docs/TOYOTA-FLAT-GLAZING.md](docs/TOYOTA-FLAT-GLAZING.md)：第三轮直柱平窗与车头前段修整记录。
- [docs/TOYOTA-CURVED-PANELS.md](docs/TOYOTA-CURVED-PANELS.md)：第二轮曲面版本的历史记录。
- [docs/TOYOTA-TRAIL-STUDY.md](docs/TOYOTA-TRAIL-STUDY.md)：第一版 Toyota 样车、旧版来源与当时的实测结果。
- [docs/VEHICLE-FIDELITY.md](docs/VEHICLE-FIDELITY.md)：上一轮三车精细版本的历史记录。
- [样车悬挂实机演示](docs/toyota-trail/06-wheel-arch-balance/20260926-proof-02/suspension.mp4)：当前 Toyota 低档通过训练场交叉轴，检查降低静态姿态后的车身与悬挂运动。

除背景音乐外，所有模型、贴图和音效都是本项目原创（程序化生成）。
