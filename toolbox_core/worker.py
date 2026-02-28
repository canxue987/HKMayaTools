# -*- coding: utf-8 -*-
import os
import shutil
import json
import io
import time
from .utils import QtCore
from . import config
from . import utils

# =========================================================================
# 1. 更新线程类 (UpdateWorker - 修复版)
# =========================================================================
class UpdateWorker(QtCore.QThread):
    finished_signal = QtCore.Signal(bool, str)

    def run(self):
        try:
            # --- 1. 基础检查 ---
            if not os.path.exists(config.SERVER_PATH):
                self.finished_signal.emit(False, u"连接超时 or 路径不存在: " + config.SERVER_PATH)
                return

            srv_scripts = os.path.join(config.SERVER_PATH, 'scripts')
            srv_icons = os.path.join(config.SERVER_PATH, 'icons')
            srv_modules = os.path.join(config.SERVER_PATH, 'modules')
            srv_core = os.path.join(config.SERVER_PATH, 'toolbox_core')

            if not os.path.exists(srv_modules):
                self.finished_signal.emit(False, u"服务器 modules 路径不存在")
                return

            total_updated_count = 0

            # --- 2. 智能同步 Modules ---
            count_modules = self._smart_sync_folder(
                srv_modules, 
                config.MODULES_DIR, 
                protected_files = [ 
                    config.USER_FILE_NAME, 
                    config.FAV_FILE_NAME,
                    config.RECENT_FILE_NAME,
                    config.HOTKEY_FILE_NAME,
                    config.VERSION_FILE_NAME
                ]
            )
            total_updated_count += count_modules

            # --- 3. 同步其他资源 ---
            # 接收返回值并累加
            total_updated_count += self._copy_files_recursive(srv_scripts, config.SCRIPTS_DIR)
            total_updated_count += self._copy_files_recursive(srv_icons, config.ICONS_DIR)
            
            # 同步核心代码 (用于自身更新)
            if os.path.exists(srv_core):
                total_updated_count += self._copy_files_recursive(srv_core, config.CORE_DIR)

            # --- 4. 同步版本文件 ---
            if os.path.exists(config.SERVER_VERSION_FILE):
                shutil.copy2(config.SERVER_VERSION_FILE, config.LOCAL_VERSION_FILE)

            # === 结果反馈 ===
            if total_updated_count > 0:
                self.finished_signal.emit(True, u"更新完成 (变动文件数: {})".format(total_updated_count))
            else:
                self.finished_signal.emit(True, "NO_UPDATES")

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.finished_signal.emit(False, str(e))

    def _is_file_different(self, src, dst):
        """对比文件是否需要更新"""
        if not os.path.exists(dst):
            return True
        try:
            s_stat = os.stat(src)
            d_stat = os.stat(dst)
            # 大小不同
            if s_stat.st_size != d_stat.st_size:
                return True
            # 服务器时间比本地新 (容差1秒)
            if s_stat.st_mtime > d_stat.st_mtime + 1:
                return True
            return False
        except:
            return True

    def _smart_sync_folder(self, src_dir, dst_dir, protected_files=[]):
        """
        同步 Modules (不递归，只处理 json)
        """
        update_count = 0

        if not os.path.exists(dst_dir):
            os.makedirs(dst_dir)

        # 1. 从服务器复制到本地
        if os.path.exists(src_dir):
            server_files = set(os.listdir(src_dir))
            for f in server_files:
                if f in protected_files: continue # 保护本地配置

                src_path = os.path.join(src_dir, f)
                dst_path = os.path.join(dst_dir, f)
                
                if os.path.isfile(src_path):
                    if self._is_file_different(src_path, dst_path):
                        shutil.copy2(src_path, dst_path)
                        update_count += 1
        else:
            server_files = set()

        # 2. 清理本地多余文件
        local_files = set(os.listdir(dst_dir))
        for f in local_files:
            if f in protected_files: continue
            
            if f not in server_files:
                path = os.path.join(dst_dir, f)
                try:
                    if os.path.isdir(path): shutil.rmtree(path)
                    else: os.remove(path)
                    # update_count += 1 # 删除也算更新的话可以取消注释
                except: pass
        
        return update_count

    def _copy_files_recursive(self, src_dir, dst_dir):
        """递归同步：复制新文件 + 删除本地多余文件"""
        count = 0
        
        # 1. 基础检查
        if not os.path.exists(src_dir): return 0
        if not os.path.exists(dst_dir): os.makedirs(dst_dir)
        
        # 2. 正向复制 (Server -> Local)
        for f in os.listdir(src_dir):
            if f.startswith(".") or f.endswith(".pyc") or f == "__pycache__": continue
            
            src = os.path.join(src_dir, f)
            dst = os.path.join(dst_dir, f)
            
            try:
                if os.path.isfile(src):
                    # 【核心修复】这里之前缺少 _is_file_different 定义
                    if self._is_file_different(src, dst):
                        shutil.copy2(src, dst)
                        count += 1
                        print(u"已更新: {}".format(f))
                elif os.path.isdir(src):
                    # 递归进入子文件夹
                    count += self._copy_files_recursive(src, dst)
            except Exception as e:
                print(u"Copy Error [{}]: {}".format(f, e))
        
        # 3. 反向清理 (Local -> Delete)
        local_protected = [
            config.USER_FILE_NAME, config.FAV_FILE_NAME,
            config.RECENT_FILE_NAME, config.HOTKEY_FILE_NAME,
            config.VERSION_FILE_NAME, "__pycache__", "User", ".git"
        ]
        
        if os.path.exists(dst_dir):
            for f in os.listdir(dst_dir):
                if f in local_protected: continue
                if f.startswith(".") or f.endswith(".pyc"): continue

                src = os.path.join(src_dir, f)
                dst = os.path.join(dst_dir, f)

                if not os.path.exists(src):
                    try:
                        if os.path.isdir(dst): shutil.rmtree(dst)
                        else: os.remove(dst)
                        print(u"移除本地废弃文件: {}".format(f))
                    except Exception as e:
                        print(u"Delete Error [{}]: {}".format(f, e))
                        
        return count


