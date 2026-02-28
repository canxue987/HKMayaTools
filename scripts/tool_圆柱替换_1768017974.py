# -*- coding: utf-8 -*-
import maya.cmds as cmds
import maya.api.OpenMaya as om
import math

# =========================================================================
# 1. 智能选择辅助系统 (Smart Selector)
# =========================================================================

def smart_get_axis_from_selection(selection_list):
    """
    智能解析用户的“一键选择”，返回精确的轴向 (Primary Axis)
    """
    if selection_list.isEmpty():
        return None, None

    dag_path, component = selection_list.getComponent(0)
    
    # A. 如果选的是物体 (全自动模式)
    if component.isNull():
        # 返回 None，让主逻辑去跑全自动算法
        return None, dag_path

    mesh_fn = om.MFnMesh(dag_path)
    axis = None

    # B. 点模式：点 -> 所在的圆环 -> 面法线
    if component.apiType() == om.MFn.kMeshVertComponent:
        # 用户只选了 1 个点，或者几个点
        # 逻辑：获取这些点相连的边，尝试扩展成一个 Loop，然后计算 Loop 的法线
        
        # 1. 获取选中的点
        sel_indices = []
        vtx_it = om.MItMeshVertex(dag_path, component)
        while not vtx_it.isDone():
            sel_indices.append(vtx_it.index())
            vtx_it.next()
            
        # 2. 如果只选了1个点，尝试自动扩选一圈 (Grow Loop)
        # 这是一个简化策略：我们假设这个点在端面的边缘上
        # 但为了稳妥，我们这里建议用户至少选 2 个点，或者干脆选一条边更准
        # 这里为了不误判，如果点少于2个，我们回退到"连线模式"
        
        if len(sel_indices) >= 3:
            # 选了3个以上点 -> 拟合平面法线
            points = []
            for idx in sel_indices:
                pt = mesh_fn.getPoint(idx, om.MSpace.kWorld)
                points.append(pt)
            axis = fit_plane_normal(points)
            # print("Smart Point: Plane Normal")
            
        elif len(sel_indices) == 2:
            # 选了2个点 -> 连线方向
            p1 = mesh_fn.getPoint(sel_indices[0], om.MSpace.kWorld)
            p2 = mesh_fn.getPoint(sel_indices[1], om.MSpace.kWorld)
            axis = (om.MVector(p2) - om.MVector(p1)).normal()
            # print("Smart Point: 2-Point Line")
            
        else:
            # 只选了1个点，很难猜，抛出警告建议选边
            cmds.warning(u"点模式建议：\n1. 选2个点 (定高度)\n2. 选3个以上点 (定平面)")
            return None, None

    # C. 边模式：边 -> 强制循环 -> 面法线
    elif component.apiType() == om.MFn.kMeshEdgeComponent:
        # 用户选了 1 条边
        # 逻辑：不管能不能 Loop，我们只取这条边参与的面，计算平均法线是不够的
        # 最稳妥的方式：这条边大概率是侧边(Height) 或者 顶盖边(Ring)
        
        edge_it = om.MItMeshEdge(dag_path, component)
        
        # 获取边的端点
        p1 = edge_it.point(0, om.MSpace.kWorld)
        p2 = edge_it.point(1, om.MSpace.kWorld)
        edge_vec = (om.MVector(p2) - om.MVector(p1)).normal()
        
        # 智能判断：这是"竖线"还是"横线"？
        # 我们需要参考一下点的分布。但在局部模式下很难。
        # 简单策略：相信用户选的是【高度线】(Side Edge)。
        # 因为在圆柱替换中，选侧边线是最直观的。
        
        axis = edge_vec
        # print("Smart Edge: Using Edge Vector")

    # D. 面模式：面 -> 法线
    elif component.apiType() == om.MFn.kMeshPolygonComponent:
        face_it = om.MItMeshPolygon(dag_path, component)
        if not face_it.isDone():
            # 获取面法线
            normal = face_it.getNormal(om.MSpace.kWorld).normal()
            
            # 判断这是顶面还是侧面？
            # 这里的逻辑是 v6.0 的精华，可以保留：
            # 但既然是"手动辅助"，我们可以约定：
            # 选面 = 选顶面 (Cap)。因为选侧面不如选侧边线直观。
            
            axis = normal
            # print("Smart Face: Using Face Normal")

    return axis, dag_path

def fit_plane_normal(points):
    """
    给一堆点，拟合出一个平面的法线 (PCA简化版)
    """
    n = len(points)
    if n < 3: return om.MVector(0,1,0)
    
    centroid = om.MVector(0,0,0)
    for p in points: centroid += om.MVector(p)
    centroid /= n
    
    cov = [[0.0]*3 for _ in range(3)]
    for p in points:
        d = om.MVector(p) - centroid
        cov[0][0]+=d.x*d.x; cov[1][1]+=d.y*d.y; cov[2][2]+=d.z*d.z
        cov[0][1]+=d.x*d.y; cov[0][2]+=d.x*d.z; cov[1][2]+=d.y*d.z
    cov[1][0]=cov[0][1]; cov[2][0]=cov[0][2]; cov[2][1]=cov[1][2]
    
    # 最小特征值对应的特征向量即为法线
    evals, evecs = jacobi_eigenvalue_algorithm(cov)
    pairs = sorted(zip(evals, evecs), key=lambda x: x[0])
    return pairs[0][1] # 最小特征值对应法线

