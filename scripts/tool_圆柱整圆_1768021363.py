# -*- coding: utf-8 -*-
import maya.cmds as cmds
import maya.api.OpenMaya as om
import math

class CylinderRegularizer:
    def __init__(self):
        pass

    def get_connected_vertices(self, dag_path, vtx_id):
        """
        【核心修复】使用迭代器获取连接的顶点 ID
        替代 MFnMesh.getConnectedVertices (API 2.0 中不存在该方法)
        """
        # 初始化顶点迭代器
        it_vtx = om.MItMeshVertex(dag_path)
        # 设置当前指针到指定顶点
        # setIndex 需要 int 类型的 prevIndex，如果直接跳可能会慢，
        # 但对于单个查询这是标准做法
        it_vtx.setIndex(vtx_id)
        # 获取连接的顶点索引 (返回 MIntArray)
        return it_vtx.getConnectedVertices()

    def get_dominant_axis(self, points):
        """ 计算主轴 (仅用于直圆柱模式) """
        if not points or len(points) < 3: return om.MVector(0,1,0)
        
        center = om.MVector(0,0,0)
        for p in points: center += om.MVector(p)
        center /= len(points)
        
        xx, xy, xz, yy, yz, zz = 0,0,0,0,0,0
        for p in points:
            d = om.MVector(p) - center
            xx += d.x * d.x
            xy += d.x * d.y
            xz += d.x * d.z
            yy += d.y * d.y
            yz += d.y * d.z
            zz += d.z * d.z
            
        axis = om.MVector(0,1,0)
        # 简化的幂迭代法
        for _ in range(10):
            nx = xx*axis.x + xy*axis.y + xz*axis.z
            ny = xy*axis.x + yy*axis.y + yz*axis.z
            nz = xz*axis.x + yz*axis.y + zz*axis.z
            n_vec = om.MVector(nx, ny, nz)
            if n_vec.length() > 1e-6:
                axis = n_vec.normal()
        return axis

    def find_edge_loops(self, mfn_mesh, edge_indices):
        """ 查找闭合的边循环 (过滤掉纵向线和杂乱线) """
        graph = {}
        valid_edges = set(edge_indices)
        
        # 1. 构建图
        for e_idx in valid_edges:
            v_pair = mfn_mesh.getEdgeVertices(e_idx)
            v1, v2 = v_pair[0], v_pair[1]
            if v1 not in graph: graph[v1] = []
            if v2 not in graph: graph[v2] = []
            graph[v1].append(v2)
            graph[v2].append(v1)
            
        loops = []
        visited = set()
        
        for v in graph.keys():
            if v in visited: continue
            
            component_verts = []
            q = [v]
            visited.add(v)
            while q:
                curr = q.pop(0)
                component_verts.append(curr)
                if curr in graph:
                    for neighbor in graph[curr]:
                        if neighbor not in visited:
                            visited.add(neighbor)
                            q.append(neighbor)
            
            if len(component_verts) < 3: continue
            
            # 2. 闭环检测：所有点的度数必须为2
            # 纵向线端点度数为1，会被过滤
            is_closed = True
            start_node = component_verts[0]
            
            for node in component_verts:
                if len(graph[node]) != 2:
                    is_closed = False
                    break
            
            if not is_closed: continue

            # 3. 排序顶点
            sorted_loop = [start_node]
            curr = start_node
            seen_in_sort = {start_node}
            max_iter = len(component_verts) * 2
            count = 0
            
            while count < max_iter:
                count += 1
                neighbors = graph.get(curr, [])
                next_node = None
                for n in neighbors:
                    if n not in seen_in_sort:
                        next_node = n
                        break
                
                if next_node is None:
                    # 检查是否回到了起点
                    if sorted_loop[0] in neighbors:
                        break 
                else:
                    sorted_loop.append(next_node)
                    seen_in_sort.add(next_node)
                    curr = next_node

            loops.append(sorted_loop)
            
        return loops

    def find_pole_vertex(self, dag_path, loop_vtx_ids):
        """ 
        查找封口极点 
        需要 dag_path 来初始化 MItMeshVertex 
        """
        if not loop_vtx_ids: return None
        v0 = loop_vtx_ids[0]
        
        # 【修复】使用 get_connected_vertices 替代不存在的 API 方法
        try:
            candidates = self.get_connected_vertices(dag_path, v0)
        except:
            return None

        loop_set = set(loop_vtx_ids)
        
        for cand in candidates:
            if cand in loop_set: continue
            
            # 极点必须连接 Loop 中每一个点
            is_pole = True
            
            # 获取 candidate 的邻居
            cand_neigh = set(self.get_connected_vertices(dag_path, cand))
            
            # 检查包含关系
            if not loop_set.issubset(cand_neigh):
                is_pole = False
            
            if is_pole:
                return cand
        return None

    def process(self, align_to_axis=True):
        # 【修复】预先保存选择字符串，防止 ValueError
        sel_strings = cmds.ls(sl=True)
        sel = om.MGlobal.getActiveSelectionList()
        
        if sel.isEmpty():
            cmds.warning(u"请先选择物体或边")
            return

        # 1. 基础信息获取
        dag_path, component = sel.getComponent(0)
        edges_to_process = []
        is_edge_mode = False
        
        if not component.isNull() and component.hasFn(om.MFn.kMeshEdgeComponent):
            is_edge_mode = True
            fn_comp = om.MFnSingleIndexedComponent(component)
            edges_to_process = list(fn_comp.getElements())

        try:
            dag_path.extendToShape()
            mfn_mesh = om.MFnMesh(dag_path)
        except:
            cmds.error(u"无法初始化网格，请确保选择的是 Mesh。")
            return

        if not is_edge_mode:
            # 物体模式：获取所有边，后续通过 find_edge_loops 自动过滤纵向线
            edges_to_process = list(range(mfn_mesh.numEdges))

        # 2. 直圆柱模式下的预过滤 (可选优化)
        all_points = mfn_mesh.getPoints(om.MSpace.kWorld)
        global_axis = om.MVector(0,1,0)

        if align_to_axis:
            global_axis = self.get_dominant_axis(all_points)
            # 如果是全选模式，尝试过滤掉明显的纵向线以加速
            if len(edges_to_process) > 500 or not is_edge_mode:
                filtered_edges = []
                for e_idx in edges_to_process:
                    v_ids = mfn_mesh.getEdgeVertices(e_idx)
                    p1 = om.MVector(all_points[v_ids[0]])
                    p2 = om.MVector(all_points[v_ids[1]])
                    vec = (p2 - p1).normal()
                    if abs(vec * global_axis) < 0.8: # 过滤掉平行于主轴的边
                        filtered_edges.append(e_idx)
                edges_to_process = filtered_edges

        # 3. 识别 Loops
        if not edges_to_process:
            cmds.warning(u"没有找到需要处理的边。")
            return

        loops = self.find_edge_loops(mfn_mesh, edges_to_process)
        if not loops:
            cmds.warning(u"未检测到闭合圆环。请确保选中了横向的边循环，或者物体端口是开放的。")
            # 【修复】使用字符串恢复选择
            if sel_strings: cmds.select(sel_strings)
            return

        print(u"模式: {} | 检测到 {} 个圆环".format(u"直圆柱" if align_to_axis else u"弯管", len(loops)))

        # 4. 计算新位置
        final_positions = {} 
        
        for loop_vtx_ids in loops:
            if len(loop_vtx_ids) < 3: continue
            
            loop_pts = [om.MVector(all_points[i]) for i in loop_vtx_ids]
            
            # A. 确定法线
            if align_to_axis:
                normal = global_axis
            else:
                # 弯管模式：使用局部平均法线
                center_temp = om.MVector(0,0,0)
                for p in loop_pts: center_temp += p
                center_temp /= len(loop_pts)
                normal = om.MVector(0,0,0)
                for i in range(len(loop_pts)):
                    p0 = loop_pts[i] - center_temp
                    p1 = loop_pts[(i+1)%len(loop_pts)] - center_temp
                    normal += (p0 ^ p1)
                normal.normalize()

            # B. 切线空间
            tangent = om.MVector(1,0,0) ^ normal
            if tangent.length() < 0.1:
                tangent = om.MVector(0,0,1) ^ normal
            tangent.normalize()
            binormal = normal ^ tangent
            binormal.normalize()

            # C. 投影与包围盒中心
            min_u, max_u = float('inf'), float('-inf')
            min_v, max_v = float('inf'), float('-inf')
            
            temp_center = om.MVector(0,0,0)
            for p in loop_pts: temp_center += p
            temp_center /= len(loop_pts)

            avg_height = 0.0
            for p in loop_pts:
                vec = p - temp_center
                u = vec * tangent
                v = vec * binormal
                h = vec * normal
                avg_height += h
                if u < min_u: min_u = u
                if u > max_u: max_u = u
                if v < min_v: min_v = v
                if v > max_v: max_v = v
            avg_height /= len(loop_pts)
            
            center_u = (min_u + max_u) / 2.0
            center_v = (min_v + max_v) / 2.0
            
            # 半径计算
            avg_radius = 0.0
            for p in loop_pts:
                vec = p - temp_center
                u = vec * tangent
                v = vec * binormal
                dist = math.sqrt((u - center_u)**2 + (v - center_v)**2)
                avg_radius += dist
            avg_radius /= len(loop_pts)
            
            # 真实几何中心
            true_center = temp_center + (tangent * center_u) + (binormal * center_v) + (normal * avg_height)

            # 起始角度
            vec_first = loop_pts[0] - temp_center
            u_first = vec_first * tangent
            v_first = vec_first * binormal
            start_angle = math.atan2(v_first - center_v, u_first - center_u)
            
            count = len(loop_vtx_ids)
            angle_step = (math.pi * 2.0) / count
            
            for i, v_idx in enumerate(loop_vtx_ids):
                theta = start_angle + (i * angle_step)
                circle_u = math.cos(theta) * avg_radius
                circle_v = math.sin(theta) * avg_radius
                final_pos = true_center + (tangent * circle_u) + (binormal * circle_v)
                final_positions[v_idx] = final_pos
            
            # --- 极点修复 (Cap Fix) ---
            # 传入 dag_path 以使用新的修复方法
            pole_idx = self.find_pole_vertex(dag_path, loop_vtx_ids)
            if pole_idx is not None:
                final_positions[pole_idx] = true_center

        # 5. 应用修改
        if final_positions:
            cmds.undoInfo(openChunk=True)
            try:
                full_path = dag_path.fullPathName()
                for v_idx, pos in final_positions.items():
                    vtx_name = "{}.vtx[{}]".format(full_path, v_idx)
                    cmds.move(pos.x, pos.y, pos.z, vtx_name, absolute=True, worldSpace=True)
            except Exception as e:
                print("Error applying positions: {}".format(e))
            finally:
                cmds.undoInfo(closeChunk=True)
        
        # 【修复】使用字符串恢复选择
        if sel_strings: 
            try:
                cmds.select(sel_strings)
            except:
                pass

