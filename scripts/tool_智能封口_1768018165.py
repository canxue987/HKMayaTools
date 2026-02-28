# -*- coding: utf-8 -*-
import maya.cmds as cmds
import maya.mel as mel

def get_target_edges():
    """
    智能获取目标边：
    1. 如果用户选择了边，返回选中的边界边。
    2. 如果用户选择了物体，返回物体上所有的边界边。
    """
    sel = cmds.ls(sl=True, fl=True)
    if not sel:
        cmds.warning(u"请先选择物体或边！")
        return None, None

    # 检查当前选择的是物体还是组件
    is_object_mode = False
    if cmds.objectType(sel[0]) == "transform":
        is_object_mode = True
    elif "." in sel[0]:
        # 简单判断是否为组件模式
        is_object_mode = False

    target_edges = []
    target_obj = ""

    if is_object_mode:
        # --- 物体模式：自动查找所有边界边 ---
        target_obj = sel[0]
        # 使用多边形选择约束来查找边界边
        cmds.select(target_obj)
        cmds.polySelectConstraint(mode=3, type=0x8000, where=1) # 1=Border
        target_edges = cmds.ls(sl=True, fl=True)
        cmds.polySelectConstraint(disable=True) # 必须重置约束，否则以后选不了别的
        
        if not target_edges:
            cmds.warning(u"物体 '{}' 没有开放的边界边。".format(target_obj))
            return None, None
            
    else:
        # --- 组件模式：过滤选中的边 ---
        # 确保只处理选中的边界边（Border Edge）
        # 这里为了灵活，我们处理所有选中的边，但最好是边界边
        # 获取边所属的物体
        target_obj = cmds.ls(sel[0], o=True)[0]
        target_edges = cmds.filterExpand(sel, sm=32) # 32 = Polygon Edge
        if not target_edges:
            cmds.warning(u"请选择边。")
            return None, None

    return target_obj, target_edges

def cap_holes(mode="center"):
    """
    mode: "center" (扇形/中心) 或 "tri" (三角化)
    """
    target_obj, target_edges = get_target_edges()
    if not target_edges:
        return

    # 开启 Undo 块
    cmds.undoInfo(openChunk=True)
    
    try:
        # 为了稳定，先将边转为这些边围成的“孔”的逻辑有点复杂
        # 最简单的方法是：对选中的边执行 Fill Hole
        # Fill Hole 命令在 Maya 中即便只选中了一部分边界边，只要能闭合，它就会封口
        
        # 1. 记录当前面数（为了找到新生成的面）
        old_face_count = cmds.polyEvaluate(target_obj, face=True)
        
        # 2. 重新选择目标边并执行 Fill Hole
        cmds.select(target_edges)
        cmds.polyCloseBorder() # 使用 polyCloseBorder 比 polyExtrude 更直接
        
        # 3. 获取新生成的面
        new_face_count = cmds.polyEvaluate(target_obj, face=True)
        if new_face_count <= old_face_count:
            cmds.warning(u"没有生成新的面，可能选中的边没有构成封闭的洞。")
            return
            
        # 新面索引范围
        new_faces = ["{}.f[{}:{}]".format(target_obj, old_face_count, new_face_count - 1)]
        
        # 4. 根据模式处理新面
        cmds.select(new_faces)
        
        if mode == "center":
            # --- 中心封口模式 (Fill + Poke) ---
            # Poke 会在面中心加点并连线，等同于“挤出合并到中心”但更完美
            cmds.polyPoke(new_faces, constructionHistory=False)
            print(u"已执行：中心封口 (Fan/Poke)")
            
        elif mode == "tri":
            # --- 三角化封口模式 (Fill + Triangulate) ---
            cmds.polyTriangulate(new_faces, constructionHistory=False)
            print(u"已执行：三角化封口")

    except Exception as e:
        cmds.error(u"封口失败: {}".format(e))
    finally:
        cmds.select(clear=True) # 清空选择以免误操作
        cmds.undoInfo(closeChunk=True)

# --- UI 入口 ---
def run_ui():
    win = "SmartCapperWindow"
    if cmds.window(win, exists=True): cmds.deleteUI(win)
    cmds.window(win, title=u"智能封口工具", widthHeight=(220, 100))
    
    main_col = cmds.columnLayout(adj=True, rowSpacing=5, columnAttach=('both', 5))
    
    cmds.text(label=u"选择物体自动封全口，选边封缺口", align='center', height=25, enable=False)
    
    cmds.button(label=u"中心封口 (扇形)", height=35, 
                command=lambda x: cap_holes(mode="center"), 
                annotation=u"生成一个中心点并向四周连线 (Poke)")
                
    cmds.button(label=u"三角化封口", height=35, 
                command=lambda x: cap_holes(mode="tri"),
                annotation=u"直接填充并三角化")
    
    cmds.showWindow(win)

def run():
    run_ui()

if __name__ == "__main__":
    run_ui()