# =========================================================================
# 2. 核心计算逻辑 (复用 v5.0 的稳健算法)
# =========================================================================

def get_points_om(dag_path):
    mesh_fn = om.MFnMesh(dag_path)
    return mesh_fn.getPoints(om.MSpace.kWorld)

def jacobi_eigenvalue_algorithm(matrix, max_iter=50):
    n = 3
    A = [[matrix[i][j] for j in range(n)] for i in range(n)]
    V = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    for _ in range(max_iter):
        pivot = 0.0
        p, q = 0, 1
        for i in range(n):
            for j in range(i + 1, n):
                if abs(A[i][j]) > pivot: pivot = abs(A[i][j]); p, q = i, j
        if pivot < 1e-9: break
        if A[p][p] == A[q][q]: theta = math.pi / 4
        else: theta = 0.5 * math.atan(2 * A[p][q] / (A[p][p] - A[q][q]))
        c = math.cos(theta); s = math.sin(theta)
        app = c*c*A[p][p] - 2*s*c*A[p][q] + s*s*A[q][q]
        aqq = s*s*A[p][p] + 2*s*c*A[p][q] + c*c*A[q][q]
        A[p][p] = app; A[q][q] = aqq; A[p][q] = A[q][p] = 0.0 
        for i in range(n):
            if i != p and i != q:
                a_ip = c*A[i][p] - s*A[i][q]; a_iq = s*A[i][p] + c*A[i][q]
                A[i][p] = A[p][i] = a_ip; A[i][q] = A[q][i] = a_iq
        for i in range(n):
            v_ip = c*V[i][p] - s*V[i][q]; v_iq = s*V[i][p] + c*V[i][q]
            V[i][p] = v_ip; V[i][q] = v_iq
    return [A[i][i] for i in range(n)], [om.MVector(V[0][i], V[1][i], V[2][i]) for i in range(n)]

def calculate_geometry_data(dag_path, manual_axis=None):
    points = get_points_om(dag_path)
    if not points or len(points) < 4: return None
    num_points = len(points)
    
    centroid = om.MVector(0, 0, 0)
    for p in points: centroid += om.MVector(p)
    centroid /= num_points
    
    primary_axis = None
    
    if manual_axis:
        # 【人工模式】直接用算出来的轴
        primary_axis = manual_axis
        primary_axis.normalize()
    else:
        # 【自动模式】
        cov = [[0.0]*3 for _ in range(3)]
        for p in points:
            d = om.MVector(p) - centroid
            cov[0][0]+=d.x*d.x; cov[1][1]+=d.y*d.y; cov[2][2]+=d.z*d.z
            cov[0][1]+=d.x*d.y; cov[0][2]+=d.x*d.z; cov[1][2]+=d.y*d.z
        cov[1][0]=cov[0][1]; cov[2][0]=cov[0][2]; cov[2][1]=cov[1][2]
        evals, evecs = jacobi_eigenvalue_algorithm(cov)
        pairs = sorted(zip(evals, evecs), key=lambda x: x[0], reverse=True)
        val_1, vec_1 = pairs[0]; val_2, vec_2 = pairs[1]; val_3, vec_3 = pairs[2]
        
        if val_2 < 1e-6: val_2 = 1e-6
        if val_3 < 1e-6: val_3 = 1e-6
        if (val_1/val_2) < 3.0 and (val_2/val_3) > 3.0: primary_axis = vec_3
        else: primary_axis = vec_1
        primary_axis.normalize()

    # 投影测量
    dummy_up = om.MVector(0, 1, 0)
    if abs(primary_axis * dummy_up) > 0.9: dummy_up = om.MVector(0, 0, 1)
    u_axis = (primary_axis ^ dummy_up).normal()
    v_axis = (primary_axis ^ u_axis).normal()
    
    min_h, max_h = float('inf'), float('-inf')
    min_u, max_u = float('inf'), float('-inf')
    min_v, max_v = float('inf'), float('-inf')
    
    projected_data = []
    for p in points:
        vec = om.MVector(p)
        h = vec * primary_axis
        u = vec * u_axis
        v = vec * v_axis
        if h < min_h: min_h = h
        if h > max_h: max_h = h
        if u < min_u: min_u = u
        if u > max_u: max_u = u
        if v < min_v: min_v = v
        if v > max_v: max_v = v
        projected_data.append((h, u, v))
        
    center_h = (min_h + max_h) / 2.0
    center_u = (min_u + max_u) / 2.0
    center_v = (min_v + max_v) / 2.0
    
    final_center = (primary_axis * center_h) + (u_axis * center_u) + (v_axis * center_v)
    height = max_h - min_h
    
    total_dist = 0.0
    for h, u, v in projected_data:
        du = u - center_u
        dv = v - center_v
        dist = math.sqrt(du*du + dv*dv)
        total_dist += dist
    radius = total_dist / num_points 

    return { "axis": primary_axis, "center": final_center, "radius": radius, "height": height }

