# 画面参考与可复用素材目录

收集于 2026-09-25。下载地址、原页面、文件大小和 SHA-256 见 [manifest.json](assets/manifest.json)。此清单把“用于观察原作的图片”和“可导入原型的资产”明确区分。

## 1. 官方画面参考：已下载 14 张

来源：[over the hill 官方 Steam 商店](https://store.steampowered.com/app/2929250/over_the_hill/)。媒体元数据存于 [steam-media-metadata.json](sources/steam-media-metadata.json)，保留实际 CDN 地址，方便核对文件来源。

| 建议优先看 | 文件 | 目的 |
| --- | --- | --- |
| 森林、道路与目的地 | [01](assets/reference/steam-01.jpg)、[10](assets/reference/steam-10.jpg) | 林群疏密、暖草与冷影、道路可读性 |
| 车辆与地形 | [04](assets/reference/steam-04.jpg)、[06](assets/reference/steam-06.jpg)、[14](assets/reference/steam-14.jpg) | 轮胎尺寸、车身姿态、底盘轮廓和石块尺度 |
| 林间氛围与停留 | [02](assets/reference/steam-02.jpg)、[07](assets/reference/steam-07.jpg)、[09](assets/reference/steam-09.jpg)、[12](assets/reference/steam-12.jpg) | 雾、冷暖对比、营地、溪湖与远山 |
| 额外边界参考 | [03](assets/reference/steam-03.jpg)、[05](assets/reference/steam-05.jpg)、[08](assets/reference/steam-08.jpg)、[11](assets/reference/steam-11.jpg)、[13](assets/reference/steam-13.jpg) | 动物、峡谷、雪地和车辙；不等于首版内容清单 |

这些文件均为官方宣传／商店画面，没有新游戏资产授权。用于研究比对，不放入游戏发布包；不提取车模、地图、纹理、音乐和 UI。逐图说明见[画面研究](02-visual-direction.md)，可离线查看[参考板](reference-board.html)。

## 2. 原型可复用素材：三套原包已下载

已读取下载包内许可，均标记为 CC0，支持个人、教学和商业项目。页面版本／宣传数量与包内实际文件可能不同；下表版本来自包内许可，GLB 数量来自本次文件清点，不等于独特游戏对象数量。[Kenney 官方使用说明](https://kenney.nl/support)

| 素材包 | 本地原包 | 已核验内容 | 在本项目中的用途 |
| --- | --- | --- | --- |
| [Car Kit](https://kenney.nl/assets/car-kit) 3.1 | [kenney_car-kit.zip](assets/reusable/kenney_car-kit.zip) | 50 个 GLB，包含车辆、车轮与配件；SUV 有独立四轮节点 | P0 占位车，验证姿态、接地与镜头；最终主角车需强化造型 |
| [Nature Kit](https://kenney.nl/assets/nature-kit) 2.1 | [kenney_nature-kit.zip](assets/reusable/kenney_nature-kit.zip) | 329 个 GLB，含松树、灌木、岩石、原木、桥与地形块 | P1 森林和障碍原型，挑少量模型统一材质 |
| [Survival Kit](https://kenney.nl/assets/survival-kit) 2.0 | [kenney_survival-kit.zip](assets/reusable/kenney_survival-kit.zip) | 80 个 GLB，含帐篷、营火组件、木结构与自然物件 | 营地和观景点道具，保留少量有用装饰 |

许可原文：[车辆](assets/reusable/licenses/kenney_car-kit-License.txt)、[自然](assets/reusable/licenses/kenney_nature-kit-License.txt)、[营地](assets/reusable/licenses/kenney_survival-kit-License.txt)。原包内包含原作者预览图，已单独取出供参考板展示；未改图。

### 推荐最先导入的文件

以下是 ZIP 内路径，不是已部署游戏资源：

| 包内路径 | 用途 | 导入前检查 |
| --- | --- | --- |
| Car：`Models/GLB format/suv.glb` | 第一辆驾驶测试车 | 四轮转轴、比例、前进轴；body 下另有备用轮节点 |
| Car：`Models/GLB format/wheel-default.glb` | 轮胎替换参考 | 半径匹配物理，不能直接使用模型原始单位 |
| Nature：`Models/GLTF format/tree_pineTallA.glb` | 高树轮廓 | 统一色板，树干简化碰撞 |
| Nature：`Models/GLTF format/tree_pineSmallA.glb` | 幼树与边缘层 | 非路障的小树不增加复杂碰撞 |
| Nature：`Models/GLTF format/plant_bush.glb` | 道路边缘灌木 | 不遮挡坡度和车轮接触 |
| Nature：`Models/GLTF format/rock_smallA.glb` | 岩石外观起点 | 驾驶障碍使用可控的专用碰撞形状 |
| Nature：`Models/GLTF format/log.glb` | 路边倒木 | 主路不摆不可理解的薄杆碰撞 |
| Survival：`Models/GLB format/tent.glb` | 起点营地 | 校准车与帐篷尺度 |
| Survival：`Models/GLB format/campfire-pit.glb` | 停靠点 | 火焰和声音另做，不假定包内含全部效果 |

素材预览显示出明显的玩具／模块化倾向，适合功能原型，不能直接当成最终森林品质承诺。主角车、近景松树轮廓和地形大形是后续最值得定制的部分。

## 3. 额外材质候选：已查页面，未下载

[Poly Haven Forest Floor](https://polyhaven.com/a/forest_floor) 可作森林地表纹理研究和低强度细节来源。其[资产许可](https://polyhaven.com/license)为 CC0；网站示例渲染等页面内容不自动等于 CC0 资产。

本项目若采用，只选 1K／2K 的必要贴图，降低细节对比并与整体色板统一。不要把整套高分辨率扫描材质直接引入网页，破坏风格并超过下载预算。当前本地没有该纹理，不能将它计入已交付素材。

## 4. 原创资产制作清单

| 资产 | 最小数量 | 优先级 | 品质要求 |
| --- | --- | --- | --- |
| 复古四驱车外观 | 1 | P1–P2 | 方正车体、厚胎、清晰轮拱、简单底盘；无现实品牌标识依赖 |
| 高／中／幼针叶树、阔叶点缀 | 3+1 类 | P1 | 每类少量轮廓变体，合批材质和远景简化 |
| 可驾驶地形及泥区 | 1 张 | P1–P2 | 道路大形手工制作，碰撞与渲染一致 |
| 主要岩石、碎石、倒木 | 6–10 种 | P1 | 可穿与不可穿对象有明显区别 |
| 木屋、望台、路牌与营地 | 4 组 | P2 | 地标轮廓从远处能区分 |
| 泥点、尘、水花、车辙 | 各 1 组 | P1 | 有限数量、按状态触发，不持续刷屏 |
| 罗盘、交互、地图印记 | 1 套 | P2 | 统一原创 UI，信息少而清楚 |
| 驾驶和自然音效 | 约 10–15 类 | P1–P3 | 原创或逐条核验许可；本次没有下载音频包 |

## 5. 素材进入游戏前的门槛

保留来源和许可，检查车轮节点、尺寸与轴向，生成合适碰撞体，删掉无用材质和贴图，统一色板，再按画面预算做简化。原型包总下载量不是最终游戏资源体积；发布时只包含实际使用的转换后资产。

本目录没有购买付费包，没有向第三方上传资料，也没有进行原作游戏资产提取。

## 6. 补充核验：素材精度与越野仿真

2026-09-25 补充检查，原始结果见 [vehicle-fidelity-audit.json](sources/vehicle-fidelity-audit.json)。**现有素材足以启动原型；SUV 不宜直接作为最终主角车，素材本身也不提供驾驶仿真精度。** CC0 是许可标记，与几何细节或物理准确度没有必然关系。

### 所查 SUV GLB 的实际内容

| 项目 | 本地检查结果 | 含义 |
| --- | --- | --- |
| 几何 | 整车节点合计 2,474 个三角形；车身 814，四个行驶轮与一个备用轮各 332 | 很轻量，但最终品质还取决于比例、轮廓、细节和材质，不能只按面数判断 |
| 可动结构 | 四个行驶轮独立节点，备用轮为车身子节点 | 可由程序控制四轮转向、滚动和升降；仍需检查轴向与枢轴 |
| 悬挂表达 | 没有独立车桥、弹簧、减震器节点；没有动画或蒙皮 | 原型可直接驱动车轮；若要看见可信的悬挂机构，应补建结构，不是简单要求加骨骼 |
| 材质 | 单个色板材质，未配置法线和粗糙度贴图 | 缺少独立表达轮胎、车漆、金属、玻璃与湿泥的材质分层 |
| 文件依赖 | 通过相对路径引用包内 `Textures/colormap.png` | 这个 GLB 不是完全自包含；不能只复制单个 GLB 后丢掉贴图 |
| 车辆物理 | 所查 GLB 未提供质量、惯量、悬挂标定、扭矩曲线或轮胎力配置 | 这些必须由驾驶系统单独建立，模型导入不等于仿真完成 |

原始模型中，前后行驶轮节点沿 Z 方向相距约 1.32，轮胎半径约 0.30，二者比值约 4.4；策划初值 2.5 m / 0.38 m 的比值约 6.58。两套比例不一致，无法仅靠整体等比缩放同时匹配。原始坐标不代表真实车型测量值，后续需调整模型或重新确定车辆规格。

### 本项目需要的精度

驾驶模型、碰撞形状和显示模型是三项分别验收的内容。提高显示模型面数，不会自动改变越障、抓地和悬挂响应；漂亮的减震器动画也不证明轮胎真正有载荷。建议把目标定为“有可信重量、接地和牵引反馈的游戏化越野”，目前不能承诺工程级仿真或与原作达到同等物理精度。

首版重点是四轮接触、负载下的悬挂行程、车身俯仰侧倾、载荷对抓地的影响、高低档动力、可理解的空转及底盘托底。选定车型后还要确定悬挂布局：如果使用整体桥，左右轮的耦合与可见车桥姿态应得到表达，不能把四个互不关联的轮点视作完整机构仿真。

当前 [Rapier 射线车辆接口](https://rapier.rs/javascript3d/classes/DynamicRayCastVehicleController.html)适合建立驾驶基线；它沿悬挂方向发射射线，并不等价于具有接触面积、胎体变形的实体轮胎。由此推论，直立石阶、窄石脊和连续攀爬须特别验证；若无法达到体验目标，需升级接触模型，不能靠增加车模面数解决。

### 对各类素材的处理建议

- **车辆：**现有 SUV 保留作 P0 占位。最终主角车定制或选取更合适的可改造模型，统一轴距、轮径、轮距、离地间隙，并增加必要底盘和悬挂结构。
- **森林：**现有树木适合布局与中远景起点；道路旁近景树、灌木、岩石与地表需要重新组织轮廓、层次和材质，才能达到策划的森林观感。
- **营地：**帐篷、木结构等次要物件较有机会直接复用，完成尺度与色板统一后再验收。

下一步仍先验证驾驶试验场，再确定最终车模规格。本次静态审计没有运行车辆、验证碰撞或测量驾驶效果，不能据此给出“仿真精度已达标”的结论。
