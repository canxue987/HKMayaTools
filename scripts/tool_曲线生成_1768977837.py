# -*- coding: utf-8 -*-
import maya.cmds as cmds
import math

try:
    from PySide2 import QtWidgets, QtCore, QtGui
except ImportError:
    from PySide6 import QtWidgets, QtCore, QtGui

# =========================================================================
# 核心算法类 (保持不变)
# =========================================================================
class HKCurveCore(object):
    def __init__(self):
        self.bridge_curve = None
        self.cached_rings = [] 
        self.extract_curve = None
        self.path_edges = []   

    def get_loop_data(self, edges):
        verts = cmds.polyListComponentConversion(edges, fe=True, tv=True)
        verts = cmds.filterExpand(verts, sm=31)
        if not verts: return None

        positions = [cmds.pointPosition(v, w=True) for v in verts]
        count = len(positions)
        center = [sum(p[i] for p in positions)/count for i in range(3)]
        
        normal = [0, 0, 0]
        for i in range(count):
            p1 = positions[i]
            p2 = positions[(i+1)%count]
            normal[0] += (p1[1] - p2[1]) * (p1[2] + p2[2])
            normal[1] += (p1[2] - p2[2]) * (p1[0] + p2[0])
            normal[2] += (p1[0] - p2[0]) * (p1[1] + p2[1])
        length = math.sqrt(sum(n**2 for n in normal))
        if length > 1e-6: normal = [n/length for n in normal]
        else: normal = [0,1,0]

        total_dist = sum(math.sqrt(sum((p[i]-center[i])**2 for i in range(3))) for p in positions)
        avg_radius = total_dist / count

        return {"center": center, "normal": normal, "radius": avg_radius}

    def create_hermite_curve(self, rings_data, tangent_scale=1.0):
        if len(rings_data) < 2: return None
        
        cv_points = []
        for i in range(len(rings_data) - 1):
            start = rings_data[i]
            end = rings_data[i+1]
            p0, p3 = start['center'], end['center']
            n0, n3 = start['normal'], end['normal']
            
            dist = math.sqrt(sum((p3[k]-p0[k])**2 for k in range(3)))
            vec_ab = [p3[k]-p0[k] for k in range(3)]
            
            if sum(n0[k]*vec_ab[k] for k in range(3)) < 0: n0 = [-n for n in n0]
            if sum(n3[k]*vec_ab[k] for k in range(3)) < 0: n3 = [-n for n in n3]

            handle_len = dist * 0.35 * tangent_scale
            
            p1 = [p0[k] + n0[k] * handle_len for k in range(3)]
            p2 = [p3[k] - n3[k] * handle_len for k in range(3)]
            
            if i == 0: cv_points.append(p0)
            cv_points.extend([p1, p2, p3])
            
        curve = cmds.curve(d=3, p=cv_points, n="HK_Bridge_Curve")
        return curve

    def run_bridge(self, ordered_selection, tangent_scale=1.0):
        if self.bridge_curve and cmds.objExists(self.bridge_curve):
            cmds.delete(self.bridge_curve)

        self.cached_rings = []
        for edges in ordered_selection:
            data = self.get_loop_data(edges)
            if data: self.cached_rings.append(data)
            
        if len(self.cached_rings) < 2: raise Exception(u"至少需要 2 组截面")
        
        self.bridge_curve = self.create_hermite_curve(self.cached_rings, tangent_scale)
        cmds.select(self.bridge_curve)
        return self.bridge_curve

    def update_bridge_tangent(self, scale):
        if not self.bridge_curve or not cmds.objExists(self.bridge_curve): return
        if not self.cached_rings: return
        
        sel = cmds.ls(sl=True)
        cmds.delete(self.bridge_curve)
        self.bridge_curve = self.create_hermite_curve(self.cached_rings, scale)
        
        if sel: 
            if "HK_Bridge_Curve" in sel[0]:
                cmds.select(self.bridge_curve)
            else:
                cmds.select(sel)
        else:
            cmds.select(self.bridge_curve)

    def calculate_radius_from_selection(self):
        sel = cmds.ls(sl=True, fl=True)
        if not sel or not cmds.filterExpand(sel, sm=32):
            raise Exception(u"请选择一圈截面边")
        data = self.get_loop_data(sel)
        if not data: raise Exception(u"无法计算半径")
        return data['radius']

    def run_extract(self, path_edges, offset_val):
        if not path_edges: raise Exception(u"未加载路径边")
        
        cmds.select(path_edges)
        result = cmds.polyToCurve(form=2, degree=3, ch=False)
        curve = result[0]
        curve = cmds.rename(curve, "HK_Center_Curve")
        
        if abs(offset_val) < 0.001:
            cmds.select(curve)
            return curve

        mesh_obj = path_edges[0].split('.')[0]
        mesh_shapes = cmds.listRelatives(mesh_obj, s=True)
        if not mesh_shapes: return curve
        
        cpom = cmds.createNode('closestPointOnMesh')
        try: cmds.connectAttr(mesh_shapes[0] + ".worldMesh[0]", cpom + ".inMesh", f=True)
        except: cmds.connectAttr(mesh_shapes[0] + ".outMesh", cpom + ".inMesh", f=True)

        cvs = cmds.ls(curve + ".cv[*]", fl=True)
        for i, cv in enumerate(cvs):
            pos = cmds.pointPosition(cv, w=True)
            cmds.setAttr(cpom + ".inPosition", *pos)
            n = cmds.getAttr(cpom + ".normal")[0]
            
            new_pos = [
                pos[0] + n[0] * offset_val,
                pos[1] + n[1] * offset_val,
                pos[2] + n[2] * offset_val
            ]
            cmds.xform(cv, t=new_pos, ws=True)
            
        cmds.delete(cpom)
        cmds.select(curve)
        return curve


