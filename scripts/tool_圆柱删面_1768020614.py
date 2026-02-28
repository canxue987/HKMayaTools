# -*- coding: utf-8 -*-
import math
from collections import deque
import maya.cmds as cmds


# --- 核心逻辑函数 (原封不动或微调) ---


def get_face_normal_in_world(face_name):
    """用3个顶点做叉积获取世界坐标法线。"""
    verts = cmds.polyListComponentConversion(face_name, toVertex=True)
    verts = cmds.ls(verts, flatten=True)
    if not verts or len(verts) < 3:
        return None


    p0 = cmds.pointPosition(verts[0], world=True)
    p1 = cmds.pointPosition(verts[1], world=True)
    p2 = cmds.pointPosition(verts[2], world=True)


    v1 = [p1[0]-p0[0], p1[1]-p0[1], p1[2]-p0[2]]
    v2 = [p2[0]-p0[0], p2[1]-p0[1], p2[2]-p0[2]]


    cx = v1[1]*v2[2] - v1[2]*v2[1]
    cy = v1[2]*v2[0] - v1[0]*v2[2]
    cz = v1[0]*v2[1] - v1[1]*v2[0]


    length = math.sqrt(cx*cx + cy*cy + cz*cz)
    if length < 1e-5:
        return None
    return [cx/length, cy/length, cz/length]


def build_face_adjacency(obj_name):
    face_count = cmds.polyEvaluate(obj_name, face=True)
    adjacency = {}
    for i in range(face_count):
        face_comp = "{}.f[{}]".format(obj_name, i)
        if not cmds.objExists(face_comp):
            continue
        face_edges = cmds.polyListComponentConversion(face_comp, fromFace=True, toEdge=True)
        face_edges = cmds.ls(face_edges, flatten=True)
        if not face_edges:
            adjacency[i] = []
            continue
        connected_faces = cmds.polyListComponentConversion(face_edges, fromEdge=True, toFace=True)
        connected_faces = cmds.ls(connected_faces, flatten=True)
        neighbors = []
        if connected_faces:
            for fcomp in connected_faces:
                if fcomp == face_comp: continue
                try:
                    idx_str = fcomp.split(".f[")[1][:-1]
                    neighbors.append(int(idx_str))
                except: pass
        adjacency[i] = list(set(neighbors))
    return adjacency


def get_shell_faces_list(obj_name, adjacency):
    face_count = cmds.polyEvaluate(obj_name, face=True)
    visited = set()
    shells = []
    for f_idx in range(face_count):
        face_comp = "{}.f[{}]".format(obj_name, f_idx)
        if f_idx in visited or not cmds.objExists(face_comp):
            continue
        queue = deque([f_idx])
        comp = []
        while queue:
            cur = queue.popleft()
            if cur not in visited:
                visited.add(cur)
                comp.append(cur)
                if cur in adjacency:
                    for nbr in adjacency[cur]:
                        if nbr not in visited:
                            queue.append(nbr)
        if comp:
            shells.append(comp)
    return shells


def measure_faces_area(obj_name, face_indices):
    if not face_indices: return 0.0
    face_comps = ["{}.f[{}]".format(obj_name, i) for i in face_indices if cmds.objExists("{}.f[{}]".format(obj_name, i))]
    if not face_comps: return 0.0
    cmds.select(face_comps, r=True)
    area_val = cmds.polyEvaluate(wa=True)
    cmds.select(clear=True)
    if area_val is None: return 0.0
    return float(area_val)


def delete_parallel_faces(obj_name, ref_face, parallel_threshold=0.99):
    ref_normal = get_face_normal_in_world(ref_face)
    if not ref_normal:
        cmds.warning(u"无法获取参考面法线。")
        return
    face_count = cmds.polyEvaluate(obj_name, face=True)
    faces_to_delete = []
    for i in range(face_count):
        face_name = "{}.f[{}]".format(obj_name, i)
        if not cmds.objExists(face_name): continue
        normal = get_face_normal_in_world(face_name)
        if not normal: continue
        dot_val = normal[0]*ref_normal[0] + normal[1]*ref_normal[1] + normal[2]*ref_normal[2]
        if abs(dot_val) >= parallel_threshold:
            faces_to_delete.append(face_name)
    if faces_to_delete:
        cmds.select(faces_to_delete, r=True)
        cmds.polyDelFacet(ch=True)
        print(u"已删除平行面: {}".format(len(faces_to_delete)))


def delete_parallel_then_keep_largest_shell():
    sel_faces = cmds.ls(sl=True, flatten=True)
    if not sel_faces:
        cmds.warning(u"请先选中一个参考面。")
        return
    
    ref_face = sel_faces[0]
    obj_name = ref_face.split('.')[0]


    delete_parallel_faces(obj_name, ref_face, parallel_threshold=0.99)


    face_count = cmds.polyEvaluate(obj_name, face=True)
    if face_count < 1: return
    
    adjacency = build_face_adjacency(obj_name)
    shells = get_shell_faces_list(obj_name, adjacency)
    if not shells or len(shells) == 1: return
    
    largest_area = 0.0
    largest_shell_faces = []


    for comp_faces in shells:
        area_val = measure_faces_area(obj_name, comp_faces)
        if area_val > largest_area:
            largest_area = area_val
            largest_shell_faces = comp_faces
    
    all_faces = set()
    for comp in shells: all_faces.update(comp)
    largest_shell_set = set(largest_shell_faces)
    
    faces_to_delete = [
        "{}.f[{}]".format(obj_name, fidx)
        for fidx in all_faces
        if fidx not in largest_shell_set and cmds.objExists("{}.f[{}]".format(obj_name, fidx))
    ]
    
    if faces_to_delete:
        cmds.select(faces_to_delete, r=True)
        cmds.polyDelFacet(ch=True)
        print(u"清理小壳完成，保留最大面积: {:.2f}".format(largest_area))
    cmds.select(clear=True)


# --- 工具箱入口 ---
def run():
    """工具箱调用的入口函数"""
    delete_parallel_then_keep_largest_shell()

