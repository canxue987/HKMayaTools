# -*- coding: utf-8 -*-
import sys
import os
import importlib

# 1. 确保当前目录在 Python 路径中
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR in sys.path:
    sys.path.remove(CURRENT_DIR)
sys.path.insert(0, CURRENT_DIR) # 确保永远在第一位

# === 【关键修复】显式导入所有子模块 ===
# 必须先 import 进内存，reload 才能找到它们，否则会报 AttributeError
import toolbox_core.config
import toolbox_core.styles
import toolbox_core.utils
import toolbox_core.worker
import toolbox_core.dialogs
import toolbox_core.widgets
import toolbox_core.ui

print("Reloading Toolbox Core...")

# 2. 强制重载 (顺序：底层 -> 顶层)
# Level 1: 基础配置
importlib.reload(toolbox_core.config)
importlib.reload(toolbox_core.styles)

# Level 2: 逻辑功能
importlib.reload(toolbox_core.utils)
importlib.reload(toolbox_core.worker)

# Level 3: UI 组件
importlib.reload(toolbox_core.dialogs) 
importlib.reload(toolbox_core.widgets)

# Level 4: 主窗口
importlib.reload(toolbox_core.ui)

# --- 桥接函数 ---
def show():
    toolbox_core.ui.show()

if __name__ == "__main__":
    show()