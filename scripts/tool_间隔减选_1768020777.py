# -*- coding: utf-8 -*-
"""
Reduce Selected Edges (Loop or Ring) - Maya 2022.4+


新增
- 模式支持：Loop（共享顶点邻接）与 Ring（四边面对边邻接）
- 保持：拓扑稳定 / 分段排序 / 偏移控制 / 精简 UI


说明
- 间隔 N => 保留 1 条跳过 N 条（步长 = N+1）
- 偏移 offset 控制起始相位（闭环/链均适用）
- Loop 模式：适用于沿着连续边（共享顶点）的走向（原逻辑）
- Ring 模式：通过四边面上的“对边”构造邻接，沿 Ring 方向分段抽取
  注：遇到三角面或 n-gon 时，Ring 会自然中断


使用
- 将脚本粘贴到 Script Editor 执行，或保存为 .py 后导入并调用 main()
- Python:
    import importlib, reduce_selected_edges_loop_ring as r
    importlib.reload(r)
    r.main()


Author: Assistant
Version: 2.0
"""


from collections import defaultdict
import maya.cmds as cmds
import maya.api.OpenMaya as om



# ---------------------- 基础工具 ----------------------


def _ls_edges(selection=None):
    """仅提取选择中的边组件（保持扁平化）"""
    sel = selection if selection is not None else (cmds.ls(selection=True, flatten=True) or [])
    return [s for s in sel if ".e[" in s]



def _parse_component(comp_str):
    """将 'pCube1.e[12]' 解析为 (dagPath, shapeFullName, [edgeIndices])"""
    sl = om.MSelectionList()
    sl.add(comp_str)
    dag, comp = sl.getComponent(0)
    try:
        dag.extendToShape()
    except Exception:
        pass
    if comp.isNull():
        raise RuntimeError(u"无法解析组件: {}".format(comp_str))
    idxs = om.MFnSingleIndexedComponent(comp).getElements()
    return dag, dag.fullPathName(), idxs



def _group_edges_by_shape(edge_comps):
    """将边组件按 shape 分组为 {shapeName: set(edgeIds)} 和 {shapeName: dag}"""
    per_shape = defaultdict(set)
    per_dag = {}
    for s in edge_comps:
        try:
            dag, shapeName, idxs = _parse_component(s)
            if not idxs:
                continue
            per_shape[shapeName].update(idxs)
            per_dag[shapeName] = dag
        except Exception:
            pass
    return per_shape, per_dag



# ---------------------- 拓扑与邻接 ----------------------


def _build_neighbors_loop(shapeDag):
    """Loop 模式邻接：共享顶点即邻接"""
    fn = om.MFnMesh(shapeDag)
    num_edges = fn.numEdges
    neighbors = {i: set() for i in range(num_edges)}
    vit = om.MItMeshVertex(shapeDag)
    while not vit.isDone():
        conn = vit.getConnectedEdges()
        for a in range(len(conn)):
            ea = conn[a]
            for b in range(a + 1, len(conn)):
                eb = conn[b]
                neighbors[ea].add(eb)
                neighbors[eb].add(ea)
        vit.next()
    return neighbors



def _build_neighbors_ring(shapeDag):
    """
    Ring 模式邻接：四边面上的对边互为邻接
    - 对每个四边面，建立 (e0<->e2) 与 (e1<->e3) 的双向邻接
    - 不跨越三角面或 n-gon；遇到非四边面自然中断
    """
    neighbors = defaultdict(set)
    pit = om.MItMeshPolygon(shapeDag)
    while not pit.isDone():
        if pit.polygonVertexCount() == 4:
            edges = list(pit.getEdges())
            if len(edges) == 4:
                e0, e1, e2, e3 = edges
                # 对边成对
                neighbors[e0].add(e2)
                neighbors[e2].add(e0)
                neighbors[e1].add(e3)
                neighbors[e3].add(e1)
        pit.next()
    return neighbors



# ---------------------- 分段与抽取 ----------------------


def _order_selected_into_sequences(neighbors, selected_indices):
    """
    将选中的边在子图中分段并排序，返回 [(seq:list[int], is_closed:bool), ...]
    - 链：存在端点（度<=1），从端点出发沿邻接遍历
    - 环：全部度=2，从最小 index 出发绕完；首尾相邻即视为闭环
    """
    sel = set(selected_indices)
    sub_adj = {e: sorted([n for n in neighbors.get(e, []) if n in sel]) for e in sel}
    degrees = {e: len(sub_adj[e]) for e in sel}
    visited = set()
    results = []


    # 链：从端点出发
    starts = [e for e, d in degrees.items() if d <= 1]
    for s in sorted(starts):
        if s in visited:
            continue
        seq = [s]
        visited.add(s)
        prev = None
        cur = s
        while True:
            nxts = [n for n in sub_adj.get(cur, []) if n != prev and n not in visited]
            if not nxts:
                break
            nxt = nxts[0]  # sub_adj 已排序，遍历稳定
            seq.append(nxt)
            visited.add(nxt)
            prev, cur = cur, nxt
        results.append((seq, False))


    # 剩余：环或未覆盖的链残段
    remaining = sorted([e for e in sel if e not in visited])
    while remaining:
        start = remaining[0]
        seq = [start]
        visited.add(start)
        prev = None
        cur = start
        while True:
            nxts = [n for n in sub_adj.get(cur, []) if n != prev and n not in visited]
            if not nxts:
                break
            nxt = nxts[0]
            seq.append(nxt)
            visited.add(nxt)
            prev, cur = cur, nxt
        is_closed = seq[0] in sub_adj.get(seq[-1], [])
        results.append((seq, is_closed))
        remaining = sorted([e for e in sel if e not in visited])


    return results



