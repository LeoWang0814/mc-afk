# Minecraft AFK 自动横扫

面向 **Minecraft Java Edition** 的 Windows 挂机辅助工具，提供中文图形界面，用于配置攻击节奏、快捷栏布局与自动进食策略。发布版为单文件 `.exe`，下载后即可直接运行，无需额外安装 Python 或第三方依赖。

## 下载

- [下载适用于 x86 平台的版本](https://github.com/LeoWang0814/mc-afk/releases/download/v1.0.0/mc-afk-gui-x64.exe)
- [下载适用于 arm64 平台的版本](https://github.com/LeoWang0814/mc-afk/releases/download/v1.0.0/mc-afk-gui-arm64.exe)

## 界面概览

![界面预览](/ui-preview.png)

## 功能特性

- 中文图形界面，适合直接双击使用
- 根据剑的攻击速度计算满冷却攻击节奏，优先稳定触发横扫攻击
- 支持分别配置剑所在快捷栏格子与食物所在快捷栏格子
- 自动为不同食物类型设置独立的进食参数
- 通过全局热键 `Alt+C` 一键启动或暂停自动化
- 自动进食逻辑会结合食物恢复量、进食时长与堆叠上限进行估算
- 修改配置后，新设置会在下一次启动自动化时生效

## 支持的食物类型

当前版本支持这类适合快捷栏轮换的常规食物：

- 可直接放在快捷栏中
- 长按右键即可直接食用
- 不会留下空碗、空瓶等容器

已内置支持的食物包括：

- 熟猪排
- 牛排
- 金胡萝卜
- 熟羊肉
- 熟鸡肉
- 熟鲑鱼
- 面包
- 烤土豆
- 熟鳕鱼
- 苹果
- 胡萝卜
- 西瓜片
- 甜菜根
- 干海带

以下类型目前不在支持范围内：

- 蛋糕
- 蜂蜜瓶
- 汤类与炖菜
- 其他会留下容器或不适合当前快捷栏轮换逻辑的食物

## 快速使用

1. 启动程序或运行打包后的 `exe`。
2. 在界面中设置剑的攻击速度、剑所在格子、食物格子和食物类型。
3. 切回 Minecraft 游戏窗口。
4. 按 `Alt+C` 开始自动化。
5. 再按一次 `Alt+C` 可暂停自动化。
6. 关闭程序窗口会立即停止自动化。

## 从源码运行

如果你希望直接运行源码，仓库已提供环境定义文件：

- [environment.yml](./environment.yml)

创建运行环境：

```powershell
conda env create -f .\environment.yml
```

启动命令行版本：

```powershell
conda run -n mc-afk-automation python .\mc_afk_attack.py
```

启动图形界面版本：

```powershell
conda run -n mc-afk-automation python .\mc_afk_gui.py
```

也可以直接使用 PowerShell 启动脚本：

```powershell
.\run_mc_afk_gui.ps1
```

## 设计说明

本工具不会直接读取 Minecraft 游戏内状态。

自动进食基于本地模型估算，而不是读取真实饥饿值或真实物品数量。这意味着：

- 食物消耗按“进食尝试次数”估算
- 更适合固定挂机场景
- 更适合同一种食物填满选中的食物格

不同食物的进食时长并不完全一致，因此界面中保留了食物类型选择，而不是将所有食物视为统一参数。例如：

- 大多数常规食物进食时长约为 `1.6s`
- `干海带` 更快，约为 `0.865s`

## 使用注意事项

- 新配置不会强行中断当前正在运行的一次自动化流程
- 在界面中修改的配置，会在下一次按下 `Alt+C` 启动时生效
- 如果 Minecraft 以管理员权限运行，而本程序不是管理员权限，键鼠输入可能会被系统拦截

## 项目结构

- [mc_afk_gui.py](./mc_afk_gui.py)：中文图形界面入口
- [mc_afk_attack.py](./mc_afk_attack.py)：自动化核心逻辑
- [run_mc_afk_gui.ps1](./run_mc_afk_gui.ps1)：GUI 启动脚本
- [run_mc_afk.ps1](./run_mc_afk.ps1)：命令行启动脚本

## 许可证

本项目基于 [MIT License](./LICENSE) 开源发布。

## 作者

- 作者：[Nanoberry](https://github.com/LeoWang0814)
- 仓库：[LeoWang0814/mc-afk](https://github.com/LeoWang0814/mc-afk)
