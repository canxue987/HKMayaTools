# -*- coding: utf-8 -*-
import maya.cmds as cmds


def extrude_and_collapse_edges():
    edges = cmds.ls(sl=True, fl=True)
    if not edges:
        cmds.warning(u"请选择要挤出的边。")
        return


    # 挤出
    try:
        cmds.polyExtrudeEdge(
            edges,
            constructionHistory=True,
            keepFacesTogether=True,
            localTranslateZ=0.2 
        )
    except Exception as e:
        cmds.warning(u"挤出失败：{}".format(e))
        return


    # 获取新边
    extruded_edges = cmds.ls(sl=True, fl=True) or []
    extruded_edges = cmds.polyListComponentConversion(extruded_edges, toEdge=True) or []
    extruded_edges = cmds.ls(extruded_edges, fl=True)


    if not extruded_edges:
        return


    # 合并
    try:
        cmds.polyCollapseEdge(extruded_edges, constructionHistory=True)
        print(u"挤出并合并完成。")
    except Exception as e:
        cmds.warning(u"合并失败：{}".format(e))


# --- 工具箱入口 ---
def run():
    extrude_and_collapse_edges()

