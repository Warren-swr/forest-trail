# 制作名单与素材来源

## 背景音乐

游戏内的背景音乐全部来自 Kevin MacLeod 的免费曲库 incompetech.com，许可证为 Creative Commons 署名 4.0（CC BY 4.0，<https://creativecommons.org/licenses/by/4.0/>）。可以商用和改编，条件是署名。

| 游戏内用途 | 曲名 | 作者 | 来源 | 处理 |
| --- | --- | --- | --- | --- |
| 白天歌单 1 | Wholesome | Kevin MacLeod | <https://incompetech.com/music/royalty-free/mp3-royaltyfree/Wholesome.mp3> | 响度归一到 -18 LUFS，96 kbps MP3 |
| 白天歌单 2 | Porch Swing Days - slower | Kevin MacLeod | <https://incompetech.com/music/royalty-free/mp3-royaltyfree/Porch%20Swing%20Days%20-%20slower.mp3> | 同上 |
| 夜晚歌单 1 | Healing | Kevin MacLeod | <https://incompetech.com/music/royalty-free/mp3-royaltyfree/Healing.mp3> | 同上，截取前 5 分钟，末尾 8 秒淡出 |
| 夜晚歌单 2 | Frost Waltz | Kevin MacLeod | <https://incompetech.com/music/royalty-free/mp3-royaltyfree/Frost%20Waltz.mp3> | 同上 |
| 标题页 / 演示模式 | Lasting Hope | Kevin MacLeod | <https://incompetech.com/music/royalty-free/mp3-royaltyfree/Lasting%20Hope.mp3> | 同上 |

署名文本（游戏内“制作名单”页同样显示）：

> "Wholesome", "Porch Swing Days - slower", "Healing", "Frost Waltz", "Lasting Hope" — Kevin MacLeod (incompetech.com). Licensed under Creative Commons: By Attribution 4.0 License. http://creativecommons.org/licenses/by/4.0/

文件位于 `public/assets/music/`。转码命令见 `docs/DESIGN.md` 第 9 节。

## 其他素材

除上述音乐外，所有内容都是本项目原创，没有使用第三方模型、贴图或音效：

- **模型：**三辆车、树木、岩石、建筑、道具和动物都由 `art/blender/*.py` 在 Blender 中程序化生成。
- **贴图：**地形、天空、车灯光斑都在运行时由着色器或 Canvas 生成。
- **音效：**发动机、轮胎、泥水、风、溪流、鸟、虫鸣、猫头鹰和绞盘都用 WebAudio 实时合成。

车辆外观参考 Land Rover Defender 90、Toyota Land Cruiser FJ60 与 Toyota Hilux RN46，由项目自行创建模型与探险装备。参考来源、结构和游戏调校范围见 [VEHICLE-FIDELITY.md](VEHICLE-FIDELITY.md)。车型名称和标识归各自品牌所有。

当前 Toyota 使用旧版风格精修样车，参考 Toyota 官方 FJ60 车型档案；模型由本项目在旧版基础上创建，未引入第三方车辆网格或贴图。见 [TOYOTA-TRAIL-STUDY.md](TOYOTA-TRAIL-STUDY.md)。
