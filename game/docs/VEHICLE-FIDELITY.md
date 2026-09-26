# Forest Trail · 经典越野车与近景模型升级

> 历史记录：本文与 `vehicle-fidelity/` 中的截图、测试和哈希对应上一轮三车精细版本。当前 Toyota 已切换为[旧版风格精修样车](TOYOTA-TRAIL-STUDY.md)，使用独立的 `vehicle_toyota_trail` 资产；本文的 Toyota 图片、面数和哈希不代表当前样车。

本次把三辆车重建为不同经典车型的探险改装版本，并同步更新底盘运动、碰撞挂点、近景环境资产和距离 LOD。实际游戏使用这些 GLB；可编辑源模型保存在 `art/blender/vehicle_*.blend`，生成源为 `art/blender/vehicle_fidelity.py`。

## 车型与参考

| 游戏 ID（兼容旧存档） | 外观参考 | 本次主要造型 | 游戏轴距 | 悬挂 |
| --- | --- | --- | --- | --- |
| `scout` | Land Rover Defender 90 / 300Tdi | 短轴车身、分离灯翼、窄格栅、铝制铆接板、外露铰链、白色硬顶、后挂备胎 | 2.36 m | 前后整体桥、螺旋弹簧 |
| `toyota` | Toyota Land Cruiser FJ60，1980–1987 圆灯车型 | 长发动机盖、收窄车顶、四门旅行车侧窗、宽横向格栅、圆灯与外侧转向灯、分体尾门 | 2.73 m | 前后整体桥、五层钢板弹簧 |
| `ranger` | Toyota Hilux RN46，1979–1983 四驱车型 | 独立单排驾驶室、圆灯镀铬格栅、冲压货斗、尾板字样、货箱护栏与绑扎钩 | 2.80 m | 前后整体桥、五层钢板弹簧 |

主要参考来源：

