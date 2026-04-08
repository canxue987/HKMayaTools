
# -*- coding: utf-8 -*-
import maya.cmds as cmds
import maya.api.OpenMaya as om
import math

class GlobalQuadRetopologyV13:
    def __init__(self):
        self.window = "GlobalQuadWindowV13"
        self.title = u"智能四边化"
        self.size = (320, 280)
        self.ui_id_tolerance = "sq_v13_tolerance_id"
        self.ui_id_chk_hard = "sq_v13_chk_hard_id"
        self.ui_id_max_iter = "sq_v13_max_iter_id"

    def _run_single_pass(self, dag_path, angle_threshold, keep_hard_edges):
        """
        执行一轮全局打分 + 贪心匹配。
        核心逻辑完全保留 V12，只做了两处精准修复：
          修复1: 四顶点正确环绕排序 (解决弯曲面误拦截)
          修复2: 凸包容忍度从 -0.1 放宽到 -0.15 (弯曲面更宽容)
        返回本轮删除的边数。
        """
        mesh_fn = om.MFnMesh(dag_path)
        it_poly = om.MItMeshPolygon(dag_path)
        it_edge = om.MItMeshEdge(dag_path)
        it_vert = om.MItMeshVertex(dag_path)
        obj_name = dag_path.partialPathName()

        # 提取每个顶点的 Valence
        valences = {}
        it_vert.reset()
        while not it_vert.isDone():
            valences[it_vert.index()] = len(it_vert.getConnectedEdges())
            it_vert.next()

        edge_candidates = []

        # ==========================================
        # 阶段 1：全局海选
        # ==========================================
        it_edge.reset()
        while not it_edge.isDone():
            edge_id = it_edge.index()

            # 1. 硬边保护
            if keep_hard_edges and not it_edge.isSmooth:
                it_edge.next()
                continue

            faces = it_edge.getConnectedFaces()
            if len(faces) != 2:
                it_edge.next()
                continue

            t1_id, t2_id = faces[0], faces[1]

            it_poly.setIndex(t1_id)
            verts_t1 = it_poly.getVertices()
            if len(verts_t1) != 3:
                it_edge.next()
                continue

            it_poly.setIndex(t2_id)
            verts_t2 = it_poly.getVertices()
            if len(verts_t2) != 3:
                it_edge.next()
                continue

            # 2. 面法线平坦度评估
            n1 = mesh_fn.getPolygonNormal(t1_id, om.MSpace.kWorld)
            n2 = mesh_fn.getPolygonNormal(t2_id, om.MSpace.kWorld)
            dot_val = max(min(n1 * n2, 1.0), -1.0)
            angle = math.degrees(math.acos(dot_val))

            if angle > angle_threshold:
                it_edge.next()
                continue

            # 提取四顶点
            v_A, v_B = it_edge.vertexId(0), it_edge.vertexId(1)
            v_C = [v for v in verts_t1 if v != v_A and v != v_B][0]
            v_D = [v for v in verts_t2 if v != v_A and v != v_B][0]

            p_A = mesh_fn.getPoint(v_A, om.MSpace.kWorld)
            p_B = mesh_fn.getPoint(v_B, om.MSpace.kWorld)
            p_C = mesh_fn.getPoint(v_C, om.MSpace.kWorld)
            p_D = mesh_fn.getPoint(v_D, om.MSpace.kWorld)

            # ====== 修复1: 正确的四顶点环绕排序 ======
            # V12 原始的 C->A->D->B 顺序在弯曲表面上不一定是正确环绕序
            # 正确做法: 三角形1 = (A,B,C) 和 三角形2 = (A,B,D)
            # 四边形的正确环绕应该是 C-A-D-B 或 C-B-D-A
            # 通过检查两种排列哪个凸包更一致来选择
            
            def _try_order(pp0, pp1, pp2, pp3):
                """尝试一种排列，返回 (edges, crosses, n_avg) 或 None"""
                ee1 = pp1 - pp0
                ee2 = pp2 - pp1
                ee3 = pp3 - pp2
                ee4 = pp0 - pp3
                cc1 = ee1 ^ ee2
                cc2 = ee2 ^ ee3
                cc3 = ee3 ^ ee4
                cc4 = ee4 ^ ee1
                nn = cc1 + cc2 + cc3 + cc4
                if nn.length() < 1e-12:
                    return None
                nn = nn.normal()
                # 计算凸包一致性分数 (全正最好)
                convex_score = min(cc1 * nn, cc2 * nn, cc3 * nn, cc4 * nn)
                return (ee1, ee2, ee3, ee4, cc1, cc2, cc3, cc4, nn, convex_score)
            
            # 尝试两种排列
            order_1 = _try_order(p_C, p_A, p_D, p_B)  # C-A-D-B (原V12)
            order_2 = _try_order(p_C, p_B, p_D, p_A)  # C-B-D-A (翻转)

            # 选择凸包一致性更好的那个
            best = None
            if order_1 is not None and order_2 is not None:
                best = order_1 if order_1[9] >= order_2[9] else order_2
            elif order_1 is not None:
                best = order_1
            elif order_2 is not None:
                best = order_2
            
            if best is None:
                it_edge.next()
                continue

            E1, E2, E3, E4, C1, C2, C3, C4, N, convex_min = best

            # 3. 3D凸包底线拦截 (修复2: 弯曲面放宽容忍度)
            if convex_min < -0.15:
                it_edge.next()
                continue

            # --- 核心打分引擎 (完全保留 V12 原版逻辑) ---

            # A. 形状方正度
            def angle_between(v1, v2):
                if v1.length() < 1e-5 or v2.length() < 1e-5:
                    return 90.0
                return math.degrees(math.acos(
                    max(min(v1.normal() * v2.normal(), 1.0), -1.0)))

            a1 = angle_between(-E4, E1)
            a2 = angle_between(-E1, E2)
            a3 = angle_between(-E2, E3)
            a4 = angle_between(-E3, E4)
            shape_dev = abs(a1 - 90) + abs(a2 - 90) + abs(a3 - 90) + abs(a4 - 90)

            # B. 法线边缘的平行流向
            dot_13 = abs(E1.normal() * E3.normal()) if E1.length() > 1e-5 and E3.length() > 1e-5 else 0.0
            dot_24 = abs(E2.normal() * E4.normal()) if E2.length() > 1e-5 and E4.length() > 1e-5 else 0.0
            parallel_penalty = (1.0 - dot_13) + (1.0 - dot_24)

            # C. 对角线长度法则
            len_diag_current = (p_A - p_B).length()
            len_diag_other = (p_C - p_D).length()
            diag_ratio = len_diag_current / len_diag_other if len_diag_other > 1e-5 else 1.0

            # D. 复杂交汇处(极点)消解奖励 (降低权重，防止形状差的也被强拉)
            val_sum = valences.get(v_A, 4) + valences.get(v_B, 4)

            # 综合分数 (保留 V12 结构，微调极点权重)
            score = ((angle * 0.5) 
                     + (shape_dev * 0.5) 
                     + (parallel_penalty * 30.0) 
                     + (diag_ratio * 20.0) 
                     - (val_sum * 2.0))

            edge_candidates.append({
                'id': edge_id,
                'score': score,
                't1': t1_id,
                't2': t2_id
            })

            it_edge.next()

        if not edge_candidates:
            return 0

        # ==========================================
        # 阶段 2：上帝视角排序分配
        # ==========================================
        edge_candidates.sort(key=lambda k: k['score'])

        consumed_faces = set()
        edges_to_delete = []

        for candidate in edge_candidates:
            t1, t2 = candidate['t1'], candidate['t2']
            if t1 not in consumed_faces and t2 not in consumed_faces:
                edges_to_delete.append("{0}.e[{1}]".format(obj_name, candidate['id']))
                consumed_faces.add(t1)
                consumed_faces.add(t2)

        if edges_to_delete:
            cmds.polyDelEdge(edges_to_delete, cv=True)
            return len(edges_to_delete)

        return 0

    def process(self):
        angle_threshold = 80.0
        keep_hard_edges = False
        max_iterations = 5

        if cmds.floatSliderGrp(self.ui_id_tolerance, exists=True):
            angle_threshold = cmds.floatSliderGrp(self.ui_id_tolerance, q=True, v=True)
        if cmds.checkBox(self.ui_id_chk_hard, exists=True):
            keep_hard_edges = cmds.checkBox(self.ui_id_chk_hard, q=True, v=True)
        if cmds.intSliderGrp(self.ui_id_max_iter, exists=True):
            max_iterations = cmds.intSliderGrp(self.ui_id_max_iter, q=True, v=True)

        sel = cmds.ls(sl=True, o=True)
        if not sel:
            cmds.warning(u"请选择需要处理的多边形模型")
            return

        target_meshes = list(set(sel))
        total_deleted = 0

        cmds.undoInfo(openChunk=True)

        try:
            for mesh_name in target_meshes:
                mesh_total = 0

                for iteration in range(max_iterations):
                    # 每轮迭代重新获取 dag_path (拓扑已变)
                    cmds.select(mesh_name, r=True)
                    sel_list = om.MGlobal.getActiveSelectionList()

                    try:
                        dag_path, _ = sel_list.getComponent(0)
                    except:
                        break

                    if dag_path.apiType() == om.MFn.kTransform:
                        try:
                            dag_path.extendToShape()
                        except:
                            break
                    if dag_path.apiType() != om.MFn.kMesh:
                        break

                    deleted = self._run_single_pass(
                        dag_path, angle_threshold, keep_hard_edges)

                    mesh_total += deleted

                    if deleted == 0:
                        break

                    obj_name = dag_path.partialPathName()
                    print(u"【V13 迭代 {}/{}】: {} -> 清理了 {} 条对角线".format(
                        iteration + 1, max_iterations, obj_name, deleted))

                total_deleted += mesh_total

        finally:
            cmds.undoInfo(closeChunk=True)

        cmds.select(target_meshes, r=True)
        if total_deleted > 0:
            om.MGlobal.displayInfo(
                u"四边化重构完成！共计消除 {} 条冗余对角线。".format(total_deleted))
        else:
            om.MGlobal.displayWarning(u"未找到符合条件的拓扑。")

    def ui(self):
        cmds.columnLayout(adj=True, rowSpacing=8, columnAttach=('both', 10))
        cmds.separator(h=5, style='none')
        cmds.text(label=u"【智能四边化】", font="boldLabelFont")
        cmds.text(label=u" ",
                  font="smallPlainLabelFont", wordWrap=True)

        cmds.separator(h=5, style='in')

        cmds.rowLayout(nc=2, adj=2, columnWidth1=80)
        cmds.text(label=u"共面容差度: ",
                  annotation=u"全局最优匹配，阈值可放心开大(80~90)")
        cmds.floatSliderGrp(self.ui_id_tolerance, field=True,
                            minValue=0.0, maxValue=180.0, value=80.0)
        cmds.setParent('..')

        cmds.rowLayout(nc=2, adj=2, columnWidth1=80)
        cmds.text(label=u"迭代次数: ",
                  annotation=u"每轮删完重新扫描，捡回被互斥挡住的三角对")
        cmds.intSliderGrp(self.ui_id_max_iter, field=True,
                          minValue=1, maxValue=20, value=5)
        cmds.setParent('..')

        cmds.rowLayout(nc=2, adj=2, columnWidth1=10)
        cmds.text(label=u" ")
        cmds.checkBox(self.ui_id_chk_hard,
                      label=u"保留硬边 (处理导入的断线模型请取消勾选!)",
                      value=False)
        cmds.setParent('..')

        cmds.separator(h=5, style='none')

        cmds.button(label=u"执行一键全局四边化", h=40, bgc=(0.35, 0.65, 0.55),
                    c=lambda x: self.process())

        cmds.separator(h=3, style='none')
        cmds.text(label=u"提示: Ctrl+Z 撤销后调参重来",
                  font="smallPlainLabelFont", wordWrap=True)


_global_quad_tool_v13 = GlobalQuadRetopologyV13()

def run_ui():
    if cmds.window(_global_quad_tool_v13.window, exists=True):
        cmds.deleteUI(_global_quad_tool_v13.window)
    cmds.window(_global_quad_tool_v13.window,
                title=_global_quad_tool_v13.title,
                widthHeight=_global_quad_tool_v13.size)
    _global_quad_tool_v13.ui()
    cmds.showWindow(_global_quad_tool_v13.window)

def run():
    run_ui()

if __name__ == "__main__":
    run()
