# -*- coding: utf-8 -*-
import maya.cmds as cmds
import maya.mel as mel


def delete_edges_and_loop():
    """
    1) 切换到 Edge 选择模式
    2) 选取“每相隔2的边环”
    3) 扩展到循环边
    4) 删除选中的边并同时移除无用顶点
    """
    # 1) 切换到 Edge 模式
    mel.eval("SelectEdgeMask")


    # 2) 选取“每相隔2的边环”
    try:
        mel.eval('polySelectEdgesEveryN "edgeRing" 2')
    except:
        pass # 防止未选择时报错
    
    # 3) 将当前选中的边扩展到“循环”边
    mel.eval("SelectEdgeLoopSp")
    
    # 4) 删除所选边并同时删除无用顶点
    mel.eval('polyDelEdge -cv true')
    print(u"已自动循环删除边。")


# --- 工具箱入口 ---
def run():
    delete_edges_and_loop()

