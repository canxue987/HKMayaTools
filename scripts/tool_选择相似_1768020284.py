# -*- coding: utf-8 -*-
import maya.cmds as cmds


def select_similar(mode=0, tolerance=0.01, useMaterial=False):
    sel = cmds.ls(sl=True, l=True, fl=True)
    sel = cmds.filterExpand(sel, sm=12)
    if not sel: return
    
    all_meshes = cmds.filterExpand(cmds.ls(l=True, tr=True), sm=12) or []
    
    # 预计算属性
    def get_area(o): 
        v = cmds.polyEvaluate(o, worldArea=True, ae=True)
        return v if isinstance(v, float) else v[0]
    
    def get_sg(o): return set(cmds.listConnections(o, type="shadingEngine") or [])
    
    area_map = {t: get_area(t) for t in all_meshes}
    
    final_sel = []
    for source in sel:
        src_area = area_map[source]
        src_sg = get_sg(source) if useMaterial else None
        
        for target in all_meshes:
            if target == source: continue
            
            # 材质判断
            if useMaterial:
                if src_sg.isdisjoint(get_sg(target)): continue
            
            # 拓扑判断
            if cmds.polyCompare(source, target, fd=True) == 0:
                if mode == 0: # 仅拓扑
                    final_sel.append(target)
                else: # 拓扑+面积
                    if abs(src_area - area_map[target]) <= (src_area * tolerance):
                        final_sel.append(target)
                        
    if final_sel: cmds.select(final_sel, add=True)
    else: cmds.warning(u"未找到相似物体")


def run_ui():
    win = "SelSimilarWin"
    if cmds.window(win, exists=True): cmds.deleteUI(win)
    cmds.window(win, title=u"选择相似", widthHeight=(300, 150))
    cmds.columnLayout(adj=True)
    cmds.text(label="模式:")
    menu = cmds.optionMenu(); cmds.menuItem(label="仅拓扑"); cmds.menuItem(label="拓扑 + 面积")
    cmds.text(label="面积误差:")
    sl = cmds.floatSliderGrp(field=True, min=0, max=1, v=0.01)
    chk = cmds.checkBox(label="匹配材质球")
    
    def do_cmd(*args):
        m = 1 if cmds.optionMenu(menu, q=True, v=True) == "拓扑 + 面积" else 0
        select_similar(m, cmds.floatSliderGrp(sl,q=True,v=True), cmds.checkBox(chk,q=True,v=True))
        
    cmds.button(label="选择", command=do_cmd)
    cmds.showWindow(win)


def run():
    run_ui()

