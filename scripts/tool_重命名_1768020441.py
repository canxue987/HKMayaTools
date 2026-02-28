# -*- coding: utf-8 -*-
import maya.cmds as cmds
import maya.api.OpenMaya as om
from functools import partial


# --- 全局 UI 控件存储 ---
UI_ELEMENTS = {}


# --- 核心逻辑 ---


def get_true_name(obj_path):
    """提取不带路径的对象短名称"""
    return obj_path.split("|")[-1]


def update_selection_list(selection, old_name, new_name):
    """当父层级重命名后，同步更新列表中的子对象路径引用"""
    for i in range(len(selection)):
        selection[i] = selection[i].replace(old_name, new_name)
    return selection


def do_select_all(*args):
    """选择场景中所有对象"""
    cmds.select(ado=True, hi=True)
    om.MGlobal.displayInfo("已选择场景中所有对象")


def do_select_by_name(*args):
    """按名称/通配符选择"""
    search_pattern = cmds.textField(UI_ELEMENTS['SelectName'], q=True, text=True)
    if not search_pattern:
        return
    try:
        selection = cmds.ls(search_pattern, l=True)
        if selection:
            cmds.select(selection)
        else:
            om.MGlobal.displayWarning(f"未找到匹配名称的对象: {search_pattern}")
    except Exception as e:
        om.MGlobal.displayError(str(e))


def do_rename_and_number(*args):
    """核心功能：重命名并编号"""
    try:
        start_val = int(cmds.textField(UI_ELEMENTS['StartValue'], q=True, text=True))
        padding = int(cmds.textField(UI_ELEMENTS['PaddingValue'], q=True, text=True))
        mode = cmds.radioButtonGrp(UI_ELEMENTS['NumberCheck'], q=True, select=True) # 1:数字, 2:字母
        base_name = cmds.textField(UI_ELEMENTS['RenameText'], q=True, text=True)
        
        selection = cmds.ls(selection=True, sn=True)
        if not selection:
            return om.MGlobal.displayWarning("请先选择对象")


        letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        
        for i, obj in enumerate(selection):
            old_short_name = get_true_name(obj)
            
            if mode == 1: # 数字模式
                suffix = f"{start_val:0{padding}d}"
                new_short_name = f"{base_name}_{suffix}"
            else: # 字母模式
                suffix = letters[i % 26]
                new_short_name = f"{base_name}_{suffix}"
            
            new_full_path = cmds.rename(obj, new_short_name)
            selection = update_selection_list(selection, old_short_name, new_short_name)
            start_val += 1
            
        om.MGlobal.displayInfo("重命名完成")
    except Exception as e:
        om.MGlobal.displayError(f"执行出错: {e}")


def do_remove_chars(mode, *args):
    """移除字符：开头、末尾或两端"""
    first_count = int(cmds.textField(UI_ELEMENTS['RemoveFirst'], q=True, text=True))
    end_count = int(cmds.textField(UI_ELEMENTS['RemoveEnd'], q=True, text=True))
    selection = cmds.ls(selection=True, sn=True)


    for obj in selection:
        old_short_name = get_true_name(obj)
        new_name = old_short_name
        
        if mode == "all":
            new_name = old_short_name[first_count : -end_count if end_count > 0 else None]
        elif mode == "begin":
            new_name = old_short_name[first_count:]
        elif mode == "end":
            new_name = old_short_name[: -end_count if end_count > 0 else None]
        elif mode == "step_forward": # 移除首个字符
            new_name = old_short_name[1:]
        elif mode == "step_backward": # 移除末尾字符
            new_name = old_short_name[:-1]


        if new_name and new_name != old_short_name:
            cmds.rename(obj, new_name)
            selection = update_selection_list(selection, old_short_name, new_name)


def do_remove_pasted(*args):
    """清除 Maya 导入常见的 'pasted__' 前缀"""
    selection = cmds.ls("pasted__*", sn=True)
    if not selection:
        return om.MGlobal.displayInfo("未发现带有 'pasted__' 前缀的对象")
        
    for obj in selection:
        old_short_name = get_true_name(obj)
        new_name = old_short_name.replace("pasted__", "")
        cmds.rename(obj, new_name)


def do_prefix_suffix(is_suffix, *args):
    """添加自定义前后缀"""
    fix_text = cmds.textField(UI_ELEMENTS['SuffixText' if is_suffix else 'PrefixText'], q=True, text=True)
    selection = cmds.ls(selection=True, sn=True)
    
    for obj in selection:
        old_short_name = get_true_name(obj)
        new_name = f"{old_short_name}{fix_text}" if is_suffix else f"{fix_text}{old_short_name}"
        cmds.rename(obj, new_name)
        selection = update_selection_list(selection, old_short_name, new_name)


def do_quick_suffix(suffix_text, *args):
    """快速添加预设后缀 (_Grp, _Geo 等)"""
    selection = cmds.ls(selection=True, sn=True)
    for obj in selection:
        old_short_name = get_true_name(obj)
        new_name = f"{old_short_name}{suffix_text}"
        cmds.rename(obj, new_name)
        selection = update_selection_list(selection, old_short_name, new_name)


def do_search_replace(*args):
    """搜索并替换名称"""
    search = cmds.textField(UI_ELEMENTS['SearchText'], q=True, text=True)
    replace = cmds.textField(UI_ELEMENTS['ReplaceText'], q=True, text=True)
    mode = cmds.radioButtonGrp(UI_ELEMENTS['SRCheck'], q=True, select=True)
    
    if mode == 1: # 已选择
        selection = cmds.ls(selection=True, sn=True)
    elif mode == 2: # 层级
        selection = cmds.ls(selection=True, hi=True, sn=True)
    else: # 所有
        selection = cmds.ls(dag=True, sn=True)


    for obj in selection:
        if search in obj:
            old_short_name = get_true_name(obj)
            new_name = old_short_name.replace(search, replace)
            cmds.rename(obj, new_name)
            selection = update_selection_list(selection, old_short_name, new_name)


