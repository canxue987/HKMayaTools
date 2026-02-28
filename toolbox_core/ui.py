# -*- coding: utf-8 -*-
import sys
import os
import json
import math
import time

try:
    from PySide2 import QtWidgets, QtCore, QtGui
    from shiboken2 import wrapInstance 
    import maya.OpenMayaUI as omui     
except ImportError:
    try:
        from PySide6 import QtWidgets, QtCore, QtGui
        from shiboken6 import wrapInstance 
        import maya.OpenMayaUI as omui
    except ImportError:
        pass

import maya.cmds as cmds 

# --- 导入核心模块 ---
from . import config
from . import utils
from . import worker
from . import styles
from . import widgets
from . import dialogs

# =========================================================================
# 辅助函数
# =========================================================================
def get_window_state_path():
    return os.path.join(config.MODULES_DIR, "window_state.json")

def load_window_state():
    path = get_window_state_path()
    if os.path.exists(path):
        try:
            with open(path, "r") as f: return json.load(f)
        except: pass
    return {"floating": False, "width": 350, "height": 800}

def save_window_state_to_disk(state_data):
    try:
        with open(get_window_state_path(), "w") as f:
            json.dump(state_data, f, indent=4)
    except: pass

def get_maya_layout_widget(layout_name):
    """通过 Maya Layout 名字获取 QWidget 对象"""
    try:
        ptr = omui.MQtUtil.findControl(layout_name)
        if ptr:
            return wrapInstance(int(ptr), QtWidgets.QWidget)
    except: pass
    return None

# =========================================================================
# 环境劫持上下文 (核心黑科技)
# =========================================================================
class ToolExecutionGuard(object):
    """
    执行守护者：
    1. 劫持 cmds.window/showWindow，防止工具弹出独立窗口。
    2. 强制将父级指向画布提供的容器，解决路径依赖问题。
    """
    def __init__(self, target_layout):
        self.target_layout = target_layout
        self.original_window = cmds.window
        self.original_show = cmds.showWindow
        self.original_dock = getattr(cmds, 'dockControl', None)
        self.original_workspace = getattr(cmds, 'workspaceControl', None)

    def __enter__(self):
        # 1. 定义哑巴函数 (Mock)
        def mock_window(*args, **kwargs):
            if kwargs.get("exists") or kwargs.get("ex"):
                return False
            return self.target_layout
            
        def mock_pass(*args, **kwargs):
            return self.target_layout

        # 2. 实施劫持
        cmds.window = mock_window
        cmds.showWindow = mock_pass
        if self.original_dock: cmds.dockControl = mock_pass
        if self.original_workspace: cmds.workspaceControl = mock_pass
        
        # 3. 【核心修复】记录旧的 parent
        try:
            self.old_parent = cmds.setParent(q=True)
        except:
            self.old_parent = None
            
        # 强制设定父级
        cmds.setParent(self.target_layout)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # 4. 恢复环境 
        cmds.window = self.original_window
        cmds.showWindow = self.original_show
        if self.original_dock: cmds.dockControl = self.original_dock
        if self.original_workspace: cmds.workspaceControl = self.original_workspace
        
        # 5. 【核心修复】恢复旧的 parent，消除野指针
        if getattr(self, "old_parent", None):
            try:
                cmds.setParent(self.old_parent)
            except:
                pass

# =========================================================================
# 自定义 MDI 子窗口
# =========================================================================
class SlimSubWindow(QtWidgets.QMdiSubWindow):
    def __init__(self, parent=None):
        super(SlimSubWindow, self).__init__(parent)
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        
        self.main_layout = QtWidgets.QVBoxLayout()
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        self.center_widget = QtWidgets.QWidget()
        self.center_widget.setLayout(self.main_layout)
        self.setWidget(self.center_widget) 
        
        # Title Bar
        self.title_bar = QtWidgets.QWidget()
        self.title_bar.setFixedHeight(24) 
        self.title_bar.setStyleSheet("""
            QWidget { background-color: #333333; }
            QLabel { color: #BBB; font-weight: bold; font-size: 12px; padding-left: 5px; }
        """)
        
        title_layout = QtWidgets.QHBoxLayout(self.title_bar)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(0)
        
        self.lbl_title = QtWidgets.QLabel("Tool")
        self.btn_close = QtWidgets.QPushButton("×")
        self.btn_close.setFixedSize(24, 24)
        self.btn_close.clicked.connect(self.close)
        self.btn_close.setStyleSheet("""
            QPushButton { background-color: transparent; color: #888; border: none; font-size: 16px; font-weight: bold; }
            QPushButton:hover { background-color: #D32F2F; color: white; }
        """)
        
        title_layout.addWidget(self.lbl_title)
        title_layout.addStretch()
        title_layout.addWidget(self.btn_close)
        self.main_layout.addWidget(self.title_bar)
        
        # Content Area
        self.content_area = QtWidgets.QWidget()
        self.content_area.setObjectName("SlimContentArea") 
        self.content_area.setStyleSheet("#SlimContentArea { background-color: #444444; border: 1px solid #333333; border-top: none; }")
        self.content_area.setContentsMargins(0, 0, 0, 0)
        
        self.content_layout = QtWidgets.QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(0, 0, 0, 0) 
        self.main_layout.addWidget(self.content_area)

        # Size Grip
        self.size_grip = QtWidgets.QSizeGrip(self)
        self.size_grip.setStyleSheet("background-color: transparent; width: 16px; height: 16px;")
        
        self._dragging = False
        self._drag_pos = QtCore.QPoint()

    def set_content_widget(self, widget):
        # 【修改】改为 self.scroll_area，方便外部访问
        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidget(widget)
        self.scroll_area.setWidgetResizable(True) 
        self.scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)
        
        self.scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        
        self.content_layout.addWidget(self.scroll_area)
        self.lbl_title.setText(widget.windowTitle())

    def resizeEvent(self, event):
        super(SlimSubWindow, self).resizeEvent(event)
        rect = self.rect()
        self.size_grip.move(rect.right() - self.size_grip.width(), rect.bottom() - self.size_grip.height())
        self.size_grip.raise_()

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            if self.title_bar.geometry().contains(event.pos()):
                self._dragging = True
                self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
                event.accept()
        super(SlimSubWindow, self).mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._dragging and (event.buttons() & QtCore.Qt.LeftButton):
            self.move(event.globalPos() - self._drag_pos)
            event.accept()
        super(SlimSubWindow, self).mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._dragging = False
        super(SlimSubWindow, self).mouseReleaseEvent(event)


