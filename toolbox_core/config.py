# -*- coding: utf-8 -*-
import os
import sys

# --- 核心配置 ---
SERVER_PATH = r"\\Haike_Nas\MayaTools\ToolBox_Repo"
ADMIN_PASSWORD = "10249585"  # 管理员密码

# --- 路径自动获取 ---
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 比如 D:/MayaToolBox/toolbox_core -> D:/MayaToolBox

SCRIPTS_DIR = os.path.join(ROOT_DIR, 'scripts')
ICONS_DIR = os.path.join(ROOT_DIR, 'icons')
MODULES_DIR = os.path.join(ROOT_DIR, "modules")

# === 新增：定义用户专用目录 ===
USER_SCRIPTS_DIR = os.path.join(SCRIPTS_DIR, "User")
USER_ICONS_DIR = os.path.join(ICONS_DIR, "User")

# 确保文件夹存在
if not os.path.exists(USER_SCRIPTS_DIR):
    os.makedirs(USER_SCRIPTS_DIR)
if not os.path.exists(USER_ICONS_DIR):
    os.makedirs(USER_ICONS_DIR)

# 核心代码目录 (用于自我更新)
CORE_DIR = os.path.join(ROOT_DIR, "toolbox_core")

# === 修改：将 User 脚本目录也加入环境变量 ===
# 这样 import tool_abc 时，无论它在 scripts 还是 scripts/User 都能被找到
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)
    
if USER_SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, USER_SCRIPTS_DIR)

# 公告文件路径
NOTICE_FILE = os.path.join(SERVER_PATH, 'notice.txt')

# 【新增】全局使用说明文件路径
GUIDE_FILE = os.path.join(SERVER_PATH, 'guide.txt')

# 【新增】定义用户的本地专用文件名为 "99_user.json"
USER_FILE_NAME = "99_user.json"

# 【新增】定义收藏夹配置文件名
FAV_FILE_NAME = "favorites.json"

# 确保 Scripts 目录在环境变量中
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR) 
# 注意：上面这行必须有缩进！

# 【新增】定义收藏夹配置文件名
FAV_FILE_NAME = "favorites.json"

# 【新增】定义快捷键配置文件名
HOTKEY_FILE_NAME = "hotkeys.json"

# 【新增】定义收藏夹配置文件名
FAV_FILE_NAME = "favorites.json"

# 【新增】定义最近使用记录文件名
RECENT_FILE_NAME = "recent.json" # <--- 添加这一行

# 【新增】定义快捷键配置文件名
HOTKEY_FILE_NAME = "hotkeys.json"

# [config.py] 添加
VERSION_FILE_NAME = "version.json"
SERVER_VERSION_FILE = os.path.join(SERVER_PATH, VERSION_FILE_NAME)
LOCAL_VERSION_FILE = os.path.join(ROOT_DIR, VERSION_FILE_NAME)

# 【新增】定义最近使用记录文件名
RECENT_FILE_NAME = "recent.json"

# 【新增】定义快捷键配置文件名
HOTKEY_FILE_NAME = "hotkeys.json"

# === 【新增】定义画布布局配置文件名 ===
CANVAS_LAYOUT_FILE = "canvas_layout.json"