# -*- coding: utf-8 -*-
import maya.cmds as cmds
import maya.mel as mel
import os

# 智能适配 Maya 2025+ (PySide6) 与老版本 Maya (PySide2)
try:
    from PySide6 import QtWidgets, QtCore, QtGui
except ImportError:
    from PySide2 import QtWidgets, QtCore, QtGui

class UltimateMaterialManager(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(UltimateMaterialManager, self).__init__(parent)
        self.setWindowTitle(u"材质管理器 (全能分栏版) v4")
        self.resize(850, 600)
        self.tabs_dict = {} 
        self.is_updating = False 
        self.setup_ui()
        self.refresh_material_list()

    def setup_ui(self):
        main_layout = QtWidgets.QHBoxLayout(self)

        # ================= 左侧：高级多列列表与分栏管理 =================
        left_layout = QtWidgets.QVBoxLayout()
        
        self.tab_widget = QtWidgets.QTabWidget()
        left_layout.addWidget(self.tab_widget)

        # 栏目管理按钮
        tab_ctrl_layout = QtWidgets.QHBoxLayout()
        self.btn_add_tab = QtWidgets.QPushButton(u"+ 新建组")
        self.btn_rename_tab = QtWidgets.QPushButton(u"重命名组")
        self.btn_del_tab = QtWidgets.QPushButton(u"删除组(保留材质)")
        tab_ctrl_layout.addWidget(self.btn_add_tab)
        tab_ctrl_layout.addWidget(self.btn_rename_tab)
        tab_ctrl_layout.addWidget(self.btn_del_tab)
        left_layout.addLayout(tab_ctrl_layout)

        main_layout.addLayout(left_layout, stretch=5)

        # ================= 右侧：集中操作面板 =================
        right_layout = QtWidgets.QVBoxLayout()
        
        # 1. 基础选择与赋予
        grp_basic = QtWidgets.QGroupBox(u"创建、选择与赋予")
        lay_basic = QtWidgets.QVBoxLayout(grp_basic)
        
        self.btn_new_lambert = QtWidgets.QPushButton(u"★ 为选中模型创建新 Lambert")
        self.btn_new_lambert.setStyleSheet("background-color: #3b5a75; color: white;")
        self.btn_select_from_model = QtWidgets.QPushButton(u"1. 从当前模型反选材质")
        self.btn_select_from_model.setStyleSheet("background-color: #2b5c5c; color: white;")
        self.btn_select_model = QtWidgets.QPushButton(u"2. 选择使用该材质的模型")
        self.btn_assign_mat = QtWidgets.QPushButton(u"3. 将选中材质赋予给模型")
        
        lay_basic.addWidget(self.btn_new_lambert)
        lay_basic.addWidget(self.btn_select_from_model)
        lay_basic.addWidget(self.btn_select_model)
        lay_basic.addWidget(self.btn_assign_mat)
        right_layout.addWidget(grp_basic)

        # 2. 命名与管理
        grp_rename = QtWidgets.QGroupBox(u"快速命名 (列表内双击可手动改名)")
        lay_rename = QtWidgets.QVBoxLayout(grp_rename)
        
        lay_suffix = QtWidgets.QHBoxLayout()
        lay_suffix.addWidget(QtWidgets.QLabel(u"后缀:"))
        self.le_suffix = QtWidgets.QLineEdit("_MAT")
        lay_suffix.addWidget(self.le_suffix)
        lay_rename.addLayout(lay_suffix)
        
        self.btn_add_suffix = QtWidgets.QPushButton(u"为选中材质添加后缀")
        self.btn_rename_by_model = QtWidgets.QPushButton(u"一键改为：模型名+后缀")
        lay_rename.addWidget(self.btn_add_suffix)
        lay_rename.addWidget(self.btn_rename_by_model)
        right_layout.addWidget(grp_rename)

        # 3. 整理与合并
        grp_org = QtWidgets.QGroupBox(u"整理、分组与合并")
        lay_org = QtWidgets.QVBoxLayout(grp_org)
        self.btn_clean_unused = QtWidgets.QPushButton(u"清理场景未使用的材质")
        self.btn_merge = QtWidgets.QPushButton(u"智能合并相同参数的材质")
        
        lay_move = QtWidgets.QHBoxLayout()
        self.combo_target_tab = QtWidgets.QComboBox()
        self.btn_move_to_tab = QtWidgets.QPushButton(u"移入该组 ->")
        lay_move.addWidget(self.combo_target_tab)
        lay_move.addWidget(self.btn_move_to_tab)
        
        lay_org.addWidget(self.btn_clean_unused)
        lay_org.addWidget(self.btn_merge)
        lay_org.addLayout(lay_move)
        right_layout.addWidget(grp_org)

        # 4. 属性调整
        grp_prop = QtWidgets.QGroupBox(u"基础属性调节")
        lay_prop = QtWidgets.QHBoxLayout(grp_prop)
        self.color_btn = QtWidgets.QPushButton(u"漫反射/颜色")
        self.color_btn.setStyleSheet("background-color: rgb(128, 128, 128);")
        self.trans_btn = QtWidgets.QPushButton(u"透明度")
        lay_prop.addWidget(self.color_btn)
        lay_prop.addWidget(self.trans_btn)
        right_layout.addWidget(grp_prop)

        right_layout.addStretch()
        main_layout.addLayout(right_layout, stretch=3)

        # ================= 信号连接 =================
        self.btn_add_tab.clicked.connect(self.add_new_tab)
        self.btn_rename_tab.clicked.connect(self.rename_current_tab)
        self.btn_del_tab.clicked.connect(self.delete_current_tab)
        self.btn_move_to_tab.clicked.connect(self.move_materials_to_tab)
        self.tab_widget.currentChanged.connect(self.update_move_combo)

        self.btn_new_lambert.clicked.connect(self.create_and_assign_lambert)
        self.btn_select_from_model.clicked.connect(self.select_material_from_model)
        self.btn_select_model.clicked.connect(self.select_models_by_material)
        self.btn_assign_mat.clicked.connect(self.assign_material_to_selected)
        self.btn_clean_unused.clicked.connect(self.clean_unused_materials)
        self.btn_merge.clicked.connect(self.deep_merge_materials)
        
        self.btn_add_suffix.clicked.connect(self.add_suffix)
        self.btn_rename_by_model.clicked.connect(self.rename_by_model)

        self.color_btn.clicked.connect(lambda: self.change_mat_attribute("color"))
        self.trans_btn.clicked.connect(lambda: self.change_mat_attribute("transparency"))

    # ================= 核心安全提取 =================
    def _get_transform_from_member(self, member):
        node_name = member.split('.')[0] 
        if cmds.objExists(node_name):
            if cmds.objectType(node_name, isAType='transform'):
                return node_name
            elif cmds.objectType(node_name, isAType='shape'):
                trans = cmds.listRelatives(node_name, parent=True, fullPath=False)
                if trans:
                    return trans[0]
        return None

    # ================= 核心：多列列表渲染与数据处理 =================
    def refresh_material_list(self):
        self.is_updating = True
        current_tab_name = self.tab_widget.tabText(self.tab_widget.currentIndex()) if self.tab_widget.count() > 0 else u"未分组"
        self.tab_widget.clear()
        self.tabs_dict.clear()
        
        materials = cmds.ls(mat=True)
        default_mats = ['lambert1', 'particleCloud1', 'shaderGlow1']
        group_data = {u"未分组": []}
        
        for mat in materials:
            if mat in default_mats: continue
            grp = self.get_mat_group(mat)
            if grp not in group_data: group_data[grp] = []
            group_data[grp].append(mat)
            
        for grp_name, mats in group_data.items():
            if not mats and grp_name != u"未分组": continue 
                
            tree_widget = QtWidgets.QTreeWidget()
            tree_widget.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
            tree_widget.setHeaderLabels([u"材质名称 (双击修改)", u"关联模型", u"贴图操作 (点击指定/替换)"])
            tree_widget.setColumnWidth(0, 160)
            tree_widget.setColumnWidth(1, 150)
            
            for mat in mats:
                item = QtWidgets.QTreeWidgetItem(tree_widget)
                item.setText(0, mat)
                item.setFlags(item.flags() | QtCore.Qt.ItemIsEditable) 
                item.setData(0, QtCore.Qt.UserRole, mat) 
                
                # 抓取并显示关联模型
                model_names = self._get_models_from_mat(mat)
                item.setText(1, ", ".join(model_names) if model_names else "-")
                
                # 抓取贴图并根据情况创建不同按钮
                tex_node = self._get_texture_from_mat(mat)
                if tex_node:
                    tex_path = cmds.getAttr(tex_node + ".fileTextureName")
                    tex_name = os.path.basename(tex_path) if tex_path else "未指定路径"
                    btn_tex = QtWidgets.QPushButton(f"🖼️ {tex_name}")
                    btn_tex.setStyleSheet("text-align: left; padding: 2px 5px;")
                    btn_tex.setToolTip(tex_path)
                    # 传入贴图节点进行替换
                    btn_tex.clicked.connect(lambda checked=False, m=mat, tn=tex_node: self.assign_or_replace_texture(m, tn))
                    tree_widget.setItemWidget(item, 2, btn_tex)
                else:
                    btn_tex = QtWidgets.QPushButton(u"➕ 点击指定贴图")
                    btn_tex.setStyleSheet("text-align: left; padding: 2px 5px; color: #888; border: 1px dashed #555;")
                    # 不传贴图节点，代表需要新建
                    btn_tex.clicked.connect(lambda checked=False, m=mat: self.assign_or_replace_texture(m, None))
                    tree_widget.setItemWidget(item, 2, btn_tex)
                
            tree_widget.itemSelectionChanged.connect(self.on_material_selected)
            tree_widget.itemChanged.connect(self.on_item_renamed) 
            
            self.tabs_dict[grp_name] = tree_widget
            self.tab_widget.addTab(tree_widget, grp_name)
            
        self.update_move_combo()
        for i in range(self.tab_widget.count()):
            if self.tab_widget.tabText(i) == current_tab_name:
                self.tab_widget.setCurrentIndex(i)
                break
        self.is_updating = False 

    def on_item_renamed(self, item, column):
        if self.is_updating or column != 0: return
        old_name = item.data(0, QtCore.Qt.UserRole)
        new_name = item.text(0).strip()
        
        if old_name and new_name and old_name != new_name:
            try:
                actual_new_name = cmds.rename(old_name, new_name)
                item.setData(0, QtCore.Qt.UserRole, actual_new_name) 
                item.setText(0, actual_new_name)
            except Exception as e:
                cmds.warning(u"重命名失败: {}".format(e))
                item.setText(0, old_name) 

    # ================= 核心：贴图指定与替换逻辑 =================
    def assign_or_replace_texture(self, mat, file_node):
        """需求更新：支持已有贴图替换，以及无贴图时新建连线"""
        
        # 1. 如果已有 file 节点，走替换逻辑
        if file_node:
            current_path = cmds.getAttr(file_node + ".fileTextureName")
            start_dir = os.path.dirname(current_path) if current_path and os.path.exists(current_path) else None
            new_path = cmds.fileDialog2(fileMode=1, caption=u"选择新贴图替换", startingDirectory=start_dir)
            if new_path:
                cmds.setAttr(file_node + ".fileTextureName", new_path[0], type="string")
                cmds.inViewMessage(amg=u"贴图已替换！", pos='midCenter', fade=True)
                self.refresh_material_list() 
        
        # 2. 如果没有 file 节点，走新建连线逻辑
        else:
            new_path = cmds.fileDialog2(fileMode=1, caption=u"为材质球指定新贴图")
            if new_path:
                # 确定要连线的属性 (不同材质球的漫反射通道名字不同)
                target_attr = None
                if cmds.objExists(mat + ".color"): target_attr = mat + ".color"
                elif cmds.objExists(mat + ".baseColor"): target_attr = mat + ".baseColor" # 支持 Arnold/StandardSurface
                
                if not target_attr:
                    return cmds.warning(u"抱歉，该材质球类型不支持通过此工具一键连接基础贴图！")

                # 创建 file 节点和 2D 放置节点
                new_file_node = cmds.shadingNode('file', asTexture=True, isColorManaged=True)
                p2d = cmds.shadingNode('place2dTexture', asUtility=True)
                
                # 建立标准的 Maya 2D 贴图连线网络
                attrs = ['coverage', 'translateFrame', 'rotateFrame', 'mirrorU', 'mirrorV', 'stagger', 'wrapU', 'wrapV', 'repeatUV', 'offset', 'rotateUV', 'noiseUV', 'vertexUvOne', 'vertexUvTwo', 'vertexUvThree', 'vertexCameraOne']
                for attr in attrs:
                    cmds.connectAttr(p2d + '.' + attr, new_file_node + '.' + attr, f=True)
                cmds.connectAttr(p2d + '.outUV', new_file_node + '.uvCoord', f=True)
                cmds.connectAttr(p2d + '.outUvFilterSize', new_file_node + '.uvFilterSize', f=True)
                
                # 赋予路径并连接到材质球
                cmds.setAttr(new_file_node + ".fileTextureName", new_path[0], type="string")
                cmds.connectAttr(new_file_node + ".outColor", target_attr, force=True)
                
                cmds.inViewMessage(amg=u"贴图节点已创建并自动连接成功！", pos='midCenter', fade=True)
                self.refresh_material_list()

    def _get_models_from_mat(self, mat):
        models = []
        sgs = cmds.listConnections(mat, type='shadingEngine')
        if sgs:
            for sg in set(sgs):
                members = cmds.sets(sg, query=True)
                if members:
                    for m in members:
                        trans = self._get_transform_from_member(m)
                        if trans: models.append(trans.split('|')[-1])
        return list(set(models))

    def _get_texture_from_mat(self, mat):
        for attr in ['.color', '.baseColor']:
            if cmds.objExists(mat + attr):
                texs = cmds.listConnections(mat + attr, type='file')
                if texs: return texs[0]
        return None

    def get_selected_materials(self):
        current_tree = self.tab_widget.currentWidget()
        if not current_tree: return []
        return [item.data(0, QtCore.Qt.UserRole) for item in current_tree.selectedItems()]

    # ================= 一键 Lambert 功能 =================
    def create_and_assign_lambert(self):
        sel_objs = cmds.ls(selection=True, dag=True, type='mesh', noIntermediate=True)
        if not sel_objs:
            return cmds.warning(u"请先在场景中选择要赋予材质的模型！")
        
        mat = cmds.shadingNode('lambert', asShader=True, name="NewLambert_MAT")
        sg = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=mat + "SG")
        cmds.connectAttr(mat + ".outColor", sg + ".surfaceShader", force=True)
        cmds.sets(sel_objs, edit=True, forceElement=sg)
        
        self.refresh_material_list()
        cmds.inViewMessage(amg=u"已创建并赋予新 Lambert", pos='midCenter', fade=True)

    # ================= 分栏管理 =================
    def get_mat_group(self, mat):
        if cmds.attributeQuery('hk_mat_group', node=mat, exists=True):
            return cmds.getAttr(mat + '.hk_mat_group') or u"未分组"
        return u"未分组"

    def set_mat_group(self, mat, group_name):
        if not cmds.attributeQuery('hk_mat_group', node=mat, exists=True):
            cmds.addAttr(mat, ln='hk_mat_group', dt='string')
        cmds.setAttr(mat + '.hk_mat_group', group_name, type='string')

    def add_new_tab(self):
        text, ok = QtWidgets.QInputDialog.getText(self, u"新建材质组", u"请输入新组名:")
        if ok and text:
            if text in self.tabs_dict: return cmds.warning(u"组名已存在！")
            self.refresh_material_list() 

    def rename_current_tab(self):
        idx = self.tab_widget.currentIndex()
        old_name = self.tab_widget.tabText(idx)
        if old_name == u"未分组": return cmds.warning(u"默认组无法重命名")
        
        new_name, ok = QtWidgets.QInputDialog.getText(self, u"重命名", u"新名称:", text=old_name)
        if ok and new_name and new_name != old_name:
            current_tree = self.tabs_dict[old_name]
            root = current_tree.invisibleRootItem()
            for i in range(root.childCount()):
                mat = root.child(i).data(0, QtCore.Qt.UserRole)
                self.set_mat_group(mat, new_name)
            self.refresh_material_list()

    def delete_current_tab(self):
        idx = self.tab_widget.currentIndex()
        grp_name = self.tab_widget.tabText(idx)
        if grp_name == u"未分组": return
        
        current_tree = self.tabs_dict[grp_name]
        root = current_tree.invisibleRootItem()
        for i in range(root.childCount()):
            mat = root.child(i).data(0, QtCore.Qt.UserRole)
            self.set_mat_group(mat, u"未分组")
        self.refresh_material_list()

    def update_move_combo(self):
        self.combo_target_tab.clear()
        for i in range(self.tab_widget.count()):
            self.combo_target_tab.addItem(self.tab_widget.tabText(i))

    def move_materials_to_tab(self):
        target_group = self.combo_target_tab.currentText()
        for mat in self.get_selected_materials():
            self.set_mat_group(mat, target_group)
        self.refresh_material_list()

    # ================= 命名功能 =================
    def add_suffix(self):
        suffix = self.le_suffix.text()
        for mat in self.get_selected_materials():
            if not mat.endswith(suffix):
                cmds.rename(mat, mat + suffix)
        self.refresh_material_list()

    def rename_by_model(self):
        suffix = self.le_suffix.text()
        for mat in self.get_selected_materials():
            sgs = cmds.listConnections(mat, type='shadingEngine')
            if sgs:
                members = cmds.sets(sgs[0], query=True)
                if members:
                    transform = self._get_transform_from_member(members[0])
                    if transform:
                        new_name = transform.split('|')[-1] + suffix
                        try: cmds.rename(mat, new_name)
                        except Exception as e: print(f"重命名 {mat} 失败: {e}")
        self.refresh_material_list()

    # ================= 其他核心操作 =================
    def select_material_from_model(self):
        sel_objs = cmds.ls(selection=True, dag=True, type='mesh', noIntermediate=True)
        if not sel_objs: return cmds.warning(u"请先选择模型！")
        sgs = cmds.listConnections(sel_objs, type='shadingEngine')
        if not sgs: return
        
        mats_to_select = set()
        for sg in set(sgs): mats_to_select.update(cmds.ls(cmds.listConnections(sg), materials=True))
            
        if mats_to_select:
            for i in range(self.tab_widget.count()): self.tab_widget.widget(i).clearSelection()
            found_tab_idx = -1
            for mat in mats_to_select:
                grp = self.get_mat_group(mat)
                if grp in self.tabs_dict:
                    tree = self.tabs_dict[grp]
                    root = tree.invisibleRootItem()
                    for idx in range(root.childCount()):
                        item = root.child(idx)
                        if item.data(0, QtCore.Qt.UserRole) == mat:
                            item.setSelected(True)
                            found_tab_idx = self.tab_widget.indexOf(tree)
            if found_tab_idx != -1: self.tab_widget.setCurrentIndex(found_tab_idx)

    def select_models_by_material(self):
        objs_to_select = []
        for mat in self.get_selected_materials():
            sgs = cmds.listConnections(mat, type='shadingEngine')
            if sgs:
                for sg in sgs:
                    members = cmds.sets(sg, query=True)
                    if members: objs_to_select.extend(members)
        if objs_to_select: cmds.select(objs_to_select, replace=True)

    def assign_material_to_selected(self):
        mats = self.get_selected_materials()
        sel_objs = cmds.ls(selection=True)
        if mats and sel_objs:
            sgs = cmds.listConnections(mats[0], type='shadingEngine')
            sg = sgs[0] if sgs else cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=mats[0] + "SG")
            cmds.sets(sel_objs, edit=True, forceElement=sg)

    def clean_unused_materials(self):
        mel.eval('MLdeleteUnused')
        self.refresh_material_list()

    def deep_merge_materials(self):
        mats = cmds.ls(mat=True)
        mat_dict = {}
        merge_count = 0
        
        for mat in mats:
            if mat in ['lambert1', 'particleCloud1', 'shaderGlow1']: continue
            fingerprint = ""
            if cmds.objExists(mat + ".color"):
                fingerprint += f"C{tuple(round(c, 2) for c in cmds.getAttr(mat + '.color')[0])}"
            if cmds.objExists(mat + ".transparency"):
                fingerprint += f"T{tuple(round(c, 2) for c in cmds.getAttr(mat + '.transparency')[0])}"
            textures = cmds.listConnections(mat, type='file')
            if textures:
                fingerprint += f"Tex{'|'.join([cmds.getAttr(t + '.fileTextureName') for t in textures])}"
                
            if fingerprint in mat_dict:
                base_mat = mat_dict[fingerprint]
                old_sgs, new_sgs = cmds.listConnections(mat, type='shadingEngine'), cmds.listConnections(base_mat, type='shadingEngine')
                if old_sgs and new_sgs:
                    members = cmds.sets(old_sgs[0], query=True)
                    if members: cmds.sets(members, edit=True, forceElement=new_sgs[0])
                try:
                    cmds.delete(mat)
                    merge_count += 1
                except: pass
            else:
                mat_dict[fingerprint] = mat
                
        self.refresh_material_list()
        cmds.inViewMessage(amg=u"已合并 {} 个相同参数的材质".format(merge_count), pos='midCenter', fade=True)

    def on_material_selected(self):
        mats = self.get_selected_materials()
        if not mats: return
        mat = mats[0]
        if cmds.objExists(mat + ".color"):
            r, g, b = [int(c * 255) for c in cmds.getAttr(mat + ".color")[0]]
            self.color_btn.setStyleSheet(f"background-color: rgb({r}, {g}, {b});")
        if cmds.objExists(mat + ".transparency"):
            r, g, b = [int(255 - c * 255) for c in cmds.getAttr(mat + ".transparency")[0]] 
            self.trans_btn.setStyleSheet(f"background-color: rgb({r}, {g}, {b});")

    def change_mat_attribute(self, attr_name):
        mats = self.get_selected_materials()
        if not mats: return
        mat = mats[0]
        if not cmds.objExists(mat + f".{attr_name}"): return
        cmds.colorEditor(rgbValue=cmds.getAttr(mat + f".{attr_name}")[0])
        if cmds.colorEditor(query=True, result=True):
            new_color = cmds.colorEditor(query=True, rgbValue=True)
            cmds.setAttr(mat + f".{attr_name}", new_color[0], new_color[1], new_color[2], type="double3")
            self.on_material_selected()

def run():
    global um_window_v4
    try: um_window_v4.close()
    except: pass
    um_window_v4 = UltimateMaterialManager()
    um_window_v4.show()

if __name__ == "__main__":
    run()