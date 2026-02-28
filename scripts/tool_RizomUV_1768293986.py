# -*- coding: utf-8 -*-
import maya.cmds as cmds
import subprocess
import tempfile
import os
import platform
import time

# 定义用于存储路径的 Maya 首选项变量名
RIZOM_PATH_VAR = "HK_Toolbox_RizomUV_Path"

def set_rizom_path_manual(*args):
    """
    手动设置 RizomUV 路径的函数 (供按钮调用)
    """
    file_filter = "Executable Files (*.exe)" if platform.system() == "Windows" else "All Files (*)"
    caption = "Set RizomUV Executable Path"
    
    selected = cmds.fileDialog2(fileMode=1, caption=caption, fileFilter=file_filter)
    
    if selected:
        new_path = selected[0]
        # 保存到 Maya 首选项
        cmds.optionVar(sv=(RIZOM_PATH_VAR, new_path))
        # 弹窗确认
        cmds.confirmDialog(title='Success', message=u'RizomUV 路径已更新:\n{0}'.format(new_path), button=['OK'])
        return new_path
    return None

def check_rizom_path():
    """
    检查并获取 RizomUV 路径。
    如果未设置或文件不存在，提示用户选择。
    """
    stored_path = None
    if cmds.optionVar(exists=RIZOM_PATH_VAR):
        stored_path = cmds.optionVar(q=RIZOM_PATH_VAR)
    
    # 验证路径是否存在
    if stored_path and os.path.exists(stored_path):
        return stored_path
    
    # 如果不存在，或者存储的路径失效了，提示用户
    msg = u'RizomUV 路径未设置或无效。\n是否现在设置？'
    result = cmds.confirmDialog(title='Setup', message=msg, button=['Yes', 'No'], defaultButton='Yes', cancelButton='No', dismissString='No')
    
    if result == 'Yes':
        return set_rizom_path_manual()
    
    return None

def sendToRizom(*args):
    rizomPath = check_rizom_path()
    if not rizomPath:
        cmds.warning(u"未指定 RizomUV 路径，操作取消。")
        return

    selected_objs = cmds.ls(selection=True, long=True, transforms=True)
    if not selected_objs:
        cmds.warning("No geometry selected to send to RizomUV.")
        return
        
    include_uvs = cmds.checkBox('uvcheck', query=True, value=True)
    exportFile = os.path.join(tempfile.gettempdir(), "RizomUVMayaBridge.obj")
    exportFileUnix = exportFile.replace("\\", "/")
    
    cmds.select(selected_objs, replace=True)
    export_options = "groups=1;ptgroups=1;materials=1;smoothing=1;normals=1;uvs=1"
    
    # Python 2/3 兼容导出
    cmds.file(
        exportFile,
        force=True,
        preserveReferences=True,
        type="OBJexport",
        exportSelected=True,
        options=export_options
    )
    
    msg = "Exported OBJ to {0} with {1}".format(exportFile, 'existing UVs' if include_uvs else 'no existing UVs')
    print(msg)
    
    if include_uvs:
        lua_script = '''
    ZomLoad({{File={{Path="{0}", ImportGroups=true, UVWProps=true, XYZUVW=true}}, NormalizeUVW=true}})
        '''.format(exportFileUnix)
    else:
        lua_script = '''
    ZomLoad({{File={{Path="{0}", ImportGroups=true, XYZ=true}}, NormalizeUVW=true}})
    ZomUnfold({{PrimType="Island", MinAngle=1e-005, Mix=1, Iterations=1, PreIterations=5, StopIfOutOFDomain=false, RoomSpace=0, BorderIntersections=true, TriangleFlips=true}})
    ZomPack({{ProcessTileSelection=false, RecursionDepth=1, RootGroup="RootGroup", Scaling={{Mode=2}}, Rotate={{}}, Translate=true, LayoutScalingMode=2}})
    ZomSave({{File={{Path="{0}", UVWProps=true}}, __UpdateUIObjFileName=true}})
        '''.format(exportFileUnix)

    control_script_path = os.path.join(tempfile.gettempdir(), "rizomuv_control_script.lua")
    control_script_path_unix = control_script_path.replace("\\", "/")
    
    with open(control_script_path, "w") as f:
        f.write(lua_script)
        
    print("Updated control script at {0}".format(control_script_path))
    
    rizom_running = False
    if platform.system() == "Windows":
        try:
            tasks = subprocess.check_output(['tasklist']).decode().lower()
            if 'rizomuv.exe' in tasks:
                rizom_running = True
        except Exception as e:
            print("Error checking if RizomUV is running: {0}".format(e))
    else:
        try:
            tasks = subprocess.check_output(['ps', 'aux']).decode().lower()
            if 'rizomuv' in tasks:
                rizom_running = True
        except Exception as e:
            print("Error checking if RizomUV is running: {0}".format(e))
            
    if not rizom_running:
        print("Starting RizomUV...")
        if platform.system() == "Windows":
            cmd = '"{0}" -cfi "{1}"'.format(rizomPath, control_script_path_unix)
            subprocess.Popen(cmd)
        else:
            cmd = [rizomPath, '-cfi', control_script_path_unix]
            subprocess.Popen(cmd)
        time.sleep(5)
    else:
        print("RizomUV is already running.")
        os.utime(control_script_path, None)
        print("Updated timestamp to trigger reload.")

