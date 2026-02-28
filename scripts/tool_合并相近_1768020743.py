# -*- coding: utf-8 -*-
import maya.cmds as cmds
import math


def get_center(obj):
    bb = cmds.xform(obj, q=True, bb=True, ws=True)
    return ((bb[0]+bb[3])*0.5, (bb[1]+bb[4])*0.5, (bb[2]+bb[5])*0.5)


def dist_sq(p1, p2):
    return (p1[0]-p2[0])**2 + (p1[1]-p2[1])**2 + (p1[2]-p2[2])**2


def merge_objects(threshold):
    sel = cmds.ls(sl=True, l=True)
    if not sel or len(sel)<2:
        cmds.warning(u"请选择多个物体")
        return
    
    centers = {obj: get_center(obj) for obj in sel}
    parent = {obj: obj for obj in sel}
    
    def find(x):
        if parent[x] != x: parent[x] = find(parent[x])
        return parent[x]
    
    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb: parent[rb] = ra
            
    t_sq = threshold * threshold
    objs = list(sel)
    for i in range(len(objs)):
        for j in range(i+1, len(objs)):
            if dist_sq(centers[objs[i]], centers[objs[j]]) < t_sq:
                union(objs[i], objs[j])
                
    groups = {}
    for obj in sel:
        root = find(obj)
        groups.setdefault(root, []).append(obj)
        
    final_objs = []
    for root, grp in groups.items():
        if len(grp) > 1:
            new_mesh = cmds.polyUnite(grp, ch=False, mergeUVSets=True)[0]
            cmds.delete(new_mesh, ch=True)
            final_objs.append(new_mesh)
        else:
            final_objs.append(grp[0])
    cmds.select(final_objs)
    print(u"合并完成。")


def run_ui():
    win = "MergeCloseWindow"
    if cmds.window(win, exists=True): cmds.deleteUI(win)
    cmds.window(win, title=u"合并相近", widthHeight=(250, 100))
    cmds.columnLayout(adj=True)
    cmds.text(label=u"距离阈值：")
    ff = cmds.floatField(value=1.0, minValue=0.0)
    cmds.button(label=u"合并", command=lambda x: merge_objects(cmds.floatField(ff, q=True, v=True)))
    cmds.showWindow(win)


def run():
    run_ui()

