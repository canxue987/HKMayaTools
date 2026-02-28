# HK Maya ToolBox (模块化智能工具箱)

![Maya Compatibility](https://img.shields.io/badge/Maya-2017%20to%202025+-0696D7.svg?style=flat)
![Python](https://img.shields.io/badge/Python-2.7%20%7C%203.7%20%7C%203.9-blue)
![PySide](https://img.shields.io/badge/PySide-2%20%7C%206-green)

**HK Maya ToolBox** 是一个为 Autodesk Maya 深度定制的模块化、数据驱动的高级工具箱系统。它不仅提供了一个现代化的 UI 来管理杂乱的 Maya 脚本，还引入了“环境劫持”、“窗口雷达抓捕”、“NAS 中央同步”以及“安全的原子级数据存储”等高级特性，旨在为技术美术（TA）和动画师团队提供极其稳定、高效的工具分发与使用体验。

---

## ✨ 核心特性 (Key Features)

### 🎨 智能工具画布 (Tool Canvas)
彻底解决 Maya 中工具窗口满天飞的痛点。
* **环境劫持 (ToolExecutionGuard)**：通过上下文管理器拦截 `cmds.window` 和 `cmds.showWindow`，强制将原生 Maya 弹窗工具无缝嵌入到统一的 MDI 画布中。
* **雷达抓捕机制**：对于绕过 cmds 的独立 PySide 窗口，工具箱会启动“雷达”检测活跃顶层窗口，强行将其吸附进画布。
* **瀑布流布局 (Smart Packing)**：内置智能排列算法，一键将画布内的所有工具面板紧凑排列，互不遮挡。

### ☁️ NAS 中央同步与权限管理
专为团队协作设计，支持工具的云端分发。
* **双模式生态**：区分普通用户与管理员（Admin）。普通用户创建的工具仅保存在本地（`User` 目录），管理员凭借密码发布工具时，可实现“服务器+本地”双写。
* **一键增量更新**：内置 `UpdateWorker` 后台线程，自动比对服务器与本地版本，一键同步最新的脚本、图标和配置，并自动清理废弃文件。

### 🛡️ 极其健壮的数据层 (Robust Data Core)
* **数据驱动**：工具列表、分类、快捷键、收藏夹全部由 JSON 驱动，解耦代码与数据。
* **原子级安全读写**：全局封装 `safe_json_load` 与 `safe_json_save`。采用 `.tmp` 临时文件替换机制，彻底杜绝因 Maya 崩溃或断电导致 JSON 配置文件清零的灾难。
* **ID 冲突自愈**：自动检测不同模块间的工具 ID 冲突并重新分配，保障数据唯一性。

### ⌨️ 动态快捷键与 UX 体验
* **原生快捷键转换**：完美解析 Qt 的 `QKeySequence`，将其转换为 Maya 原生的 `hotkey` (支持 k, ctl, alt, sht 参数组合)。
* **防冲突预警**：绑定快捷键前自动检测 Maya 现有绑定，拦截覆盖警告。
* **人性化交互**：支持工具拖拽至画布、右键菜单快捷管理、收藏夹机制以及内置的 Markdown 风格使用说明渲染器。

---

## 🚀 安装与配置 (Installation)

1. **获取代码**：
   将本仓库克隆或下载到本地任意目录（例如 `D:\MayaTools`）。

2. **核心配置 (`toolbox_core/config.py`)**：
   根据你的团队环境，修改配置文件中的服务器路径和管理员密码：
   ```python
   # 配置你的 NAS 或共享服务器路径
   SERVER_PATH = r"\\Your_NAS\MayaTools\ToolBox_Repo"
   # 设置工具发布的管理员密码
   ADMIN_PASSWORD = "your_password"
   ```

3. **在 Maya 中启动**：
   将 `launcher.py` 拖入 Maya 视口，或在脚本编辑器（Python）中执行以下代码即可呼出工具箱：
   ```python
   import sys
   # 将路径替换为你实际存放 launcher.py 的目录
   toolbox_path = r"D:\MayaTools"
   if toolbox_path not in sys.path:
       sys.path.insert(0, toolbox_path)
       
   import launcher
   launcher.show()
   ```

---

## 📂 目录结构 (Directory Structure)

```text
HK_MayaToolBox/
├── launcher.py               # 启动入口与热重载管理
├── toolbox_core/             # 核心系统代码
│   ├── config.py             # 全局路径与变量配置
│   ├── utils.py              # JSON 安全读写、ID生成、快捷键解析等工具函数
│   ├── ui.py                 # 主面板、Canvas 画布、环境劫持逻辑
│   ├── worker.py             # NAS 同步线程、双写发布逻辑
│   ├── widgets.py            # 自定义 UI 组件 (如 ToolButton)
│   ├── dialogs.py            # 发布、编辑、快捷键绑定等弹窗 UI
│   └── styles.py             # 全局 Qt QSS 样式表
├── modules/                  # 工具配置文件存放区 (JSON)
│   ├── 10_modeling.json      # (按前缀数字控制排序)
│   ├── 99_user.json          # 普通用户的私有工具存放处
│   └── hotkeys.json          # 用户的快捷键配置文件
├── scripts/                  # 工具脚本源码存放区 (.py)
│   └── User/                 # 用户私有脚本存放区
└── icons/                    # 图标存放区
```

---

## 🛠️ 使用指南 (Usage)

### 1. 发布新工具
* 点击左侧边栏的 **`＋` (发布工具)** 按钮。
* 填写工具名称、一句话提示及详细的使用说明。
* 粘贴你的 Python 脚本代码（大于 100 行会自动存为独立的 `.py` 文件）。
* 如果输入管理员密码，可以选择将其发布到公共分类（同步至 NAS）；否则将存入本地 `[本地] 99_user` 分类。

### 2. 画布吸附与管理
* 点击侧边栏的 **`▣` (Tool Canvas)** 打开工作台。
* 将工具箱里的工具按钮**拖拽**进画布中，即可生成吸附式的 MDI 窗口。
* 点击画布顶部的 **`⊞ 瀑布流排列`** 可以自动整理所有窗口。

### 3. 绑定快捷键
* 在任意工具按钮上 **右键 -> 设置快捷键**。
* 在弹出的输入框中直接按下键盘组合键（例如 `Ctrl+Shift+A`）。
* 点击保存，系统会自动判断是否与 Maya 现有热键冲突并完成注册。

---

## 🤝 贡献与反馈 (Contributing)

欢迎提交 Issue 和 Pull Request！如果你有好的 Maya 工具代码，也欢迎通过 PR 补充到 `scripts` 与 `modules` 目录中。

**已知兼容性：**
* 已在 Maya 2018-2024 (PySide2) 环境下稳定测试。
* 已兼容 Maya 2025+ (PySide6) 架构。

## 📄 许可证 (License)
本项目基于 [MIT License](LICENSE) 开源，允许自由修改与商业使用。