def getFromRizom(*args):
    originalOBJs = cmds.ls(selection=True, long=True, transforms=True)
    if not originalOBJs:
        cmds.warning("No geometry selected to get UVs from RizomUV.")
        return
        
    importFile = os.path.join(tempfile.gettempdir(), "RizomUVMayaBridge.obj")
    
    # 清理旧命名空间
    allNamespaces = cmds.namespaceInfo(listOnlyNamespaces=True, recurse=True)
    for ns in allNamespaces:
        if "RIZOMUV" in ns:
            try:
                cmds.namespace(removeNamespace=ns, mergeNamespaceWithRoot=True)
            except Exception as e:
                print("Failed to remove namespace {0}: {1}".format(ns, e))
                
    # 修复长行问题
    if cmds.checkBox('linecheck', query=True, value=True):
        if os.path.exists(importFile):
            with open(importFile, "r") as f:
                lines = f.readlines()
            with open(importFile, "w") as f:
                for line in lines:
                    if not line.startswith("#ZOMPROPERTIES"):
                        f.write(line)
            print("Long lines fixed in OBJ file.")
        else:
            cmds.warning("Import file not found: {0}".format(importFile))
            return
            
    cmds.file(importFile, i=True, type="OBJ", ignoreVersion=True, mergeNamespacesOnClash=True, namespace="RIZOMUV")
    
    imported_transforms = cmds.ls("RIZOMUV:*", transforms=True, long=True)
    if not imported_transforms:
        cmds.warning("No objects imported from RizomUV.")
        return
        
    for orig_obj in originalOBJs:
        target_obj_name = orig_obj.split('|')[-1]
        corresponding_imp = None
        
        for imp_transform in imported_transforms:
            imp_name = imp_transform.split(':')[-1]
            if imp_name == target_obj_name:
                corresponding_imp = imp_transform
                break
                
        if corresponding_imp:
            src_shapes = cmds.listRelatives(corresponding_imp, shapes=True, fullPath=True)
            trg_shapes = cmds.listRelatives(orig_obj, shapes=True, fullPath=True)
            
            if not src_shapes or not trg_shapes:
                continue
                
            src = src_shapes[0]
            trg = trg_shapes[0]
            
            # 传递 UV
            cmds.transferAttributes(
                src, trg,
                transferPositions=0,
                transferNormals=0,
                transferUVs=2,
                transferColors=0,
                sampleSpace=4,
                sourceUvSpace="map1",
                targetUvSpace="map1",
                searchMethod=3,
                flipUVs=0,
                colorBorders=1
            )
            cmds.delete(trg, ch=True)
            print("Transferred UVs from {0} to {1}".format(src, trg))
        else:
            cmds.warning("No corresponding object found for {0}".format(orig_obj))
            
    for obj in imported_transforms:
        try:
            if cmds.objExists(obj):
                cmds.delete(obj)
        except:
            pass