# =========================================================================
# 2. 工具修改函数 (支持 Admin 双写)
# =========================================================================
def update_tool(original_tool_data, new_info, is_admin):
    """
    更新工具逻辑 (修复版：支持双写 + 彻底清理旧文件)
    """
    import json
    import shutil
    import time
    import io
    import os
    from . import config
    from . import utils
    
    source_file = original_tool_data.get("__source_file__")
    target_file = new_info.get("category_file")
    
    # 1. 权限检查
    # 如果源文件在服务器上，且不是管理员，则禁止修改
    if config.SERVER_PATH in source_file and not is_admin:
        return False, u"权限不足：无法修改服务器上的公共工具！"
    
    # 2. 确定写入目标 (New Entry Targets)
    # 如果是 Admin，主要目标是 Server，但也需要在本地写一份以便立即生效
    # 如果是 User，只能写 Local
    target_json_paths = []
    
    if is_admin:
        filename = os.path.basename(target_file)
        # 真正的服务器路径
        server_json_path = os.path.join(config.SERVER_PATH, "modules", filename)
        # 管理员的本地路径
        local_json_path = os.path.join(config.MODULES_DIR, filename)
        
        target_json_paths = [local_json_path, server_json_path]
    else:
        # 普通用户试图写入服务器路径 -> 拦截
        if config.SERVER_PATH in target_file:
             return False, u"权限不足：需要管理员密码才能写入服务器文件。"
        target_json_paths = [target_file] # 只有本地

    # 3. 准备新数据
    tool_id = original_tool_data.get("id")
    # 如果旧数据没有ID，生成一个新的
    if not tool_id or tool_id == original_tool_data.get("name"):
        tool_id = utils.generate_uid()

    final_tool_data = {
        "id": tool_id,
        "name": new_info["name"],
        "type": "command", 
        "icon": new_info["icon"],
        "tooltip": new_info["tooltip"],
        "help_content": new_info.get("help_content", ""),
        "command": "", 
        "favorite": original_tool_data.get("favorite", False)
    }

    # 4. 处理脚本文件 (Script Handling)
    raw_cmd = new_info["command"]
    final_tool_data["command"] = raw_cmd
    
    # 如果代码较长，保存为 .py 文件
    if "\n" in raw_cmd and len(raw_cmd) > 100 and "import " not in raw_cmd[:20]:
        safe_name = "".join([c for c in new_info["name"] if c.isalnum() or c in ('_')]).strip()
        if not safe_name: safe_name = "tool"
        
        script_filename = "tool_{}_{}.py".format(safe_name, int(time.time()))

        # 【双写脚本逻辑】
        save_dirs = [config.SCRIPTS_DIR] # 总是写本地
        if is_admin:
            save_dirs.append(os.path.join(config.SERVER_PATH, "scripts")) # Admin 追加写服务器
            
        script_write_success = False # <--- 【新增】标记是否至少成功写入一次
            
        for s_dir in save_dirs:
            if not os.path.exists(s_dir): 
                try:
                    os.makedirs(s_dir)
                except Exception:
                    pass
            
            script_path = os.path.join(s_dir, script_filename)
            try:
                with io.open(script_path, "w", encoding="utf-8") as f:
                    f.write(raw_cmd)
                script_write_success = True # <--- 只要有一处成功即可
            except Exception as e: 
                print(u"写入脚本文件失败 [{}]: {}".format(script_path, e))
                pass # 忽略单个写入失败
                
        if script_write_success:
            final_tool_data["command"] = "import {0}\n{0}.run()".format(script_filename.replace(".py",""))
        else:
            # <--- 【新增兜底拦截】如果全部写入失败，直接中断执行，保护 JSON 不被污染
            return False, u"严重错误：代码文件写入失败！请检查本地或服务器权限、磁盘空间。"

    # 5. 执行更新操作
    # =========================================================
    # A. 从旧文件删除 (Cleanup Old Entry)
    # =========================================================
    cleanup_targets = []
    if os.path.exists(source_file):
        cleanup_targets.append(source_file)
        
    if is_admin:
        if config.MODULES_DIR in source_file:
            f_name = os.path.basename(source_file)
            if f_name != config.USER_FILE_NAME:
                srv_path = os.path.join(config.SERVER_PATH, "modules", f_name)
                cleanup_targets.append(srv_path)
        elif config.SERVER_PATH in source_file:
            cleanup_targets.append(source_file)

    for old_json_path in set(cleanup_targets):
        if os.path.exists(old_json_path):
            source_json = utils.safe_json_load(old_json_path)
            if not source_json or "tools" not in source_json:
                continue
            
            current_id = original_tool_data.get("id")
            current_name = original_tool_data.get("name")
            original_count = len(source_json["tools"])
            
            new_tools = []
            for t in source_json["tools"]:
                t_id = t.get("id", t.get("name"))
                if t_id == current_id: continue
                if (not current_id) and (t.get("name") == current_name): continue
                new_tools.append(t)
            
            # 只有当数量发生变化时才写入，避免无意义的 IO
            if len(new_tools) < original_count:
                source_json["tools"] = new_tools
                utils.safe_json_save(old_json_path, source_json)

    # =========================================================
    # B. 写入新文件 (Write New Entry)
    # =========================================================
    for json_path in target_json_paths:
        cat_name = new_info.get("category_name", os.path.basename(json_path).replace(".json",""))
        
        # 安全加载，如果文件不存在会自动使用 default_val 创建基本骨架
        data = utils.safe_json_load(json_path, default_val={"name": cat_name, "tools": []})
        
        # 追加新数据 (先简单排重防止 ID 冲突)
        if "tools" not in data: data["tools"] = []
        data["tools"] = [t for t in data["tools"] if t.get("id") != tool_id]
        data["tools"].append(final_tool_data)
        
        utils.safe_json_save(json_path, data)
        
    # 如果是管理员，顺便更新一下版本号，通知其他用户
    if is_admin and hasattr(utils, "update_server_version"):
        utils.update_server_version()

    return True, u"修改成功！"


