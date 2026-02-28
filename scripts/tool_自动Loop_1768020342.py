# -*- coding: utf-8 -*-
import maya.cmds as cmds
import maya.api.OpenMaya as om
import math
import traceback

# --- 全局变量 ---
AUTO_JOB_ID = None
IS_PROCESSING = False

# ========================================================
#  1. 核心算法 (API 2.0 - 120度黄金阈值)
# ========================================================

def get_vector(p1, p2):
    return om.MVector(p2.x - p1.x, p2.y - p1.y, p2.z - p1.z)

def get_best_next(mesh_fn, it_vert, dag_path, current_edge_id, pivot_vertex_id):
    """ 计算下一条最直的边 """
    pivot_point = mesh_fn.getPoint(pivot_vertex_id, om.MSpace.kWorld)
    v_ids = mesh_fn.getEdgeVertices(current_edge_id)
    prev_vertex_id = v_ids[0] if v_ids[1] == pivot_vertex_id else v_ids[1]
    prev_point = mesh_fn.getPoint(prev_vertex_id, om.MSpace.kWorld)
    
    vec_back = get_vector(pivot_point, prev_point)
    vec_back.normalize()
    
    it_vert.setIndex(pivot_vertex_id)
    connected_edges = it_vert.getConnectedEdges()
    
    best_edge = None
    min_dot = 1.0 
    
    for edge_id in connected_edges:
        if edge_id == current_edge_id: continue 
        
        ev_ids = mesh_fn.getEdgeVertices(edge_id)
        candidate_v_id = ev_ids[0] if ev_ids[1] == pivot_vertex_id else ev_ids[1]
        candidate_point = mesh_fn.getPoint(candidate_v_id, om.MSpace.kWorld)
        
        vec_fwd = get_vector(pivot_point, candidate_point)
        vec_fwd.normalize()
        
        dot = vec_back * vec_fwd
        
        if dot < min_dot:
            min_dot = dot
            best_edge = edge_id

    # 阈值 -0.45 (约117度)，保证能过三角面且不乱跑
    threshold_dot = -0.45 
    
    if best_edge is not None and min_dot < threshold_dot:
        return best_edge
    return None

def calculate_loop(edge_name):
    """ 计算单条边的完整 Loop """
    try:
        sel_list = om.MSelectionList()
        try:
            sel_list.add(edge_name)
        except:
            return set()

        dag_path, component = sel_list.getComponent(0)
        if component.apiType() != om.MFn.kMeshEdgeComponent:
            return set()
            
        mesh_fn = om.MFnMesh(dag_path)
        it_edge = om.MItMeshEdge(dag_path, component)
        it_vert = om.MItMeshVertex(dag_path)
        
        start_edge_id = it_edge.index()
        result_ids = set([start_edge_id])
        
        start_verts = mesh_fn.getEdgeVertices(start_edge_id)
        
        for initial_pivot in start_verts:
            curr_edge = start_edge_id
            curr_pivot = initial_pivot
            
            for _ in range(500): 
                next_edge = get_best_next(mesh_fn, it_vert, dag_path, curr_edge, curr_pivot)
                
                if next_edge is None or next_edge in result_ids: 
                    break
                    
                result_ids.add(next_edge)
                
                curr_edge = next_edge
                ev_ids = mesh_fn.getEdgeVertices(next_edge)
                curr_pivot = ev_ids[1] if ev_ids[0] == curr_pivot else ev_ids[0]
        
        # 返回全名集合
        result_names = set()
        full_path = dag_path.fullPathName()
        for eid in result_ids:
            result_names.add("{0}.e[{1}]".format(full_path, eid))
            
        return result_names
        
    except:
        return set()

# ========================================================
#  2. 智能扫描逻辑 (解决顺序混乱问题的关键)
# ========================================================

def _selection_callback():
    global IS_PROCESSING
    if IS_PROCESSING: return

    # 1. 获取当前所有边 (不关心顺序)
    try:
        # 即使 os=False 也没关系，我们不需要顺序了
        sel_raw = cmds.ls(sl=True, fl=True, long=True)
    except:
        return

    if not sel_raw: return

    # 过滤出边
    current_edges = [x for x in sel_raw if ".e[" in x]
    if not current_edges: return

    IS_PROCESSING = True
    
    try:
        # 2. 准备集合用于快速比对
        current_set = set(current_edges)
        
        # 这是一个缓存池，用来记录那些“已经被确认完整的 Loop”
        # 比如 Edge A 和 Edge B 在同一个 Loop 里，算完 A 之后，B 就不用算了
        checked_edges = set() 
        
        edges_to_add_final = set()
        has_new_stuff = False

        # 3. 遍历当前所有选中的边 (智能扫描)
        for edge in current_edges:
            
            # 如果这条边属于之前已经检查过的完美 Loop，直接跳过 (性能优化)
            if edge in checked_edges:
                continue
            
            # 如果这条边还没检查过，计算它所属的 Loop
            loop_set = calculate_loop(edge)
            
            # 把算出来的这一圈都标记为“已检查”
            checked_edges.update(loop_set)
            
            # 4. 核心差异检测
            # 看看这个 Loop 里，是不是还有没被选中的边？
            # 如果有，说明这是一个“残缺的 Loop” (即用户刚刚 Shift 加选的那个)
            diff = loop_set - current_set
            
            if diff:
                edges_to_add_final.update(diff)
                has_new_stuff = True
                
                # 优化：通常一次点击只会产生一组残缺 Loop。
                # 找到一组后，我们可以选择 break 以提升速度。
                # 但为了极度稳健，我们可以继续扫完 (API 很快，扫几百个边也就几毫秒)
                # break 

        # 5. 执行操作
        if has_new_stuff:
            # 使用 add=True 模式
            cmds.select(list(edges_to_add_final), add=True)

    except Exception as e:
        print("Auto Loop Error: " + str(e))
        traceback.print_exc()
    finally:
        IS_PROCESSING = False

# ========================================================
#  3. UI
# ========================================================

def toggle_tool(state):
    global AUTO_JOB_ID
    
    if AUTO_JOB_ID:
        try: cmds.scriptJob(kill=AUTO_JOB_ID, force=True)
        except: pass
        AUTO_JOB_ID = None

    if state:
        AUTO_JOB_ID = cmds.scriptJob(event=["SelectionChanged", _selection_callback], protected=True)
        om.MGlobal.displayInfo(u"自动Loop: 已开启")
        _selection_callback()
    else:
        om.MGlobal.displayInfo(u"自动Loop: 已关闭")

def on_close(win):
    toggle_tool(False)
    if cmds.window(win, exists=True):
        cmds.deleteUI(win)

def run_ui():
    win = "AutoLoopV11"
    if cmds.window(win, exists=True):
        cmds.deleteUI(win)
    
    cmds.window(win, title=u"Loop V11 (Fix Shift)", widthHeight=(200, 200))
    cmds.scriptJob(uiDeleted=[win, lambda: toggle_tool(False)], runOnce=True)
    
    cmds.columnLayout(adj=True, rowSpacing=10, columnAttach=('both', 10))
    cmds.separator(h=5, style='none')
    cmds.text(label=u"【自动Loop】", font="boldLabelFont")
    cmds.text(label=u"支持加选加选", font="smallPlainLabelFont")
    cmds.checkBox(label=u"启用", value=False, changeCommand=lambda x: toggle_tool(x))
    cmds.separator(h=10, style='in')
    cmds.button(label=u"关闭", c=lambda x: on_close(win))
    cmds.showWindow(win)

def run():
    toggle_tool(False)
    run_ui()
if __name__ == "__main__":
    run()