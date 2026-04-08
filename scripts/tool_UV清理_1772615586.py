# -*- coding: utf-8 -*-
import maya.cmds as cmds
import maya.mel as mel

# 智能适配 Maya 2025+ (PySide6) 与老版本 Maya (PySide2)
try:
    from PySide6 import QtWidgets, QtCore, QtGui
except ImportError:
    from PySide2 import QtWidgets, QtCore, QtGui

class UVSetManager(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(UVSetManager, self).__init__(parent)
        self.setWindowTitle(u"UV通道管理器 (UV Set Manager) v3.2")
        self.resize(450, 620)
        
        self.current_mesh = None 
        self.job_num = None
        self.is_updating = False # 防止脚本切换选择时触发死循环
        
        self.setup_ui()
        self.create_script_job()
        self.refresh_uv_list()

    def setup_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)

        # ================= 1. 顶部状态与一键清理/映射 =================
        grp_quick = QtWidgets.QGroupBox(u"★ 核心工作流：清理与基础映射")
        grp_quick.setStyleSheet("QGroupBox { font-weight: bold; border: 1px solid #4CAF50; margin-top: 10px;} QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 3px 0 3px; color: #4CAF50; }")
        lay_quick = QtWidgets.QVBoxLayout(grp_quick)
        
        self.btn_one_click_clean = QtWidgets.QPushButton(u"1. 一键清理模型：仅保留当前UV并重命名为 map1")
        self.btn_one_click_clean.setStyleSheet("background-color: #2b5c3b; color: white; padding: 8px; font-weight: bold;")
        lay_quick.addWidget(self.btn_one_click_clean)
        
        # 新增：平面映射操作区
        lay_proj = QtWidgets.QHBoxLayout()
        self.combo_proj_axis = QtWidgets.QComboBox()
        self.combo_proj_axis.addItems([u"最佳平面 (Best)", u"Y 轴 (Top)", u"X 轴 (Side)", u"Z 轴 (Front)", u"摄像机 (Camera)"])
        self.btn_planar_map = QtWidgets.QPushButton(u"2. 对选中模型进行平面映射")
        self.btn_planar_map.setStyleSheet("background-color: #3b5a75; color: white; padding: 5px;")
        
        lay_proj.addWidget(self.combo_proj_axis)
        lay_proj.addWidget(self.btn_planar_map)
        lay_quick.addLayout(lay_proj)
        
        main_layout.addWidget(grp_quick)

        # ================= 2. 当前选中模型状态 =================
        self.lbl_status = QtWidgets.QLabel(u"当前未选择多边形模型")
        self.lbl_status.setStyleSheet("color: #aaa;")
        main_layout.addWidget(self.lbl_status)

        # ================= 3. 列表管理区 =================
        grp_list = QtWidgets.QGroupBox(u"当前模型 UV 通道列表")
        lay_list = QtWidgets.QHBoxLayout(grp_list)
        
        self.list_uvs = QtWidgets.QListWidget()
        lay_list.addWidget(self.list_uvs)
        
        lay_list_btn = QtWidgets.QVBoxLayout()
        self.btn_set_current = QtWidgets.QPushButton(u"设为当前激活")
        self.btn_add_uv = QtWidgets.QPushButton(u"+ 新增空白通道")
        self.btn_rename_uv = QtWidgets.QPushButton(u"重命名选中通道")
        self.btn_del_uv = QtWidgets.QPushButton(u"- 删除选中通道")
        self.btn_del_uv.setStyleSheet("background-color: #7a3b3b;")
        
        lay_list_btn.addWidget(self.btn_set_current)
        lay_list_btn.addWidget(self.btn_add_uv)
        lay_list_btn.addWidget(self.btn_rename_uv)
        lay_list_btn.addWidget(self.btn_del_uv)
        lay_list_btn.addStretch()
        
        lay_list.addLayout(lay_list_btn)
        main_layout.addWidget(grp_list)

        # ================= 4. 通道内复制 =================
        grp_copy = QtWidgets.QGroupBox(u"通道内 UV 复制")
        lay_copy = QtWidgets.QHBoxLayout(grp_copy)
        
        lay_copy.addWidget(QtWidgets.QLabel(u"将选中通道复制到:"))
        self.le_copy_target = QtWidgets.QLineEdit("map2")
        self.btn_copy_uv = QtWidgets.QPushButton(u"执行复制")
        lay_copy.addWidget(self.le_copy_target)
        lay_copy.addWidget(self.btn_copy_uv)
        main_layout.addWidget(grp_copy)

        # ================= 5. 模型间传递 =================
        grp_transfer = QtWidgets.QGroupBox(u"模型间 UV 传递 (先选源模型，再选目标模型)")
        lay_transfer = QtWidgets.QVBoxLayout(grp_transfer)
        
        lay_options = QtWidgets.QHBoxLayout()
        self.radio_topo = QtWidgets.QRadioButton(u"基于拓扑 (点线面一致)")
        self.radio_topo.setChecked(True)
        self.radio_space = QtWidgets.QRadioButton(u"基于空间 (模型需重合)")
        lay_options.addWidget(self.radio_topo)
        lay_options.addWidget(self.radio_space)
        lay_transfer.addLayout(lay_options)
        
        self.btn_transfer_uv = QtWidgets.QPushButton(u"将源模型当前 UV 传递给目标模型")
        lay_transfer.addWidget(self.btn_transfer_uv)
        main_layout.addWidget(grp_transfer)

        # ================= 信号连接 =================
        self.btn_one_click_clean.clicked.connect(self.one_click_cleanup)
        self.btn_planar_map.clicked.connect(self.apply_planar_mapping) # 绑定映射功能
        self.btn_set_current.clicked.connect(self.set_current_uv_set)
        self.btn_add_uv.clicked.connect(self.add_uv_set)
        self.btn_rename_uv.clicked.connect(self.rename_uv_set)
        self.btn_del_uv.clicked.connect(self.delete_uv_set)
        self.btn_copy_uv.clicked.connect(self.copy_uv_set)
        self.btn_transfer_uv.clicked.connect(self.transfer_uvs)

    # ================= ScriptJob 自动刷新 =================
    def create_script_job(self):
        self.job_num = cmds.scriptJob(event=["SelectionChanged", self.on_selection_changed])

    def on_selection_changed(self):
        try:
            self.list_uvs.count()
        except RuntimeError:
            if self.job_num and cmds.scriptJob(exists=self.job_num):
                cmds.evalDeferred(lambda: cmds.scriptJob(kill=self.job_num))
            return

        if not self.is_updating:
            self.refresh_uv_list()

    def closeEvent(self, event):
        if self.job_num and cmds.scriptJob(exists=self.job_num):
            cmds.scriptJob(kill=self.job_num)
        super(UVSetManager, self).closeEvent(event)

    # ================= 核心安全提取 =================
    def get_first_selected_mesh(self):
        sel = cmds.ls(selection=True, dag=True, type='mesh', noIntermediate=True, long=True)
        if sel:
            trans = cmds.listRelatives(sel[0], parent=True, fullPath=True)
            return trans[0] if trans else sel[0]
        return None

    def refresh_uv_list(self):
        if self.is_updating: return
        self.list_uvs.clear()
        self.current_mesh = self.get_first_selected_mesh()
        
        if not self.current_mesh:
            self.lbl_status.setText(u"当前未选择多边形模型")
            return
            
        display_name = self.current_mesh.split('|')[-1]
        self.lbl_status.setText(u"当前编辑模型: <b>{}</b>".format(display_name))
        
        self.is_updating = True
        
        cmds.undoInfo(stateWithoutFlush=False)
        original_sel = cmds.ls(selection=True)
        try:
            cmds.select(self.current_mesh, replace=True)
            uv_sets = cmds.polyUVSet(query=True, allUVSets=True)
            current_set = cmds.polyUVSet(query=True, currentUVSet=True)
            current_set_name = current_set[0] if current_set else ""
        except Exception as e:
            print(f"Error reading UVs: {e}")
            uv_sets = []
            current_set_name = ""
        finally:
            if original_sel: cmds.select(original_sel, replace=True)
            else: cmds.select(clear=True)
            cmds.undoInfo(stateWithoutFlush=True)
            self.is_updating = False
            
        if not uv_sets: return
        
        for uv in uv_sets:
            item = QtWidgets.QListWidgetItem()
            if uv == current_set_name:
                item.setText(f"{uv}  [当前激活]")
                item.setForeground(QtGui.QColor("#4CAF50"))
                item.setData(QtCore.Qt.UserRole, uv)
            else:
                item.setText(uv)
                item.setData(QtCore.Qt.UserRole, uv)
            self.list_uvs.addItem(item)

    def get_selected_uv_name(self):
        sel_items = self.list_uvs.selectedItems()
        if not sel_items:
            cmds.warning(u"请在列表中选择一个UV通道！")
            return None
        return sel_items[0].data(QtCore.Qt.UserRole)

    # ================= 新增：基础平面映射功能 =================
    def apply_planar_mapping(self):
        sel_objs = cmds.ls(selection=True, dag=True, type='mesh', noIntermediate=True, long=True)
        if not sel_objs:
            return cmds.warning(u"请先在场景中选中要映射的模型！")

        # 映射轴向代号字典
        axis_map = {
            0: 'b', # 最佳平面 Best Plane
            1: 'y', # Y轴
            2: 'x', # X轴
            3: 'z', # Z轴
            4: 'c'  # 摄像机 Camera
        }
        axis_code = axis_map.get(self.combo_proj_axis.currentIndex(), 'b')

        self.is_updating = True
        cmds.undoInfo(openChunk=True) # 开启撤销包裹
        original_sel = cmds.ls(selection=True)
        success_count = 0

        try:
            for mesh in sel_objs:
                trans = cmds.listRelatives(mesh, parent=True, fullPath=True)[0]
                cmds.select(trans, replace=True)
                
                try:
                    # 执行平面映射
                    cmds.polyPlanarProjection(trans, mapDirection=axis_code)
                    # 映射完毕后自动清除历史，防止场景里产生大量的 polyPlanarProj 垃圾节点
                    cmds.delete(trans, constructionHistory=True)
                    success_count += 1
                except Exception as e:
                    print(f"为 {trans} 映射UV失败: {e}")
        finally:
            if original_sel: cmds.select(original_sel, replace=True)
            else: cmds.select(clear=True)
            cmds.undoInfo(closeChunk=True)
            self.is_updating = False
            
        self.refresh_uv_list()
        cmds.inViewMessage(amg=u"平面映射完成！成功处理 {} 个模型".format(success_count), pos='midCenter', fade=True)

    # ================= 基础管理 =================
    def set_current_uv_set(self):
        uv_name = self.get_selected_uv_name()
        if not uv_name or not self.current_mesh: return
        self._safe_execute(lambda: cmds.polyUVSet(currentUVSet=True, uvSet=uv_name))

    def add_uv_set(self):
        if not self.current_mesh: return cmds.warning(u"请先选择模型！")
        text, ok = QtWidgets.QInputDialog.getText(self, u"新增UV通道", u"输入新通道名称:", text="new_uv_set")
        if ok and text:
            self._safe_execute(lambda: cmds.polyUVSet(create=True, uvSet=text))

    def rename_uv_set(self):
        uv_name = self.get_selected_uv_name()
        if not uv_name or not self.current_mesh: return
        text, ok = QtWidgets.QInputDialog.getText(self, u"重命名UV通道", u"新名称:", text=uv_name)
        if ok and text and text != uv_name:
            self._safe_execute(lambda: cmds.polyUVSet(rename=True, uvSet=uv_name, newUVSet=text))

    def delete_uv_set(self):
        uv_name = self.get_selected_uv_name()
        if not uv_name or not self.current_mesh: return
        
        self.is_updating = True
        cmds.undoInfo(openChunk=True)
        original_sel = cmds.ls(selection=True)
        try:
            cmds.select(self.current_mesh, replace=True)
            all_sets = cmds.polyUVSet(query=True, allUVSets=True)
            if len(all_sets) <= 1:
                return cmds.warning(u"模型必须至少保留一个UV通道，无法删除！")
            if uv_name == all_sets[0]:
                return cmds.warning(u"Maya 不允许直接删除第一个（默认）UV通道。请将其他通道设为激活后清理。")
            cmds.polyUVSet(delete=True, uvSet=uv_name)
        finally:
            if original_sel: cmds.select(original_sel, replace=True)
            else: cmds.select(clear=True)
            cmds.undoInfo(closeChunk=True)
            self.is_updating = False
            self.refresh_uv_list()

    def copy_uv_set(self):
        src_uv = self.get_selected_uv_name()
        dst_uv = self.le_copy_target.text().strip()
        if not src_uv or not self.current_mesh or not dst_uv: return
        self._safe_execute(lambda: cmds.polyCopyUV(uvSetNameInput=src_uv, uvSetName=dst_uv))

    def _safe_execute(self, func):
        """通用安全执行器：打包撤销块，防止撤销碎片化"""
        self.is_updating = True
        cmds.undoInfo(openChunk=True) 
        original_sel = cmds.ls(selection=True)
        try:
            cmds.select(self.current_mesh, replace=True)
            func()
        except Exception as e:
            cmds.warning(u"操作失败: {}".format(e))
        finally:
            if original_sel: cmds.select(original_sel, replace=True)
            else: cmds.select(clear=True)
            cmds.undoInfo(closeChunk=True) 
            self.is_updating = False
            self.refresh_uv_list()

    # ================= 一键清理 =================
    def one_click_cleanup(self):
        sel_objs = cmds.ls(selection=True, dag=True, type='mesh', noIntermediate=True, long=True)
        if not sel_objs:
            return cmds.warning(u"请先在场景中选中要清理的模型！")
            
        self.is_updating = True
        cmds.undoInfo(openChunk=True) 
        original_sel = cmds.ls(selection=True)
        cleaned_count = 0
        
        try:
            for mesh in sel_objs:
                trans = cmds.listRelatives(mesh, parent=True, fullPath=True)[0]
                cmds.select(trans, replace=True)
                
                uv_sets = cmds.polyUVSet(query=True, allUVSets=True)
                if not uv_sets or len(uv_sets) <= 0: continue
                
                current_set_res = cmds.polyUVSet(query=True, currentUVSet=True)
                if not current_set_res: continue
                
                current_set = current_set_res[0]
                default_set = uv_sets[0]
                
                if current_set != default_set:
                    cmds.polyCopyUV(uvSetNameInput=current_set, uvSetName=default_set)
                    cmds.polyUVSet(currentUVSet=True, uvSet=default_set)
                    keep_set = default_set
                else:
                    keep_set = current_set
                
                for uv in uv_sets:
                    if uv != keep_set:
                        try: cmds.polyUVSet(delete=True, uvSet=uv)
                        except: pass
                
                if keep_set != "map1":
                    try: cmds.polyUVSet(rename=True, uvSet=keep_set, newUVSet="map1")
                    except Exception as e: print(f"重命名 {trans} 失败: {e}")
                        
                cleaned_count += 1
        finally:
            if original_sel: cmds.select(original_sel, replace=True)
            else: cmds.select(clear=True)
            cmds.undoInfo(closeChunk=True) 
            self.is_updating = False
            
        self.refresh_uv_list()
        cmds.inViewMessage(amg=u"一键清理完成！成功处理 {} 个模型".format(cleaned_count), pos='midCenter', fade=True)

    # ================= 模型间传递 =================
    def transfer_uvs(self):
        sel = cmds.ls(selection=True, long=True)
        if len(sel) < 2:
            return cmds.warning(u"请至少选择两个模型！（第一个选的是源模型，后面选的是接收模型）")
            
        source_obj = sel[0]
        target_objs = sel[1:]
        sample_space = 4 if self.radio_topo.isChecked() else 5
        
        self.is_updating = True
        cmds.undoInfo(openChunk=True)
        
        success_count = 0
        try:
            for target in target_objs:
                try:
                    cmds.transferAttributes(source_obj, target, 
                                          transferPositions=0, transferNormals=0, 
                                          transferUVs=1, transferColors=0, 
                                          sampleSpace=sample_space)
                    cmds.delete(target, constructionHistory=True)
                    success_count += 1
                except Exception as e:
                    print(f"向 {target} 传递UV失败: {e}")
        finally:
            cmds.undoInfo(closeChunk=True)
            self.is_updating = False
                
        cmds.inViewMessage(amg=u"UV传递完成！成功作用于 {} 个模型".format(success_count), pos='midCenter', fade=True)
        self.refresh_uv_list()

def run():
    global uv_manager_window_v5
    try: uv_manager_window_v5.close()
    except: pass
    uv_manager_window_v5 = UVSetManager()
    uv_manager_window_v5.show()

if __name__ == "__main__":
    run()