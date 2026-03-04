# -*- coding: utf-8 -*-
# toolbox_core/native_ui.py

import os
import json
import time
import maya.cmds as cmds
import maya.OpenMayaUI as omui

try:
    from PySide2 import QtWidgets, QtCore, QtGui
    from shiboken2 import wrapInstance
except ImportError:
    from PySide6 import QtWidgets, QtCore, QtGui
    from shiboken6 import wrapInstance

from toolbox_core import config
from toolbox_core import utils
from toolbox_core import worker

_DRAGGED_WIDGET = None

# ====================================================================
# 自由拖放容器 (Free-form Drop Container)
# ====================================================================
# ====================================================================
# 自由拖放容器 (Free-form Drop Container)
# 支持内部模块重排 + 外部工具拖入
# ====================================================================
class PanelContainer(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(PanelContainer, self).__init__(parent)
        self.setAcceptDrops(True)
        self.on_reorder_callback = None

    def dragEnterEvent(self, event):
        text = event.mimeData().text()
        # 允许内部模块把手拖拽 (hk_tool_drag) 或 外部工具按钮拖入 (JSON字符串以 '{' 开头)
        if text == "hk_tool_drag" or text.startswith("{"):
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        text = event.mimeData().text()
        if text == "hk_tool_drag" or text.startswith("{"):
            event.acceptProposedAction()

    def dropEvent(self, event):
        text = event.mimeData().text()
        drop_pos = event.pos()
        layout = self.layout()
        
        # 1. 计算鼠标落入了哪一列
        target_col = 0
        min_dx = float('inf')
        if hasattr(layout, 'col_info') and layout.col_info:
            for i, info in enumerate(layout.col_info):
                col_center_x = info['x'] + info['w'] / 2.0
                dx = abs(drop_pos.x() - col_center_x)
                if dx < min_dx:
                    min_dx = dx
                    target_col = i

        # === 分支 A：从外部列表拖入新工具 ===
        if text.startswith("{"):
            try:
                import json
                tool_data = json.loads(text)
                # 使用单次定时器异步执行，防止 Qt 的拖拽事件循环卡死 UI
                QtCore.QTimer.singleShot(10, lambda: SuperPanelManager.run_and_embed(tool_data, init_col=target_col))
            except Exception as e:
                print(u"拖拽解析失败:", e)
            event.acceptProposedAction()
            return

        # === 分支 B：内部模块互相拖拽重排 ===
        if text == "hk_tool_drag":
            global _DRAGGED_WIDGET
            if not _DRAGGED_WIDGET: return
            
            insert_before_item = None
            if hasattr(layout, 'col_info') and layout.col_info:
                col_items = layout.col_info[target_col]['items']
                for item in col_items:
                    wid = item.widget()
                    if wid == _DRAGGED_WIDGET: continue
                    center_y = wid.geometry().center().y()
                    if drop_pos.y() < center_y:
                        insert_before_item = item
                        break
                        
            _DRAGGED_WIDGET._assigned_col = target_col
            
            from_idx = -1
            for i, item in enumerate(layout.itemList):
                if item.widget() == _DRAGGED_WIDGET:
                    from_idx = i
                    break
                    
            if from_idx != -1:
                item = layout.itemList.pop(from_idx)
                if insert_before_item:
                    target_idx = layout.itemList.index(insert_before_item)
                else:
                    target_idx = len(layout.itemList)
                    
                layout.itemList.insert(target_idx, item)
                layout.invalidate()
                layout.activate() 
                
                if self.on_reorder_callback:
                    self.on_reorder_callback()
                    
            event.acceptProposedAction()

# ====================================================================
# 拖拽把手事件过滤器
# ====================================================================
class HeaderDragFilter(QtCore.QObject):
    def __init__(self, section):
        super(HeaderDragFilter, self).__init__(section)
        self.section = section
        self.drag_start_pos = None
        
    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.MouseButtonPress:
            if event.button() == QtCore.Qt.LeftButton:
                self.drag_start_pos = event.pos()
                return True 
        elif event.type() == QtCore.QEvent.MouseMove:
            if event.buttons() & QtCore.Qt.LeftButton and self.drag_start_pos:
                if (event.pos() - self.drag_start_pos).manhattanLength() >= QtWidgets.QApplication.startDragDistance():
                    self.start_drag(event.pos())
                    self.drag_start_pos = None
                    return True
        elif event.type() == QtCore.QEvent.MouseButtonRelease:
            self.drag_start_pos = None
        return False

    def start_drag(self, hotspot):
        drag = QtGui.QDrag(self.section)
        mime_data = QtCore.QMimeData()
        mime_data.setText("hk_tool_drag")
        drag.setMimeData(mime_data)
        
        pixmap = self.section.grab()
        painter = QtGui.QPainter(pixmap)
        painter.setCompositionMode(QtGui.QPainter.CompositionMode_DestinationIn)
        painter.fillRect(pixmap.rect(), QtGui.QColor(0, 0, 0, 160))
        painter.end()
        
        drag.setPixmap(pixmap)
        drag.setHotSpot(hotspot)
        
        global _DRAGGED_WIDGET
        _DRAGGED_WIDGET = self.section
        drag.exec_(QtCore.Qt.MoveAction)
        _DRAGGED_WIDGET = None

# ====================================================================
# 宽度缩放把手
# ====================================================================
class ResizeHandle(QtWidgets.QLabel):
    def __init__(self, target_widget, parent=None):
        super(ResizeHandle, self).__init__(parent)
        self.target_widget = target_widget 
        self.setFixedSize(14, 14)
        self.setCursor(QtCore.Qt.SizeHorCursor) 
        self._is_resizing = False
        self._start_pos = None
        self._start_width = None

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setPen(QtGui.QPen(QtGui.QColor(130, 130, 130), 1.5))
        w, h = self.width(), self.height()
        painter.drawLine(w - 4, h, w, h - 4)
        painter.drawLine(w - 8, h, w, h - 8)
        painter.drawLine(w - 12, h, w, h - 12)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._is_resizing = True
            self._start_pos = event.globalPos()
            self._start_width = self.target_widget._custom_width
            event.accept()

    def mouseMoveEvent(self, event):
        if self._is_resizing:
            delta = event.globalPos() - self._start_pos
            new_w = max(self._start_width + delta.x(), 200)
            self.target_widget.set_custom_width(new_w)
            
            p = self.target_widget.parentWidget()
            if p:
                p.updateGeometry()
                p.adjustSize()
                
            SuperPanelManager.auto_fit_window()
            event.accept()

    def mouseReleaseEvent(self, event):
        self._is_resizing = False
        SuperPanelManager._save_current_order()
        event.accept()

# ====================================================================
# 自由列对齐物理引擎 (Free-form Column Layout)
# 【核心逻辑】：彻底解绑数学取余，完全听从每个工具自己的 _assigned_col
# ====================================================================
class StrictColumnLayout(QtWidgets.QLayout):
    def __init__(self, parent=None, margin=8, spacing=8):
        super(StrictColumnLayout, self).__init__(parent)
        self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self.itemList = []
        self.column_count = 1 
        self.col_info = []

    def set_column_count(self, count):
        self.column_count = max(1, count)
        self.invalidate()

    def __del__(self):
        item = self.takeAt(0)
        while item: item = self.takeAt(0)

    def addItem(self, item): self.itemList.append(item)
    def count(self): return len(self.itemList)
    def itemAt(self, index): return self.itemList[index] if 0 <= index < len(self.itemList) else None
    def takeAt(self, index): return self.itemList.pop(index) if 0 <= index < len(self.itemList) else None
    def expandingDirections(self): return QtCore.Qt.Orientations(0)
    def hasHeightForWidth(self): return True
    def heightForWidth(self, width): return self.doLayout(QtCore.QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super(StrictColumnLayout, self).setGeometry(rect)
        self.doLayout(rect, False)

    def sizeHint(self): return self.minimumSize()

    def minimumSize(self):
        x0, y0 = 0, 0
        spaceX, spaceY = self.spacing(), self.spacing()
        margins = self.contentsMargins()
        
        total_w = 0
        for i in range(self.column_count):
            w = 230
            for item in self.itemList:
                wid = item.widget()
                if wid and getattr(wid, '_assigned_col', 0) == i:
                    w = max(w, getattr(wid, '_custom_width', 230))
            total_w += w
                
        total_w += (self.column_count - 1) * spaceX
        total_w += margins.left() + margins.right()
        
        total_h = self.doLayout(QtCore.QRect(0, 0, total_w, 0), True)
        return QtCore.QSize(total_w, total_h)

    def doLayout(self, rect, testOnly):
        x0, y0 = rect.x(), rect.y()
        spaceX, spaceY = self.spacing(), self.spacing()
        
        self.col_info = []
        current_x = x0
        
        # 1. 扫描每一列的最宽元素，确定各列宽度和 X 坐标
        for i in range(self.column_count):
            w = 230
            for item in self.itemList:
                wid = item.widget()
                if wid and not wid.isVisibleTo(wid.parentWidget()): continue
                if getattr(wid, '_assigned_col', 0) == i:
                    w = max(w, getattr(wid, '_custom_width', 230))
                    
            self.col_info.append({'x': current_x, 'w': w, 'bottom': y0, 'items': []})
            current_x += w + spaceX
            
        if not self.col_info: return 0
        
        # 2. 将工具按其自带的归属列分发，维护顺序
        for item in self.itemList:
            wid = item.widget()
            if wid and not wid.isVisibleTo(wid.parentWidget()): continue
            
            # 读取自身绑定的列
            col_idx = getattr(wid, '_assigned_col', 0)
            if col_idx >= self.column_count: col_idx = self.column_count - 1
            
            col = self.col_info[col_idx]
            
            c_x = col['x']
            c_y = col['bottom']
            c_w = col['w']
            h = item.sizeHint().height() 
            
            if not testOnly: 
                item.setGeometry(QtCore.QRect(c_x, c_y, c_w, h))
                
            col['bottom'] = c_y + h + spaceY
            col['items'].append(item)

        return (max([c['bottom'] for c in self.col_info]) if self.col_info else y0) - y0


# ====================================================================
# UI 组件：折叠栏
# ====================================================================
class CollapsibleSection(QtWidgets.QWidget):
    closed_signal = QtCore.Signal() 

    def __init__(self, tool_id, title="Section", parent=None, expanded=True, init_width=230):
        super(CollapsibleSection, self).__init__(parent)
        self.tool_id = tool_id 
        self.is_expanded = expanded
        self._custom_width = init_width
        self._assigned_col = 0 # 【核心属性】记录自己所在的列
        
        self.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.header_widget = QtWidgets.QWidget()
        self.header_widget.setFixedHeight(28)
        self.header_widget.setStyleSheet("background-color: #3e3e3e; border-bottom: 1px solid #2b2b2b;")
        
        self.header_layout = QtWidgets.QHBoxLayout(self.header_widget)
        self.header_layout.setContentsMargins(5, 0, 5, 0)
        self.header_layout.setSpacing(5)

        self.lbl_grip = QtWidgets.QLabel(u"⠿")
        self.lbl_grip.setStyleSheet("color: #777; font-size: 14px; padding-bottom: 2px;")
        self.lbl_grip.setCursor(QtCore.Qt.OpenHandCursor)
        self.lbl_grip.setToolTip(u"按住拖动以自由重排")
        
        self.drag_filter = HeaderDragFilter(self)
        self.lbl_grip.installEventFilter(self.drag_filter)
        
        self.btn_toggle = QtWidgets.QPushButton()
        self.btn_toggle.setStyleSheet("QPushButton { color: #ddd; border: none; text-align: left; font-weight: bold; font-size: 12px; background: transparent; }")
        self.btn_toggle.setCursor(QtCore.Qt.PointingHandCursor)
        
        self.btn_tear = QtWidgets.QPushButton(u"⏏")
        self.btn_tear.setFixedSize(20, 20)
        self.btn_tear.setToolTip(u"撕下为独立窗口 (Tear off)")
        self.btn_tear.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_tear.setStyleSheet("QPushButton { color: #888; border: none; font-weight: bold; font-size: 14px; background: transparent; } QPushButton:hover { color: #4CAF50; }")
        
        self.btn_close = QtWidgets.QPushButton(u"✕")
        self.btn_close.setFixedSize(20, 20)
        self.btn_close.setToolTip(u"关闭工具")
        self.btn_close.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_close.setStyleSheet("QPushButton { color: #888; border: none; font-weight: bold; font-size: 14px; background: transparent; } QPushButton:hover { color: #F44336; }")
        
        self.header_layout.addWidget(self.lbl_grip)
        self.header_layout.addWidget(self.btn_toggle)
        self.header_layout.addStretch()
        self.header_layout.addWidget(self.btn_tear)
        self.header_layout.addWidget(self.btn_close)

        self.content_frame = QtWidgets.QFrame()
        self.content_frame.setObjectName("HKContentFrame") 
        self.content_frame.setStyleSheet("QFrame#HKContentFrame { background-color: #2b2b2b; border: 1px solid #1a1a1a; border-top: none; }")
        
        self.content_outer_layout = QtWidgets.QVBoxLayout(self.content_frame)
        self.content_outer_layout.setContentsMargins(4, 4, 0, 0)
        self.content_outer_layout.setSpacing(0)
        
        self.content_inner_layout = QtWidgets.QVBoxLayout()
        self.content_inner_layout.setContentsMargins(0, 0, 4, 4)
        
        self.bottom_handle_layout = QtWidgets.QHBoxLayout()
        self.bottom_handle_layout.setContentsMargins(0, 0, 0, 0)
        self.bottom_handle_layout.addStretch()
        self.resize_handle = ResizeHandle(self)
        self.bottom_handle_layout.addWidget(self.resize_handle)
        
        self.content_outer_layout.addLayout(self.content_inner_layout, 1)
        self.content_outer_layout.addLayout(self.bottom_handle_layout, 0)
        
        self.main_layout.addWidget(self.header_widget)
        self.main_layout.addWidget(self.content_frame)

        self.btn_toggle.clicked.connect(self.toggle_content)
        self.btn_tear.clicked.connect(self.tear_off)
        self.btn_close.clicked.connect(self.close_section)
        
        self._update_title(title)
        self.content_frame.setVisible(self.is_expanded)

    def sizeHint(self):
        h = self.main_layout.sizeHint().height()
        return QtCore.QSize(self._custom_width, h)
        
    def set_custom_width(self, w):
        self._custom_width = w
        self.updateGeometry()

    def _update_title(self, title):
        self.base_title = title
        arrow = u"▼ " if self.is_expanded else u"▶ "
        self.btn_toggle.setText(arrow + self.base_title)

    def toggle_content(self):
        self.is_expanded = not self.is_expanded
        self._update_title(self.base_title)
        self.content_frame.setVisible(self.is_expanded)
        if self.parentWidget():
            self.parentWidget().adjustSize()
            self.parentWidget().updateGeometry()
            SuperPanelManager.auto_fit_window()

    def add_widget(self, widget):
        self.content_inner_layout.addWidget(widget)

    def tear_off(self):
        if self.content_inner_layout.count() > 0:
            target_win = self.content_inner_layout.itemAt(0).widget()
            if target_win:
                target_win.setParent(None)
                target_win.setWindowFlags(QtCore.Qt.Window)
                target_win.show()
        self.close_section()

    def close_section(self):
        self.closed_signal.emit()
        self.setParent(None) 
        self.deleteLater() 
        if self.parentWidget():
            self.parentWidget().adjustSize()
            SuperPanelManager.auto_fit_window()


class NativeWorkspaceManager(object):
    @classmethod
    def create_panel(cls, panel_id, title=u"HK Panel"):
        control_name = "HK_NativePanel_{}_WorkspaceControl".format(panel_id)
        if cmds.workspaceControl(control_name, exists=True):
            cmds.deleteUI(control_name)
            cmds.workspaceControlState(control_name, remove=True)
            
        cmds.workspaceControl(control_name, label=title, retain=False, floating=True)
        
        ptr = omui.MQtUtil.findControl(control_name)
        dock_widget = wrapInstance(int(ptr), QtWidgets.QWidget)
        
        dock_layout = dock_widget.layout()
        if not dock_layout:
            dock_layout = QtWidgets.QVBoxLayout(dock_widget)
        dock_layout.setContentsMargins(0, 0, 0, 0)
        dock_layout.setSpacing(0)
        
        top_bar = QtWidgets.QWidget()
        top_bar.setStyleSheet("background-color: #333; border-bottom: 1px solid #222;")
        top_bar.setFixedHeight(30)
        top_layout = QtWidgets.QHBoxLayout(top_bar)
        top_layout.setContentsMargins(10, 0, 10, 0)
        
        lbl_col = QtWidgets.QLabel(u"布局列数:")
        lbl_col.setStyleSheet("color: #ccc; font-weight: bold;")
        
        spin_col = QtWidgets.QSpinBox()
        spin_col.setRange(1, 10)
        spin_col.setStyleSheet("QSpinBox { background-color: #555; color: #fff; border: 1px solid #222; border-radius: 3px; }")
        
        btn_fit = QtWidgets.QPushButton(u"⛶ 自适应")
        btn_fit.setToolTip(u"紧凑包裹当前所有工具")
        btn_fit.setStyleSheet("QPushButton { background-color: #444; color: #ccc; border: 1px solid #222; border-radius: 3px; padding: 2px 8px; } QPushButton:hover { background-color: #555; }")
        
        top_layout.addWidget(lbl_col)
        top_layout.addWidget(spin_col)
        top_layout.addStretch()
        top_layout.addWidget(btn_fit)
        
        dock_layout.addWidget(top_bar)
        
        scroll_area = QtWidgets.QScrollArea(dock_widget)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)
        
        main_container = PanelContainer(scroll_area)
        main_layout = StrictColumnLayout(main_container, margin=8, spacing=8)
        
        scroll_area.setWidget(main_container)
        dock_layout.addWidget(scroll_area)
        
        return main_container, main_layout, spin_col, btn_fit

    @classmethod
    def add_section_to_panel(cls, panel_layout, tool_id, section_title, expanded=True, init_width=230):
        section = CollapsibleSection(tool_id=tool_id, title=section_title, expanded=expanded, init_width=init_width)
        panel_layout.addWidget(section)
        return section

# ====================================================================
# 超级工具包管理器
# ====================================================================
class SuperPanelManager(object):
    PANEL_ID = "HK_SuperToolkit"
    CONTROL_NAME = "HK_NativePanel_HK_SuperToolkit_WorkspaceControl"
    _current_layout = None
    _spin_col_ref = None

    @classmethod
    def get_state_file(cls):
        return os.path.join(config.MODULES_DIR, "super_panel_state.json")

    @classmethod
    def load_state(cls):
        path = cls.get_state_file()
        if os.path.exists(path):
            try:
                with open(path, "r") as f: 
                    data = json.load(f)
                    if isinstance(data, list):
                        return {"tools": data, "columns": 1, "widths": {}, "tool_cols": {}}
                    return data
            except: pass
        return {"tools": [], "columns": 1, "widths": {}, "tool_cols": {}}

    @classmethod
    def save_state(cls, state_dict):
        path = cls.get_state_file()
        try:
            with open(path, "w") as f: json.dump(state_dict, f, indent=4)
        except: pass

    @classmethod
    def _save_current_order(cls):
        if not cls._current_layout: return
        new_tools = []
        widths = {}
        tool_cols = {} # 记忆列坐标
        for item in cls._current_layout.itemList:
            wid = item.widget()
            if hasattr(wid, 'tool_id'):
                new_tools.append(wid.tool_id)
                widths[wid.tool_id] = wid._custom_width
                tool_cols[wid.tool_id] = getattr(wid, '_assigned_col', 0)
                
        cols = cls._spin_col_ref.value() if cls._spin_col_ref else 1
        state = {"tools": new_tools, "columns": cols, "widths": widths, "tool_cols": tool_cols}
        cls.save_state(state)

    @classmethod
    def is_panel_open(cls):
        return cmds.workspaceControl(cls.CONTROL_NAME, q=True, exists=True) and cmds.workspaceControl(cls.CONTROL_NAME, q=True, visible=True)

    @classmethod
    def auto_fit_window(cls):
        if not cls.is_panel_open() or not cls._current_layout: return
        
        w = cls._current_layout.sizeHint().width() + 35 
        h = cls._current_layout.sizeHint().height() + 70 
        
        w = min(max(w, 250), 1600)
        h = min(max(h, 200), 1200)
        
        cmds.workspaceControl(cls.CONTROL_NAME, e=True, resizeWidth=w, resizeHeight=h)

    @classmethod
    def toggle_panel(cls):
        if cmds.workspaceControl(cls.CONTROL_NAME, q=True, exists=True):
            if cmds.workspaceControl(cls.CONTROL_NAME, q=True, visible=True):
                cmds.workspaceControl(cls.CONTROL_NAME, e=True, visible=False)
                return
            else:
                cmds.workspaceControl(cls.CONTROL_NAME, e=True, visible=True)
                return

        container, layout, spin_col, btn_fit = NativeWorkspaceManager.create_panel(cls.PANEL_ID, u"超级工具包")
        cls._current_layout = layout
        cls._spin_col_ref = spin_col
        
        container.on_reorder_callback = cls._save_current_order
        
        def on_col_changed(val):
            layout.set_column_count(val)
            cls._save_current_order()
            cls.auto_fit_window() 

        spin_col.valueChanged.connect(on_col_changed)
        btn_fit.clicked.connect(cls.auto_fit_window)

        state = cls.load_state()
        saved_tools = state.get("tools", [])
        saved_cols = state.get("columns", 1)
        saved_widths = state.get("widths", {})
        saved_tool_cols = state.get("tool_cols", {})
        
        spin_col.blockSignals(True)
        spin_col.setValue(saved_cols)
        layout.set_column_count(saved_cols)
        spin_col.blockSignals(False)

        for tool_id in saved_tools:
            tool_data = utils.find_tool_by_id(tool_id)
            if tool_data:
                saved_w = saved_widths.get(tool_id, 230)
                saved_c = saved_tool_cols.get(tool_id, 0)
                cls.run_and_embed(tool_data, init_w=saved_w, init_col=saved_c, save_state=False)
                
        QtCore.QTimer.singleShot(150, cls.auto_fit_window)

    @classmethod
    def run_and_embed(cls, tool_data, init_w=230, init_col=-1, save_state=True):
        tool_name = tool_data.get("name", "Tool")
        tool_id = tool_data.get("id")

        # 防重复检测
        if cls._current_layout:
            for item in cls._current_layout.itemList:
                wid = item.widget()
                if hasattr(wid, 'tool_id') and wid.tool_id == tool_id:
                    if not wid.is_expanded:
                        wid.toggle_content() 
                    print(u"[{}] 已在超级面板中，跳过重复添加。".format(tool_name))
                    return True

        old_windows = set(QtWidgets.QApplication.topLevelWidgets())

        try:
            import toolbox_core.worker as worker
            worker.execute_tool(tool_data)
        except Exception as e:
            print(u"执行异常: {}".format(e))
            return False

        for _ in range(5):
            QtWidgets.QApplication.processEvents()
            time.sleep(0.02)

        new_windows = set(QtWidgets.QApplication.topLevelWidgets()) - old_windows
        target_win = None
        
        if new_windows:
            for win in new_windows:
                # 排除不可见和主窗口
                if not win.isVisible() or win.objectName() == 'MayaWindow': 
                    continue
                
                # === 【核心安全修复】 ===
                # 坚决不使用任何会引发 PySide6 报错的底层 Flag 强制转换
                
                # 1. 通过类名特征排除 Maya 的内部悬浮窗 (inViewMessage)
                cls_name = str(win.__class__.__name__)
                if "InView" in cls_name or "Message" in cls_name or "Menu" in cls_name or "Tip" in cls_name or "Popup" in cls_name:
                    continue
                
                # 2. 排除鼠标穿透的纯视觉浮层 (找回窗口的绿色提示字就是这种)
                if win.testAttribute(QtCore.Qt.WA_TransparentForMouseEvents):
                    continue
                
                target_win = win
                break

        if target_win and cls._current_layout:
            sh = target_win.sizeHint()
            optimal_w = max(sh.width(), init_w)
            
            section = NativeWorkspaceManager.add_section_to_panel(cls._current_layout, tool_id, tool_name, expanded=True, init_width=optimal_w)

            # 核心智能掉落
            if init_col >= 0:
                section._assigned_col = init_col
            else:
                if hasattr(cls._current_layout, 'col_info') and cls._current_layout.col_info:
                    min_col = 0
                    min_h = float('inf')
                    for i, info in enumerate(cls._current_layout.col_info):
                        if info['bottom'] < min_h:
                            min_h = info['bottom']
                            min_col = i
                    section._assigned_col = min_col
                else:
                    section._assigned_col = 0

            target_win.setParent(section.content_frame)
            target_win.setWindowFlags(QtCore.Qt.Widget)
            target_win.setMinimumSize(0, 0)
            target_win.setMaximumSize(16777215, 16777215)
            
            section.add_widget(target_win)
            target_win.show()

            section.set_custom_width(optimal_w)

            if save_state:
                cls._save_current_order()
                QtCore.QTimer.singleShot(50, cls.auto_fit_window) 

            def on_close():
                QtCore.QTimer.singleShot(50, cls._save_current_order)
                QtCore.QTimer.singleShot(100, cls.auto_fit_window)
            
            section.closed_signal.connect(on_close)
            return True
            
        else:
            # === 【新增】如果没有抓到窗口，且是用户主动拖放进来的 (save_state=True) ===
            if save_state:
                import maya.cmds as cmds
                cmds.warning(u"HKToolbox: 该工具【{}】属于无界面动作脚本，已直接执行，无需吸附。".format(tool_name))
            return False