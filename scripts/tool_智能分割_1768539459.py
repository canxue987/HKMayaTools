# -*- coding: utf-8 -*-
import maya.cmds as cmds
import maya.mel as mel
import math

class SymmetryMasterTool_Cmds:
    def __init__(self):
        self.window = "SymmetryMasterWin_Cmds"
        self.title = u"Symmetry Master Pro v7.0"
        self.size = (300, 500)
        
        # 数据存储
        self.custom_axis_data = None
        
        # UI 控件名称 (ID)
        self.ui_lbl_status = "sm_lbl_status"
        self.ui_chk_x = "sm_chk_x"
        self.ui_chk_y = "sm_chk_y"
        self.ui_chk_z = "sm_chk_z"
        self.ui_chk_keep = "sm_chk_keep"
        self.ui_chk_del = "sm_chk_del"

    # ================= UI 构建 =================
    def ui(self):
        # 主布局
        cmds.columnLayout(adjustableColumn=True, rowSpacing=10, columnOffset=['both', 10])
        
        # --- 1. 高级模式：自定义轴向 ---
        cmds.frameLayout(label=u"① 任意空间轴向 (Custom Axis)", collapsable=False, 
                         backgroundColor=(0.25, 0.25, 0.25), marginWidth=5, marginHeight=5)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=5)
        
        # 状态标签
        self.ui_lbl_status = cmds.text(label=u"当前状态: 世界坐标模式", align='center', height=25, backgroundColor=(0.18, 0.18, 0.18))
        
        cmds.rowLayout(numberOfColumns=2, adjustableColumn=1, columnWidth2=[180, 60], columnAttach2=['both', 'both'])
        cmds.button(label=u"拾取轴向点 (2点)", height=30, backgroundColor=(0.36, 0.25, 0.22), 
                    annotation=u"选择模型上的两个顶点 (P1, P2) 定义轴向",
                    command=lambda x: self.on_pick_axis())
        cmds.button(label=u"重置", height=30, backgroundColor=(0.3, 0.3, 0.3), 
                    command=lambda x: self.on_reset_axis())
        cmds.setParent('..') # end row
        cmds.setParent('..') # end column
        cmds.setParent('..') # end frame

        # --- 2. 轴向选择 ---
        cmds.frameLayout(label=u"② 方向 (Direction)", collapsable=False, marginWidth=5, marginHeight=5)
        cmds.rowLayout(numberOfColumns=3, columnWidth3=[80, 80, 80])
        self.ui_chk_x = cmds.checkBox(label="X", value=True)
        self.ui_chk_y = cmds.checkBox(label="Y", value=False)
        self.ui_chk_z = cmds.checkBox(label="Z", value=False)
        cmds.setParent('..')
        cmds.setParent('..')

        # --- 3. 核心功能 ---
        cmds.frameLayout(label=u"③ 操作 (Actions)", collapsable=False, marginWidth=5, marginHeight=5)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=6)
        
        self.ui_chk_keep = cmds.checkBox(label=u"保留原模型 (Keep Original)", value=False, 
                                       annotation=u"勾选后，操作将在副本上进行，原模型不动")
        
        cmds.separator(height=5, style='none')
        
        cmds.button(label=u"✂️ 切割分离 (Split)", height=35, backgroundColor=(0.32, 0.52, 0.65), 
                    command=lambda x: self.run_wrapper("SPLIT"))
        
        cmds.button(label=u"🧩 镜像合并 (Mirror)", height=35, backgroundColor=(0.18, 0.49, 0.19), 
                    command=lambda x: self.run_wrapper("MIRROR"))
        
        cmds.separator(height=5, style='none')
        
        self.ui_chk_del = cmds.checkBox(label=u"合并后自动删中线", value=True)
        
        cmds.setParent('..') # end column
        cmds.setParent('..') # end frame
        
        cmds.setParent('..') # end main column

    # ================= 逻辑处理 =================

    def on_pick_axis(self):
        sel = cmds.ls(sl=True, flatten=True)
        if len(sel) != 2 or ".vtx" not in sel[0]:
            cmds.warning(u"请务必选择模型上的【2个顶点】！")
            return
        p1 = cmds.xform(sel[0], q=True, ws=True, t=True)
        p2 = cmds.xform(sel[1], q=True, ws=True, t=True)
        obj_name = sel[0].split(".")[0]
        
        self.custom_axis_data = {"p1": p1, "p2": p2, "obj": obj_name}
        
        # 更新UI状态
        cmds.text(self.ui_lbl_status, edit=True, label=u"状态: 自定义轴已激活 (一次性)", backgroundColor=(0.6, 0.4, 0.0))
        cmds.select(obj_name)
        print(u"自定义轴已设定。")

    def on_reset_axis(self):
        self.custom_axis_data = None
        cmds.text(self.ui_lbl_status, edit=True, label=u"当前状态: 世界坐标模式", backgroundColor=(0.18, 0.18, 0.18))

    def get_axes(self):
        axes = []
        if cmds.checkBox(self.ui_chk_x, q=True, v=True): axes.append('x')
        if cmds.checkBox(self.ui_chk_y, q=True, v=True): axes.append('y')
        if cmds.checkBox(self.ui_chk_z, q=True, v=True): axes.append('z')
        return axes

    def handle_backup(self):
        if cmds.checkBox(self.ui_chk_keep, q=True, v=True):
            selection = cmds.ls(sl=True, objectsOnly=True)
            if not selection: return False
            duplicates = cmds.duplicate(selection, rr=True)
            cmds.select(duplicates)
            return True
        return False

    def run_wrapper(self, mode):
        # 1. 获取轴向
        axes = self.get_axes()
        if not axes:
            cmds.warning(u"请至少选择一个轴向 (X/Y/Z)")
            return

        # 2. 处理备份
        self.handle_backup()

        # 3. 智能调度
        if self.custom_axis_data:
            self._run_smart_axis(mode, axes)
        else:
            # 普通世界坐标模式
            self._run_normal(mode, axes)

    def _run_normal(self, mode, axes):
        selection = cmds.ls(sl=True, objectsOnly=True)
        if not selection: return
        try:
            for obj in selection:
                if mode == "SPLIT":
                    self.process_split(obj, axes)
                else:
                    self.process_mirror(obj, axes)
        except Exception as e:
            cmds.warning(str(e))

    def _run_smart_axis(self, mode, axes):
        obj_list = cmds.ls(sl=True, objectsOnly=True)
        if not obj_list: return
        obj = obj_list[0]
        
        p1 = self.custom_axis_data['p1']
        p2 = self.custom_axis_data['p2']
        
        # 1. 空间校正
        loc_guide = cmds.spaceLocator(n="temp_guide_loc")[0]
        loc_aim = cmds.spaceLocator(n="temp_aim_loc")[0]
        cmds.xform(loc_guide, t=p1, ws=True)
        cmds.xform(loc_aim, t=p2, ws=True)
        cmds.aimConstraint(loc_aim, loc_guide, aimVector=(1,0,0), upVector=(0,1,0), worldUpType="scene")
        
        rot = cmds.xform(loc_guide, q=True, ws=True, ro=True)
        trans = cmds.xform(loc_guide, q=True, ws=True, t=True)
        
        corrector = cmds.group(empty=True, n="corrector_grp")
        cmds.xform(corrector, t=trans, ws=True)
        cmds.xform(corrector, ro=rot, ws=True)
        
        cmds.parent(obj, corrector)
        cmds.xform(corrector, t=(0,0,0), ro=(0,0,0), ws=True) # 摆正
        
        cmds.parent(obj, w=True)
        cmds.makeIdentity(obj, apply=True, t=1, r=1, s=1, n=0, pn=1) # 冻结
        
        # 2. 调整 Pivot
        if mode == "SPLIT":
            cmds.xform(obj, centerPivots=True)
        elif mode == "MIRROR":
            cmds.xform(obj, piv=(0,0,0), ws=True) # 吸附到P1 (此时P1在原点)

        # 3. 执行
        if mode == "SPLIT":
            self.process_split(obj, axes)
        else:
            self.process_mirror(obj, axes)
            
        result_objs = cmds.ls(sl=True)
        
        # 4. 还原
        if result_objs:
            cmds.parent(result_objs, corrector)
            cmds.xform(corrector, t=trans, ws=True)
            cmds.xform(corrector, ro=rot, ws=True)
            cmds.parent(result_objs, w=True)
            cmds.makeIdentity(result_objs, apply=True, t=1, r=1, s=1, n=0, pn=1)
            
            if not cmds.checkBox(self.ui_chk_keep, q=True, v=True) or mode == "SPLIT":
                cmds.xform(result_objs, cp=True)
        
        cmds.delete([loc_guide, loc_aim, corrector])
        
        # 自动重置
        self.on_reset_axis()
        print(u"自定义轴向操作完成，已重置。")

    # ================= 核心算法 (Cmds 版) =================

    def process_split(self, obj, axes):
        # 如果不是自定义模式，强制居中一下 pivot
        if not self.custom_axis_data:
            cmds.xform(obj, centerPivots=True)
            
        target_pivot = cmds.xform(obj, q=True, ws=True, rp=True)
        cmds.makeIdentity(obj, apply=True, t=1, r=1, s=1, n=0, pn=1)
        cmds.delete(obj, ch=True)
        
        axis_settings = {
            'x': {'pos_rot': (0, 90, 0), 'neg_rot': (0, -90, 0)},
            'y': {'pos_rot': (90, 0, 0), 'neg_rot': (-90, 0, 0)},
            'z': {'pos_rot': (0, 0, 0),  'neg_rot': (180, 0, 0)}
        }
        current_objs = [obj]
        for axis in axes:
            next_step_objs = []
            settings = axis_settings[axis]
            for curr in current_objs:
                half_2 = cmds.duplicate(curr, rr=True)[0]
                half_1 = curr 
                cmds.polyCut(half_1, cutPlaneCenter=target_pivot, cutPlaneRotate=settings['pos_rot'], deleteFaces=True)
                cmds.polyCut(half_2, cutPlaneCenter=target_pivot, cutPlaneRotate=settings['neg_rot'], deleteFaces=True)
                cmds.delete(half_1, ch=True); cmds.delete(half_2, ch=True)
                if cmds.polyEvaluate(half_1, v=True) > 0: next_step_objs.append(half_1)
                else: cmds.delete(half_1)
                if cmds.polyEvaluate(half_2, v=True) > 0: next_step_objs.append(half_2)
                else: cmds.delete(half_2)
            current_objs = next_step_objs
        if current_objs: cmds.select(current_objs)

    def process_mirror(self, obj, axes):
        current_obj = obj
        for axis in axes:
            pivot = cmds.xform(current_obj, q=True, ws=True, rp=True)
            mirrored = cmds.duplicate(current_obj, rr=True)[0]
            scale_attr = [1, 1, 1]
            if axis == 'x': scale_attr[0] = -1
            elif axis == 'y': scale_attr[1] = -1
            elif axis == 'z': scale_attr[2] = -1
            
            grp = cmds.group(empty=True)
            cmds.move(pivot[0], pivot[1], pivot[2], grp)
            cmds.parent(mirrored, grp)
            cmds.setAttr(grp + ".scale", *scale_attr)
            cmds.parent(mirrored, w=True)
            cmds.delete(grp)
            
            cmds.makeIdentity(mirrored, apply=True, t=1, r=1, s=1, n=0, pn=1)
            cmds.polyNormal(mirrored, normalMode=0, userNormalMode=0, ch=False)
            united = cmds.polyUnite(current_obj, mirrored, ch=False, mergeUVSets=1)[0]
            cmds.delete(united, ch=True)
            cmds.polyMergeVertex(united, d=0.001, ch=False)
            cmds.polyNormal(united, normalMode=2, userNormalMode=0, ch=False)
            cmds.delete(united, ch=True)
            
            if cmds.checkBox(self.ui_chk_del, q=True, v=True):
                self.remove_center_loop(united, axis, pivot)
            current_obj = united
        
        if not self.custom_axis_data:
            cmds.xform(current_obj, centerPivots=True)
            
        cmds.select(current_obj)
        cmds.delete(current_obj, ch=True)

    def remove_center_loop(self, obj, axis, pivot_pos):
        threshold = 0.001
        axis_idx = {'x':0, 'y':1, 'z':2}[axis]
        center_val = pivot_pos[axis_idx]
        vtxs = cmds.ls(obj + ".vtx[:]", flatten=True)
        if not vtxs: return
        positions = cmds.xform(vtxs, q=True, ws=True, t=True)
        center_vtxs = []
        for i in range(0, len(positions), 3):
            if abs(positions[i + axis_idx] - center_val) < threshold:
                center_vtxs.append(vtxs[int(i/3)])
        if center_vtxs:
            cmds.select(center_vtxs)
            center_edges = cmds.polyListComponentConversion(center_vtxs, toEdge=True, internal=True)
            if center_edges: cmds.polyDelEdge(center_edges, cv=True)
        cmds.select(clear=True)

# ================= 启动入口 =================
# 全局实例，保持状态 (和 Smart Stitch Bridge 一样的做法)
_symmetry_tool_instance = SymmetryMasterTool_Cmds()

def run_ui():
    """
    符合工具箱规范的启动函数
    """
    win = _symmetry_tool_instance.window
    
    # 1. 如果窗口已存在，先删除 (防止重复)
    if cmds.window(win, exists=True):
        cmds.deleteUI(win)
        
    # 2. 创建窗口 (会被工具箱劫持)
    cmds.window(win, title=_symmetry_tool_instance.title, widthHeight=_symmetry_tool_instance.size)
    
    # 3. 构建 UI
    _symmetry_tool_instance.ui()
    
    # 4. 显示窗口 (工具箱会忽略这一步，因为父级已经劫持了)
    cmds.showWindow(win)

# 工具箱标准入口
def run():
    run_ui()

if __name__ == "__main__":
    run_ui()