# =========================================================================
# 3. 其他辅助函数
# =========================================================================

def execute_tool_by_id(tool_id):
    """快捷键调用入口"""
    tool_data = utils.find_tool_by_id(tool_id)
    if tool_data:
        import maya.mel as mel
        msg = u"执行: {}".format(tool_data.get("name"))
        mel.eval('inViewMessage -smg "{}" -pos topCenter -bkc 0x00000000 -fade;'.format(msg))
        execute_tool(tool_data)
    else:
        print(u"HK Toolbox Error: 找不到 ID 为 {} 的工具".format(tool_id))

def execute_tool(tool_data):
    import maya.mel as mel
    import sys
    import importlib
    import traceback
    
    if config.SCRIPTS_DIR not in sys.path:
        sys.path.insert(0, config.SCRIPTS_DIR)
    
    tool_type = tool_data.get("type", "command")
    cmd = tool_data.get("command", "").strip()
    
    try:
        if tool_type == "command":
            if cmd.endswith(";"): 
                 mel.eval(cmd)
            else:
                try:
                    exec(cmd, globals(), locals())
                except NameError as e:
                    error_msg = str(e)
                    if "name '" in error_msg and "' is not defined" in error_msg:
                        missing_name = error_msg.split("'")[1]
                        print(u"尝试自动加载模块: {}".format(missing_name))
                        try:
                            mod = importlib.import_module(missing_name)
                            importlib.reload(mod)
                            globals()[missing_name] = mod
                            exec(cmd, globals(), locals())
                        except Exception as e2:
                            print(u"自动加载失败: {}".format(e2))
                            raise e
                    else:
                        raise e

        elif tool_type == "script":
            script_path = os.path.join(config.SCRIPTS_DIR, cmd)
            if os.path.exists(script_path):
                with io.open(script_path, "r", encoding="utf-8") as f:
                    exec(f.read(), globals(), locals())
            else:
                print(u"脚本文件不存在: " + script_path)
    except Exception as e:
        print(u"工具执行出错: " + str(e))
        traceback.print_exc()