def rizomAutoRoundtrip(*args):
    rizomPath = check_rizom_path()
    if not rizomPath:
        return

    originalOBJs = cmds.ls(selection=True, long=True, transforms=True)
    if not originalOBJs:
        cmds.warning("No objects selected.")
        return
        
    exportFile = os.path.join(tempfile.gettempdir(), "RizomUVMayaBridge.obj")
    exportFileUnix = exportFile.replace("\\", "/")
    
    cmds.select(originalOBJs, replace=True)
    cmds.file(
        exportFile,
        force=True,
        preserveReferences=True,
        type="OBJexport",
        exportSelected=True,
        options="groups=1;ptgroups=1;materials=1;smoothing=1;normals=1"
    )
    
    luascript = """
ZomLoad({{File={{Path="{0}", ImportGroups=true, XYZ=true}}, NormalizeUVW=true}})
ZomSelect({{PrimType="Edge", Select=true, ResetBefore=true, Auto={{ByAngle={{Angle=45, Seams=false}}, BySharpness=45, Seams=true, ByGroup=true}}}})
ZomCut({{PrimType="Edge"}})
ZomUnfold({{PrimType="Island", MinAngle=1e-005, Mix=1, Iterations=1, PreIterations=5, StopIfOutOFDomain=false, RoomSpace=0, BorderIntersections=true, TriangleFlips=true}})
ZomIslandGroups({{Mode="DistributeInTilesEvenly", MergingPolicy=8322, GroupPath="RootGroup"}})
ZomPack({{ProcessTileSelection=false, RecursionDepth=1, RootGroup="RootGroup", Scaling={{Mode=2}}, Rotate={{}}, Translate=true, LayoutScalingMode=2}})
ZomSave({{File={{Path="{0}", UVWProps=true}}, __UpdateUIObjFileName=true}})
ZomQuit()
""".format(exportFileUnix)

    luaFile = os.path.join(tempfile.gettempdir(), "riz.lua")
    with open(luaFile, "w") as f:
        f.write(luascript)
    luaFileUnix = luaFile.replace("\\", "/")
    
    cmd = [rizomPath, '--execute', luaFileUnix]
    print("Executing RizomUV...")
    try:
        if platform.system() == "Windows":
            subprocess.call(cmd)
        else:
            subprocess.call(cmd)
    except Exception as e:
        cmds.warning("Failed to execute RizomUV: {0}".format(e))
        
    time.sleep(2)
    getFromRizom()
    
    if os.path.exists(luaFile):
        try:
            os.remove(luaFile)
        except:
            pass

def createUI():
    """创建工具界面"""
    if cmds.window("rizomUVBridgeWin", exists=True):
        cmds.deleteUI("rizomUVBridgeWin", window=True)
        
    # 稍微增加一点高度以容纳新按钮
    window = cmds.window("rizomUVBridgeWin", title="RizomUV Bridge", widthHeight=(250, 130))
    
    main_layout = cmds.columnLayout(adjustableColumn=True, rowSpacing=5)
    
    # 顶部留白
    cmds.separator(h=5, style='none')
    
    # 1. 发送区域
    cmds.button(label="发送到 Rizom", command=sendToRizom, height=30, backgroundColor=(0.23, 0.23, 0.23))
    cmds.checkBox('uvcheck', label='包含现有UV', align='center', value=True)
    
    cmds.separator(h=5, style='in')
    
    # 2. 接收区域
    cmds.button(label="从 Rizom 获取", command=getFromRizom, height=30, backgroundColor=(0.23, 0.23, 0.23))
    cmds.checkBox('linecheck', label='修复长行', align='center', value=False)
    
    cmds.separator(h=5, style='in')
    
    # 3. 自动区域
    cmds.button(label="Auto Unfold (自动展开)", command=rizomAutoRoundtrip, height=30, backgroundColor=(0.3, 0.4, 0.3))
    
    # 4. 【新增】设置区域
    # 使用双分割线区分功能区和设置区
    cmds.separator(h=10, style='double')
    
    # 底部设置按钮，稍微矮一点，颜色淡一点
    cmds.button(label=u"⚙ 设置路径", 
                command=set_rizom_path_manual, 
                height=24, 
                backgroundColor=(0.2, 0.2, 0.2),
                annotation="Click to change the rizomuv.exe path")
    
    cmds.separator(h=5, style='none')

    cmds.showWindow(window)

def run():
    createUI()

if __name__ == "__main__":
    run()