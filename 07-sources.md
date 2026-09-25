# 来源、证据与视频入口

访问日期统一为 **2026-09-25（Asia/Shanghai）**。下列摘要为本次整理，不保存媒体文章全文。官方页面在发售前可能持续更新，因此“已公布”不等于“最终版本已实测”。

## 1. 原作一手来源

| ID | 来源与链接 | 日期／状态 | 本次用途 |
| --- | --- | --- | --- |
| S01 | [Funselektor 官方页面](https://www.funselektor.com/overthehill) | 当前产品页 | 定位、探索、合作、环境与摄影 |
| S02 | [Steam 商店，App 2929250](https://store.steampowered.com/app/2929250/over_the_hill/) | 当前页列 2026-10-14 | 核验作品身份和发售计划；官方截图入口 |
| S03 | [官方置顶 FAQ](https://steamcommunity.com/app/2929250/discussions/0/554627937323741779/) | 2025-09-16 发帖，页面显示 9 月 17 日编辑 | 区域地图、传动简化、损伤与抓地；未复述全部问答 |
| S04 | [Steam Next Fest Public Demo Out Now](https://store.steampowered.com/news/app/2929250/view/676249280988579366) | 2026-06-12 | 当时试玩内容：Emerald Lake 与目标类型 |
| S05 | [August Progress Update](https://store.steampowered.com/news/app/2929250/view/812455995175338652) | 2025-08-18 | 罗盘替代小地图，车轮机制调整 |
| S06 | [Next Fest Day Update and Future Plans](https://store.steampowered.com/news/app/2929250/view/676249280988579578) | 2026-06-15 | 官方对试玩性能问题及修复的回应 |
| S07 | [August Progress Update + Exciting News](https://store.steampowered.com/news/app/2929250/view/706653652015645005) | 2026-08-06 | 后续镜头、悬挂、性能打磨；短视频入口 |
| S08 | [September Progress Update](https://store.steampowered.com/news/app/2929250/view/787688820859471016) | 2025-09-16 | 泥地和涉水附件研究入口；旧计划需用新公告覆盖 |
| S09 | [February 2026 Progress Update](https://store.steampowered.com/news/app/2929250/view/541129880857739326) | 2026-02-04 | 环境音、车辆录音和工具研究入口 |
| S10 | [开发者 Reddit AMA](https://www.reddit.com/r/pcgaming/comments/1u9aa48/we_are_the_developers_of_over_the_hill_ask_us/) | 2026 年 6 月试玩期 | 核对简化设计与燃料／形变等边界；只把开发者回答当作官方表态 |
| S13 | [Release Date Announcement](https://store.steampowered.com/news/app/2929250/view/706653652015645738) | 2026-08-10 | Steam 发售日及 Canada／Algeria 区域计划 |
| S14 | [官方新闻 API](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=2929250&count=100&maxlength=0) | 本次实时读取 | Steam 动态页面正文的补充读取通道；根据公告跳转核对规范 URL |

### 资料状态的处理

- 中文搜索缓存曾只显示“2026 年”，实时英文商店与最新 FAQ 已给出明确日期，因此本研究采用 2026-10-14。
- 6 月试玩发布公告只证明那时开放。8 月公告解释了暂停维持公开 demo 的原因，不能据旧页面断言今天还能下载试玩。
- 官网链接的 [Press Kit](https://funselektor.notion.site/over-the-hill-Press-Kit-de04078ef9eb49f3a7391aa592419808) 在本次网页读取中返回 404，未取得内容或许可；改用可访问的 Steam 官方图片。
- 有些 Steam 新闻网页依赖客户端脚本，本次正文经 S14 读取，标题、日期与跳转链接对应；没有把空网页当作正文已读。

## 2. 辅助试玩来源

| ID | 来源 | 日期 | 采用范围 |
| --- | --- | --- | --- |
| S11 | [PC Gamer · Next Fest demo hands-on](https://www.pcgamer.com/games/sim/over-the-hills-next-fest-demo-promises-a-stylized-off-roading-game-for-people-who-actually-like-to-drive/) | 2026-06-12 | 慢行、脱困和路线选择的体验证据，不复制长篇叙事 |
| S12 | [The Drive · Virtual Off-Roading preview](https://www.thedrive.com/news/over-the-hill-preview-virtual-off-roading-that-will-lower-your-blood-pressure) | 2026-06-12 | 风景回报、试玩性能反馈；不据作者机器推导技术根因 |

论坛中的个别抱怨、商店用户标签、同名手机作品及搜索结果摘要均不作为机械参数或最终内容量的依据。

## 3. 美术与技术一手来源

| ID | 来源 | 核验结果／用途 |
| --- | --- | --- |
| A01 | [Kenney Car Kit](https://kenney.nl/assets/car-kit) | 已下载原 ZIP 并读取许可；车辆原型 |
| A02 | [Kenney Nature Kit](https://kenney.nl/assets/nature-kit) | 已下载；树、岩、灌木、原木和桥 |
| A03 | [Kenney Survival Kit](https://kenney.nl/assets/survival-kit) | 已下载；营地道具 |
| A04 | [Kenney 官方使用说明](https://kenney.nl/support) | CC0 使用说明；实际交付仍保留每包许可 |
| A05 | [Poly Haven Forest Floor](https://polyhaven.com/a/forest_floor) | 已查页面，未下载；备用地表材质方向 |
| A06 | [Poly Haven 资产许可](https://polyhaven.com/license) | 区分 CC0 资产与网站页面内容 |
| T01 | [Rapier DynamicRayCastVehicleController](https://rapier.rs/javascript3d/classes/DynamicRayCastVehicleController.html) | 当前逐轮接口和射线控制器边界；不是已验证的完整越野方案 |
| T02 | [Three.js 官方车辆例子](https://threejs.org/examples/physics_rapier_vehicle_controller.html) | 车辆接入参考，本次未运行该例子 |
| T03 | [Three.js InstancedMesh](https://threejs.org/docs/pages/InstancedMesh.html) | 森林重复模型的合批能力 |

## 4. 官方视频研究入口

下面链接来自已读的官方开发公告。**本次仅核对来源关联，未完整观看、未试听、未下载视频，故没有编造时间码或逐帧结论。** 作用是为后续动态核验提供准确入口。

| 主题（按官方公告描述） | 视频 | 所属来源 | 后续需要观察 |
| --- | --- | --- | --- |
| 试玩预告 | [MKZD20fRT6U](https://www.youtube.com/watch?v=MKZD20fRT6U) | S04 | 操作、目标与摄影如何连接 |
| 罗盘 | [d8nf3rakquk](https://www.youtube.com/watch?v=d8nf3rakquk) | S05 | HUD 信息与地标导航 |
| 车轮机制 | [lsaTt030jVY](https://www.youtube.com/watch?v=lsaTt030jVY) | S05 | 接触点、轮胎与车身的运动关系 |
| 泥地机制 | [F6Ds0bQ5qPo](https://www.youtube.com/watch?v=F6Ds0bQ5qPo) | S08 | 空转、推进与车辙的关系 |
| 涉水附件 | [zYHx7g3m9ug](https://www.youtube.com/watch?v=zYHx7g3m9ug) | S08 | 画面反馈与深水限制 |
| 环境声音 | [qbJS4aWFUB4](https://www.youtube.com/watch?v=qbJS4aWFUB4) | S09 | 风、鸟、远近环境层 |
| 视觉氛围 | [zxJ3jd6c7KI](https://www.youtube.com/watch?v=zxJ3jd6c7KI) | S09 | 雾、天光、树林层次 |
| 车辆录音 | [bZK5G7xfks0](https://www.youtube.com/watch?v=bZK5G7xfks0) | S09 | 音源类型，不据此推断游戏混音算法 |
| 千斤顶工具 | [M1S64BanCIE](https://www.youtube.com/watch?v=M1S64BanCIE) | S09 | 恢复逻辑与工具交互 |
| 车辆分类 | [VYUjy2dA66A](https://www.youtube.com/watch?v=VYUjy2dA66A) | S07 | 体型、轴距与地形适应差异 |
| 新悬挂 | [GPU3EjVVP7Y](https://www.youtube.com/watch?v=GPU3EjVVP7Y) | S07 | 压缩、伸长、回弹与镜头稳定 |
| 恶劣环境工具 | [Elj1Nv5WwaI](https://www.youtube.com/watch?v=Elj1Nv5WwaI) | S07 | 工具如何减少持续受困 |

另有 3 条商店预告的名称和媒体地址已存入 [steam-media-metadata.json](sources/steam-media-metadata.json)；CDN 媒体地址可能变化，优先从商店或公告页回访。

## 5. 本次实际完成的证据工作

读取官方文本并核对来源；下载并逐张观察 14 张官方图；下载三套原型素材、读取各包许可、清点 GLB、查看预览，检查 SUV 节点结构；形成原创改编方案。素材完整性、相对链接和离线参考板检查结果见 [verification.json](checks/verification.json)。

未完成且不冒称：原作亲自试玩、视频动态测量、音频试听、目标浏览器驾驶测试、森林性能实测、最终资产优化。上述不足不影响进入本项目的灰盒验证，但会影响对原作动态细节的精确结论。