# --- UI 界面 ---


def run_ui():
    sizeX = 240
    version = "v1.1 (Py3)"
    win_id = "igEzRenameWin"
    
    if cmds.window(win_id, exists=True):
        cmds.deleteUI(win_id)
    
    window = cmds.window(win_id, title=f"ig Easy Rename Tool {version}", widthHeight=(sizeX+10, 550), mnb=True, mxb=False, sizeable=False)
    
    main_layout = cmds.columnLayout(adj=True, co=["both", 5])


    # --- 选择区域 ---
    cmds.separator(h=10, style="none")
    cmds.button(label="选择所有对象", h=25, c=do_select_all, bgc=[0.2, 0.2, 0.2])
    cmds.separator(h=5, style="none")
    
    cmds.rowLayout(nc=2, ad2=2, cw2=[80, 150])
    cmds.button(label="按名称选择", c=do_select_by_name)
    UI_ELEMENTS['SelectName'] = cmds.textField(ann="支持通配符，如 *_grp")
    cmds.setParent(main_layout)
    
    cmds.separator(h=10, style="in")


    # --- 重命名与编号 ---
    cmds.text(label="重命名与编号:", align="left", font="boldLabelFont")
    cmds.rowLayout(nc=2, ad2=2, cw2=[60, 170])
    cmds.text(label="  名称:")
    UI_ELEMENTS['RenameText'] = cmds.textField()
    cmds.setParent(main_layout)


    cmds.rowLayout(nc=4, cw4=[60, 50, 60, 50])
    cmds.text(label="  起始:")
    UI_ELEMENTS['StartValue'] = cmds.textField(text="1")
    cmds.text(label="  位数:")
    UI_ELEMENTS['PaddingValue'] = cmds.textField(text="2")
    cmds.setParent(main_layout)


    UI_ELEMENTS['NumberCheck'] = cmds.radioButtonGrp(labelArray2=['数字', '字母'], nrb=2, sl=1, cw2=[100, 100])
    cmds.button(label="重命名并编号", h=30, bgc=[0.1, 0.5, 0.3], c=do_rename_and_number)
    
    cmds.separator(h=10, style="in")


    # --- 字符移除 ---
    cmds.text(label="移除字符:", align="left", font="boldLabelFont")
    cmds.rowLayout(nc=2, cw2=[115, 115])
    cmds.button(label="移除首字符 ->", c=partial(do_remove_chars, "step_forward"))
    cmds.button(label="<- 移除末尾字符", c=partial(do_remove_chars, "step_backward"))
    cmds.setParent(main_layout)
    
    cmds.button(label="移除 'pasted__' 前缀", c=do_remove_pasted)
    
    cmds.rowLayout(nc=5, cw5=[30, 60, 50, 60, 30])
    UI_ELEMENTS['RemoveFirst'] = cmds.textField(text="0")
    cmds.button(label="开头移除", c=partial(do_remove_chars, "begin"))
    cmds.button(label="双端", c=partial(do_remove_chars, "all"))
    cmds.button(label="末尾移除", c=partial(do_remove_chars, "end"))
    UI_ELEMENTS['RemoveEnd'] = cmds.textField(text="1")
    cmds.setParent(main_layout)


    cmds.separator(h=10, style="in")


    # --- 前后缀 ---
    cmds.rowLayout(nc=3, cw3=[50, 120, 50])
    cmds.text(label=" 前缀:")
    UI_ELEMENTS['PrefixText'] = cmds.textField(text="pre_")
    cmds.button(label="添加", c=partial(do_prefix_suffix, False))
    cmds.setParent(main_layout)


    cmds.rowLayout(nc=3, cw3=[50, 120, 50])
    cmds.text(label=" 后缀:")
    UI_ELEMENTS['SuffixText'] = cmds.textField(text="_suf")
    cmds.button(label="添加", c=partial(do_prefix_suffix, True))
    cmds.setParent(main_layout)


    cmds.rowLayout(nc=5, cw5=[46, 46, 46, 46, 46])
    for tag in ["_Grp", "_Geo", "_Ctrl", "_Jnt", "_Drv"]:
        cmds.button(label=tag, bgc=[0.1, 0.2, 0.3], c=partial(do_quick_suffix, tag))
    cmds.setParent(main_layout)


    cmds.separator(h=10, style="in")


    # --- 搜索与替换 ---
    cmds.text(label="搜索与替换:", align="left", font="boldLabelFont")
    cmds.rowLayout(nc=2, cw2=[60, 170])
    cmds.text(label="  搜索:")
    UI_ELEMENTS['SearchText'] = cmds.textField()
    cmds.setParent(main_layout)
    cmds.rowLayout(nc=2, cw2=[60, 170])
    cmds.text(label="  替换:")
    UI_ELEMENTS['ReplaceText'] = cmds.textField()
    cmds.setParent(main_layout)


    UI_ELEMENTS['SRCheck'] = cmds.radioButtonGrp(labelArray3=['已选择', '层级', '所有'], nrb=3, sl=1, cw3=[75, 75, 75])
    cmds.button(label="执行替换", h=30, bgc=[0.1, 0.5, 0.3], c=do_search_replace)


    cmds.showWindow(window)


# --- 统一入口 ---


def run():
    """为了提高处理效率，我们将 UI 和逻辑分离，
    以此确保核心重命名逻辑在 Python 3 环境下运行清晰。"""
    run_ui()


if __name__ == "__main__":
    run()