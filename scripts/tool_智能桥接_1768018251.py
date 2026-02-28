# -*- coding: utf-8 -*-
import math
import maya.cmds as cmds
import maya.mel as mel

class SmartStitchBridge_Compact:
    def __init__(self):
        self.window = "SmartStitchBridgeWin_Compact"
        self.title = u"智能桥接"
        self.size = (240, 480) # 界面更窄
        
        # 数据缓存
        self.is_initialized = False
        self.loop_a_pos = [] 
        self.base_loop_b_pos = [] 
        
        self.center_a = [0,0,0]; self.normal_a = [0,1,0]
        self.center_b = [0,0,0]; self.normal_b = [0,1,0]
        self.source_obj = ""
        self.preview_grp = "Stitch_Preview_Grp"
        self.b_count = 10 

    # --- 基础几何运算 ---
    def get_pos(self, vtx): return cmds.xform(vtx, q=True, ws=True, t=True)
    def dist_sq(self, p1, p2): return (p1[0]-p2[0])**2 + (p1[1]-p2[1])**2 + (p1[2]-p2[2])**2
    def dist_val(self, p1, p2): return math.sqrt(self.dist_sq(p1, p2))
    
    def bezier_point(self, p0, p1, p2, p3, t):
        u = 1 - t; tt = t*t; uu = u*u; uuu = uu*u; ttt = tt*t
        p = [0,0,0]
        for i in range(3):
            p[i] = uuu*p0[i] + 3*uu*t*p1[i] + 3*u*tt*p2[i] + ttt*p3[i]
        return p

    def calc_loop_stats(self, pos_list):
        count = len(pos_list)
        if count < 3: return [0,0,0], [0,1,0]
        cx=cy=cz=0.0
        for p in pos_list: cx+=p[0]; cy+=p[1]; cz+=p[2]
        center = [cx/count, cy/count, cz/count]
        nx=ny=nz=0.0
        for i in range(count):
            p1 = pos_list[i]; p2 = pos_list[(i+1)%count]
            nx += (p1[1]-p2[1])*(p1[2]+p2[2])
            ny += (p1[2]-p2[2])*(p1[0]+p2[0])
            nz += (p1[0]-p2[0])*(p1[1]+p2[1])
        l = math.sqrt(nx*nx+ny*ny+nz*nz)
        if l < 1e-6: return center, [0,1,0]
        return center, [nx/l, ny/l, nz/l]

    # --- 拓扑处理 ---
    def get_ordered_vertices(self, edge_loop):
        vtxs = cmds.ls(cmds.polyListComponentConversion(edge_loop, fe=True, tv=True), fl=True)
        adj_map = {}
        target_edges = set(cmds.ls(edge_loop, fl=True, l=True))
        for v in vtxs:
            connected = cmds.ls(cmds.polyListComponentConversion(v, fv=True, te=True), fl=True, l=True)
            valid = [e for e in connected if e in target_edges]
            adj_map[v] = []
            for e in valid:
                neighs = cmds.ls(cmds.polyListComponentConversion(e, fe=True, tv=True), fl=True)
                for n in neighs:
                    if n != v: adj_map[v].append(n)
        ordered = []
        if not adj_map: return []
        start = list(adj_map.keys())[0]
        curr = start; prev = None; safe = 0
        while len(ordered) < len(adj_map) and safe < len(adj_map)+5:
            ordered.append(curr)
            neighbors = adj_map.get(curr, [])
            next_v = None
            for n in neighbors:
                if n != prev: next_v = n; break
            if not next_v or next_v == start: break
            prev = curr; curr = next_v; safe += 1
        return ordered

    def filter_border_edges(self, edges):
        if not edges: return []
        cmds.select(edges, r=True)
        cmds.polySelectConstraint(m=2, t=0x8000, w=1); real = cmds.ls(sl=True, fl=True)
        cmds.polySelectConstraint(m=0, w=0)
        return real

    def separate_loops(self, edges):
        if not edges: return []
        all_e = set(edges); visited = set(); loops = []
        for e in edges:
            if e in visited: continue
            cur = []; stack = [e]; visited.add(e)
            while stack:
                curr = stack.pop(); cur.append(curr)
                vtxs = cmds.polyListComponentConversion(curr, fe=True, tv=True)
                con = cmds.ls(cmds.polyListComponentConversion(vtxs, fv=True, te=True), fl=True)
                for n in con:
                    if n in all_e and n not in visited: visited.add(n); stack.append(n)
            loops.append(cur)
        return loops

    # --- 核心引擎 ---
    def solve_by_distance(self, pos_a, pos_b):
        len_b = len(pos_b)
        best_score = float('inf'); best_pos_b = []
        def calc_score(src, dst):
            t = 0.0; ls = len(src); ld = len(dst)
            for i in range(ls):
                idx = int(math.floor(float(i)/ls * ld)) % ld
                t += self.dist_sq(src[i], dst[idx])
            return t
        for s in range(len_b):
            shifted = pos_b[s:] + pos_b[:s]
            sc = calc_score(pos_a, shifted)
            if sc < best_score: best_score = sc; best_pos_b = shifted
        rev_b = list(reversed(pos_b))
        for s in range(len_b):
            shifted = rev_b[s:] + rev_b[:s]
            sc = calc_score(pos_a, shifted)
            if sc < best_score: best_score = sc; best_pos_b = shifted
        return best_pos_b

    def solve_by_lookat(self, pos_a, pos_b, center_a, center_b):
        min_d = float('inf'); idx_a = 0
        for i, p in enumerate(pos_a):
            d = self.dist_sq(p, center_b)
            if d < min_d: min_d = d; idx_a = i
        min_d = float('inf'); idx_b = 0
        for i, p in enumerate(pos_b):
            d = self.dist_sq(p, center_a)
            if d < min_d: min_d = d; idx_b = i
            
        len_a = len(pos_a); len_b = len(pos_b)
        target_idx_b_slot = int(math.floor(float(idx_a)/len_a * len_b)) % len_b
        shift = (idx_b - target_idx_b_slot) % len_b
        best_pos_b = pos_b[shift:] + pos_b[:shift]
        
        rev_b = list(reversed(pos_b))
        min_d = float('inf'); idx_b_rev = 0
        for i, p in enumerate(rev_b):
            d = self.dist_sq(p, center_a)
            if d < min_d: min_d = d; idx_b_rev = i
        shift_rev = (idx_b_rev - target_idx_b_slot) % len_b
        best_pos_b_rev = rev_b[shift_rev:] + rev_b[:shift_rev]
        
        def calc_score(src, dst):
            t = 0.0; ls = len(src); ld = len(dst)
            for i in range(ls):
                idx = int(math.floor(float(i)/ls * ld)) % ld
                t += self.dist_sq(src[i], dst[idx])
            return t
        if calc_score(pos_a, best_pos_b_rev) < calc_score(pos_a, best_pos_b):
            return best_pos_b_rev
        return best_pos_b

    # --- 交互逻辑 ---
    def init_interactive(self):
        try:
            edges = cmds.ls(sl=True, fl=True)
            if not edges: raise Exception(u"请选择两条边界")
            edges = self.filter_border_edges(edges)
            loops = self.separate_loops(edges)
            if len(loops) != 2: raise Exception(u"需选中2个独立边界")
            
            self.source_obj = edges[0].split('.')[0]
            loop_a = self.get_ordered_vertices(loops[0])
            loop_b = self.get_ordered_vertices(loops[1])
            if not loop_a or not loop_b: raise Exception(u"顶点解析错误")
            
            self.b_count = len(loop_b)
            self.loop_a_pos = [self.get_pos(v) for v in loop_a]
            raw_b_pos = [self.get_pos(v) for v in loop_b]
            
            self.center_a, self.normal_a = self.calc_loop_stats(self.loop_a_pos)
            self.center_b, self.normal_b = self.calc_loop_stats(raw_b_pos)
            
            self.sol_dist = self.solve_by_distance(self.loop_a_pos, raw_b_pos)
            self.sol_lookat = self.solve_by_lookat(self.loop_a_pos, raw_b_pos, self.center_a, self.center_b)
            
            # 默认使用几何流 (LookAt)
            self.base_loop_b_pos = self.sol_lookat
            
            self.is_initialized = True
            
            # 激活控件 (UI控制)
            limit = self.b_count
            cmds.intFieldGrp(self.fl_offset, e=True, en=True, v1=0)
            cmds.intFieldGrp(self.fl_divs, e=True, en=True)
            cmds.floatFieldGrp(self.fl_mult, e=True, en=True)
            cmds.checkBox(self.chk_flip_a, e=True, en=True)
            cmds.checkBox(self.chk_flip_b, e=True, en=True)
            cmds.radioButtonGrp(self.rb_solver, e=True, en=True, select=2)
            
            # 按钮状态切换
            cmds.button(self.btn_init, e=True, en=False, label=u"交互中...")
            cmds.button(self.btn_apply, e=True, en=True, bgc=(0.4, 0.8, 0.4))
            
            self.update_preview()
            
        except Exception as e:
            cmds.warning(str(e))
            self.cleanup_interactive()

    def change_solver(self, mode):
        if not self.is_initialized: return
        if mode == 1: self.base_loop_b_pos = self.sol_dist
        else: self.base_loop_b_pos = self.sol_lookat
        cmds.intFieldGrp(self.fl_offset, e=True, v1=0)
        self.update_preview()

    def update_preview(self, *args):
        if not self.is_initialized: return
        
        # 获取数值 (Fields)
        offset = cmds.intFieldGrp(self.fl_offset, q=True, v1=True)
        divs = cmds.intFieldGrp(self.fl_divs, q=True, v1=True)
        mult = cmds.floatFieldGrp(self.fl_mult, q=True, v1=True)
        flip_a = cmds.checkBox(self.chk_flip_a, q=True, v=True)
        flip_b = cmds.checkBox(self.chk_flip_b, q=True, v=True)
        
        if cmds.objExists(self.preview_grp): cmds.delete(self.preview_grp)
        
        src = self.loop_a_pos
        dst_base = self.base_loop_b_pos
        shift = offset % len(dst_base)
        dst = dst_base[shift:] + dst_base[:shift]
        
        swapped = False
        if len(src) < len(dst): src, dst = dst, src; swapped = True
        len_src = len(src); len_dst = len(dst)
        
        nA = self.normal_a; nB = self.normal_b
        if flip_a: nA = [-x for x in nA]
        if flip_b: nB = [-x for x in nB]
        
        preview_faces = []
        for i in range(len_src):
            ratio1 = float(i)/len_src * len_dst
            ratio2 = float(i+1)/len_src * len_dst
            idx_d1 = int(math.floor(ratio1)) % len_dst
            idx_d2 = int(math.floor(ratio2)) % len_dst
            p_s1 = src[i]; p_s2 = src[(i+1)%len_src]
            p_d1 = dst[idx_d1]; p_d2 = dst[idx_d2]
            
            dist1 = self.dist_val(p_s1, p_d1)
            dist2 = self.dist_val(p_s2, p_d2)
            raw_len1 = dist1 * mult * 0.5
            raw_len2 = dist2 * mult * 0.5
            limit1 = max(dist1 * 0.6, 0.05)
            limit2 = max(dist2 * 0.6, 0.05)
            t_len1 = min(raw_len1, limit1)
            t_len2 = min(raw_len2, limit2)
            
            n_src = nB if swapped else nA
            n_dst = nA if swapped else nB
            t_s1 = [n_src[k] * t_len1 for k in range(3)]
            t_s2 = [n_src[k] * t_len2 for k in range(3)]
            t_d1 = [n_dst[k] * t_len1 for k in range(3)]
            t_d2 = [n_dst[k] * t_len2 for k in range(3)]

            c1_p0, c1_p3 = p_s1, p_d1
            c1_p1 = [c1_p0[k] + t_s1[k] for k in range(3)]
            c1_p2 = [c1_p3[k] + t_d1[k] for k in range(3)]
            c2_p0, c2_p3 = p_s2, p_d2
            c2_p1 = [c2_p0[k] + t_s2[k] for k in range(3)]
            c2_p2 = [c2_p3[k] + t_d2[k] for k in range(3)]
            
            grid_points = []
            for d in range(divs + 2):
                t = float(d) / float(divs + 1)
                pt1 = self.bezier_point(c1_p0, c1_p1, c1_p2, c1_p3, t)
                pt2 = self.bezier_point(c2_p0, c2_p1, c2_p2, c2_p3, t)
                grid_points.append((pt1, pt2))
            
            for d in range(divs + 1):
                r1_p1, r1_p2 = grid_points[d]
                r2_p1, r2_p2 = grid_points[d+1]
                if not swapped: pts = [r1_p1, r1_p2, r2_p2, r2_p1]
                else: pts = [r1_p1, r2_p1, r2_p2, r1_p2]
                if self.dist_sq(pts[2], pts[3]) < 1e-6: pts = [pts[0], pts[1], pts[2]]
                elif self.dist_sq(pts[0], pts[1]) < 1e-6: pts = [pts[0], pts[2], pts[3]]
                f = cmds.polyCreateFacet(p=pts, tx=1, s=1)[0]
                preview_faces.append(f)

        if preview_faces:
            cmds.group(preview_faces, n=self.preview_grp)
            cmds.select(self.preview_grp)

    def apply_bridge(self):
        if not self.is_initialized or not cmds.objExists(self.preview_grp): return
        try:
            faces = cmds.listRelatives(self.preview_grp, c=True, f=True)
            if not cmds.objExists(self.source_obj): raise Exception(u"原物体丢失")
            
            final_obj = cmds.polyUnite([self.source_obj] + faces, ch=1, mergeUVSets=1, n="Stitched_Mesh")[0]
            cmds.polyMergeVertex(final_obj, d=0.01, ch=1)
            
            # --- 修复 2: 自动修正法线 ---
            # normalMode=2 (Conform) 自动对齐法线方向
            cmds.polyNormal(final_obj, normalMode=2, userNormalMode=0, ch=1)
            
            cmds.delete(final_obj, ch=True)
            if cmds.objExists(self.preview_grp): cmds.delete(self.preview_grp)
            cmds.select(final_obj)
            print(u"桥接完成 (法线已修复)")
            
        except Exception as e:
            cmds.warning(str(e))
        finally:
            self.cleanup_interactive()

    def cleanup_interactive(self):
        self.is_initialized = False
        
        # --- 修复 1: 健壮的状态重置 ---
        # 即使在 ToolCanvas 中，只要控件还在，就能重置
        # 检查控件是否存在，而不是检查窗口
        if cmds.control(self.btn_init, exists=True):
            cmds.button(self.btn_init, e=True, en=True, label=u"1. 初始化")
            cmds.button(self.btn_apply, e=True, en=False, bgc=(0.3, 0.3, 0.3))
            
            # 禁用输入框
            cmds.intFieldGrp(self.fl_offset, e=True, en=False, v1=0)
            cmds.intFieldGrp(self.fl_divs, e=True, en=False)
            cmds.floatFieldGrp(self.fl_mult, e=True, en=False)
            cmds.checkBox(self.chk_flip_a, e=True, en=False)
            cmds.checkBox(self.chk_flip_b, e=True, en=False)
            cmds.radioButtonGrp(self.rb_solver, e=True, en=False)
        
        if cmds.objExists(self.preview_grp): cmds.delete(self.preview_grp)

    def ui(self):
        # 紧凑布局
        cmds.columnLayout(adj=True, rs=8, co=['both', 5])
        
        # --- 按钮组 1 (固定大小) ---
        cmds.rowLayout(nc=1, adj=1) # 用 rowLayout 包裹来控制按钮宽度
        self.btn_init = cmds.button(label=u"1. 初始化", h=35, bgc=(0.3, 0.6, 0.8), 
                                  c=lambda x: self.init_interactive())
        cmds.setParent('..')
        
        cmds.frameLayout(label=u"参数控制", bgc=(0.25, 0.25, 0.25), collapsable=False)
        cmds.columnLayout(adj=True, rs=4)
        
        # 紧凑数值输入框 (Remove Sliders)
        # columnWidth 设置让标签占小部分，输入框占大部分
        cw = [(1, 60), (2, 50)]
        self.fl_offset = cmds.intFieldGrp(label=u"偏移:", value1=0, en=False, columnWidth=cw,
                                        cc=lambda *x: self.update_preview())
                                        
        self.fl_divs = cmds.intFieldGrp(label=u"分段:", value1=8, en=False, columnWidth=cw,
                                      cc=lambda *x: self.update_preview())
                                      
        self.fl_mult = cmds.floatFieldGrp(label=u"强度:", value1=0.9, pre=2, en=False, columnWidth=cw,
                                        cc=lambda *x: self.update_preview())
        
        # 选项
        cmds.rowLayout(nc=2, columnWidth2=[80, 80])
        self.chk_flip_a = cmds.checkBox(label=u"反转A", v=False, en=False, cc=lambda x: self.update_preview())
        self.chk_flip_b = cmds.checkBox(label=u"反转B", v=False, en=False, cc=lambda x: self.update_preview())
        cmds.setParent('..')
        
        cmds.text(label=u"引擎:", align='left', height=15)
        self.rb_solver = cmds.radioButtonGrp(labelArray2=[u'A.直线', u'B.几何'], 
                                           numberOfRadioButtons=2, select=2, en=False, columnWidth2=[60, 60],
                                           cc=lambda x: self.change_solver(int(x)))
        
        cmds.setParent('..'); cmds.setParent('..')
        
        # --- 按钮组 2 (固定大小) ---
        cmds.rowLayout(nc=1, adj=1)
        self.btn_apply = cmds.button(label=u"2. 完成 (Bake)", h=35, bgc=(0.3, 0.3, 0.3), en=False,
                                   c=lambda x: self.apply_bridge())
        cmds.setParent('..')
        
        cmds.rowLayout(nc=1, adj=1)
        cmds.button(label=u"重置 / 取消", h=25, bgc=(0.5, 0.3, 0.3), c=lambda x: self.cleanup_interactive())
        cmds.setParent('..')

_tool_compact = SmartStitchBridge_Compact()
def run_ui():
    win = _tool_compact.window
    if cmds.window(win, exists=True): cmds.deleteUI(win)
    cmds.window(win, title=_tool_compact.title, widthHeight=_tool_compact.size)
    _tool_compact.ui()
    # 绑定窗口关闭事件，防止残留
    cmds.scriptJob(uiDeleted=(win, _tool_compact.cleanup_interactive), runOnce=True)
    cmds.showWindow(win)
def run(): run_ui()

if __name__ == "__main__":
    run_ui()