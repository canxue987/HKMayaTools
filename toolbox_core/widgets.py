# -*- coding: utf-8 -*-
import os
import json

try:
    from PySide2 import QtWidgets, QtCore, QtGui
except ImportError:
    from PySide6 import QtWidgets, QtCore, QtGui

# 导入同级模块
from . import config
from . import utils
from . import worker
# 【关键】导入弹窗模块，用于右键菜单调用
from . import dialogs 

class ToolButton(QtWidgets.QToolButton): # <--- 修改1: 改为继承 QToolButton
    """
    自定义工具按钮组件
    包含：图标显示、左键执行、右键菜单(收藏/编辑/快捷键)
    """
    def __init__(self, tool_data, parent=None):
        super(ToolButton, self).__init__(parent)
        self.tool_data = tool_data
        
        # 开启右键菜单策略
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_menu)
        
        # 绑定左键点击
        self.clicked.connect(self.click_tool)
        
        self.init_ui()

    def init_ui(self):
        # 1. 尺寸设置 
        # (宽72不变，高度增加到95以容纳文字)
        self.setFixedSize(72, 72) 
        
        # <--- 修改2: 设置文字在图标下方
        self.setToolButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon)
        
        # 2. 文字处理
        name = self.tool_data.get("name", "Unknown")
        # 简单截断防止过长换行太丑 (可选)
        if len(name) > 8:
            # 如果全是中文，8个字可能也会换行，这里简单处理
            pass 
        self.setText(name)

        # 3. 图标处理
        icon_name = self.tool_data.get("icon", "default.png")
        
        # 判断是绝对路径还是相对路径
        if os.path.isabs(icon_name):
            icon_path = icon_name
        else:
            icon_path = os.path.join(config.ICONS_DIR, icon_name)
            
        if os.path.exists(icon_path):
            self.setIcon(QtGui.QIcon(icon_path))
        else:
            # 没图标时，显示默认或空图标
            self.setIcon(QtGui.QIcon())
            
        # 图标稍微调小一点，给文字腾地儿
        self.setIconSize(QtCore.QSize(40, 40)) 
        
        # 4. Tooltip 优化
        tooltip = self.tool_data.get("tooltip", "")
        if tooltip:
            self.setToolTip(u"<b>{}</b><br>{}".format(name, tooltip))
        else:
            self.setToolTip(name)
            
        # 5. 按钮独立样式 (深色块 + 圆角)
        # <--- 修改3: 选择器改为 QToolButton，并增加 font-size
        is_fav = self.tool_data.get("favorite", False)
        # 如果收藏了用亮黄色(#FFEB3B)，否则用灰白色(#EEE)
        text_color = "#FFEB3B" if is_fav else "#EEE"

        self.setStyleSheet("""
            QToolButton {{
                background-color: #333;
                border: 1px solid #444;
                border-radius: 8px;
                color: {0}; /* <--- 这里填入动态颜色 */
                font-weight: bold;
                font-family: "Microsoft YaHei";
                font-size: 11px;
                padding-top: 5px;
            }}
            QToolButton:hover {{
                background-color: #444;
                border-color: #666;
            }}
            QToolButton:pressed {{
                background-color: #222;
                border-color: #555;
            }}
        """.format(text_color)) 
        # === 修改结束 ===
    
    # === 【新增】 拖拽支持 ===
    def mousePressEvent(self, event):
        # 记录按下位置，用于判断是否是拖拽
        if event.button() == QtCore.Qt.LeftButton:
            self._drag_start_pos = event.pos()
        super(ToolButton, self).mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        # 如果没有按下左键，忽略
        if not (event.buttons() & QtCore.Qt.LeftButton):
            return
        
        # 判断拖拽距离是否超过阈值（防抖动）
        if (event.pos() - self._drag_start_pos).manhattanLength() < QtWidgets.QApplication.startDragDistance():
            return

        # 开始拖拽
        drag = QtGui.QDrag(self)
        mime_data = QtCore.QMimeData()
        
        # 将工具数据转为 JSON 字符串传递
        mime_data.setText(json.dumps(self.tool_data))
        drag.setMimeData(mime_data)
        
        # 设置拖拽时的图标（截取当前按钮的样子）
        pixmap = self.grab()
        drag.setPixmap(pixmap)
        # 设置热点在鼠标点击的位置
        drag.setHotSpot(event.pos())
        
        drag.exec_(QtCore.Qt.CopyAction)

    def click_tool(self):
        """
        执行工具 (回归纯粹版本)
        点击按钮只负责执行，不负责画布吸附。
        想吸附请拖拽到画布中。
        """
        # 1. 执行工具
        try:
            worker.execute_tool(self.tool_data)
        except Exception as e:
            print(u"工具执行出错: {}".format(e))

        # 2. 记录最近使用
        try:
            utils.add_to_recent(self.tool_data)
        except: pass

    def show_menu(self, pos):
        """显示右键菜单"""
        menu = QtWidgets.QMenu(self)
        # 注意：QMenu 的样式会自动继承 styles.py 里定义的全局样式
        
        # 1. 收藏
        fav = self.tool_data.get("favorite", False)
        action_fav = menu.addAction(u"取消收藏" if fav else u"加入收藏")
        action_fav.triggered.connect(self.toggle_fav)
        
        menu.addSeparator()
        
        # 2. 快捷键
        tool_id = self.tool_data.get("id", self.tool_data.get("name"))
        hotkeys = utils.load_hotkeys()
        current_key = hotkeys.get(tool_id, "")
        
        hk_text = u"设置快捷键"
        if current_key:
            hk_text += u" ({})".format(current_key)
            
        action_hk = menu.addAction(hk_text)
        action_hk.triggered.connect(lambda: self.open_hotkey_dialog(current_key))
        
        menu.addSeparator()

        # 【新增】使用说明
        # 不带图标，纯文字
        action_help = menu.addAction(u"使用说明")
        action_help.triggered.connect(self.show_help)

        menu.addSeparator()
        
        # 3. 编辑
        action_edit = menu.addAction(u"编辑工具")
        action_edit.triggered.connect(self.open_edit_dialog)
        
        menu.exec_(self.mapToGlobal(pos))

    def show_help(self):
        """修复：调用主窗口的帮助页面显示工具说明"""
        ui = self._get_main_ui()
        if ui:
            ui.show_tool_guide(self.tool_data)
        else:
            # 兜底方案：如果找不到主界面，还是弹窗显示
            QtWidgets.QMessageBox.information(self, "Info", u"使用说明: " + self.tool_data.get("tooltip", u"暂无"))

    def toggle_fav(self):
        if utils.toggle_tool_favorite(self.tool_data):
            self.reload_parent_ui()

    def open_edit_dialog(self):
        # 调用 dialogs 里的 EditDialog
        dialog = dialogs.EditDialog(self.tool_data, self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            self.reload_parent_ui()

    def open_hotkey_dialog(self, current_key):
        # 调用 dialogs 里的 HotkeyDialog
        dialog = dialogs.HotkeyDialog(self.tool_data, current_key, self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            new_key = dialog.get_key_string()
            tool_id = self.tool_data.get("id", self.tool_data.get("name"))
            
            hotkeys = utils.load_hotkeys()
            
            # 先解绑旧的
            if current_key:
                utils.unregister_hotkey(current_key)
                if tool_id in hotkeys: del hotkeys[tool_id]

            if new_key:
                # 注册新的
                success, msg = utils.register_hotkey(tool_id, new_key)
                if success:
                    hotkeys[tool_id] = new_key
                    utils.save_hotkeys(hotkeys)
                    QtWidgets.QMessageBox.information(self, "Success", u"快捷键已绑定: " + new_key)
                else:
                    QtWidgets.QMessageBox.warning(self, "Error", u"绑定失败: " + msg)
            else:
                # 清除
                utils.save_hotkeys(hotkeys)
                QtWidgets.QMessageBox.information(self, "Success", u"快捷键已清除")

    def reload_parent_ui(self):
        """修复：即时刷新界面（用于收藏/取消收藏后）"""
        ui = self._get_main_ui()
        if ui:
            ui.reload_ui()
        else:
            print(u"Warning: 无法找到主窗口实例，界面未刷新。")

    def _get_main_ui(self):
        """
        【修复核心】向上遍历查找 MayaToolBoxUI 主窗口实例。
        解决了在 Dock 模式下 self.window() 获取到 Maya 主窗口导致调用失败的问题。
        """
        parent = self.parent()
        while parent:
            # 通过检查是否有 reload_ui 方法来判断是否是我们的主窗口
            if hasattr(parent, "reload_ui") and hasattr(parent, "show_tool_guide"):
                return parent
            parent = parent.parent()
        return None