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
from . import native_ui

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
# Main UI Class (MayaToolBoxUI)
# =========================================================================
class MayaToolBoxUI(QtWidgets.QWidget):
    _instance = None

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

        self.btn_publish = QtWidgets.QPushButton(u"＋")
        self.btn_publish.setObjectName("SideBtn")
        self.btn_publish.setFixedSize(40, 30)
        self.btn_publish.setToolTip(u"发布工具 (Publish)")
        self.btn_publish.clicked.connect(self.open_publish_dialog)

        # ------------------- 核心修改：雷达磁吸按钮 -------------------
        self.btn_magnet = QtWidgets.QPushButton(u"🧲") 
        self.btn_magnet.setObjectName("SideBtn")
        self.btn_magnet.setFixedSize(40, 30)
        self.btn_magnet.setToolTip(u"磁化活跃窗口 (可吸附任意Maya独立面板)")
        self.btn_magnet.clicked.connect(self.radar_magnetize_active)
        # --------------------------------------------------------------
        
        self.btn_dock_toggle = QtWidgets.QPushButton(u"❐") 
        self.btn_dock_toggle.setObjectName("SideBtn")
        self.btn_dock_toggle.setFixedSize(40, 30)
        self.btn_dock_toggle.setToolTip(u"切换 停靠/浮动 (Toggle Dock/Float)")
        self.btn_dock_toggle.clicked.connect(self.toggle_dock_mode)

        sidebar_layout.addWidget(self.btn_magnet)
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

    # ------------------- 核心功能：手动磁化与执行磁化 -------------------
    def radar_magnetize_active(self):
        """【修改】现在这个按钮变成了呼出超级工具包面板"""
        from toolbox_core.native_ui import SuperPanelManager
        SuperPanelManager.toggle_panel()

    def run_tool_and_magnetize(self, tool_data):
        """智能分发：如果面板开着就塞进面板，没开就正常弹出"""
        from toolbox_core.native_ui import SuperPanelManager
        
        # 1. 探测超级工具包是否开启
        if SuperPanelManager.is_panel_open():
            # 执行剥离并注入面板
            success = SuperPanelManager.run_and_embed(tool_data)
            if success:
                try: cmds.inViewMessage(amg=u'<span style="color:#00FF00;">已吸附到超级面板: {}</span>'.format(tool_data.get("name")), pos='midCenterTop', fade=True)
                except: pass
            else:
                print(u"该工具无独立UI，直接执行完毕。")
        else:
            # 2. 面板没开，走最原始的安全执行，让窗口自己弹出来
            import toolbox_core.worker as worker
            try:
                worker.execute_tool(tool_data)
            except Exception as e:
                print(u"执行异常: {}".format(e))

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
                # ---------------- 接管点击事件 ----------------
                try: btn.clicked.disconnect()
                except: pass
                btn.clicked.connect(lambda checked=False, t=tool: self.run_tool_and_magnetize(t))
                # ----------------------------------------------
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
                    # ---------------- 接管点击事件 ----------------
                    try: btn.clicked.disconnect()
                    except: pass
                    btn.clicked.connect(lambda checked=False, t=tool: self.run_tool_and_magnetize(t))
                    # ----------------------------------------------
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
        current = self.pages.currentIndex()
        if current != self.pages.count() - 1:
            self.last_page_index = current
        
        self.sidebar_list.clearSelection()
        self.help_title.setText(title)
        
        while self.help_content_layout.count():
            item = self.help_content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if not line: continue 
            
            if line.startswith("#"):
                lbl = QtWidgets.QLabel(line.lstrip("#").strip())
                lbl.setStyleSheet(styles.HELP_TITLE_LBL)
                lbl.setWordWrap(True)
                self.help_content_layout.addWidget(lbl)
            elif line.startswith("---"):
                sep = QtWidgets.QFrame()
                sep.setFrameShape(QtWidgets.QFrame.HLine)
                sep.setStyleSheet("color: #444; margin: 10px 0;")
                self.help_content_layout.addWidget(sep)
            elif line.startswith("-") or line.startswith(u"•") or line.startswith("*"):
                text = line.lstrip("-").lstrip(u"•").lstrip("*").strip()
                lbl = QtWidgets.QLabel(u"• " + text)
                lbl.setStyleSheet(styles.HELP_ITEM_LBL)
                lbl.setWordWrap(True)
                self.help_content_layout.addWidget(lbl)
            else:
                lbl = QtWidgets.QLabel(line)
                if u"注意" in line or u"Tip" in line or u"警告" in line:
                     lbl.setStyleSheet(styles.HELP_HIGHLIGHT_LBL)
                else:
                     lbl.setStyleSheet(styles.HELP_BODY_LBL)
                lbl.setWordWrap(True)
                lbl.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
                self.help_content_layout.addWidget(lbl)
        
        self.help_content_layout.addStretch()
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
        name = tool_data.get("name", "Unknown")
        help_content = tool_data.get("help_content", "")
        tooltip = tool_data.get("tooltip", "")

        if not help_content:
            help_content = u"# {}\n\n{}\n\n---\n*注意：该工具暂无详细使用文档。*".format(name, tooltip)
        
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