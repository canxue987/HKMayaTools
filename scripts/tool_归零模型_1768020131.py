# -*- coding: utf-8 -*-
import maya.cmds as cmds
import maya.api.OpenMaya as om


# --- 核心算法 ---


def process_pivot_and_move(selected_objects):
    """
    核心逻辑：将物体轴心对齐到底部中心，移动至世界原点并冻结变换。
    """
    if not selected_objects:
        om.MGlobal.displayWarning(u"请选择至少一个模型")
        return


    for obj in selected_objects:
        # 1. 将轴心初步归到物体几何中心
        cmds.xform(obj, centerPivots=True)
        
        # 2. 计算底部中心坐标
        bbox = cmds.xform(obj, query=True, boundingBox=True, worldSpace=True)
        x_min, y_min, z_min, x_max, y_max, z_max = bbox
        
        pivot_x = (x_min + x_max) / 2.0
        pivot_y = y_min  # 物体最底部
        pivot_z = (z_min + z_max) / 2.0
        
        # 3. 设置新的轴心位置（世界坐标系）
        cmds.xform(obj, pivots=(pivot_x, pivot_y, pivot_z), worldSpace=True)
        
        # 4. 将物体移动到世界中心 (0,0,0)
        # 获取当前旋转轴心位置
        current_pivot = cmds.xform(obj, query=True, worldSpace=True, rotatePivot=True)
        cmds.move(-current_pivot[0], -current_pivot[1], -current_pivot[2], 
                 obj, relative=True, worldSpace=True)
        
        # 5. 冻结变换使坐标归零
        cmds.makeIdentity(obj, apply=True, translate=True, rotate=True, scale=True)


    om.MGlobal.displayInfo(u"操作成功完成！已处理 {} 个对象".format(len(selected_objects)))


# --- UI 入口 ---


def run_ui():
    """
    创建并显示工具界面
    """
    win_name = "CenterPivotMoveWindow"
    
    if cmds.window(win_name, exists=True):
        cmds.deleteUI(win_name)
        
    cmds.window(win_name, title=u"轴心归位工具", widthHeight=(250, 100), sizeable=False)
    
    cmds.columnLayout(adj=True, rowSpacing=10, columnOffset=['both', 10])
    cmds.text(label=u"\n将轴心移至底部中心\n并将物体对齐到世界原点", align="center")
    
    # 按钮回调：获取当前选择并执行核心算法
    cmds.button(
        label=u"执行对齐与归零", 
        height=40,
        command=lambda x: process_pivot_and_move(cmds.ls(selection=True, type="transform"))
    )
    
    cmds.showWindow(win_name)


def run():
    """
    统一入口函数
    """
    run_ui()


if __name__ == "__main__":
    run()