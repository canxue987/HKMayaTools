# [utils.py]
# -*- coding: utf-8 -*-
import os
import json
import io
import re
import uuid

# === 导入 Maya 模块 (修复 NameError) ===
import maya.cmds as cmds
import maya.mel as mel

# 导入配置模块
import toolbox_core.config as config 

# --- PySide 兼容性 ---
try:
    from PySide2 import QtWidgets, QtCore, QtGui
except ImportError:
    try:
        from PySide6 import QtWidgets, QtCore, QtGui
    except ImportError:
        pass

# === 全局 JSON 安全读写封装 ===
def safe_json_load(filepath, default_val=None):
    """安全读取 JSON，带错误拦截与 Maya 视口警告兜底"""
    if default_val is None:
        default_val = {}
    if not os.path.exists(filepath):
        return default_val
    try:
        with io.open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        import traceback
        print(u"[HK ToolBox 错误] JSON读取失败: {} | 错误信息: {}".format(filepath, e))
        traceback.print_exc()
        try:
            # 尝试在 Maya 视口抛出警告，避免无声失败
            import maya.cmds as cmds
            cmds.warning(u"HKToolbox: 配置文件读取失败或损坏，请检查控制台: {}".format(os.path.basename(filepath)))
        except:
            pass
        return default_val

def safe_json_save(filepath, data):
    """安全写入 JSON，使用 .tmp 临时文件替换法防丢数据"""
    try:
        parent_dir = os.path.dirname(filepath)
        if not os.path.exists(parent_dir):
            os.makedirs(parent_dir)

        # 1. 先写入临时文件
        temp_path = filepath + ".tmp"
        with io.open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

        # 2. 写入成功后再替换原文件 (防止中途断电/崩溃导致原文件清空)
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except OSError:
                pass # 如果被占用可能删不掉
        os.rename(temp_path, filepath)
        return True
    except Exception as e:
        import traceback
        print(u"[HK ToolBox 错误] JSON保存失败: {} | 错误信息: {}".format(filepath, e))
        traceback.print_exc()
        try:
            import maya.cmds as cmds
            cmds.warning(u"HKToolbox: 配置文件保存失败: {}".format(os.path.basename(filepath)))
        except:
            pass
        return False
    
# === ID 生成器 ===
def generate_uid():
    """生成一个唯一的字符串ID"""
    return str(uuid.uuid4())


def get_favorites_path():
    """获取收藏配置文件的完整路径"""
    return os.path.join(config.MODULES_DIR, config.FAV_FILE_NAME)

def load_favorites_list():
    """读取本地收藏名单 (重构版)"""
    path = get_favorites_path()
    data = safe_json_load(path, default_val=[])
    if isinstance(data, list):
        return set(data)
    return set()

def save_favorites_list(fav_names):
    """保存收藏名单 (重构版)"""
    path = get_favorites_path()
    return safe_json_save(path, sorted(list(fav_names)))

def get_recent_tools_data():
    """
    【新增】专门获取最近使用的工具列表，不生成分类结构
    供 UI 在收藏夹底部调用
    """
    recent_path = get_recent_path()
    recent_tools = []
    
    # 1. 获取 ID 映射表 (为了通过 ID 找到工具详情)
    id_tool_map = {}
    modules_dir = getattr(config, "MODULES_DIR", "")
    if modules_dir and os.path.exists(modules_dir):
        files = [f for f in os.listdir(modules_dir) if f.endswith(".json")]
        for filename in files:
            # 排除非工具配置文件
            if filename in [config.FAV_FILE_NAME, config.HOTKEY_FILE_NAME, config.RECENT_FILE_NAME]: continue
            
            path = os.path.join(modules_dir, filename)
            data = safe_json_load(path, default_val={})
            
            # === 【核心修复点】增加类型判断，防止文件内容为列表时报错 ===
            if isinstance(data, dict):
                for tool in data.get("tools", []):
                    tid = tool.get("id", tool.get("name"))
                    # 确保把 source_file 也带上，方便后续操作
                    tool["__source_file__"] = path
                    id_tool_map[tid] = tool

    # 2. 读取 recent.json
    recent_ids = safe_json_load(recent_path, default_val=[])
    
    # 同样加上类型保护，防止 recent.json 损坏变成字典
    if isinstance(recent_ids, list):
        for rid in recent_ids:
            if rid in id_tool_map:
                import copy
                tool = copy.copy(id_tool_map[rid])
                recent_tools.append(tool)
        
    return recent_tools

