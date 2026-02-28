# -*- coding: utf-8 -*-
import maya.cmds as cmds
import traceback

class AxisAlignerTool(object):
    def __init__(self):
        self.window_name = "HK_AxisAligner_UI"
        self.grp_name = "HK_Aligner_Guide_Grp"
        self.loc_base = "HK_Aligner_Base"
        self.loc_top = "HK_Aligner_Top"
        self.loc_front = "HK_Aligner_Front"
        self.temp_grp_name = "HK_Temp_Align_Group"

    def show(self):
        """显示UI"""
        if cmds.window(self.window_name, exists=True):
            cmds.deleteUI(self.window_name)
            
        self.win = cmds.window(self.window_name, title=u"万能摆正 Pro (Toolbox版)", widthHeight=(260, 260), sizeable=False)
        
        main_layout = cmds.columnLayout(adjustableColumn=True, rowSpacing=8)
        cmds.frameLayout(label=u"操作指南 (三点定位)", borderStyle="etchedIn", marginWidth=10, marginHeight=10, parent=main_layout)
        cmds.text(label=u"1. 黄点(Base) -> 吸附到底部中心\n2. 红点(Top)  -> 吸附到顶部 (定Y轴)\n3. 蓝点(Front)-> 吸附到正前方 (定Z轴)", 
                  align="left", font="smallObliqueLabelFont")
        
        cmds.separator(style="none", height=5, parent=main_layout)
        
        cmds.button(label=u"❶ 创建辅助定位点 (三点)", height=35, backgroundColor=(0.3, 0.5, 0.6), 
                    command=self.create_locators, parent=main_layout)
        
        cmds.separator(style="in", height=10, parent=main_layout)
        
        cmds.button(label=u"❷ 执行完美摆正 (Y轴向上+Z轴向前)", height=45, backgroundColor=(0.4, 0.7, 0.4), 
                    command=self.execute_align, parent=main_layout)
        
        cmds.rowLayout(numberOfColumns=2, columnWidth2=(130, 120), parent=main_layout)
        cmds.button(label=u"仅摆正垂直(Y)", height=30, width=128, backgroundColor=(0.4, 0.4, 0.4), 
                    command=lambda x: self.execute_align(ignore_front=True))
        cmds.button(label=u"清除辅助点", height=30, width=120, backgroundColor=(0.5, 0.3, 0.3), 
                    command=self.cleanup)

        cmds.showWindow(self.win)

    def create_locators(self, *args):
        self.cleanup() 
        cmds.group(em=True, name=self.grp_name)
        
        # Base (黄)
        base = cmds.spaceLocator(name=self.loc_base)[0]
        self._set_color(base, 17) 
        cmds.setAttr(base + "Shape.localScale", 3, 3, 3)
        cmds.parent(base, self.grp_name)
        cmds.move(0, 0, 0, base)
        
        # Top (红)
        top = cmds.spaceLocator(name=self.loc_top)[0]
        self._set_color(top, 13)
        cmds.setAttr(top + "Shape.localScale", 2, 2, 2)
        cmds.parent(top, self.grp_name)
        cmds.move(0, 10, 0, top)
        
        # Front (蓝)
        front = cmds.spaceLocator(name=self.loc_front)[0]
        self._set_color(front, 6)
        cmds.setAttr(front + "Shape.localScale", 2, 2, 2)
        cmds.parent(front, self.grp_name)
        cmds.move(0, 0, 10, front)
        
        self._create_annotation(base, top, u"Y(上)")
        self._create_annotation(base, front, u"Z(前)")
        
        cmds.select(base)
        cmds.inViewMessage(amg=u"<hl>三点模式</hl>: 黄(底)、红(上)、蓝(前)", pos='topCenter', fade=True)

    def _set_color(self, node, color_index):
        cmds.setAttr(node + ".overrideEnabled", 1)
        cmds.setAttr(node + ".overrideColor", color_index)

    def _create_annotation(self, start_obj, end_obj, label):
        anno = cmds.annotate(start_obj, tx=label, point=(0,0,0))
        anno_trans = cmds.listRelatives(anno, parent=True)[0]
        cmds.parent(anno_trans, end_obj)
        cmds.setAttr(anno_trans + ".template", 1) 

    def execute_align(self, ignore_front=False, *args):
        # 0. 基础环境检查
        if not cmds.objExists(self.loc_base) or not cmds.objExists(self.loc_top):
            cmds.warning(u"找不到基础辅助点(Base/Top)，请先创建！")
            return
            
        selection = cmds.ls(sl=True, long=True, type="transform")
        if not selection:
            cmds.warning(u"请选择需要摆正的物体！")
            return
        
        # 过滤掉辅助点自己
        safe_selection = [obj for obj in selection if self.grp_name not in obj]
        if not safe_selection:
            cmds.warning(u"不能选择辅助点自己进行摆正！")
            return

        use_front = False
        if not ignore_front and cmds.objExists(self.loc_front):
            use_front = True
            
        # 清理残留
        if cmds.objExists(self.temp_grp_name):
            try: cmds.delete(self.temp_grp_name)
            except: pass
        wildcards = cmds.ls("HK_Temp_Align_Group*", type="transform")
        if wildcards:
            try: cmds.delete(wildcards)
            except: pass

        cmds.undoInfo(openChunk=True)
        align_grp = None
        
        try:
            # 1. 记录原始父级信息
            obj_parents = {}
            for obj in safe_selection:
                parents = cmds.listRelatives(obj, parent=True, fullPath=True)
                obj_parents[obj] = parents[0] if parents else None

            # 2. 创建临时组并定位
            pos_base = cmds.xform(self.loc_base, q=True, ws=True, t=True)
            align_grp = cmds.group(em=True, name=self.temp_grp_name)
            cmds.xform(align_grp, ws=True, t=pos_base)
            
            # 3. 约束对齐
            constraints = []
            if use_front:
                const = cmds.aimConstraint(self.loc_top, align_grp, 
                                           aimVector=(0, 1, 0), upVector=(0, 0, 1), 
                                           worldUpType="object", worldUpObject=self.loc_front)
            else:
                const = cmds.aimConstraint(self.loc_top, align_grp, 
                                           aimVector=(0, 1, 0), upVector=(0, 0, 1), 
                                           worldUpType="scene")
            
            if const: constraints.extend(const)
            if constraints: cmds.delete(constraints)
            
            # 4. 进组
            moved_objs = cmds.parent(safe_selection, align_grp)
            
            # 5. 暴力归零
            cmds.setAttr(align_grp + ".r", 0, 0, 0)
            
            # 6. 还原列表准备
            restore_list = list(zip(safe_selection, moved_objs))
            restore_list.sort(key=lambda x: x[0].count("|"))

            # 7. 执行还原
            for orig_obj, curr_obj in restore_list:
                original_parent = obj_parents.get(orig_obj)
                
                if not cmds.objExists(curr_obj):
                    continue

                if original_parent and cmds.objExists(original_parent):
                    try: 
                        cmds.parent(curr_obj, original_parent)
                    except: 
                        cmds.parent(curr_obj, world=True)
                else:
                    cmds.parent(curr_obj, world=True)
            
            mode_str = u"垂直+水平" if use_front else u"仅垂直"
            cmds.inViewMessage(amg=u"<hl>矫正成功 ({})</hl>".format(mode_str), pos='midCenter', fade=True)
            
        except Exception as e:
            cmds.warning(u"摆正出错: {}".format(e))
            print(traceback.format_exc())
        finally:
            if align_grp and cmds.objExists(align_grp):
                cmds.delete(align_grp)
            cmds.undoInfo(closeChunk=True)

    def cleanup(self, *args):
        if cmds.objExists(self.grp_name):
            cmds.delete(self.grp_name)
        if cmds.objExists(self.temp_grp_name):
            try: cmds.delete(self.temp_grp_name)
            except: pass

# ==========================================
# 【关键修改】入口函数名改为 run() 
# 这样工具箱发布后才能正确识别
# ==========================================
def run(): 
    tool = AxisAlignerTool()
    tool.show()