def publish_tool(is_admin, tool_data, category_filename, icon_source_path, category_name=None):
    """
    发布工具逻辑 (支持 Admin 双写)
    """
    import time
    from .utils import generate_uid 

    # 1. 确定所有需要写入的目标路径
    targets = []
    # 总是写本地
    targets.append({
        "modules": config.MODULES_DIR,
        "scripts": config.SCRIPTS_DIR,
        "icons": config.ICONS_DIR
    })
    # Admin 额外写服务器
    if is_admin:
        targets.append({
            "modules": os.path.join(config.SERVER_PATH, "modules"),
            "scripts": os.path.join(config.SERVER_PATH, "scripts"),
            "icons": os.path.join(config.SERVER_PATH, "icons")
        })
    else:
        category_filename = config.USER_FILE_NAME

    from .utils import generate_uid, find_tool_by_id
    
    new_id = generate_uid()
    # 偏执检查：如果生成的 ID 居然真的存在 (几率极低)，或者与内存中缓存的冲突，则重生成
    # 注意：find_tool_by_id 依赖于已加载的内存数据
    while find_tool_by_id(new_id):
        new_id = generate_uid()
        
    tool_data["id"] = new_id

    # 处理脚本
    raw_command = tool_data.get("command", "").strip()
    script_content = None 
    script_filename = None

    if "\n" in raw_command or len(raw_command) > 100:
        safe_name = "".join([c for c in tool_data["name"] if c.isalnum() or c in ('_')]).strip()
        if not safe_name: safe_name = "tool"
        
        script_filename = "tool_{}_{}.py".format(safe_name, int(time.time()))
        script_content = raw_command
        
        module_name = script_filename.replace(".py", "")
        tool_data["command"] = "import {0}\n{0}.run()".format(module_name)

    # 处理图标
    final_icon_name = "default.png"
    if icon_source_path and os.path.exists(icon_source_path):
        ext = os.path.splitext(icon_source_path)[-1]
        safe_name = "".join([c for c in tool_data["name"] if c.isalnum() or c in (' ','_','-')]).strip()
        final_icon_name = "{}_{}{}".format(safe_name, int(time.time()), ext)
    
    tool_data["icon"] = final_icon_name

    error_msgs = []
    
    # 循环写入所有目标 (Local + Server)
    for paths in targets:
        try:
            # --- 脚本与图标保存逻辑保持不变 ---
            if script_filename and script_content:
                if not os.path.exists(paths["scripts"]): os.makedirs(paths["scripts"])
                s_path = os.path.join(paths["scripts"], script_filename)
                with io.open(s_path, "w", encoding="utf-8") as f:
                    f.write(script_content)

            if icon_source_path and final_icon_name != "default.png":
                if not os.path.exists(paths["icons"]): os.makedirs(paths["icons"])
                t_icon_path = os.path.join(paths["icons"], final_icon_name)
                import shutil
                shutil.copy2(icon_source_path, t_icon_path)

            # --- JSON 写入逻辑重构 ---
            if not os.path.exists(paths["modules"]): os.makedirs(paths["modules"])
            json_path = os.path.join(paths["modules"], category_filename)

            # 决定分类名称
            if category_name: display = category_name
            else: display = category_filename.replace(".json", "")
            
            # 使用安全加载获取数据或初始化骨架
            data = utils.safe_json_load(json_path, default_val={"name": display, "tools": []})
            if "tools" not in data: data["tools"] = []
            
            # 排重并覆盖
            new_tools_list = [t for t in data["tools"] if t.get("id") != tool_data["id"] and t.get("name") != tool_data["name"]]
            new_tools_list.append(tool_data)
            data["tools"] = new_tools_list
            
            # 安全保存
            if not utils.safe_json_save(json_path, data):
                error_msgs.append(u"保存 JSON 失败: " + json_path)

        except Exception as e:
            error_msgs.append(str(e))

    if error_msgs:
        return False, u"部分写入失败: " + ";".join(error_msgs)
    
    location_str = u"服务器+本地" if is_admin else u"本地"
    return True, u"发布成功 ({})".format(location_str)

class CheckUpdateWorker(QtCore.QThread):
    result_signal = QtCore.Signal(bool, dict)

    def run(self):
        if not os.path.exists(config.SERVER_VERSION_FILE):
            self.result_signal.emit(False, {})
            return

        # 安全加载服务端数据
        server_data = utils.safe_json_load(config.SERVER_VERSION_FILE, default_val={})
        server_time = server_data.get("timestamp", 0)

        # 安全加载本地端数据
        local_time = 0
        if os.path.exists(config.LOCAL_VERSION_FILE):
            local_data = utils.safe_json_load(config.LOCAL_VERSION_FILE, default_val={})
            local_time = local_data.get("timestamp", 0)
        
        if server_time > local_time + 1:
            self.result_signal.emit(True, server_data)
        else:
            self.result_signal.emit(False, server_data)