# [utils.py] -> 找到 load_tools_data 函数并替换
def load_tools_data():  
    """
    加载模块并融合收藏状态 + 最近使用
    【优化】增加了 ID 冲突自动检测与修复机制
    """  
    all_categories = []  
    modules_dir = getattr(config, "MODULES_DIR", "")  
    if not modules_dir or not os.path.exists(modules_dir):  
        return []  

    fav_set = load_favorites_list()
    
    # --- 1. 准备文件列表 ---
    files = [f for f in os.listdir(modules_dir) if f.lower().endswith(".json")]
    exclude_files = [config.FAV_FILE_NAME, config.HOTKEY_FILE_NAME, config.RECENT_FILE_NAME]
    for exclude_file in exclude_files:
        if exclude_file in files:
            files.remove(exclude_file)
    files.sort()  
    
    # 建立一个 ID -> Tool 的映射字典
    id_tool_map = {}
    
    # 【新增】用于检测冲突的 ID 集合
    seen_ids = set()

    # --- 2. 遍历读取 ---
    for filename in files:  
        path = os.path.join(modules_dir, filename)  
        
        # 直接使用安全加载，不用再自己写 try...except 了
        data = safe_json_load(path, default_val={})
        
        if isinstance(data, dict) and "name" in data and "tools" in data:  
            valid_tools = []
            
            for tool in data["tools"]:  
                tool["__source_file__"] = path 
                
                # 确保有 ID
                if "id" not in tool:
                    tool["id"] = tool.get("name") # 兼容旧数据
                
                raw_id = tool["id"]
                
                # === 【核心优化】冲突检测逻辑 ===
                if raw_id in seen_ids:
                    # 发现冲突！生成临时新 ID
                    new_safe_id = generate_uid()
                    print(u"Warning: ID冲突检测 - 工具 '{}' (in {}) ID重复!".format(tool.get("name"), filename))
                    print(u"  -> 已自动重分配临时ID: {} -> {}".format(raw_id, new_safe_id))
                    tool["id"] = new_safe_id
                    raw_id = new_safe_id
                
                # 记录 ID
                seen_ids.add(raw_id)
                
                # 设置收藏状态
                if tool.get("name") in fav_set:
                    tool["favorite"] = True
                else:
                    tool["favorite"] = False
                    
                # 存入映射表
                id_tool_map[raw_id] = tool
                valid_tools.append(tool)

            # 更新该分类的工具列表 (使用处理过 ID 的列表)
            data["tools"] = valid_tools
            all_categories.append(data)  

    # 3. 生成 [收藏夹]
    fav_tools = []  
    for category in all_categories:  
        for tool in category.get("tools", []):  
            if tool.get("favorite", False):  
                fav_tools.append(tool)  
    
    if fav_tools:  
        all_categories.insert(0, {  
            "name": u"收藏夹",  
            "tools": fav_tools  
        })  

    return all_categories

def toggle_tool_favorite(tool_data):  
    """切换工具收藏状态"""  
    target_name = tool_data.get("name")
    if not target_name: return False

    fav_set = load_favorites_list()
    
    current_state = tool_data.get("favorite", False)
    new_state = not current_state
    tool_data["favorite"] = new_state 

    if new_state:
        fav_set.add(target_name)
    else:
        if target_name in fav_set:
            fav_set.remove(target_name)

    return save_favorites_list(fav_set)

# === ID 查找工具辅助函数 ===
def find_tool_by_id(tool_id):
    """通过 ID 查找工具数据"""
    modules_dir = getattr(config, "MODULES_DIR", "")
    if not modules_dir: return None
    
    files = [f for f in os.listdir(modules_dir) if f.lower().endswith(".json")]
    
    for filename in files:
        if filename in [config.FAV_FILE_NAME, config.HOTKEY_FILE_NAME]:
            continue

        path = os.path.join(modules_dir, filename)
        # 使用安全加载函数
        data = safe_json_load(path, default_val={})
        for tool in data.get("tools", []):
            tid = tool.get("id", tool.get("name"))
            if tid == tool_id:
                return tool
    return None

# === 快捷键管理 (核心修复部分) ===
def get_hotkeys_path():
    return os.path.join(config.MODULES_DIR, config.HOTKEY_FILE_NAME)

def load_hotkeys():
    """读取快捷键配置 (重构版)"""
    path = get_hotkeys_path()
    return safe_json_load(path, default_val={})

def save_hotkeys(data):
    """保存快捷键配置 (重构版)"""
    path = get_hotkeys_path()
    safe_json_save(path, data)