def _take_every_n(seq, interval, start_offset=0):
    """
    间隔 N 表示“保留 1，跳过 N”，即步长 step = N+1，从 start_offset 起步
    """
    step = max(1, int(interval) + 1)
    start = start_offset % step
    return [seq[k] for k in range(start, len(seq), step)]



# ---------------------- UI + 功能 ----------------------


class ReduceSelectedEdgesLoopRing:
    def __init__(self):
        self.window_name = "reduceSelectedEdgesLoopRing"
        self.interval_value = 1
        self.offset_value = 0
        self.mode = "loop"  # "loop" 或 "ring"


    def create_ui(self):
        # 防止窗口在屏幕外：先清理旧窗口与偏好
        if cmds.window(self.window_name, exists=True):
            cmds.deleteUI(self.window_name)
        if cmds.windowPref(self.window_name, exists=True):
            cmds.windowPref(self.window_name, remove=True)


        win = cmds.window(
            self.window_name,
            title=u"减少已选择的边（Loop / Ring）",
            widthHeight=(420, 230),
            sizeable=False
        )


        cmds.columnLayout(adjustableColumn=True, rowSpacing=10, columnAttach=("both", 10))
        cmds.text(label=u"Reduce Selected Edges (Loop / Ring)", font="boldLabelFont", height=26)
        cmds.separator(height=8, style="in")


        # 模式选择
        cmds.rowLayout(numberOfColumns=2, columnWidth2=(120, 260), columnAlign=(1, "right"))
        cmds.text(label=u"模式：")
        self.mode_ctrl = cmds.optionMenu(changeCommand=lambda v: setattr(self, "mode", "loop" if v == u"Loop（循环边）" else "ring"))
        cmds.menuItem(label=u"Loop（循环边）")
        cmds.menuItem(label=u"Ring（环形边）")
        cmds.optionMenu(self.mode_ctrl, edit=True, value=u"Loop（循环边）")
        cmds.setParent("..")


        # 参数
        cmds.rowLayout(numberOfColumns=5, columnWidth5=(140, 120, 30, 60, 30), columnAlign=(1, "right"))
        cmds.text(label=u"间隔数量（N）：")
        self.interval_field = cmds.intSliderGrp(
            field=True, value=self.interval_value,
            minValue=1, maxValue=10,
            fieldMinValue=1, fieldMaxValue=1000,
            step=1, fieldStep=1,
            changeCommand=lambda v: setattr(self, "interval_value", int(v))
        )
        cmds.text(label=u"偏移：")
        self.offset_field = cmds.intField(
            value=self.offset_value, changeCommand=lambda v: setattr(self, "offset_value", int(v))
        )
        cmds.setParent("..")


        cmds.separator(height=6, style="none")
        cmds.button(
            label=u"执行：按间隔保留边",
            height=34, backgroundColor=(0.30, 0.50, 0.30),
            command=lambda x: self.reduce_selected_edges()
        )


        cmds.separator(height=6, style="none")
        cmds.text(
            label=u"说明：间隔 N = 保留 1 条，跳过 N 条（步长=N+1）。\n"
                  u"Loop：共享顶点方向的连续段。Ring：四边面对边方向的连续段（遇到非四边面会中断）。\n"
                  u"偏移用于控制每段的起点相位（链/闭环均生效）。",
            align="left", font="smallPlainLabelFont"
        )


        cmds.showWindow(win)


    def reduce_selected_edges(self):
        edges = _ls_edges()
        if not edges:
            cmds.warning(u"请先选择一些边")
            return


        per_shape, per_dag = _group_edges_by_shape(edges)
        if not per_shape:
            cmds.warning(u"没有可处理的边")
            return


        N = int(cmds.intSliderGrp(self.interval_field, query=True, value=True))
        offset = int(cmds.intField(self.offset_field, query=True, value=True))
        mode = self.mode
        keep = []


        for shapeName, idx_set in per_shape.items():
            dag = per_dag[shapeName]
            if mode == "ring":
                neighbors = _build_neighbors_ring(dag)
            else:
                neighbors = _build_neighbors_loop(dag)


            sequences = _order_selected_into_sequences(neighbors, sorted(idx_set))
            for seq, is_closed in sequences:
                if not seq:
                    continue
                takes = _take_every_n(seq, N, start_offset=(offset % (N + 1)))
                keep.extend([u"{}.e[{}]".format(shapeName, e) for e in takes])


        if keep:
            cmds.select(keep, replace=True)
            try:
                cmds.inViewMessage(
                    amg=u'<span style="color:#00ff00;">按间隔保留 {} 条边（模式={}，N={}，偏移={}）</span>'.format(
                        len(keep), "Ring" if mode == "ring" else "Loop", N, offset),
                    pos='midCenter', fade=True, fadeStayTime=1200
                )
            except Exception:
                pass
        else:
            cmds.warning(u"没有边被保留（可能选择未形成有效的 {} 连续段）".format("Ring" if mode == "ring" else "Loop"))



# ---------------------- 入口 ----------------------


def main():
    """打开 UI"""
    tool = ReduceSelectedEdgesLoopRing()
    tool.create_ui()
    return tool



# --- 工具箱入口 ---  
def run():  
    tool = ReduceSelectedEdgesLoopRing()  
    tool.create_ui()