- [Toyota 官方 FJ60 车型档案](https://www.toyota-global.com/company/history_of_toyota/75years/vehicle_lineage/car/id60013889/)：圆灯 60 系车身、2.73 m 轴距与旅行车比例。
- [Toyota UK：1979 Hilux 4WD](https://mag.toyota.co.uk/in-focus-1979-toyota-hilux-4wd/)：官方修复车图片、2.80 m 轴距、前后整体桥钢板弹簧、前盘后鼓制动和货斗结构。
- [Land Rover：Defender 历史](https://www.landrover.com/defender-world/heritage/the-defender-story.html)：传统 Defender 的车身特征与螺旋弹簧演变。
- [JLR Classic 原厂螺旋弹簧目录](https://parts.jaguarlandroverclassic.com/nrc9448-spring-road-coil.html)：传统 Defender 的螺旋弹簧结构参考。

模型为本项目自行建模，没有下载第三方车辆网格或贴图。车轮、升高悬挂、行李架、绞盘与拖钩为游戏的探险配置；车型比例和可见结构参考实车，质量、限速、牵引力、阻尼与装备间隙保留游戏调校，不作为原厂 CAD 或实车动力学数据。选车界面的车长包含游戏装备，按实际模型外廓校正。

## 细节与资产结构

- 有厚度的车身板件、弧面车顶与发动机盖、卷边和轮拱返回边；车厢为空腔，透明玻璃可以看到内部。
- 可见的座椅褶线、头枕支架、安全带扣、仪表刻度与指针、出风口、收音机、挡杆、遮阳板和后视镜；方向盘随转向输入运动。
- 64 段圆周胎体、分行交错胎纹和细沟、胎肩块、凸起侧壁字样、气门嘴、六角轮母、自由轮毂，以及真正开孔的冲压钢轮圈。
- 灯具含独立反光杯、玻璃纹路、灯框和固定螺钉；近光、远光、尾灯、刹车灯与倒车灯继续接入原游戏灯光逻辑。
- 底盘包含车架、桥壳与差速器盖、传动轴、分动箱、发动机下部、油箱及固定带、排气管、减震器安装眼、缓冲块、钢板弹簧 U 形卡箍。
- 制动盘 / 卡钳跟随转向节，轮胎和轮毂旋转时卡钳保持静止；后桥使用鼓式制动的可见外壳。

导出节点：`Body`、`Glazing`、`Wheel`、`Body_LOD1`、`Wheel_LOD1`、`AxleFront`、`AxleRear`、`Spring`、`ShockBody`、`ShockRod`、`BrakeFront`、`BrakeRear`、`Driveshaft`、`SteeringWheel`。车漆、玻璃、橡胶、金属、内饰、灯具材质分离；不依赖远端图片或贴图请求。

| 车辆 | 车身三角面 | 单轮三角面 | 近景完整装配 | 远景完整装配 |
| --- | ---: | ---: | ---: | ---: |
| Defender 90 | 172,688 | 68,908 | 480,980 | 171,999 |
| FJ60 | 107,924 | 69,132 | 409,520 | 141,339 |
| Hilux | 152,636 | 69,132 | 453,800 | 157,003 |

完整装配数字包含四轮、四组悬挂与减震器、两桥、两轴和制动器，没有把隐藏的另一级 LOD 算入。镜头距离大于 23 m 时切换简化模型，小于 18 m 时恢复近景模型，中间有回差，避免边界闪烁。物理模型不随 LOD 改变。

## 驾驶与悬挂

保持原有 60 Hz 刚体、Ackermann 转向、弹簧 / 压缩与回弹阻尼、缓冲块、防倾杆和轮胎摩擦圈模型，并修正以下实际问题：

1. 悬挂长度的上一帧状态在积分前保存，避免 `snapshot()` 抹掉插值；轮胎旋转与转向也插值。
2. 整体桥碰撞体随两侧悬挂的平均高度和侧倾移动，避免视觉车桥抬升而碰撞体留在原位。
3. 每轮从原来 7 个中心弧线探测扩展到 11 个探测点，增加胎肩接地覆盖。窄石块压在胎肩时能产生支撑力和悬挂压缩。
4. 车轮姿态包含整体桥侧倾；视觉桥长保持固定。刹车组件随转向节运动，不随轮胎旋转。
5. 螺旋弹簧与钢板弹簧使用真实顶点形变；钢板弹簧上层两端固定，中段跟随轮桥行程，叶片厚度保持不变。
6. 减震筒保持固定尺寸，活塞只显示随行程变化的外露部分；传动轴的方向由两个挂点计算，消除后轴上下运动时的俯仰方向错误。
7. 更新了三车尺寸、碰撞外廓、绞盘与后拖点，原 `scout / toyota / ranger` 存档 ID 保留。

这仍是适合网页实时驾驶的单车身刚体 + 多点轮胎接地模拟，未添加独立簧下刚体、轮胎有限元、真实变速箱齿轮或车身碰撞变形。悬挂视觉与实际物理行程联动，不使用循环播放的摆动动画。

## 场景模型与摄影

岩石近景增加风化倒角；倒木和树桩增加细分树皮起伏、年轮和切面裂纹。原有摆放、地形与碰撞位置保留。8 种基础岩石 / 木材资产增加低模版本，近景阈值 48 m、最远显示距离 260 m，远景关闭它们的投影。

摄影模式可以靠近至 2.6 m、拉远至 24 m，并以更低角度观察底盘。景深焦点跟随镜头距离更新，退出摄影时恢复驾驶镜头的距离限制。暂停菜单的车辆页提供「近距离检视车辆」。

## 验证与可复现入口

- **45 / 45 驾驶检查通过**：三车各 15 项，覆盖起步、制动、倒车、静止漂移、单轮凸起、交叉轴、10° / 18° / 25° 上坡、泥地、侧坡、涉水、绞盘、复位与 30 / 60 / 120 fps 一致性。见 `tools/proving-results*.json`。
- **27 / 27 装配姿态通过**：直接读取保存的 Blender 网格和形变结果，检测车轮 / 车身、桥壳 / 车身、弹簧 / 车身、减震器 / 车身、传动轴 / 车身以及轮胎 / 桥壳和弹簧；不缩小网格，仅排除明确的安装接触区域。见 `art/vehicle-clearance.json`。
- **9 / 9 资产及物理回归检查通过**：读取最终 GLB 核对尺寸、灯具 / 拖点、透明玻璃、LOD、弹簧形变和固定端点；在窄台阶上实测胎肩压缩和车桥碰撞体位置；确认旋转插值状态未被覆盖。见 `tools/vehicle-rig-results.json`。
- **三车完整环线**：加载全部树木、岩石、建筑、桥梁和原木碰撞体，三车均完成 1,667 / 1,671 m 环线（终点容差 5 m）。Defender / FJ60 / Hilux 分别用时 324 / 326 / 322 s，均为 0 次复位，最大连续低速停滞不超过 0.23 s，最小车身朝上分量分别为 0.96 / 0.96 / 0.97。原始输出见 `vehicle-fidelity/full-lap-*.txt`。
- **生产浏览器验收**：最终结果、显卡、帧率、截图 SHA-256 和实际越野行程统计见 [`vehicle-fidelity/browser-report.json`](vehicle-fidelity/browser-report.json)。照片和视频来自实际 WebGL 画布，Blender 工作室预览与实机截图分别保存。

本次在 NVIDIA L4 / Vulkan、1600×1000 视口下，三车近景各采样 120 帧，平均约 60 FPS、P95 帧间隔约 16.8 ms。通过三车切换、四组独立弹簧形变、制动器节点分离、LOD 往返切换、夜间车灯、泥污、近景景深和 844×390 车辆菜单检查。训练场实机演示中两侧悬挂最大行程差约 0.26 m；视频以 1600×1000、60 fps 保存。这是上述测试设备和场景的实测值。

[`vehicle-fidelity/manifest.json`](vehicle-fidelity/manifest.json) 记录最终源码、GLB、Blender 文件、构建入口和实机媒体的 SHA-256。浏览器报告中的三车 GLB 哈希已与 `public/` 和 `dist/` 对照，三者一致。

展示入口：[三车工作室预览](../art/previews/vehicle_lineup.png) · [FJ60 实机近景](vehicle-fidelity/toyota-front.png) · [车轮细节](vehicle-fidelity/toyota-wheel.png) · [悬挂实机视频](vehicle-fidelity/suspension.mp4)。

```bash
npm run test:proving
npm run test:rig
VEH=toyota FULL=1 npx tsx tools/sim-test.ts lap
blender --background --threads 6 --python-exit-code 1 --python art/blender/verify_vehicles.py
npm run build
node tools/vehicle-browser.cjs
```

浏览器脚本需要本机 Playwright / Chromium，可用 `PLAYWRIGHT_MODULE` 和 `FOREST_CHROMIUM` 指向已有安装。它启动只监听回环地址的临时静态服务，完成后关闭；结果写入 `docs/vehicle-fidelity/`。

重新建模：

```bash
# 三车：输出 GLB、挂点 JSON、可编辑 .blend 与 8 角度 / 姿态预览
blender --background --threads 6 --python-exit-code 1 --python art/blender/vehicle_fidelity.py
# 指定车型；只跳过渲染预览，不跳过模型导出
blender --background --threads 6 --python-exit-code 1 --python art/blender/vehicle_fidelity.py -- toyota --no-preview
# 近景岩石 / 木材及 LOD
blender --background --threads 6 --python-exit-code 1 --python art/blender/rocks.py
python3 art/blender/report.py
```

导出后必须重新进行装配检查、`test:rig` 和生产构建，不能只替换预览图。预览源码与完整建模文件都保留在项目内。