# =========================================================================
# Canvas Window (终极混合模式：筑巢 + 劫持 + 补漏)
# =========================================================================
class CanvasWindow(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        super(CanvasWindow, self).__init__(parent)
        self.setWindowTitle(u"Tool Canvas - 工具工作台")
        self.resize(1000, 700)
        self.setAcceptDrops(True)
        
        self.mdi_area = QtWidgets.QMdiArea()
        self.mdi_area.setBackground(QtGui.QBrush(QtGui.QColor("#202020")))
        self.mdi_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.mdi_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.mdi_area.setAcceptDrops(True)
        self.mdi_area.installEventFilter(self)
        self.setCentralWidget(self.mdi_area)
        
        toolbar = self.addToolBar("Manager")
        toolbar.setMovable(False)
        toolbar.setStyleSheet("""
            QToolBar { border-bottom: 1px solid #444; background: #333; spacing: 10px; padding: 5px; }
            QToolButton { background: #444; color: #EEE; padding: 4px; border-radius: 3px; }
            QToolButton:hover { background: #555; }
        """)
        
        act_arrange = toolbar.addAction(u"⊞ 瀑布流排列")
        act_arrange.triggered.connect(self.arrange_windows)
        act_save = toolbar.addAction(u"💾 保存布局") 
        act_save.triggered.connect(self.save_layout)
        act_close_all = toolbar.addAction(u"✕ 关闭所有")
        act_close_all.triggered.connect(self.clear_canvas)

        QtCore.QTimer.singleShot(100, self.load_layout)

    def eventFilter(self, source, event):
        if source == self.mdi_area:
            if event.type() == QtCore.QEvent.DragEnter:
                if event.mimeData().hasText():
                    event.acceptProposedAction()
                    return True 
            elif event.type() == QtCore.QEvent.Drop:
                self.dropEvent(event)
                return True
        return super(CanvasWindow, self).eventFilter(source, event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event):
        try:
            json_str = event.mimeData().text()
            tool_data = json.loads(json_str)
            self.execute_and_embed(tool_data)
            event.acceptProposedAction()
        except Exception as e:
            print(u"Drop Error: {}".format(e))

    def execute_and_embed(self, tool_data, geometry=None):
        tool_name = tool_data.get("name", "Tool")
        print(u"--- 开始嵌入流程: {} ---".format(tool_name))
        
        # === 【防御性编程】消除 Maya 父级野指针 ===
        # 尝试查询当前 parent，如果抛出异常说明父级已失效（被意外删除）
        try:
            cmds.setParent(q=True)
        except:
            # 强制回退到 Maya 主窗口作为安全基准
            try: cmds.setParent("MayaWindow")
            except: pass
        
        # === Step 1: 筑巢 ===
        nest_layout_name = cmds.columnLayout(adjustableColumn=True)
        
        nest_widget = get_maya_layout_widget(nest_layout_name)
        if not nest_widget:
            return

        sub_window = SlimSubWindow()
        sub_window.set_content_widget(nest_widget)
        sub_window.lbl_title.setText(tool_name)
        sub_window._stored_tool_data = tool_data
        
        self.mdi_area.addSubWindow(sub_window)
        sub_window.show()
        
        # === Step 2: 劫持执行 ===
        initial_children_count = 0
        children = cmds.layout(nest_layout_name, q=True, childArray=True)
        if children: initial_children_count = len(children)

        try:
            with ToolExecutionGuard(target_layout=nest_layout_name):
                worker.execute_tool(tool_data)
        except Exception as e:
            print(u"工具执行异常: {}".format(e))

        # === Step 3: 尺寸自适应与验收补漏 ===
        try:
            current_children = cmds.layout(nest_layout_name, q=True, childArray=True)
        except:
            current_children = None
            
        final_children_count = len(current_children) if current_children else 0
        
        if final_children_count > initial_children_count:
            # A. 成功捕获 CMDs 工具
            print(u"√ 成功嵌入 CMDs 工具")
            
            # 强制刷新，让 Layout 计算出真实大小
            QtWidgets.QApplication.processEvents()
            
            sh = nest_widget.sizeHint()
            
            target_w = max(sh.width() + 30, 250) 
            target_h = min(sh.height() + 40, 800)
            
            sub_window.resize(target_w, target_h)
            
            if geometry:
                sub_window.setGeometry(*geometry)
                
        else:
            # B. 容器为空 -> 无UI脚本，或PySide独立窗口
            print(u"× 容器为空，启动雷达抓捕...")
            
            sub_window.close()
            sub_window.deleteLater()
            
            try: cmds.deleteUI(nest_layout_name)
            except: pass
            
            self.radar_capture(tool_data, geometry)

    def radar_capture(self, tool_data, geometry=None):
        """雷达抓捕：专门对付 PySide 独立窗口"""
        tool_name = tool_data.get("name", "")
        
        # 【BUG修复】: 删除或注释掉下面这行代码
        # worker.execute_tool(tool_data)  <--- 之前这里重复执行了
        
        # 解释：因为刚才在 execute_and_embed 的 Guard 里已经执行过一次了。
        # 如果是 PySide 工具，它现在应该已经弹出来了。
        # 我们不需要再次执行，直接找现成的活跃窗口即可。
        
        target_widget = None
        
        # 稍微给点时间让窗口显示出来 (特别是如果代码比较庞大时)
        for i in range(10):
            QtWidgets.QApplication.processEvents()
            time.sleep(0.05)
            
            # 策略1：找活跃窗口
            active = QtWidgets.QApplication.activeWindow()
            if self._is_valid_tool_window(active):
                target_widget = active
                print(u"雷达锁定活跃窗口: {}".format(active.windowTitle()))
                break
                
            # 策略2：遍历顶层窗口查找名称匹配的
            top_widgets = QtWidgets.QApplication.topLevelWidgets()
            for w in top_widgets:
                if self._is_valid_tool_window(w):
                    t_title = w.windowTitle().lower()
                    if tool_name.lower() in t_title:
                        target_widget = w
                        break
            if target_widget: break
            
        if target_widget:
            self.add_widget(target_widget, tool_data)
            if geometry:
                # 恢复之前保存的位置信息
                sub = self.mdi_area.subWindowList()[-1]
                sub.setGeometry(*geometry)
        else:
            print(u"雷达捕获失败：请检查该工具是否兼容。")

    def _is_valid_tool_window(self, w):
        try:
            if w is None: return False
            if w == self or w == self.mdi_area: return False
            if w.parent() == self.mdi_area: return False
            if w.objectName() in ["MayaWindow", "HKToolboxWorkspaceControl", "ConsoleWindow"]: return False
            if w.windowFlags() & QtCore.Qt.ToolTip: return False
            if not w.isVisible(): return False
            return True
        except: return False

    def add_widget(self, widget, tool_data):
        tool_name = tool_data.get("name", "Tool")
        widget.setAutoFillBackground(True)
        pal = widget.palette()
        pal.setColor(QtGui.QPalette.Window, QtGui.QColor("#444444"))
        pal.setColor(QtGui.QPalette.WindowText, QtGui.QColor("#DDDDDD"))
        widget.setPalette(pal)
        
        sub = SlimSubWindow() 
        sub.set_content_widget(widget)
        sub.lbl_title.setText(tool_name)
        sub._stored_tool_data = tool_data
        
        self.mdi_area.addSubWindow(sub)
        widget.show()
        sub.show()
        
        sh = widget.sizeHint()
        w = max(sh.width(), 200)
        h = max(sh.height(), 100)
        sub.resize(w, h + 24 + 10)

    def clear_canvas(self):
        self.mdi_area.closeAllSubWindows()

    def arrange_windows(self):
        """
        智能紧凑排列 (Smart Packing / Masonry Layout)
        算法逻辑：
        1. 不改变任何窗口的大小。
        2. 扫描所有候选位置（左上角、已有窗口的右侧、已有窗口的下方）。
        3. 找到第一个能容纳当前窗口且不与现有窗口重叠的位置。
        4. 优先填补上方和左侧的空缺 (Top-Left Priority)。
        """
        windows = self.mdi_area.subWindowList()
        # 过滤出可见窗口
        visible_windows = [w for w in windows if w.isVisible()]
        if not visible_windows: return
        
        area_width = self.mdi_area.width()
        gap = 10 # 窗口间距
        
        # 记录已放置的矩形区域 (x, y, w, h)
        placed_rects = []
        
        # --- 内部辅助函数：检测重叠 ---
        def is_overlapping(x, y, w, h, rects):
            """检测 (x,y,w,h) 是否与 rects 中的任意矩形重叠 (包含间距)"""
            for rx, ry, rw, rh in rects:
                # 判定重叠条件：水平方向重叠 且 垂直方向重叠
                # 使用 gap 确保两个窗口之间至少保留 gap 的距离
                
                # 水平重叠: A左 < B右+gap  且  A右+gap > B左
                horizontal_overlap = (x < rx + rw + gap) and (x + w + gap > rx)
                
                # 垂直重叠: A上 < B下+gap  且  A下+gap > B上
                vertical_overlap = (y < ry + rh + gap) and (y + h + gap > ry)
                
                if horizontal_overlap and vertical_overlap:
                    return True
            return False

        # --- 开始排列 ---
        for sub in visible_windows:
            w = sub.width()
            h = sub.height()
            
            best_x, best_y = 10, 10
            found = False
            
            # 生成候选位置列表
            # 每一个已放置窗口的【右边】和【下边】都是潜在的放置点
            # 同时加入 (10, 10) 作为起始点
            candidates = set()
            candidates.add((10, 10))
            
            for rx, ry, rw, rh in placed_rects:
                candidates.add((rx + rw + gap, ry))       # 右侧紧邻位置
                candidates.add((rx, ry + rh + gap))       # 下方紧邻位置
                candidates.add((10, ry + rh + gap))       # 换行起始位置
            
            # 将候选点转为列表并排序
            # 排序优先级：先 Y (越靠上越好)，再 X (越靠左越好)
            sorted_candidates = sorted(list(candidates), key=lambda pos: (pos[1], pos[0]))
            
            # 遍历候选点，寻找“最佳坑位”
            for cx, cy in sorted_candidates:
                # 1. 越界检查 (宽度)
                if cx + w > area_width:
                    continue
                
                # 2. 重叠检查
                if not is_overlapping(cx, cy, w, h, placed_rects):
                    best_x, best_y = cx, cy
                    found = True
                    break
            
            # 兜底：如果所有候选点都不行（极少见，除非窗口比画布还宽），
            # 就放到当前所有内容的最下方
            if not found:
                max_y = 10
                for _, ry, _, rh in placed_rects:
                    max_y = max(max_y, ry + rh + gap)
                best_x, best_y = 10, max_y

            # 移动窗口到最佳位置
            sub.move(best_x, best_y)
            
            # 记录这个位置已被占用
            placed_rects.append((best_x, best_y, w, h))

    def get_layout_path(self):
        return os.path.join(config.ROOT_DIR, "modules", config.CANVAS_LAYOUT_FILE)

    def save_layout(self):
        layout_data = []
        for sub in self.mdi_area.subWindowList():
            geo = sub.geometry()
            rect = [geo.x(), geo.y(), geo.width(), geo.height()]
            if hasattr(sub, "_stored_tool_data") and sub._stored_tool_data:
                tool_data = sub._stored_tool_data
                layout_data.append({
                    "tool_id": tool_data.get("id"),
                    "tool_name": tool_data.get("name"),
                    "geometry": rect
                })
        try:
            with open(self.get_layout_path(), "w") as f:
                json.dump(layout_data, f, indent=4)
            QtWidgets.QMessageBox.information(self, u"保存成功", u"画布布局已保存！\n包含 {} 个工具窗口。".format(len(layout_data)))
        except Exception as e:
            print(u"保存布局失败: {}".format(e))
            QtWidgets.QMessageBox.warning(self, u"保存失败", str(e))

    def load_layout(self):
        path = self.get_layout_path()
        if not os.path.exists(path): return
        try:
            with open(path, "r") as f:
                layout_data = json.load(f)
            if not layout_data: return
            print(u"正在恢复画布布局...")
            for item in layout_data:
                tool_id = item.get("tool_id")
                geo = item.get("geometry")
                tool_data = utils.find_tool_by_id(tool_id)
                if tool_data:
                    self.execute_and_embed(tool_data, geometry=geo)
        except Exception as e:
            print(u"加载布局失败: {}".format(e))

    def closeEvent(self, event):
        try:
            layout_data = []
            for sub in self.mdi_area.subWindowList():
                geo = sub.geometry()
                rect = [geo.x(), geo.y(), geo.width(), geo.height()]
                if hasattr(sub, "_stored_tool_data") and sub._stored_tool_data:
                    tool_data = sub._stored_tool_data
                    layout_data.append({
                        "tool_id": tool_data.get("id"),
                        "tool_name": tool_data.get("name"),
                        "geometry": rect
                    })
            with open(self.get_layout_path(), "w") as f:
                json.dump(layout_data, f, indent=4)
        except: pass
        super(CanvasWindow, self).closeEvent(event)
    
    def find_tool_data_by_name(self, name):
        all_cats = utils.load_tools_data()
        for cat in all_cats:
            for tool in cat.get("tools", []):
                if tool.get("name") == name:
                    return tool
        return None


# =========================================================================
# Main UI Class (MayaToolBoxUI)
# =========================================================================

class MayaToolBoxUI(QtWidgets.QWidget):
    _instance = None

    def toggle_canvas(self):
        if not self.canvas_window:
            self.canvas_window = CanvasWindow(parent=utils.get_maya_window())
        
        if self.canvas_window.isVisible():
            self.canvas_window.hide()
            self.btn_canvas.setStyleSheet("")
        else:
            self.canvas_window.show()
            self.btn_canvas.setStyleSheet("background-color: #5285A6; color: white;")

    def closeEvent(self, event):
        try:
            is_floating = cmds.workspaceControl(WORKSPACE_CONTROL_NAME, q=True, floating=True)
            current_state = load_window_state()
            current_state["floating"] = is_floating
            if is_floating:
                current_state["width"] = self.width()
                current_state["height"] = self.height()
            save_window_state_to_disk(current_state)
        except: pass

        if hasattr(self, 'worker_thread') and self.worker_thread.isRunning():
            try:
                self.worker_thread.finished_signal.disconnect()
            except: pass
        event.accept()

    def __init__(self, parent=None):
        super(MayaToolBoxUI, self).__init__(parent)
        self.setWindowTitle("Maya ToolBox - Modular")
        self.setMinimumWidth(300)
        self.categories = utils.load_tools_data()
        self.last_page_index = 0
        self.canvas_window = None 
        self.init_ui()

    def init_ui(self):
        self.setStyleSheet(styles.GLOBAL_STYLES)
        utils.init_all_hotkeys()
        
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(4, 4, 4, 4) 
        
        notice_text = utils.load_notice_text(config.NOTICE_FILE)
        if notice_text:
            self.notice_box = QtWidgets.QFrame()
            self.notice_box.setStyleSheet("QFrame { background-color: #263238; border-radius: 6px; border: 1px solid #37474F; }")
            notice_layout = QtWidgets.QVBoxLayout(self.notice_box)
            notice_layout.setContentsMargins(15, 15, 15, 15)
            notice_layout.setSpacing(8)
            title = QtWidgets.QLabel(u"📢  公告 / Notice")
            title.setStyleSheet("color: #64B5F6; font-weight: bold; font-size: 13px; border: none;")
            notice_layout.addWidget(title)
            content = QtWidgets.QLabel(notice_text)
            content.setWordWrap(True)
            content.setStyleSheet("color: #CFD8DC; font-size: 12px; border: none;") 
            notice_layout.addWidget(content)
            main_layout.addWidget(self.notice_box)

        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText("Search tools...")
        self.search_input.setStyleSheet("QLineEdit { background-color: #222; border: 1px solid #444; border-radius: 4px; padding: 6px; color: #EEE; }")
        self.search_input.textChanged.connect(self.filter_tools)
        main_layout.addWidget(self.search_input)

        body_layout = QtWidgets.QHBoxLayout()
        body_layout.setSpacing(0)
        body_layout.setContentsMargins(0, 0, 0, 0)
        
        # === 侧边栏 ===
        self.sidebar_container = QtWidgets.QWidget()
        self.sidebar_container.setObjectName("SidebarContainer")
        self.sidebar_container.setFixedWidth(40)
        
        sidebar_layout = QtWidgets.QVBoxLayout(self.sidebar_container)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)
        
        self.sidebar_list = QtWidgets.QListWidget()
        self.sidebar_list.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.sidebar_list.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        
        self.btn_help = QtWidgets.QPushButton(u"?")
        self.btn_help.setStyleSheet(styles.SIDE_HELP_BTN)
        self.btn_help.setFixedSize(40, 30)
        self.btn_help.setToolTip(u"工具箱使用说明")
        self.btn_help.clicked.connect(self.show_global_guide)

        self.btn_update = QtWidgets.QPushButton(u"↻") 
        self.btn_update.setObjectName("SideBtn")
        self.btn_update.setFixedSize(40, 30) 
        self.btn_update.setToolTip(u"检查更新 (Sync from NAS)")
        self.btn_update.clicked.connect(self.sync_from_nas)
        self.btn_update.setObjectName("BtnUpdate")

        self.btn_publish = QtWidgets.QPushButton(u"＋")
        self.btn_publish.setObjectName("SideBtn")
        self.btn_publish.setFixedSize(40, 30)
        self.btn_publish.setToolTip(u"发布工具 (Publish)")
        self.btn_publish.clicked.connect(self.open_publish_dialog)

        self.btn_canvas = QtWidgets.QPushButton(u"▣") 
        self.btn_canvas.setObjectName("SideBtn")
        self.btn_canvas.setFixedSize(40, 30)
        self.btn_canvas.setToolTip(u"打开工具画布 (Tool Canvas)")
        self.btn_canvas.clicked.connect(self.toggle_canvas)
        
        self.btn_dock_toggle = QtWidgets.QPushButton(u"❐") 
        self.btn_dock_toggle.setObjectName("SideBtn")
        self.btn_dock_toggle.setFixedSize(40, 30)
        self.btn_dock_toggle.setToolTip(u"切换 停靠/浮动 (Toggle Dock/Float)")
        self.btn_dock_toggle.clicked.connect(self.toggle_dock_mode)

        sidebar_layout.addWidget(self.btn_canvas)
        sidebar_layout.addWidget(self.btn_dock_toggle)
        sidebar_layout.addWidget(self.sidebar_list)
        
        sidebar_layout.addWidget(self.btn_help)
        sidebar_layout.addWidget(self.btn_update)
        sidebar_layout.addWidget(self.btn_publish)
        
        self.pages = QtWidgets.QStackedWidget()
        self.populate_ui()
        self.help_page = self.create_help_page()
        self.pages.addWidget(self.help_page)
        self.sidebar_list.currentRowChanged.connect(self.pages.setCurrentIndex)
        body_layout.addWidget(self.sidebar_container)
        body_layout.addWidget(self.pages)
        main_layout.addLayout(body_layout)
        self.check_for_updates()

    def toggle_dock_mode(self):
        try:
            is_floating = cmds.workspaceControl(WORKSPACE_CONTROL_NAME, q=True, floating=True)
            if is_floating:
                cmds.workspaceControl(WORKSPACE_CONTROL_NAME, e=True, floating=False)
                cmds.workspaceControl(WORKSPACE_CONTROL_NAME, e=True, tabToControl=("AttributeEditor", -1))
            else:
                cmds.workspaceControl(WORKSPACE_CONTROL_NAME, e=True, floating=True)
            
            new_state = load_window_state()
            new_state["floating"] = not is_floating
            save_window_state_to_disk(new_state)
        except Exception as e:
            print(u"切换停靠模式失败: {}".format(e))

    def check_for_updates(self):
        self.check_worker = worker.CheckUpdateWorker()
        self.check_worker.result_signal.connect(self.on_check_finished)
        self.check_worker.start()

    def on_check_finished(self, has_update, server_data):
        if has_update:
            self.btn_update.setStyleSheet("""
                QPushButton { background-color: #FBC02D; color: #000; font-weight: bold; border: 1px solid #F57F17; }
                QPushButton:hover { background-color: #FDD835; }
            """)
            self.btn_update.setToolTip(u"发现新版本！点击更新")
        else:
            self.btn_update.setStyleSheet("") 
            self.btn_update.setToolTip(u"检查更新 (Sync from NAS)")

    def create_help_page(self):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(0)
        header_widget = QtWidgets.QWidget()
        header_widget.setStyleSheet("background-color: #222; border-bottom: 1px solid #444;")
        header_layout = QtWidgets.QHBoxLayout(header_widget)
        header_layout.setContentsMargins(10, 10, 10, 10)
        header_layout.setSpacing(10)
        self.btn_back = QtWidgets.QPushButton(u"◀ 返回")
        self.btn_back.setFixedSize(60, 24)
        self.btn_back.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_back.setStyleSheet("QPushButton { color: #64B5F6; border: 1px solid #444; border-radius: 3px; background-color: #333; font-weight: bold; } QPushButton:hover { background-color: #444; color: #FFF; }")
        self.btn_back.clicked.connect(self.go_back)
        self.help_title = QtWidgets.QLabel(u"使用说明")
        self.help_title.setStyleSheet("color: #FFF; font-weight: bold; font-size: 14px; border: none;")
        header_layout.addWidget(self.btn_back)
        header_layout.addWidget(self.help_title)
        header_layout.addStretch()
        layout.addWidget(header_widget)
        self.help_scroll = QtWidgets.QScrollArea()
        self.help_scroll.setWidgetResizable(True)
        self.help_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.help_scroll.setStyleSheet("background-color: #2B2B2B;")
        self.help_content_widget = QtWidgets.QWidget()
        self.help_content_layout = QtWidgets.QVBoxLayout(self.help_content_widget)
        self.help_content_layout.setSpacing(4) 
        self.help_content_layout.setContentsMargins(10, 10, 10, 20)
        self.help_content_layout.setAlignment(QtCore.Qt.AlignTop) 
        self.help_scroll.setWidget(self.help_content_widget)
        layout.addWidget(self.help_scroll)
        return page

    def populate_ui(self):
        self.sidebar_list.clear()
        while self.pages.count():
            widget = self.pages.widget(0)
            self.pages.removeWidget(widget)
            widget.deleteLater()
        if not self.categories:
            lbl = QtWidgets.QLabel(u"无数据")
            lbl.setAlignment(QtCore.Qt.AlignCenter)
            self.pages.addWidget(lbl)
            return
        for cat_data in self.categories:
            raw_name = cat_data.get("name", "Unknown")
            is_favorites = (u"收藏夹" in raw_name)
            scroll = self.create_tab_content(cat_data.get("tools", []), append_recent=is_favorites)
            self.pages.addWidget(scroll)
            clean_name = raw_name.replace(u"", "").strip() 
            vertical_name = "\n".join(list(clean_name))
            item = QtWidgets.QListWidgetItem(vertical_name)
            item.setTextAlignment(QtCore.Qt.AlignCenter)
            if is_favorites: item.setToolTip(u"收藏夹")
            else: item.setToolTip(raw_name)
            self.sidebar_list.addItem(item)
        self.help_page = self.create_help_page()
        self.pages.addWidget(self.help_page)
        if self.sidebar_list.count() > 0:
            self.sidebar_list.setCurrentRow(0)

    def create_tab_content(self, tools_list, append_recent=False):
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setStyleSheet("background-color: #2B2B2B;") 
        container = QtWidgets.QWidget()
        container.setStyleSheet("background-color: transparent;")
        main_v_layout = QtWidgets.QVBoxLayout(container)
        main_v_layout.setSpacing(10)
        main_v_layout.setContentsMargins(5, 5, 5, 5)
        if tools_list:
            grid_widget = QtWidgets.QWidget()
            grid_layout = QtWidgets.QGridLayout(grid_widget)
            grid_layout.setSpacing(5) 
            grid_layout.setContentsMargins(0, 0, 0, 0)
            COLUMNS = 4
            for i, tool in enumerate(tools_list):
                btn = widgets.ToolButton(tool, parent=self)
                row = i // COLUMNS
                col = i % COLUMNS
                grid_layout.addWidget(btn, row, col, QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)
            total_rows = (len(tools_list) + COLUMNS - 1) // COLUMNS
            grid_layout.setRowStretch(total_rows, 1)
            grid_layout.setColumnStretch(COLUMNS, 1) 
            main_v_layout.addWidget(grid_widget)
        else:
            if append_recent: 
                empty_lbl = QtWidgets.QLabel(u"（暂无收藏，右键添加）")
                empty_lbl.setStyleSheet("color: #666; font-style: italic; margin: 10px;")
                empty_lbl.setAlignment(QtCore.Qt.AlignCenter)
                main_v_layout.addWidget(empty_lbl)
        main_v_layout.addStretch()
        if append_recent:
            recent_tools = utils.get_recent_tools_data()
            if recent_tools:
                recent_tools = recent_tools[:8]
                recent_container = QtWidgets.QWidget()
                recent_container.setStyleSheet("background-color: #262626; border-radius: 6px;")
                recent_layout = QtWidgets.QVBoxLayout(recent_container)
                recent_layout.setContentsMargins(5, 5, 5, 5)
                recent_layout.setSpacing(5)
                lbl_recent = QtWidgets.QLabel(u"最近使用")
                lbl_recent.setStyleSheet("color: #666; font-weight: bold; font-size: 11px; margin-left: 2px;")
                recent_layout.addWidget(lbl_recent)
                recent_grid_widget = QtWidgets.QWidget()
                recent_grid_widget.setStyleSheet("background-color: transparent;")
                recent_grid = QtWidgets.QGridLayout(recent_grid_widget)
                recent_grid.setSpacing(5)
                recent_grid.setContentsMargins(0, 0, 0, 0)
                COLUMNS = 4
                for i, tool in enumerate(recent_tools):
                    btn = widgets.ToolButton(tool, parent=self)
                    btn.setFixedSize(70, 70) 
                    row = i // COLUMNS
                    col = i % COLUMNS
                    recent_grid.addWidget(btn, row, col, QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)
                recent_layout.addWidget(recent_grid_widget)
                main_v_layout.addWidget(recent_container)
        scroll.setWidget(container)
        return scroll

    def on_category_changed(self, index):
        if index >= 0:
            self.pages.setCurrentIndex(index)

    def switch_to_help_view(self, title, content):
        """
        【修复】切换到帮助页面并渲染内容
        """
        # 1. 记录当前页面索引，以便点击“返回”时能回去
        current = self.pages.currentIndex()
        # 只有当当前不在帮助页时，才更新 last_page_index，防止在帮助页内跳转丢失历史
        if current != self.pages.count() - 1:
            self.last_page_index = current
        
        # 2. 清除侧边栏选中状态，表明现在处于详情视图
        self.sidebar_list.clearSelection()
        
        # 3. 设置标题
        self.help_title.setText(title)
        
        # 4. 清空旧内容
        while self.help_content_layout.count():
            item = self.help_content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # 5. 渲染新内容 (复用 styles.py 里的样式)
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if not line: continue 
            
            if line.startswith("#"):
                # 标题
                lbl = QtWidgets.QLabel(line.lstrip("#").strip())
                lbl.setStyleSheet(styles.HELP_TITLE_LBL)
                lbl.setWordWrap(True)
                self.help_content_layout.addWidget(lbl)
            elif line.startswith("---"):
                # 分割线
                sep = QtWidgets.QFrame()
                sep.setFrameShape(QtWidgets.QFrame.HLine)
                sep.setStyleSheet("color: #444; margin: 10px 0;")
                self.help_content_layout.addWidget(sep)
            elif line.startswith("-") or line.startswith(u"•") or line.startswith("*"):
                # 列表项
                text = line.lstrip("-").lstrip(u"•").lstrip("*").strip()
                lbl = QtWidgets.QLabel(u"• " + text)
                lbl.setStyleSheet(styles.HELP_ITEM_LBL)
                lbl.setWordWrap(True)
                self.help_content_layout.addWidget(lbl)
            else:
                # 普通文本
                lbl = QtWidgets.QLabel(line)
                if u"注意" in line or u"Tip" in line or u"警告" in line:
                     lbl.setStyleSheet(styles.HELP_HIGHLIGHT_LBL)
                else:
                     lbl.setStyleSheet(styles.HELP_BODY_LBL)
                lbl.setWordWrap(True)
                lbl.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse) # 允许复制文字
                self.help_content_layout.addWidget(lbl)
        
        self.help_content_layout.addStretch()
        
        # 6. 切换 Stack 页面到最后一页 (Help Page)
        self.pages.setCurrentIndex(self.pages.count() - 1)

    def go_back(self):
        target_idx = self.last_page_index
        max_content_index = self.pages.count() - 2 
        if max_content_index < 0: max_content_index = 0
        if target_idx > max_content_index:
            target_idx = 0
        self.pages.setCurrentIndex(target_idx)
        if self.sidebar_list.count() > target_idx:
            self.sidebar_list.setCurrentRow(target_idx)

    def show_global_guide(self):
        content = utils.load_guide_text()
        if "<html>" in content:
            content = u"# 读取到的是HTML格式，请修改 guide.txt 为纯文本格式以获得最佳显示效果。\n" + content
        self.switch_to_help_view(u"工具箱使用说明", content)

    def show_tool_guide(self, tool_data):
        """
        【修复】显示工具详情页
        将工具的 help_content 格式化后，切换到 Help Page 显示
        """
        name = tool_data.get("name", "Unknown")
        help_content = tool_data.get("help_content", "")
        tooltip = tool_data.get("tooltip", "")

        # 如果没有详细说明，自动生成一个基础说明
        if not help_content:
            # 构造 Markdown 风格的文本
            help_content = u"# {}\n\n{}\n\n---\n*注意：该工具暂无详细使用文档。*".format(name, tooltip)
        
        # 调用切换视图方法
        self.switch_to_help_view(u"工具说明: " + name, help_content)  

    def filter_tools(self, text):
        text = text.lower()
        for i in range(self.pages.count()):
            scroll = self.pages.widget(i)
            if isinstance(scroll, QtWidgets.QScrollArea):
                container = scroll.widget()
                if container and container.layout():
                    layout = container.layout()
                    count = layout.count()
                    for j in range(count):
                        item = layout.itemAt(j)
                        if item and item.widget() and isinstance(item.widget(), widgets.ToolButton):
                            w = item.widget()
                            name = w.tool_data.get("name", "").lower()
                            tooltip = w.tool_data.get("tooltip", "").lower()
                            if text in name or text in tooltip:
                                w.setVisible(True)
                            else:
                                w.setVisible(False)

    def reload_ui(self):
        self.categories = utils.load_tools_data()
        current_idx = self.sidebar_list.currentRow()
        self.populate_ui()
        if current_idx >= 0 and current_idx < self.sidebar_list.count():
            self.sidebar_list.setCurrentRow(current_idx)
        elif self.sidebar_list.count() > 0:
            self.sidebar_list.setCurrentRow(0)

    def sync_from_nas(self):
        sender = self.sender()
        if sender:
            sender.setEnabled(False)
            sender.setText(u"...") 
        self.worker_thread = worker.UpdateWorker()
        self.worker_thread.finished_signal.connect(self.on_update_finished)
        self.worker_thread.start()

    def on_update_finished(self, success, message):
        self.btn_update.setEnabled(True)
        self.btn_update.setText(u"↻")
        self.btn_update.setStyleSheet("") 
        self.btn_update.setToolTip(u"检查更新 (Sync from NAS)")
        if success:
            if message == "NO_UPDATES":
                QtWidgets.QMessageBox.information(self, u"提示", u"当前已是最新版本，无需更新。")
            else:
                reply = QtWidgets.QMessageBox.information(
                    self, "更新成功", 
                    u"{}\n是否立即刷新界面？".format(message),
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
                )
                if reply == QtWidgets.QMessageBox.Yes:
                    self.reload_ui_full_restart()
        else:
            QtWidgets.QMessageBox.warning(self, "更新失败", message)
            self.reload_ui()

    def open_publish_dialog(self):
        dialog = dialogs.PublishDialog(self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            reply = QtWidgets.QMessageBox.question(
                self, u"刷新", u"发布成功，是否刷新界面以查看新工具？",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )
            if reply == QtWidgets.QMessageBox.Yes:
                self.reload_ui()

    def reload_ui_full_restart(self):
        global _instance
        if _instance:
            try: _instance.deleteLater()
            except: pass
        _instance = None
        show()

# =========================================================================
# 启动入口
# =========================================================================

WORKSPACE_CONTROL_NAME = "HKToolboxWorkspaceControl"

def show():
    if MayaToolBoxUI._instance:
        try:
            MayaToolBoxUI._instance.close()
            MayaToolBoxUI._instance.deleteLater()
        except: pass
        MayaToolBoxUI._instance = None

    if cmds.workspaceControl(WORKSPACE_CONTROL_NAME, exists=True):
        cmds.deleteUI(WORKSPACE_CONTROL_NAME)
        cmds.workspaceControlState(WORKSPACE_CONTROL_NAME, remove=True)

    state = load_window_state()
    start_floating = state.get("floating", False)
    
    kwargs = {
        "label": "HK ToolBox",
        "uiScript": "pass",
        "retain": False, 
        "loadImmediately": True,
        "initialWidth": 350
    }
    
    if start_floating:
        kwargs["floating"] = True
        kwargs["initialWidth"] = state.get("width", 350)
        kwargs["initialHeight"] = state.get("height", 800)
    else:
        kwargs["tabToControl"] = ("AttributeEditor", -1)

    cmds.workspaceControl(WORKSPACE_CONTROL_NAME, **kwargs)

    ptr = omui.MQtUtil.findControl(WORKSPACE_CONTROL_NAME)
    if ptr:
        dock_widget = wrapInstance(int(ptr), QtWidgets.QWidget)
        
        layout = dock_widget.layout()
        if not layout:
            layout = QtWidgets.QVBoxLayout(dock_widget)
        
        layout.setContentsMargins(0, 0, 0, 0)
        
        app = MayaToolBoxUI(parent=dock_widget)
        layout.addWidget(app)
        
        app.show()
        
        MayaToolBoxUI._instance = app
    else:
        print("Error: Could not create WorkspaceControl.")