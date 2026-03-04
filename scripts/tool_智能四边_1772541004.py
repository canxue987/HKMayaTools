# -*- coding: utf-8 -*-
import maya.cmds as cmds
import maya.api.OpenMaya as om
import math

class SmartQuadrangulateV5:
    def __init__(self):
        self.window = "SmartQuadWindowV5"
        self.title = u"智能四边化 V5 (纯享优化版)"
        self.size = (280, 220)
        
        # UI 唯一标识符，适配 HKMayaTools 嵌套
        self.ui_id_slider = "sq_v5_angle_slider_id"
        self.ui_id_strict = "sq_v5_strict_slider_id"
        self.ui_id_chk_hard = "sq_v5_chk_hard_id"

    def calculate_quad_quality(self, mesh_fn, it_edge, strictness):
        connected_faces = it_edge.getConnectedFaces()
        if len(connected_faces) != 2: return None, None, None

        face1_verts = list(mesh_fn.getPolygonVertices(connected_faces[0]))
        face2_verts = list(mesh_fn.getPolygonVertices(connected_faces[1]))
        if len(face1_verts) != 3 or len(face2_verts) != 3: return None, None, None 

        edge_verts = [it_edge.vertexId(0), it_edge.vertexId(1)]
        shared_v1, shared_v2 = edge_verts[0], edge_verts[1]
        
        opp_v1_list = [v for v in face1_verts if v not in edge_verts]
        opp_v2_list = [v for v in face2_verts if v not in edge_verts]
        if not opp_v1_list or not opp_v2_list: return None, None, None
            
        opp_v1, opp_v2 = opp_v1_list[0], opp_v2_list[0]

        p_s1 = mesh_fn.getPoint(shared_v1, om.MSpace.kWorld)
        p_s2 = mesh_fn.getPoint(shared_v2, om.MSpace.kWorld)
        p_o1 = mesh_fn.getPoint(opp_v1, om.MSpace.kWorld)
        p_o2 = mesh_fn.getPoint(opp_v2, om.MSpace.kWorld)

        # 1. 纯 3D 凸包检测 (绝对底线，防止形成凹进去的飞镖面)
        V0, V1, V2, V3 = p_s1, p_o1, p_s2, p_o2
        E0, E1, E2, E3 = V1 - V0, V2 - V1, V3 - V2, V0 - V3
        C0, C1, C2, C3 = E0 ^ (-E3), E1 ^ (-E0), E2 ^ (-E1), E3 ^ (-E2)
        
        N = C0 + C1 + C2 + C3
        if N.length() < 1e-5: return None, None, None
        N.normalize()
        
        # 容忍微小浮点误差，严格拦截凹面
        if (C0 * N) < -1e-3 or (C1 * N) < -1e-3 or (C2 * N) < -1e-3 or (C3 * N) < -1e-3:
            return None, None, None

        # 2. 对角线对称性
        diag_shared_vec = p_s1 - p_s2
        diag_opp_vec = p_o1 - p_o2
        len_diag_shared = diag_shared_vec.length()
        len_diag_opp = diag_opp_vec.length()
        
        if len_diag_shared < 1e-5 or len_diag_opp < 1e-5: return None, None, None
        diag_diff = abs(len_diag_shared - len_diag_opp) / max(len_diag_shared, len_diag_opp)

        # 3. 角度偏离度
        angles = []
        for vA, vB in [(E0, -E3), (E1, -E0), (E2, -E1), (E3, -E2)]:
            lenA, lenB = vA.length(), vB.length()
            if lenA < 1e-5 or lenB < 1e-5: return None, None, None
            dot = max(min((vA * vB) / (lenA * lenB), 1.0), -1.0)
            angles.append(math.degrees(math.acos(dot)))
            
        angle_dev = sum([abs(a - 90.0) for a in angles]) / 360.0
        
        # strictness介入：严格度越低，形状缺陷扣分越少，越容易被合并
        score = (diag_diff * (10.0 * strictness)) + (angle_dev * strictness)

        # 4. 定向哈希值 (核心防劈叉技术)
        # 通过提取绝对方向并乘以非对称质数，让平行的线段获得完全一致的 Hash 值
        edge_dir = diag_shared_vec.normal()
        dir_hash = abs(edge_dir.x) * 1.31 + abs(edge_dir.y) * 0.73 + abs(edge_dir.z) * 0.29

        return score, dir_hash, connected_faces

    def process(self):
        angle_threshold = 45.0
        strictness = 1.0
        keep_hard_edges = True
        
        if cmds.floatSliderGrp(self.ui_id_slider, exists=True):
            angle_threshold = cmds.floatSliderGrp(self.ui_id_slider, q=True, v=True)
        if cmds.floatSliderGrp(self.ui_id_strict, exists=True):
            strictness = cmds.floatSliderGrp(self.ui_id_strict, q=True, v=True)
        if cmds.checkBox(self.ui_id_chk_hard, exists=True):
            keep_hard_edges = cmds.checkBox(self.ui_id_chk_hard, q=True, v=True)

        sel = cmds.ls(sl=True, o=True)
        if not sel:
            cmds.warning(u"请选择需要处理的多边形模型")
            return

        target_meshes = set(sel)
        processed_paths = set() 
        total_deleted = 0

        cmds.select(list(target_meshes), r=True)
        sel_list = om.MGlobal.getActiveSelectionList()

        for i in range(sel_list.length()):
            try: dag_path, _ = sel_list.getComponent(i)
            except: continue
            
            if dag_path.apiType() == om.MFn.kTransform:
                try: dag_path.extendToShape()
                except: continue
                    
            if dag_path.apiType() != om.MFn.kMesh: continue

            path_str = dag_path.fullPathName()
            if path_str in processed_paths: continue
            processed_paths.add(path_str)

            mesh_fn = om.MFnMesh(dag_path)
            it_edge = om.MItMeshEdge(dag_path)
            obj_name = dag_path.partialPathName()
            
            edge_candidates = []
            
            while not it_edge.isDone():
                edge_id = it_edge.index()
                
                if keep_hard_edges and not it_edge.isSmooth:
                    it_edge.next()
                    continue

                faces = it_edge.getConnectedFaces()
                if len(faces) == 2:
                    norm1 = mesh_fn.getPolygonNormal(faces[0], om.MSpace.kWorld)
                    norm2 = mesh_fn.getPolygonNormal(faces[1], om.MSpace.kWorld)
                    dot = max(min(norm1 * norm2, 1.0), -1.0)
                    angle = math.degrees(math.acos(dot))
                    
                    if angle <= angle_threshold:
                        score, dir_hash, connected_faces = self.calculate_quad_quality(mesh_fn, it_edge, strictness)
                        if score is not None:
                            edge_candidates.append({
                                'id': edge_id, 
                                'score': score, 
                                'dir_hash': dir_hash,
                                'faces': set(connected_faces)
                            })
                it_edge.next()

            # --- 全局智能排序 (V5 灵魂) ---
            # 1. 先按分数(四舍五入到两位数)分组，忽略微小瑕疵
            # 2. 在同分组内，按定向 Hash 排序，强迫平行对角线一起被处理
            edge_candidates = sorted(edge_candidates, key=lambda k: (round(k['score'], 2), k['dir_hash']))

            consumed_faces = set()
            edges_to_delete = []

            for candidate in edge_candidates:
                face_set = candidate['faces']
                if not face_set.intersection(consumed_faces):
                    edges_to_delete.append("{0}.e[{1}]".format(obj_name, candidate['id']))
                    consumed_faces.update(face_set)

            if edges_to_delete:
                cmds.polyDelEdge(edges_to_delete, cv=True)
                total_deleted += len(edges_to_delete)
                print(u"【智能四边化 V5】: {} -> 优化删除了 {} 条边。".format(obj_name, len(edges_to_delete)))

        cmds.select(list(target_meshes), r=True)
        if total_deleted > 0:
            om.MGlobal.displayInfo(u"四边化完成，共计合并 {} 处。".format(total_deleted))
        else:
            om.MGlobal.displayWarning(u"未找到符合条件的三角面。")

    def ui(self):
        cmds.columnLayout(adj=True, rowSpacing=8, columnAttach=('both', 10))
        cmds.separator(h=5, style='none')
        cmds.text(label=u"【智能四边化 V5.0】", font="boldLabelFont")
        cmds.text(label=u"引入定向哈希算法，自动统一布线流", font="smallPlainLabelFont")
        
        cmds.separator(h=5, style='in')
        
        cmds.rowLayout(nc=2, adj=2, columnWidth1=70)
        cmds.text(label=u"共面阈值: ", annotation=u"允许参与合并的最大夹角")
        cmds.floatSliderGrp(self.ui_id_slider, field=True, minValue=0.0, maxValue=180.0, value=45.0)
        cmds.setParent('..')

        cmds.rowLayout(nc=2, adj=2, columnWidth1=70)
        cmds.text(label=u"形状严格度:", annotation=u"1.0=仅限完美矩形，0.1=允许畸形四边形（能连尽连）")
        cmds.floatSliderGrp(self.ui_id_strict, field=True, minValue=0.1, maxValue=2.0, value=1.0)
        cmds.setParent('..')
        
        cmds.rowLayout(nc=2, adj=2, columnWidth1=70)
        cmds.text(label=u" ")
        cmds.checkBox(self.ui_id_chk_hard, label=u"保留硬边 (保护转折结构)", value=True)
        cmds.setParent('..')
        
        cmds.separator(h=5, style='none')
        
        cmds.button(label=u"执行一键四边化", h=35, bgc=(0.3, 0.6, 0.8), c=lambda x: self.process())

_smart_quad_tool = SmartQuadrangulateV5()

def run_ui():
    if cmds.window(_smart_quad_tool.window, exists=True):
        cmds.deleteUI(_smart_quad_tool.window)
    cmds.window(_smart_quad_tool.window, title=_smart_quad_tool.title, widthHeight=_smart_quad_tool.size)
    _smart_quad_tool.ui()
    cmds.showWindow(_smart_quad_tool.window)

def run():
    run_ui()

if __name__ == "__main__":
    run()