# --- UI ---
def run_ui():
    win = "CylinderRegularizerUI"
    if cmds.window(win, exists=True): cmds.deleteUI(win)
    cmds.window(win, title=u"完美整圆工具 v5.0", widthHeight=(250, 100))
    
    cmds.columnLayout(adj=True, rowSpacing=5, columnAttach=('both', 5))
    
    cmds.text(label=u"根据模型类型选择模式：", align='left', height=25)
    
    # 按钮 1：直圆柱
    cmds.button(label=u"整圆 (直圆柱)", height=35, bgc=(0.3, 0.6, 0.3),
                annotation=u"适用于标准圆柱。会强制对齐所有圆环到主轴，修复歪斜。",
                command=lambda x: run_tool(align=True))
    
    cmds.separator(h=5, style='none')
    
    # 按钮 2：弯管/异形
    cmds.button(label=u"整圆 (弯管/异形)", height=35, bgc=(0.3, 0.5, 0.7),
                annotation=u"适用于弯管。不改变整体走势，只把每一圈线变圆。",
                command=lambda x: run_tool(align=False))
    
    cmds.showWindow(win)

def run_tool(align):
    tool = CylinderRegularizer()
    tool.process(align_to_axis=align)

def run():
    run_ui()

if __name__ == "__main__":
    run_ui()