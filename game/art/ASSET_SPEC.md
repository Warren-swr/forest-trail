# Forest Trail 自制资产规格（Blender）

所有资产由 `art/blender/*.py` 脚本在 Blender 4.5 中程序化生成，脚本即可编辑源文件；同时保存 `.blend` 以便手工修改。
导出 GLB 到 `public/assets/models/`。运行：`blender --background --python art/blender/build_all.py`。

## 通用约定

- 单位：米。Blender Z 向上；车辆/物体“前方”朝 Blender **+Y**（导出 glTF 后为 -Z，即 PlayCanvas 的前方）。
- 导出：`export_format='GLB'`，`export_yup=True`，应用修改器，不导出相机/灯光。
- 植被、岩石、道具：**每个 GLB 仅 1 个网格对象、1 个材质**，颜色写入顶点色 `COLOR_0`（sRGB 色值），材质名 `VC`。便于游戏里实例化合批。
- 车辆：可多材质，材质名固定（见下），便于运行时换漆和加泥污。
- 色板（画面方向文档）：深林阴影 #203E35、松针 #49694B、苔藓 #7D8D53、暖草 #C5A861、干土 #8D795B、湿泥 #51483D、远山雾 #A6B9B5、车漆 #B75B3D。
- 风格：环境保留轮廓清晰的风格化写实（参考 over the hill 的针叶树：层叠下垂、边缘锯齿的树冠层）；近景车辆使用精细曲面和机械部件，与森林的色调保持协调。

## 车辆（当前资产，fidelity=3）

三车分别参考 Defender 90、Toyota Land Cruiser FJ60、Toyota Hilux RN46；模型为探险改装配置。Toyota 当前使用 `style=trail-v2-refinement/1`、`revision=06-wheel-arch-balance` 的旧版风格样车，见 [轮眉与车身姿态调整](../docs/TOYOTA-ARCH-BALANCE.md)。其余两车沿用[上一轮实现](../docs/VEHICLE-FIDELITY.md)。

- 原点仍为两轴中点、静态轮心；Blender +Y 朝前，导出后游戏 -Z 朝前。
- 当前文件为 `vehicle_scout.glb` / `vehicle_toyota_trail.glb` / `vehicle_ranger.glb`，存档 ID 仍为 `scout` / `toyota` / `ranger`。上一轮 `vehicle_toyota.glb` 留作参考。
- 共有节点为 `Body`、`Wheel`、`Body_LOD1`、`Wheel_LOD1`、`AxleFront`、`AxleRear`、`Spring`、`ShockBody`、`ShockRod`、`BrakeFront`、`BrakeRear`、`Driveshaft`。透明车窗车型另有 `Glazing`、`SteeringWheel`；Toyota 样车的深色不透明玻璃包含在 `Body` 中。
- Toyota 保留旧版单体车壳、宽轮眉和厚胎纹，增加浅凹门缝、连续窗框和实际开孔轮圈。其余两车保留上一轮薄板车身、透明窗与内饰。制动器和轮胎旋转节点分离。
- `Spring` 导出 `Bump` / `Droop` 两个形变目标；钢板弹簧上层两端固定。减震筒长度固定，活塞绘制外露部分。
- 挂点 JSON 是游戏装配依据，包括弹簧类型、减震器上下端、方向盘、灯具、绞盘、拖点与 LOD 回差距离。
- 不对网格使用缩小掩盖干涉。几何检查覆盖静态、全压缩、全伸展、两种交叉轴和满舵组合；上跳极限包含物理缓冲块的 0.06 m 容许压缩，转向检查覆盖 Ackermann 内轮最大角度。
- Toyota 的引擎盖、压筋和车顶使用实际曲面；车柱及窗框边线笔直，保留倾角，八块车窗各自为平面。机盖与车头前缘轻微收窄约 3%，圆灯仅调整位置。轮胎直径 88 cm、名义胎宽 30 cm、轮距 176 cm，钢轮圈保留原尺寸，备胎和远景轮胎尺寸一致。轮眉带宽 5.5 cm，为带内翻边的渐变截面；静载车身较前一版降低约 5.9 cm。正常悬挂行程 38 cm；固定减振筒长和安装点由 sidecar 的 `shock` 字段同步到运行时。尾部采用分层灯座与上下尾门结构，备胎架避开灯组，`LampPlate` 材质随车灯开关联动。实际装配 192,626 三角面，远景 67,389；其余两车约 45–48 万三角面。高模 / 低模统计按节点写入 JSON，完整资产清单在 `asset-report.json`。
- 材质按功能区分车漆、玻璃、橡胶、钢铁、镀铬、内饰和灯具。Toyota 车漆粗糙度 0.56、clearcoat 为 0，玻璃为不透明深色；其余两车保留原资产参数。运行时尊重资产的透明模式，泥污、换色和灯光继续由游戏驱动。

