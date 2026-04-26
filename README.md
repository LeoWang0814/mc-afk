# Minecraft AFK 自动横扫

一个面向 Minecraft Java Edition 的挂机辅助工具。

它提供了一个中文图形界面，用来配置剑的攻击速度、快捷栏布局和食物类型。程序默认暂停，按 `Alt+C` 开始或暂停自动化；关闭窗口会立即停止程序。

## 功能

- 中文 GUI，适合后续直接打包成 Windows `.exe`
- 按剑的攻击速度计算满冷却攻击节奏，优先稳定触发横扫之刃
- 支持选择：
  - 哪个快捷栏格子放剑
  - 哪些快捷栏格子放食物
  - 使用哪一种可直接手持食用的食物
  - 剑的攻击速度
- 使用全局热键 `Alt+C` 启动和暂停
- 自动进食，按食物恢复量、进食时长和堆叠上限做估算
- 修改配置后，会在下一次 `Alt+C` 启动自动化时生效

## 当前支持的食物类型

当前 GUI 只提供这类食物：

- 能直接放在快捷栏里
- 长按右键就能直接吃下去
- 不会留下空碗、空瓶等容器

这意味着像蛋糕、蜂蜜瓶、汤、炖菜这类物品不在当前支持范围内。

大多数这类食物在 Java 版中的进食时长约为 `1.6s`，但并不完全一致，例如：

- `干海带` 更快，约 `0.865s`
- `蜂蜜瓶` 更慢，约 `2.0s`
- `蛋糕` 是放置后分片食用，不适合当前这套快捷栏轮换逻辑

因此，GUI 里保留了食物类型选择，不把所有食物都当成同一进食时长处理。

## 运行环境

- Windows
- Anaconda / Miniconda
- Python `3.11`

当前仓库提供的环境定义文件：

- [environment.yml](./environment.yml)

创建环境：

```powershell
conda env create -f .\environment.yml
```

## 启动方式

命令行入口：

```powershell
conda run -n mc-afk-automation python .\mc_afk_attack.py
```

GUI 入口：

```powershell
conda run -n mc-afk-automation python .\mc_afk_gui.py
```

也可以直接运行 PowerShell 启动脚本：

```powershell
.\run_mc_afk_gui.ps1
```

## 使用说明

1. 启动 GUI。
2. 在窗口中设置：
   - 剑的攻击速度
   - 哪个格子放剑
   - 哪些格子放食物
   - 食物类型
3. 切回 Minecraft。
4. 按 `Alt+C` 开始自动化。
5. 再按一次 `Alt+C` 暂停。
6. 关闭窗口会立即停止程序。

注意：

- 新配置不会强行打断当前这次运行。
- 你在窗口中修改的设置，会在下一次 `Alt+C` 启动自动化时生效。
- 如果 Minecraft 以管理员权限运行，而脚本不是管理员权限，键鼠输入可能被系统拦截。

## 项目结构

- [mc_afk_gui.py](./mc_afk_gui.py)：中文图形界面入口
- [mc_afk_attack.py](./mc_afk_attack.py)：自动化核心逻辑
- [run_mc_afk_gui.ps1](./run_mc_afk_gui.ps1)：GUI 启动脚本
- [run_mc_afk.ps1](./run_mc_afk.ps1)：命令行启动脚本

## 设计约束

这个工具不会直接读取 Minecraft 游戏内状态。

因此，自动进食基于本地模型估算，而不是读取真实饥饿值或真实物品数量。这是当前版本的设计前提，也意味着：

- 食物消耗按“进食尝试次数”估算
- 更适合固定挂机场景
- 更适合使用同一种食物填满选中的食物格

## 许可证

本项目使用 [MIT License](./LICENSE)。

## 作者

- 作者：[Nanoberry](https://github.com/LeoWang0814)
- 仓库：[LeoWang0814/mc-afk](https://github.com/LeoWang0814/mc-afk)
