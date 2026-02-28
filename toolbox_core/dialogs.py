# -*- coding: utf-8 -*-
import os
import json
import io
import time

try:
    from PySide2 import QtWidgets, QtCore, QtGui
except ImportError:
    from PySide6 import QtWidgets, QtCore, QtGui

# 导入同级模块
from . import config
from . import utils
from . import worker
from . import styles 

# =========================================================================
# 1. 新建分类弹窗 (保持不变)
# =========================================================================
class NewCategoryDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(NewCategoryDialog, self).__init__(parent)
        self.setWindowTitle(u"新建分类")
        self.resize(300, 150)
        self.setModal(True)
        
        self.result_filename = None
        self.result_displayname = None
        
        self.init_ui()
        
    def init_ui(self):
        self.setStyleSheet(styles.DIALOG_STYLES)
        
        layout = QtWidgets.QVBoxLayout(self)
        
        layout.addWidget(QtWidgets.QLabel(u"文件名 (用于排序, 建议带序号):"))
        self.input_filename = QtWidgets.QLineEdit()
        self.input_filename.setPlaceholderText(u"例如: 50_Animation")
        layout.addWidget(self.input_filename)
        
        layout.addWidget(QtWidgets.QLabel(u"显示名称 (UI显示的标签名):"))
        self.input_display = QtWidgets.QLineEdit()
        self.input_display.setPlaceholderText(u"例如: 动画工具")
        layout.addWidget(self.input_display)
        
        btn_layout = QtWidgets.QHBoxLayout()
        btn_ok = QtWidgets.QPushButton(u"确定")
        btn_ok.clicked.connect(self.on_accept)
        btn_cancel = QtWidgets.QPushButton(u"取消")
        btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)
        
    def on_accept(self):
        f_name = self.input_filename.text().strip()
        d_name = self.input_display.text().strip()
        
        if not f_name:
            QtWidgets.QMessageBox.warning(self, "Error", u"文件名不能为空")
            return
            
        if not f_name.endswith(".json"):
            f_name += ".json"
            
        if not d_name:
            d_name = f_name.replace(".json", "")
            
        self.result_filename = f_name
        self.result_displayname = d_name
        self.accept()