# =========================================================================
# UI 类
# =========================================================================
class HKCurveToolDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(HKCurveToolDialog, self).__init__(parent)
        self.setObjectName("HKCurveMasterWindow") 
        
        # 【关键修复】确保标题包含常见的中文关键词，以便雷达识别
        # 你在工具箱里发布叫“曲线生成”或“Curve”，这里必须包含这些字眼
        self.setWindowTitle(u"曲线生成专家 (Curve Master)") 
        
        self.setWindowFlags(QtCore.Qt.Window)
        self.resize(320, 480)
        self.core = HKCurveCore()
        self.bridge_selections = [] 
        self.extract_path_edges = []
        self.init_ui()

    def init_ui(self):
        self.setStyleSheet("""
            QDialog {background:#333; color:#EEE;} 
            QLabel{color:#BBB; font-weight:bold;} 
            QPushButton{background:#444; border:1px solid #555; color:#EEE; padding:6px; border-radius:3px;}
            QPushButton:hover{background:#555;}
            QListWidget{background:#222; border:1px solid #444; color:#DDD;}
            QTabWidget::pane { border: 1px solid #444; }
            QTabBar::tab { background: #333; color: #BBB; padding: 8px 12px; border: 1px solid #444; border-bottom: none; }
            QTabBar::tab:selected { background: #444; color: #FFF; }
            QGroupBox { border:1px solid #555; margin-top:6px; padding-top:10px; }
            QDoubleSpinBox { background:#222; border:1px solid #555; color:#EEE; padding:2px; }
            QSlider::groove:horizontal { border: 1px solid #444; height: 6px; background: #222; margin: 2px 0; border-radius: 3px; }
            QSlider::handle:horizontal { background: #5285A6; border: 1px solid #5285A6; width: 14px; height: 14px; margin: -5px 0; border-radius: 7px; }
        """)
        main_layout = QtWidgets.QVBoxLayout(self)
        tabs = QtWidgets.QTabWidget()
        main_layout.addWidget(tabs)
        
        # --- Tab 1 ---
        tab1 = QtWidgets.QWidget()
        t1_layout = QtWidgets.QVBoxLayout(tab1)
        
        t1_layout.addWidget(QtWidgets.QLabel(u"1. 截面列表 (按顺序连接):"))
        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection) 
        t1_layout.addWidget(self.list_widget)
        
        btn_box = QtWidgets.QHBoxLayout()
        btn_add = QtWidgets.QPushButton(u"+ 添加")
        btn_add.clicked.connect(self.add_bridge_sel)
        btn_rem = QtWidgets.QPushButton(u"- 移除选中")
        btn_rem.clicked.connect(self.remove_bridge_sel)
        btn_clr = QtWidgets.QPushButton(u"清空")
        btn_clr.clicked.connect(self.clear_bridge_sel)
        btn_box.addWidget(btn_add)
        btn_box.addWidget(btn_rem)
        btn_box.addWidget(btn_clr)
        t1_layout.addLayout(btn_box)
        
        t1_layout.addSpacing(10)
        self.btn_bridge = QtWidgets.QPushButton(u"生成中心曲线 (Generate)")
        self.btn_bridge.setStyleSheet("background:#5285A6; font-weight:bold; height: 35px;")
        self.btn_bridge.clicked.connect(self.run_bridge)
        t1_layout.addWidget(self.btn_bridge)
        
        # 曲率调整
        grp_param = QtWidgets.QGroupBox(u"参数调整 (可实时)")
        gp_layout = QtWidgets.QVBoxLayout(grp_param)
        gp_layout.addWidget(QtWidgets.QLabel(u"曲率力度 (Curvature):"))
        curvature_layout = QtWidgets.QHBoxLayout()
        self.sl_tangent = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.sl_tangent.setRange(0, 300) 
        self.sl_tangent.setValue(100)    
        self.spin_tangent = QtWidgets.QDoubleSpinBox()
        self.spin_tangent.setRange(0.0, 3.0)
        self.spin_tangent.setSingleStep(0.1)
        self.spin_tangent.setValue(1.0)
        self.spin_tangent.setFixedWidth(60)
        curvature_layout.addWidget(self.sl_tangent)
        curvature_layout.addWidget(self.spin_tangent)
        gp_layout.addLayout(curvature_layout)
        t1_layout.addWidget(grp_param)
        t1_layout.addStretch()
        tabs.addTab(tab1, u"截面连线")
        
        # --- Tab 2 ---
        tab2 = QtWidgets.QWidget()
        t2_layout = QtWidgets.QVBoxLayout(tab2)
        grp_path = QtWidgets.QGroupBox(u"第一步: 加载路径")
        gp_layout = QtWidgets.QVBoxLayout(grp_path)
        path_line = QtWidgets.QHBoxLayout()
        self.lbl_path_status = QtWidgets.QLabel(u"未加载")
        self.lbl_path_status.setStyleSheet("color: #E57373; font-weight: normal;")
        btn_load_path = QtWidgets.QPushButton(u"加载选中边")
        btn_load_path.clicked.connect(self.load_extract_path)
        btn_clr_path = QtWidgets.QPushButton(u"❌")
        btn_clr_path.setFixedWidth(30)
        btn_clr_path.clicked.connect(self.clear_extract_path)
        path_line.addWidget(btn_load_path)
        path_line.addWidget(btn_clr_path)
        path_line.addWidget(self.lbl_path_status)
        gp_layout.addLayout(path_line)
        t2_layout.addWidget(grp_path)
        
        grp_offset = QtWidgets.QGroupBox(u"第二步: 设置偏移")
        go_layout = QtWidgets.QVBoxLayout(grp_offset)
        ring_line = QtWidgets.QHBoxLayout()
        btn_calc_radius = QtWidgets.QPushButton(u"拾取截面自动计算半径")
        btn_calc_radius.clicked.connect(self.auto_calc_offset)
        btn_clr_offset = QtWidgets.QPushButton(u"❌")
        btn_clr_offset.setFixedWidth(30)
        btn_clr_offset.clicked.connect(lambda: self.spin_offset.setValue(0))
        ring_line.addWidget(btn_calc_radius)
        ring_line.addWidget(btn_clr_offset)
        go_layout.addLayout(ring_line)
        
        val_box = QtWidgets.QHBoxLayout()
        val_box.addWidget(QtWidgets.QLabel(u"法向偏移:"))
        self.spin_offset = QtWidgets.QDoubleSpinBox()
        self.spin_offset.setRange(-10000.0, 10000.0)
        self.spin_offset.setSingleStep(0.1)
        self.spin_offset.setValue(0.0)
        val_box.addWidget(self.spin_offset)
        go_layout.addLayout(val_box)
        t2_layout.addWidget(grp_offset)
        
        t2_layout.addSpacing(10)
        self.btn_extract = QtWidgets.QPushButton(u"生成并偏移 (Generate)")
        self.btn_extract.setStyleSheet("background:#5285A6; font-weight:bold; height:40px;")
        self.btn_extract.clicked.connect(self.run_extract)
        t2_layout.addWidget(self.btn_extract)
        t2_layout.addStretch()
        tabs.addTab(tab2, u"选边提取")
        
        self.sl_tangent.valueChanged.connect(self.on_slider_changed)
        self.spin_tangent.valueChanged.connect(self.on_spin_changed)

    def on_slider_changed(self, val):
        float_val = val / 100.0
        self.spin_tangent.blockSignals(True)
        self.spin_tangent.setValue(float_val)
        self.spin_tangent.blockSignals(False)
        self.core.update_bridge_tangent(float_val)

    def on_spin_changed(self, val):
        int_val = int(val * 100)
        self.sl_tangent.blockSignals(True)
        self.sl_tangent.setValue(int_val)
        self.sl_tangent.blockSignals(False)
        self.core.update_bridge_tangent(val)

    def add_bridge_sel(self):
        sel = cmds.ls(os=True, fl=True)
        if not sel or not cmds.filterExpand(sel, sm=32):
            cmds.warning(u"请选择边 (Edge)")
            return
        self.bridge_selections.append(sel)
        self.list_widget.addItem(u"截面 {} ({} edges)".format(len(self.bridge_selections), len(sel)))

    def remove_bridge_sel(self):
        rows = sorted([item.row() for item in self.list_widget.selectionModel().selectedIndexes()], reverse=True)
        for row in rows:
            self.list_widget.takeItem(row)
            del self.bridge_selections[row]

    def clear_bridge_sel(self):
        self.bridge_selections = []
        self.list_widget.clear()
        
    def run_bridge(self):
        try:
            self.core.run_bridge(self.bridge_selections, self.spin_tangent.value())
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Error", str(e))

    def load_extract_path(self):
        sel = cmds.ls(os=True, fl=True)
        if not sel or not cmds.filterExpand(sel, sm=32):
            self.lbl_path_status.setText(u"需选边")
            self.lbl_path_status.setStyleSheet("color: #E57373;")
            return
        self.extract_path_edges = sel
        self.lbl_path_status.setText(u"已加载 {} 边".format(len(sel)))
        self.lbl_path_status.setStyleSheet("color: #81C784; font-weight: bold;")

    def clear_extract_path(self):
        self.extract_path_edges = []
        self.lbl_path_status.setText(u"未加载")
        self.lbl_path_status.setStyleSheet("color: #E57373; font-weight: normal;")

    def auto_calc_offset(self):
        try:
            r = self.core.calculate_radius_from_selection()
            self.spin_offset.setValue(-r)
            print(u"半径: {:.3f}, 偏移设为: {:.3f}".format(r, -r))
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Warning", str(e))

    def run_extract(self):
        try:
            self.core.run_extract(self.extract_path_edges, self.spin_offset.value())
            self.clear_extract_path()
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Error", str(e))

# =========================================================================
# 标准化入口
# =========================================================================
def run():
    import __main__
    
    # 1. 查找 Maya 主窗口 (仅用于获取屏幕信息，不作为 Parent)
    maya_win = None
    for w in QtWidgets.QApplication.topLevelWidgets():
        if w.objectName() == 'MayaWindow':
            maya_win = w
            break
            
    # 2. 单例管理
    if hasattr(__main__, "hk_curve_win_instance"):
        try:
            __main__.hk_curve_win_instance.close()
            __main__.hk_curve_win_instance.deleteLater()
        except: pass
        
    # 3. 【关键修复】创建窗口，Parent 设为 None
    # 这样它就是一个 TopLevel 窗口，工具箱的雷达才能在 QApplication.topLevelWidgets() 里扫到它
    win = HKCurveToolDialog(parent=None) 
    win.show()
    
    # 4. 保持引用
    __main__.hk_curve_win_instance = win
    
    return win