def parse_qt_key_sequence(key_seq):
    """
    将 Qt 快捷键字符串转换为 Maya 参数 (终极修正版)
    解决:
    1. Ctrl+A -> Ctrl+Shift+A 问题
    2. Ctrl+Shift+6 -> 失效问题 (需转换为 k='^', sht=False)
    """
    if not key_seq: return "", False, False, False

    # 1. 拆分修饰键和主键
    # 使用 rpartition('+') 从右边切一刀
    if "+" in key_seq:
        modifiers_str, _, raw_key = key_seq.rpartition("+")
    else:
        modifiers_str = ""
        raw_key = key_seq
        
    raw_key = raw_key.strip()
    mods = [m.lower().strip() for m in modifiers_str.split("+") if m.strip()]
    
    ctl = "ctrl" in mods
    alt = "alt" in mods
    shift = "shift" in mods 
    
    # 2. 映射表：Shift + 数字/符号 -> 对应符号
    # 针对标准美式键盘布局
    shift_symbol_map = {
        '1': '!', '2': '@', '3': '#', '4': '$', '5': '%',
        '6': '^', '7': '&', '8': '*', '9': '(', '0': ')',
        '-': '_', '=': '+', 
        '[': '{', ']': '}', '\\': '|',
        ';': ':', "'": '"',
        ',': '<', '.': '>', '/': '?',
        '`': '~'
    }

    # 3. 映射表：Qt 键名 -> Maya 键名
    qt_to_maya_map = {
        "Esc": "Escape", "Del": "Delete", "Ins": "Insert", 
        "PgUp": "Page_Up", "PgDown": "Page_Down",
        "Return": "Return", "Enter": "Enter", 
        "Backspace": "BackSpace",
        "Tab": "Tab", "Space": "Space", 
        "Home": "Home", "End": "End",
        "Left": "Left", "Right": "Right", "Up": "Up", "Down": "Down",
        "Print": "Print", "Pause": "Pause", "Help": "Help",
        "CapsLock": "CapsLock", "NumLock": "Num_Lock", "ScrollLock": "Scroll_Lock"
    }
    
    maya_key = raw_key
    
    # === 情况 A: 特殊功能键 (F1, Home, Enter...) ===
    if len(raw_key) > 1:
        if raw_key in qt_to_maya_map:
            maya_key = qt_to_maya_map[raw_key]
        else:
            # 比如 F1, F12，保持首字母大写
            maya_key = raw_key[0].upper() + raw_key[1:]
            
    # === 情况 B: 单字符键 (数字, 字母, 符号) ===
    else:
        # 1. 先检查是否是 Shift + 数字/符号 (解决 Ctrl+Shift+6 问题)
        if shift and raw_key in shift_symbol_map:
            maya_key = shift_symbol_map[raw_key]
            # 【关键】既然已经变成了符号(如^)，它本身就隐含了Shift，所以必须把 shift 标记关掉
            shift = False 
            
        # 2. 字母 (a-z, A-Z)
        # Maya 规则: k='A' 隐含 Shift; k='a' 无 Shift
        elif raw_key.isalpha():
            if shift:
                maya_key = raw_key.upper()
                # 对于字母，Maya 允许 k='A', sht=True 同时存在，不关也可以，但为了严谨可以保留 True
            else:
                maya_key = raw_key.lower()
                
        # 3. 其他无 Shift 的符号/数字 (比如单纯的 Ctrl+6)
        else:
            maya_key = raw_key # 保持原样 (如 '6')

    return maya_key, ctl, alt, shift

def register_hotkey(tool_id, key_seq):
    """在 Maya 中注册快捷键"""
    tool_data = find_tool_by_id(tool_id)
    if not tool_data: return False, u"找不到工具ID"
    
    safe_id = tool_id.replace("-", "_")
    cmd_name = "HK_Tool_{}".format(safe_id)
    annotation = u"HK Toolbox: {}".format(tool_data.get("name"))
    
    py_cmd = 'import toolbox_core.worker as w; w.execute_tool_by_id("{}")'.format(tool_id)
    
    try:
        if not cmds.runTimeCommand(cmd_name, exists=True):
            cmds.runTimeCommand(cmd_name, annotation=annotation, command=py_cmd, category="HK_Toolbox", commandLanguage="python")
        else:
            cmds.runTimeCommand(cmd_name, edit=True, command=py_cmd, annotation=annotation)
            
        name_cmd = cmd_name + "NameCommand"
        cmds.nameCommand(name_cmd, annotation=annotation, command=cmd_name)
        
        key, ctl, alt, shift = parse_qt_key_sequence(key_seq)
        
        print(u"Binding: k='{}', ctl={}, alt={}, sht={}".format(key, ctl, alt, shift))
        
        # === 【核心修复点】 参数名改为 k (keyShortcut) 和 sht (shiftModifier) ===
        cmds.hotkey(k=key, ctl=ctl, alt=alt, sht=shift, name=name_cmd)
        
        return True, u"绑定成功"
        
    except RuntimeError as e:
        return False, u"Maya拒绝: " + str(e)
    except Exception as e:
        return False, str(e)