def create_cylinder_logic(dag_path, subdivisions, keep_original, capped, manual_axis=None):
    data = calculate_geometry_data(dag_path, manual_axis)
    if not data: return None
        
    obj_name = dag_path.partialPathName()
    
    cyl_transform = cmds.polyCylinder(
        radius=data["radius"], 
        height=data["height"], 
        subdivisionsX=subdivisions, 
        subdivisionsY=1, subdivisionsZ=1, 
        axis=(0, 1, 0), roundCap=0, createUVs=2,
        name=obj_name + "_Replaced"
    )[0]

    y_axis = om.MVector(0, 1, 0)
    target_axis = data["axis"]
    quat = y_axis.rotateTo(target_axis)
    trans_mat = om.MTransformationMatrix()
    trans_mat.setRotation(quat)
    trans_mat.setTranslation(data["center"], om.MSpace.kWorld)
    cmds.xform(cyl_transform, m=list(trans_mat.asMatrix()), worldSpace=True)
    
    if not capped:
        sel_list = om.MSelectionList(); sel_list.add(cyl_transform)
        mesh_fn_cyl = om.MFnMesh(sel_list.getDagPath(0))
        faces = []
        for i in range(mesh_fn_cyl.numPolygons):
            if abs(mesh_fn_cyl.getPolygonNormal(i, om.MSpace.kObject).y) > 0.9:
                faces.append("{}.f[{}]".format(cyl_transform, i))
        if faces: cmds.delete(faces)
    
    cmds.delete(cyl_transform, ch=True)
    
    if not keep_original: cmds.delete(obj_name)
    else: cmds.hide(obj_name)
    
    return cyl_transform

def run_operation(subdivisions, keep_original=True, capped=True):
    sel = om.MGlobal.getActiveSelectionList()
    if sel.isEmpty():
        cmds.warning(u"请选择物体，或选择组件")
        return

    cmds.undoInfo(openChunk=True)
    results = []
    
    try:
        # === 智能获取轴向 ===
        manual_axis, dag_path_comp = smart_get_axis_from_selection(sel)
        
        if manual_axis and dag_path_comp:
            # 模式 A: 有指引
            print(u"辅助指引已激活...")
            res = create_cylinder_logic(dag_path_comp, subdivisions, keep_original, capped, manual_axis)
            if res: results.append(res)
            
        else:
            # 模式 B: 全自动
            print(u"全自动模式...")
            sel_strings = cmds.ls(sl=True, long=True)
            for obj in sel_strings:
                if not cmds.listRelatives(obj, s=True, type='mesh'): continue
                t_sel = om.MSelectionList(); t_sel.add(obj)
                t_dag = t_sel.getDagPath(0)
                res = create_cylinder_logic(t_dag, subdivisions, keep_original, capped, None)
                if res: results.append(res)

    except Exception as e:
        cmds.error(u"Error: {}".format(e))
    finally:
        cmds.undoInfo(closeChunk=True)
        
    if results: 
        cmds.select(results)
        print(u"替换完成。")

# --- UI ---
def run_ui():
    win = "CylinderCreatorWindow"
    if cmds.window(win, exists=True): cmds.deleteUI(win)
    cmds.window(win, title=u"圆柱替换 v5.5 (辅助选择)", widthHeight=(300, 180))
    cmds.columnLayout(adj=True, rs=10, co=('both', 5))
    
    cmds.frameLayout(l=u"操作模式 (Smart Select)", cl=0, bgc=(0.2,0.2,0.2), mh=5)
    cmds.text(l=u"1. 选 1 条侧边线 -> 识别为高度轴 (最推荐)", al='left', font="boldLabelFont")
    cmds.text(l=u"2. 选 1 个顶面/底面 -> 识别为垂直轴", al='left')
    cmds.text(l=u"3. 选 3 个以上点 -> 拟合平面法线", al='left')
    cmds.setParent('..')

    cmds.rowLayout(nc=2, cw2=(80, 200), adj=2)
    cmds.text(l=u"圆柱段数：", al='right')
    sf_subdiv = cmds.intSliderGrp(f=True, min=3, max=64, v=8)
    cmds.setParent('..')
    
    cmds.rowLayout(nc=2, cw2=(80, 200), adj=2)
    cmds.text(l=u"选项：", al='right')
    cmds.rowColumnLayout(nc=2, cw=[(1, 110), (2, 100)])
    cb_keep = cmds.checkBox(l=u"保留原物体", v=True)
    cb_caps = cmds.checkBox(l=u"两端封口", v=True)
    cmds.setParent('..'); cmds.setParent('..') 

    cmds.button(l=u"执行替换", h=40, bgc=(0.3, 0.5, 0.6), 
                c=lambda x: run_operation(cmds.intSliderGrp(sf_subdiv,q=1,v=1), 
                                          cmds.checkBox(cb_keep,q=1,v=1), 
                                          cmds.checkBox(cb_caps,q=1,v=1)))
    cmds.showWindow(win)

def run():
    run_ui()
if __name__ == "__main__":
    run()