# =========================================================================
# 2. 发布工具弹窗 (已修改：增加使用说明)
# =========================================================================
class PublishDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(PublishDialog, self).__init__(parent)
        self.setWindowTitle(u"发布工具")
        self.resize(500, 700) # 稍微调高一点高度
        self.setModal(True)
        self.icon_path = ""
        
        self.new_category_map = {} 
        
        self.init_ui()
        self.refresh_categories()

    def init_ui(self):
        self.setStyleSheet(styles.DIALOG_STYLES)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(25, 25, 25, 25)

        # === 头部区域 ===
        header_layout = QtWidgets.QHBoxLayout()
        header_layout.setSpacing(15)
        
        self.btn_icon_preview = QtWidgets.QPushButton()
        self.btn_icon_preview.setFixedSize(64, 64)
        self.btn_icon_preview.setIconSize(QtCore.QSize(40, 40))
        self.btn_icon_preview.setToolTip(u"点击选择图标")
        self.btn_icon_preview.clicked.connect(self.browse_icon)
        self.btn_icon_preview.setStyleSheet(styles.ICON_PREVIEW_BTN)
        header_layout.addWidget(self.btn_icon_preview)
        
        name_layout = QtWidgets.QVBoxLayout()
        name_layout.setSpacing(6)
        name_layout.setContentsMargins(0, 2, 0, 2)
        
        lbl_name = QtWidgets.QLabel(u"工具名称")
        lbl_name.setStyleSheet("font-weight: bold; color: #DDD; font-size: 13px;")
        
        self.input_name = QtWidgets.QLineEdit()
        self.input_name.setPlaceholderText(u"输入工具名称...")
        self.input_name.setStyleSheet("font-weight: bold; font-size: 14px; padding: 6px;")
        
        name_layout.addWidget(lbl_name)
        name_layout.addWidget(self.input_name)
        
        header_layout.addLayout(name_layout)
        layout.addLayout(header_layout)

        # === 表单区域 ===
        form_layout = QtWidgets.QGridLayout()
        form_layout.setVerticalSpacing(12)
        form_layout.setHorizontalSpacing(10)
        
        # Row 0: 分类
        form_layout.addWidget(QtWidgets.QLabel(u"目标分类:"), 0, 0)
        cat_layout = QtWidgets.QHBoxLayout()
        cat_layout.setSpacing(5)
        self.combo_category = QtWidgets.QComboBox()
        self.combo_category.setMinimumHeight(28)
        self.combo_category.setEnabled(False)
        self.combo_category.setPlaceholderText(u"需管理员权限")
        self.btn_new_cat = QtWidgets.QPushButton(u"+")
        self.btn_new_cat.setFixedSize(30, 28)
        self.btn_new_cat.setToolTip(u"新建分类")
        self.btn_new_cat.setEnabled(False) 
        self.btn_new_cat.clicked.connect(self.add_new_category)
        cat_layout.addWidget(self.combo_category)
        cat_layout.addWidget(self.btn_new_cat)
        form_layout.addLayout(cat_layout, 0, 1)

        # Row 1: 简短提示
        form_layout.addWidget(QtWidgets.QLabel(u"一句话提示:"), 1, 0)
        self.input_tooltip = QtWidgets.QLineEdit()
        self.input_tooltip.setPlaceholderText(u"鼠标悬停时的说明文字")
        form_layout.addWidget(self.input_tooltip, 1, 1)

        # Row 2: [新增] 详细使用说明
        form_layout.addWidget(QtWidgets.QLabel(u"详细说明:"), 2, 0, QtCore.Qt.AlignTop)
        self.input_help = QtWidgets.QTextEdit()
        self.input_help.setPlaceholderText(u"输入详细的使用教程，显示在帮助页面...")
        self.input_help.setFixedHeight(60) # 设置一个较小的高度
        form_layout.addWidget(self.input_help, 2, 1)

        # Row 3: 密码
        form_layout.addWidget(QtWidgets.QLabel(u"管理密码:"), 3, 0)
        self.input_pwd = QtWidgets.QLineEdit()
        self.input_pwd.setEchoMode(QtWidgets.QLineEdit.Password)
        self.input_pwd.setPlaceholderText(u"输入密码以同步到NAS，否则仅存本地")
        self.input_pwd.textChanged.connect(self.check_admin_rights)
        form_layout.addWidget(self.input_pwd, 3, 1)
        
        layout.addLayout(form_layout)

        # === 代码区域 ===
        lbl_code = QtWidgets.QLabel(u"脚本代码:")
        lbl_code.setStyleSheet("margin-top: 8px; font-weight: bold; color: #DDD;")
        layout.addWidget(lbl_code)
        
        self.input_cmd = QtWidgets.QTextEdit()
        self.input_cmd.setPlaceholderText("import tool_xxx\ntool_xxx.run()\n\n(如果代码较长，会自动保存为脚本文件)")
        layout.addWidget(self.input_cmd)

        # === 底部按钮 ===
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.setSpacing(10)
        
        self.btn_cancel = QtWidgets.QPushButton(u"取消")
        self.btn_cancel.setFixedSize(80, 32)
        self.btn_cancel.clicked.connect(self.reject)
        
        self.btn_ok = QtWidgets.QPushButton(u"发布 (本地)")
        self.btn_ok.setMinimumWidth(120)
        self.btn_ok.setFixedHeight(32)
        self.btn_ok.setStyleSheet(styles.BTN_GRAY)
        self.btn_ok.clicked.connect(self.on_publish)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_ok)
        layout.addLayout(btn_layout)

    def refresh_categories(self):
        self.combo_category.clear()
        if os.path.exists(config.MODULES_DIR):
            files = sorted([f for f in os.listdir(config.MODULES_DIR) if f.endswith(".json")])
            for f in files:
                if f == config.USER_FILE_NAME: continue
                path = os.path.join(config.MODULES_DIR, f)
                
                # === 修改点：使用安全加载，无需 try...except ===
                data = utils.safe_json_load(path, default_val={})
                if data: # 如果成功读到内容
                    name = data.get("name", f)
                    self.combo_category.addItem(name, f)

    def browse_icon(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select Icon", "", "Images (*.png *.jpg *.svg)")
        if path:
            self.icon_path = path
            self.btn_icon_preview.setIcon(QtGui.QIcon(path))
            self.btn_icon_preview.setIconSize(QtCore.QSize(48, 48))

    def check_admin_rights(self, text):
        if text == config.ADMIN_PASSWORD:
            self.combo_category.setEnabled(True)
            self.btn_new_cat.setEnabled(True)
            self.btn_ok.setText(u"发布 (NAS)")
            self.btn_ok.setStyleSheet(styles.BTN_GREEN)
        else:
            self.combo_category.setEnabled(False)
            self.btn_new_cat.setEnabled(False)
            self.btn_ok.setText(u"发布 (本地)")
            self.btn_ok.setStyleSheet(styles.BTN_GRAY)

    def add_new_category(self):
        dialog = NewCategoryDialog(self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            filename = dialog.result_filename
            display_name = dialog.result_displayname
            
            # 检查重复
            for i in range(self.combo_category.count()):
                if self.combo_category.itemData(i) == filename:
                    QtWidgets.QMessageBox.warning(self, "Error", u"分类已存在")
                    return

            combo_text = u"{} ({})".format(display_name, filename)
            # 【修改】存入 itemData
            self.combo_category.addItem(combo_text, filename)
            self.new_category_map[filename] = display_name
            self.combo_category.setCurrentIndex(self.combo_category.count() - 1)

    def on_publish(self):
        name = self.input_name.text().strip()
        cmd = self.input_cmd.toPlainText().strip()
        pwd = self.input_pwd.text().strip()
        
        if not name or not cmd:
            QtWidgets.QMessageBox.warning(self, "Warning", u"请填写完整信息")
            return

        is_admin = (pwd == config.ADMIN_PASSWORD)
        
        tool_data = {
            "name": name,
            "type": "command", 
            "command": cmd,
            "tooltip": self.input_tooltip.text().strip(),
            "help_content": self.input_help.toPlainText(), # [新增] 获取帮助内容
            "favorite": False
        }

        category_file = ""
        custom_category_name = None
        if is_admin:
            if self.combo_category.currentIndex() >= 0:
                # 【修改】从 itemData 获取文件名，而不是从列表索引
                category_file = self.combo_category.currentData()
                
                if category_file in self.new_category_map:
                    custom_category_name = self.new_category_map[category_file]
            else:
                 QtWidgets.QMessageBox.warning(self, "Warning", u"管理员模式必须选择一个分类")
                 return
        
        success, msg = worker.publish_tool(
            is_admin, tool_data, category_file, self.icon_path, category_name=custom_category_name
        )
        if success:
            QtWidgets.QMessageBox.information(self, u"成功", msg)
            self.accept()
        else:
            QtWidgets.QMessageBox.critical(self, u"错误", msg)


# =========================================================================
# 3. 编辑工具弹窗 (已修改：增加使用说明)
# =========================================================================
class EditDialog(QtWidgets.QDialog):
    def __init__(self, tool_data, parent=None):
        super(EditDialog, self).__init__(parent)
        self.setWindowTitle(u"编辑工具")
        self.resize(500, 700) 
        self.tool_data = tool_data
        self.icon_path = tool_data.get("icon")
        self.new_category_map = {} 
        
        self.init_ui()
        self.load_data()

    def init_ui(self):
        self.setStyleSheet(styles.DIALOG_STYLES)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(25, 25, 25, 25)

        # === 头部 ===
        header_layout = QtWidgets.QHBoxLayout()
        header_layout.setSpacing(15)
        self.btn_icon = QtWidgets.QPushButton()
        self.btn_icon.setFixedSize(64, 64)
        self.btn_icon.setIconSize(QtCore.QSize(40, 40))
        self.btn_icon.clicked.connect(self.browse_icon)
        self.btn_icon.setStyleSheet(styles.ICON_PREVIEW_BTN)
        header_layout.addWidget(self.btn_icon)
        
        name_layout = QtWidgets.QVBoxLayout()
        name_layout.setSpacing(6)
        name_layout.setContentsMargins(0, 2, 0, 2)
        lbl_name = QtWidgets.QLabel(u"工具名称")
        lbl_name.setStyleSheet("font-weight: bold; color: #DDD; font-size: 13px;")
        self.input_name = QtWidgets.QLineEdit()
        self.input_name.setStyleSheet("font-weight: bold; font-size: 14px; padding: 6px;")
        name_layout.addWidget(lbl_name)
        name_layout.addWidget(self.input_name)
        header_layout.addLayout(name_layout)
        layout.addLayout(header_layout)

        # === 表单 ===
        form_layout = QtWidgets.QGridLayout()
        form_layout.setVerticalSpacing(12)
        form_layout.setHorizontalSpacing(10)
        
        # Row 0
        form_layout.addWidget(QtWidgets.QLabel(u"所属分类:"), 0, 0)
        cat_layout = QtWidgets.QHBoxLayout()
        cat_layout.setSpacing(5)
        self.combo_category = QtWidgets.QComboBox()
        self.combo_category.setMinimumHeight(28)
        self.load_categories()
        self.btn_new_cat = QtWidgets.QPushButton(u"+")
        self.btn_new_cat.setFixedSize(30, 28)
        self.btn_new_cat.setToolTip(u"新建分类文件")
        self.btn_new_cat.clicked.connect(self.add_new_category)
        cat_layout.addWidget(self.combo_category)
        cat_layout.addWidget(self.btn_new_cat)
        form_layout.addLayout(cat_layout, 0, 1)
        
        # Row 1
        form_layout.addWidget(QtWidgets.QLabel(u"一句话提示:"), 1, 0)
        self.input_tooltip = QtWidgets.QLineEdit()
        form_layout.addWidget(self.input_tooltip, 1, 1)

        # Row 2: [新增] 详细说明
        form_layout.addWidget(QtWidgets.QLabel(u"详细说明:"), 2, 0, QtCore.Qt.AlignTop)
        self.input_help = QtWidgets.QTextEdit()
        self.input_help.setFixedHeight(60)
        form_layout.addWidget(self.input_help, 2, 1)

        # Row 3
        form_layout.addWidget(QtWidgets.QLabel(u"管理密码:"), 3, 0)
        self.input_pwd = QtWidgets.QLineEdit()
        self.input_pwd.setEchoMode(QtWidgets.QLineEdit.Password)
        self.input_pwd.setPlaceholderText(u"仅修改服务器工具需要")
        form_layout.addWidget(self.input_pwd, 3, 1)
        
        layout.addLayout(form_layout)

        # === 代码 ===
        lbl_code = QtWidgets.QLabel(u"脚本代码:")
        lbl_code.setStyleSheet("margin-top: 8px; font-weight: bold; color: #DDD;")
        layout.addWidget(lbl_code)
        self.input_cmd = QtWidgets.QTextEdit()
        layout.addWidget(self.input_cmd)

        # === 按钮 ===
        btn_layout = QtWidgets.QHBoxLayout()
        self.btn_cancel = QtWidgets.QPushButton(u"取消")
        self.btn_cancel.setFixedSize(80, 32)
        self.btn_cancel.clicked.connect(self.reject)
        
        self.btn_save = QtWidgets.QPushButton(u"保存修改")
        self.btn_save.setFixedSize(100, 32)
        self.btn_save.setStyleSheet(styles.BTN_GREEN)
        self.btn_save.clicked.connect(self.on_save)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_save)
        layout.addLayout(btn_layout)

    def add_new_category(self):
        dialog = NewCategoryDialog(self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            filename = dialog.result_filename
            display_name = dialog.result_displayname
            full_path = os.path.join(config.MODULES_DIR, filename)
            for i in range(self.combo_category.count()):
                if self.combo_category.itemData(i) == full_path:
                    QtWidgets.QMessageBox.warning(self, "Error", u"该分类已存在！")
                    return
            combo_text = u"{} ({})".format(display_name, filename)
            self.combo_category.addItem(combo_text, full_path)
            self.new_category_map[full_path] = display_name
            self.combo_category.setCurrentIndex(self.combo_category.count() - 1)

    def load_categories(self):
        current_source = self.tool_data.get("__source_file__", "")
        import glob
        json_files = glob.glob(os.path.join(config.MODULES_DIR, "*.json"))
        json_files.sort()
        for f in json_files:
            fname = os.path.basename(f)
            if fname == config.FAV_FILE_NAME: continue
            
            # === 修改点：使用安全加载 ===
            data = utils.safe_json_load(f, default_val={})
            if data:
                cat_name = data.get("name", fname)
                prefix = u"[本地] " if fname == config.USER_FILE_NAME else u"[公共] "
                self.combo_category.addItem(prefix + cat_name, f)
                if os.path.normpath(f) == os.path.normpath(current_source):
                    self.combo_category.setCurrentIndex(self.combo_category.count() - 1)
            
    def load_data(self):
        self.input_name.setText(self.tool_data.get("name", ""))
        self.input_cmd.setText(self.tool_data.get("command", ""))
        self.input_tooltip.setText(self.tool_data.get("tooltip", ""))
        # [新增] 读取说明
        self.input_help.setText(self.tool_data.get("help_content", ""))
        
        icon_name = self.tool_data.get("icon", "")
        if icon_name:
            path = icon_name if os.path.isabs(icon_name) else os.path.join(config.ICONS_DIR, icon_name)
            if os.path.exists(path): self.btn_icon.setIcon(QtGui.QIcon(path))
            else: self.btn_icon.setText(u"No Img")

    def browse_icon(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select Icon", "", "Images (*.png *.jpg *.svg)")
        if path:
            self.icon_path = path
            self.btn_icon.setIcon(QtGui.QIcon(path))

    def on_save(self):
        target_path = self.combo_category.currentData()
        cat_display_name = None
        if target_path in self.new_category_map:
            cat_display_name = self.new_category_map[target_path]
            
        new_info = {
            "name": self.input_name.text(),
            "icon": os.path.basename(self.icon_path) if self.icon_path else "default.png",
            "command": self.input_cmd.toPlainText(),
            "tooltip": self.input_tooltip.text(),
            "help_content": self.input_help.toPlainText(), # [新增] 保存说明
            "category_file": target_path,
            "category_name": cat_display_name
        }
        
        pwd = self.input_pwd.text()
        is_admin = (pwd == config.ADMIN_PASSWORD)
        
        if self.icon_path and os.path.isabs(self.icon_path) and self.icon_path != self.tool_data.get("icon"):
             import shutil
             target_icon = os.path.join(config.ICONS_DIR, os.path.basename(self.icon_path))
             try:
                 shutil.copy2(self.icon_path, target_icon)
                 new_info["icon"] = os.path.basename(target_icon)
             except: pass

        success, msg = worker.update_tool(self.tool_data, new_info, is_admin)
        if success:
            QtWidgets.QMessageBox.information(self, u"成功", u"修改成功！\n请点击更新按钮刷新界面。")
            self.accept()
        else:
            QtWidgets.QMessageBox.warning(self, u"错误", msg)


# =========================================================================
# 4. 快捷键弹窗 (保持不变)
# =========================================================================
class HotkeyDialog(QtWidgets.QDialog):
    def __init__(self, tool_data, current_key="", parent=None):
        super(HotkeyDialog, self).__init__(parent)
        self.setWindowTitle(u"设置快捷键")
        self.resize(300, 150)
        self.tool_data = tool_data
        self.key_sequence = current_key
        
        self.init_ui()
        
    def init_ui(self):
        self.setStyleSheet(styles.DIALOG_STYLES)
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(QtWidgets.QLabel(u"当前工具: " + self.tool_data.get("name")))
        layout.addWidget(QtWidgets.QLabel(u"请直接按下键盘组合键:"))
        
        self.key_editor = QtWidgets.QKeySequenceEdit()
        if self.key_sequence:
            self.key_editor.setKeySequence(QtGui.QKeySequence(self.key_sequence))
        
        self.key_editor.setStyleSheet("""
            QKeySequenceEdit {
                background-color: #1E1E1E; border: 1px solid #5285A6; 
                color: #FFF; font-size: 14px; padding: 5px;
            }
        """)
        layout.addWidget(self.key_editor)
        
        self.lbl_info = QtWidgets.QLabel(u"")
        self.lbl_info.setStyleSheet("color: #E57373;")
        layout.addWidget(self.lbl_info)
        
        btn_layout = QtWidgets.QHBoxLayout()
        self.btn_clear = QtWidgets.QPushButton(u"清除/解绑")
        self.btn_clear.clicked.connect(self.clear_hotkey)
        
        self.btn_save = QtWidgets.QPushButton(u"保存")
        self.btn_save.setStyleSheet(styles.BTN_GREEN)
        self.btn_save.clicked.connect(self.on_save_check)
        
        btn_layout.addWidget(self.btn_clear)
        btn_layout.addWidget(self.btn_save)
        layout.addLayout(btn_layout)
        
        self.key_editor.keySequenceChanged.connect(self.check_key)

    def check_key(self, key_seq):
        key_str = key_seq.toString()
        self.lbl_info.setText(u"即将绑定: " + key_str if key_str else u"")

    def clear_hotkey(self):
        self.key_editor.clear()
        self.accept()

    def get_key_string(self):
        return self.key_editor.keySequence().toString(QtGui.QKeySequence.PortableText)
    
    def on_save_check(self):
        """保存前的安全检查"""
        key_seq = self.get_key_string()
        
        # 1. 检查冲突
        is_conflict, owner_cmd = utils.check_hotkey_conflict(key_seq)
        
        if is_conflict:
            # 弹窗警告
            msg = (u"警告：快捷键 '{}' 目前已被 Maya 占用！\n\n"
                   u"占用命令: {}\n\n"
                   u"如果强制覆盖，Maya 原生功能将失效。\n"
                   u"是否继续覆盖？").format(key_seq, owner_cmd)
                   
            reply = QtWidgets.QMessageBox.warning(
                self, 
                u"快捷键冲突", 
                msg,
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )
            
            # 如果用户选 No，则中止保存
            if reply == QtWidgets.QMessageBox.No:
                return

        # 2. 如果没冲突，或者用户坚持覆盖，则通过
        self.accept()