def unregister_hotkey(key_seq):
    """解绑快捷键"""
    if not key_seq: return
    key, ctl, alt, shift = parse_qt_key_sequence(key_seq)
    try:
        # name="" 会移除用户定义的绑定，Maya 通常会自动回退到默认设置
        cmds.hotkey(k=key, ctl=ctl, alt=alt, sht=shift, name="")
    except:
        pass

def init_all_hotkeys():
    """启动时调用：注册所有快捷键"""
    hotkeys = load_hotkeys()
    count = 0
    for tid, key in hotkeys.items():
        if key:
            register_hotkey(tid, key)
            count += 1
    if count > 0:
        print(u"HK Toolbox: 已加载 {} 个快捷键".format(count))

def load_notice_text(filepath):
    if not os.path.exists(filepath): return ""
    try:
        with io.open(filepath, 'r', encoding='utf-8') as f: return f.read()
    except: return ""

# 【新增】读取全局使用说明
def load_guide_text():
    # 如果文件不存在，返回默认提示
    if not os.path.exists(config.GUIDE_FILE):
        return u"<h1>欢迎使用 HK Maya 工具箱</h1><p>暂无详细使用说明，请联系管理员添加。</p>"
    try:
        with io.open(config.GUIDE_FILE, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return u"读取说明文件失败: {}".format(e)
    
def get_recent_path():
    """
    获取最近使用记录文件的完整路径
    强制指向 ROOT_DIR (本地核心目录)，防止 config.MODULES_DIR 指向服务器导致无权写入
    """
    # 强制指定保存到本地根目录下的 modules 文件夹
    local_modules_dir = os.path.join(config.ROOT_DIR, "modules")
    
    # 如果文件夹不存在，创建一个
    if not os.path.exists(local_modules_dir):
        os.makedirs(local_modules_dir)
        
    return os.path.join(local_modules_dir, config.RECENT_FILE_NAME)

def add_to_recent(tool_data):
    """将工具添加到最近使用列表 (重构版)"""
    tool_id = tool_data.get("id", tool_data.get("name"))
    path = get_recent_path()
    
    # 1. 安全读取
    recent_ids = safe_json_load(path, default_val=[])
            
    # 2. 更新列表
    if tool_id in recent_ids:
        recent_ids.remove(tool_id)
        
    recent_ids.insert(0, tool_id) # 插到第一个
    
    if len(recent_ids) > 8:
        recent_ids = recent_ids[:8] # 保持最多 8 个
        
    # 3. 安全保存
    safe_json_save(path, recent_ids)

# === 快捷键冲突检测 ===
def check_hotkey_conflict(key_seq):
    """
    检查快捷键是否已被占用
    """
    if not key_seq:
        return False, None

    key, ctl, alt, shift = parse_qt_key_sequence(key_seq)
    
    try:
        # === 核心修改点 ===
        # 错误写法 (你之前遇到的报错): 
        # existing_cmd = cmds.hotkey(k=key, ctl=ctl, ... query=True)
        
        # 正确写法: 
        # 将 key 放在第一个位置，不要写 k=
        # 仅查询命令名称 (name=True)
        existing_cmd = cmds.hotkey(key, ctl=ctl, alt=alt, sht=shift, query=True, name=True)
        
        # 如果查询到了命令，且不是工具箱自己的 (HK_Tool_ 开头)，则视为冲突
        if existing_cmd and not existing_cmd.startswith("HK_Tool_"):
            return True, existing_cmd
            
        return False, None
        
    except RuntimeError:
        # 如果该按键从未被绑定过，Maya 可能会直接抛出 RuntimeError
        # 这种情况下说明没有冲突
        return False, None
    except Exception as e:
        print(u"检测快捷键冲突出错: {}".format(e))
        return False, None
    
def get_maya_window():
    for widget in QtWidgets.QApplication.topLevelWidgets():
        if widget.objectName() == 'MayaWindow':
            return widget
    return None