只生成当前 Toyota 样车并验证游戏装配：

```bash
npm run assets:toyota
npm run test:rig
```

`vehicle_toyota_trail.py` 为当前样车入口；`vehicle_scout.py` / `vehicle_ranger.py` 为其余两车入口，`vehicle_toyota.py` 为上一轮 Toyota 入口。`build_all.py` 同时生成样车与上一轮资产。`.blend` 默认显示装配后的模型，导出源零件保存在独立隐藏集合，可在 Blender 中展开编辑。

## 植被（每个都要 `_lod1` 低模版本，三角面约为高模的 1/6–1/4）

| 文件 | 描述 | 高度 | 高模三角面 |
| --- | --- | --- | --- |
| `pine_tall_a.glb` / `pine_tall_b.glb` | 高针叶树，7–9 层下垂锯齿树冠，树干下部可见 | 17–20 m | ≤1400 |
| `pine_mid.glb` | 中等针叶树，更密 | 10–12 m | ≤1000 |
| `pine_young.glb` | 幼树，接近地面就有枝层 | 3.5–5 m | ≤500 |
| `aspen_gold.glb` | 金黄阔叶树（林窗标记），细白树干 + 簇状树冠（#D9A93B 系） | 9–11 m | ≤1200 |
| `snag.glb` | 枯立木，灰色树干与几根断枝 | 9 m | ≤300 |
| `bush_a.glb` / `bush_b.glb` | 路边灌木 | 0.8–1.4 m | ≤300 |
| `fern.glb` | 蕨类/林下草丛 | 0.5 m | ≤200 |
| `grass_tuft.glb` | 暖色高草簇（交叉叶片） | 0.5–0.7 m | ≤60 |

树干底部原点在地面（Z=0），树干中心在 X=Y=0。树冠顶点色：内侧/下方偏暗（#203E35），外缘/上方偏亮（#5E7F52），带轻微随机色差。
法线：树冠使用“从树轴向外”的柔和自定义法线，避免碎面闪烁。

## 岩石与地面物件

| 文件 | 描述 |
| --- | --- |
| `rock_a.glb`、`rock_b.glb`、`rock_c.glb` | 大小 1.2–2.5 m 的切面巨石，顶面带苔藓色 |
| `rock_slab.glb` | 扁平石板（2.4×1.6×0.5 m），用于岩阶 |
| `rock_post.glb` | 竖立的岩桩（绞盘锚点），约 1.6 m 高、直径 0.8 m |
| `pebbles.glb` | 小碎石簇（非碰撞装饰） |
| `log.glb` | 倒木，长 6 m、直径 0.5 m，沿 X |
| `stump.glb` | 树桩 |

岩石原点在底部中心；允许底部埋入地面 0.2–0.4 m。

## 建筑与道具（地标轮廓要从远处可辨）

| 文件 | 描述 |
| --- | --- |
| `cabin.glb` | 林窗小屋：A 字形陡坡屋顶的木屋，约 7×9 m，前廊、烟囱、窗户（窗用暖色顶点色表示灯光） |
| `lookout.glb` | 山脊望台：木结构观景平台（离地约 1.2 m，带栏杆、台阶、长椅、投币望远镜），旁有一座约 9 m 高的木质火警瞭望塔 |
| `tent.glb` | 营地帐篷（橙色/墨绿帆布） |
| `campfire.glb` | 石圈篝火与木柴（火焰由游戏另做） |
| `bench_log.glb` | 原木长凳 |
| `picnic_table.glb` | 野餐桌 |
| `signpost.glb` | 木路牌（立柱+两块箭头板） |
| `toolbox.glb` | 红色金属工具箱（约 0.7×0.35×0.35 m） |
| `shed.glb` | 旧锯木棚：开放式木棚、木材堆 |
| `dock.glb` | 湖边木栈道/码头（约 10 m 长） |
| `fence.glb` | 木栅栏一段（长 3 m） |
| `bridge_plank.glb` | （可选）木板便桥 |

## 验收

`art/previews/` 下每个资产或每组资产一张渲染预览 PNG；打印每个 GLB 的三角面数与包围盒到 `art/asset-report.json`。
