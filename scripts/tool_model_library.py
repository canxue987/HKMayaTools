# -*- coding: utf-8 -*-
import os
import json
import shutil
import time
import subprocess
import platform
import maya.cmds as cmds
import maya.mel as mel
from PySide2 import QtWidgets, QtCore, QtGui

# 尝试获取工具箱配置
try:
    import toolbox_core.config as config
    LIBRARY_ROOT = os.path.join(config.ROOT_DIR, "Library")
except ImportError:
    LIBRARY_ROOT = os.path.join(os.path.dirname(__file__), "Library")

if not os.path.exists(LIBRARY_ROOT):
    os.makedirs(LIBRARY_ROOT)

class AssetButton(QtWidgets.QWidget):
    """
    单个资产组件
    增加：右键菜单 (删除、重命名、打开位置)
    """
    # 增加一个信号，当删除成功时发送，通知父窗口刷新布局或移除自己
    delete_signal = QtCore.Signal() 

    def __init__(self, asset_data, root_path, parent=None):
        super(AssetButton, self).__init__(parent)
        self.asset_data = asset_data
        self.root_path = root_path
        
        # 解析路径
        self.file_name = asset_data.get("file_name")
        self.display_name = asset_data.get("name")
        self.thumb_name = asset_data.get("thumbnail")
        
        self.full_file_path = os.path.join(root_path, self.file_name)
        self.full_thumb_path = os.path.join(root_path, self.thumb_name)
        # 记录元数据JSON的路径，用于重命名和删除
        self.json_filename = "{}_{}.json".format(
            self.file_name.rsplit('_', 1)[0], # 简易反推，或者在刷新时传入完整json路径更好
            asset_data.get("created_at")
        )
        # 修正：上面反推json名不可靠，稍后在LibraryWindow里直接传入json_path更稳妥
        # 这里先留空，由外部传入
        self.json_path = "" 

        self.setFixedSize(140, 160)
        
        # === 开启右键菜单 ===
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

        self.init_ui()

    def init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(5,5,5,5)
        layout.setSpacing(5)
        
        # 缩略图按钮
        self.btn_img = QtWidgets.QPushButton()
        self.btn_img.setFixedSize(130, 120)
        self.btn_img.setStyleSheet("""
            QPushButton {
                background-color: #333;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #444; }
            QPushButton:pressed { background-color: #222; }
        """)
        
        if os.path.exists(self.full_thumb_path):
            icon = QtGui.QIcon(self.full_thumb_path)
            self.btn_img.setIcon(icon)
            self.btn_img.setIconSize(QtCore.QSize(120, 110))
        else:
            self.btn_img.setText("No Image")

        # 左键点击导入
        self.btn_img.clicked.connect(self.on_click_import)

        # 文字标签
        self.lbl_text = QtWidgets.QLabel(self.display_name)
        self.lbl_text.setAlignment(QtCore.Qt.AlignCenter)
        self.lbl_text.setStyleSheet("color: #DDD; font-size: 11px;")
        self.update_label_text(self.display_name)

        layout.addWidget(self.btn_img)
        layout.addWidget(self.lbl_text)

    def update_label_text(self, text):
        font_metrics = QtGui.QFontMetrics(self.lbl_text.font())
        elided_text = font_metrics.elidedText(text, QtCore.Qt.ElideRight, 120)
        self.lbl_text.setText(elided_text)
        self.lbl_text.setToolTip(text)

    def on_click_import(self):
        # 转发给父级处理，或者直接在这里处理
        # 这里演示直接调用导入逻辑
        if not os.path.exists(self.full_file_path):
            QtWidgets.QMessageBox.warning(self, "Error", u"文件不存在: " + self.full_file_path)
            return
            
        try:
            namespace = self.file_name.split(".")[0]
            nodes = cmds.file(self.full_file_path, i=True, returnNewNodes=True, namespace=namespace)
            if nodes:
                cmds.select(nodes)
                cmds.viewFit(nodes, animate=True)
            print(u"已导入: {}".format(self.display_name))
            # 屏幕提示
            cmds.inViewMessage(amg=u'<span style="color:lime;">成功导入: {}</span>'.format(self.display_name), pos='topCenter', fade=True)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Error", str(e))

    def show_context_menu(self, pos):
        menu = QtWidgets.QMenu(self)
        menu.setStyleSheet("""
            QMenu { background-color: #2F2F2F; border: 1px solid #555; }
            QMenu::item { color: #DDD; padding: 5px 20px; }
            QMenu::item:selected { background-color: #5285A6; color: #FFF; }
        """)

        action_import = menu.addAction(u"导入到场景")
        menu.addSeparator()
        action_rename = menu.addAction(u"重命名")
        action_open = menu.addAction(u"打开文件位置")
        menu.addSeparator()
        action_delete = menu.addAction(u"删除资产")

        action_import.triggered.connect(self.on_click_import)
        action_rename.triggered.connect(self.on_rename)
        action_open.triggered.connect(self.on_open_folder)
        action_delete.triggered.connect(self.on_delete)

        menu.exec_(self.mapToGlobal(pos))

    def on_open_folder(self):
        """打开文件所在文件夹并选中文件"""
        path = os.path.normpath(self.full_file_path)
        if not os.path.exists(path):
            path = os.path.dirname(path) # 如果文件没了，就打开文件夹
        
        try:
            if platform.system() == "Windows":
                # explorer /select, "filename" 可以直接选中文件
                subprocess.Popen(['explorer', '/select,', path])
            elif platform.system() == "Darwin":
                subprocess.Popen(['open', '-R', path])
            else:
                subprocess.Popen(['xdg-open', os.path.dirname(path)])
        except Exception as e:
            print(u"打开文件夹失败: {}".format(e))

    def on_rename(self):
        """重命名逻辑：只改 JSON 中的 Display Name，不改文件名（防断连）"""
        new_name, ok = QtWidgets.QInputDialog.getText(
            self, u"重命名", u"请输入新名称:", 
            QtWidgets.QLineEdit.Normal, self.display_name
        )
        
        if ok and new_name and new_name != self.display_name:
            if os.path.exists(self.json_path):
                try:
                    # 1. 读取旧数据
                    with open(self.json_path, 'r') as f:
                        data = json.load(f)
                    
                    # 2. 修改名称
                    data['name'] = new_name
                    
                    # 3. 写回
                    with open(self.json_path, 'w') as f:
                        json.dump(data, f, indent=4)
                    
                    # 4. 更新 UI
                    self.display_name = new_name
                    self.update_label_text(new_name)
                    
                except Exception as e:
                    QtWidgets.QMessageBox.warning(self, "Error", u"重命名失败: " + str(e))

    def on_delete(self):
        """删除逻辑：删除 json, 模型, 缩略图"""
        reply = QtWidgets.QMessageBox.question(
            self, u"确认删除", 
            u"确定要永久删除资产 [{}] 吗?\n此操作无法撤销。".format(self.display_name),
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        
        if reply == QtWidgets.QMessageBox.Yes:
            try:
                # 删除 JSON
                if os.path.exists(self.json_path): os.remove(self.json_path)
                # 删除 模型
                if os.path.exists(self.full_file_path): os.remove(self.full_file_path)
                # 删除 缩略图
                if os.path.exists(self.full_thumb_path): os.remove(self.full_thumb_path)
                
                # 发送信号，让 UI 移除自己
                self.deleteLater()
                
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Error", u"删除失败: " + str(e))

class PublishDialog(QtWidgets.QDialog):
    """发布新资产的弹窗 (保持不变)"""
    def __init__(self, parent=None):
        super(PublishDialog, self).__init__(parent)
        self.setWindowTitle(u"发布资产到库")
        self.resize(300, 200)
        self.result_data = None
        self.init_ui()

    def init_ui(self):
        self.setStyleSheet("QDialog { background-color: #333; color: #EEE; } QLabel{ color: #DDD; } QLineEdit { background: #222; border: 1px solid #555; color: #FFF; padding: 4px; }")
        layout = QtWidgets.QVBoxLayout(self)
        
        layout.addWidget(QtWidgets.QLabel(u"资产名称:"))
        self.input_name = QtWidgets.QLineEdit()
        self.input_name.setPlaceholderText(u"例如: SciFi_Box_01")
        layout.addWidget(self.input_name)

        layout.addWidget(QtWidgets.QLabel(u"文件格式:"))
        self.combo_format = QtWidgets.QComboBox()
        self.combo_format.addItems(["mayaBinary (.mb)", "FBX export (.fbx)"])
        layout.addWidget(self.combo_format)

        self.chk_snapshot = QtWidgets.QCheckBox(u"自动截取选中物体缩略图")
        self.chk_snapshot.setStyleSheet("color: #DDD;")
        self.chk_snapshot.setChecked(True)
        layout.addWidget(self.chk_snapshot)

        btn_layout = QtWidgets.QHBoxLayout()
        btn_ok = QtWidgets.QPushButton(u"发布")
        btn_ok.clicked.connect(self.on_accept)
        btn_cancel = QtWidgets.QPushButton(u"取消")
        btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def on_accept(self):
        name = self.input_name.text().strip()
        if not name:
            QtWidgets.QMessageBox.warning(self, "Error", u"请输入名称")
            return
        
        ext = ".mb" if self.combo_format.currentIndex() == 0 else ".fbx"
        self.result_data = {
            "name": name,
            "ext": ext,
            "snapshot": self.chk_snapshot.isChecked()
        }
        self.accept()

class LibraryWindow(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(LibraryWindow, self).__init__(parent)
        self.setWindowTitle("Model Library")
        self.resize(550, 600)
        self.init_ui()
        self.refresh_library()

    def init_ui(self):
        # 整体样式
        self.setStyleSheet("""
            QWidget { background-color: #2B2B2B; color: #EEE; font-family: "Microsoft YaHei"; }
            QLineEdit { background-color: #222; border: 1px solid #444; padding: 6px; border-radius: 4px; color: #EEE; }
            QScrollArea { border: none; background-color: #2B2B2B; }
            QPushButton { background-color: #444; border-radius: 4px; padding: 6px; color: #EEE; border: 1px solid #333; }
            QPushButton:hover { background-color: #5285A6; border-color: #64B5F6; }
            QPushButton:pressed { background-color: #222; }
        """)

        main_layout = QtWidgets.QVBoxLayout(self)

        # --- 顶部工具栏 ---
        top_layout = QtWidgets.QHBoxLayout()
        
        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText(u"搜索资产...")
        self.search_input.textChanged.connect(self.filter_assets)
        
        self.btn_add = QtWidgets.QPushButton(u"+ 添加选中模型")
        self.btn_add.setStyleSheet("background-color: #2E7D32; font-weight: bold; border: none;")
        self.btn_add.clicked.connect(self.add_asset_from_selection)

        self.btn_refresh = QtWidgets.QPushButton(u"↻")
        self.btn_refresh.setFixedSize(30, 30)
        self.btn_refresh.setToolTip(u"刷新库")
        self.btn_refresh.clicked.connect(self.refresh_library)

        top_layout.addWidget(self.search_input)
        top_layout.addWidget(self.btn_add)
        top_layout.addWidget(self.btn_refresh)
        main_layout.addLayout(top_layout)

        # --- 内容显示区域 ---
        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        
        self.container = QtWidgets.QWidget()
        self.flow_layout = QtWidgets.QGridLayout(self.container) # 使用 Grid 模拟流式
        self.flow_layout.setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)
        
        self.scroll.setWidget(self.container)
        main_layout.addWidget(self.scroll)
        
        # 底部提示
        lbl_hint = QtWidgets.QLabel(u"Tip: 左键点击导入，右键管理菜单")
        lbl_hint.setStyleSheet("color: #777; font-size: 10px; margin-left: 5px;")
        main_layout.addWidget(lbl_hint)

    def refresh_library(self):
        # 清空当前显示
        while self.flow_layout.count():
            item = self.flow_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        # 遍历文件夹
        if not os.path.exists(LIBRARY_ROOT):
            return

        # 获取所有json文件并按时间倒序排列 (最新的在前面)
        json_files = [f for f in os.listdir(LIBRARY_ROOT) if f.endswith(".json")]
        # 简单按文件名排序（因为文件名里带时间戳），如果想更严谨可以读内容里的 created_at
        json_files.sort(reverse=True) 

        assets = []
        for f in json_files:
            path = os.path.join(LIBRARY_ROOT, f)
            try:
                with open(path, 'r') as fp:
                    data = json.load(fp)
                    # 把 json 路径存进去，方便后面传给 AssetButton
                    data["__json_path__"] = path
                    assets.append(data)
            except: pass

        # 重新生成 UI
        # 动态计算列数
        win_width = self.width()
        col_count = max(3, win_width // 160) 
        
        for i, asset in enumerate(assets):
            # 创建按钮
            btn = AssetButton(asset, LIBRARY_ROOT)
            # 关键：手动传入 json 路径，确保 AssetButton 知道删除哪个文件
            btn.json_path = asset.get("__json_path__")
            
            row = i // col_count
            col = i % col_count
            self.flow_layout.addWidget(btn, row, col)

    def resizeEvent(self, event):
        # 窗口大小改变时，延迟一点点刷新布局，使其自适应列数
        # 这里简单起见不自动重排，手动点刷新即可。
        # 若要自动，可使用 QTimer.singleShot(200, self.refresh_library)
        super(LibraryWindow, self).resizeEvent(event)

    def filter_assets(self, text):
        text = text.lower()
        for i in range(self.flow_layout.count()):
            widget = self.flow_layout.itemAt(i).widget()
            if widget:
                name = widget.display_name.lower()
                if text in name:
                    widget.show()
                else:
                    widget.hide()

    def add_asset_from_selection(self):
        selection = cmds.ls(sl=True)
        if not selection:
            QtWidgets.QMessageBox.warning(self, "Warning", u"请先选择要保存的模型！")
            return

        dialog = PublishDialog(self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            data = dialog.result_data
            name = data["name"]
            ext = data["ext"]
            do_snapshot = data["snapshot"]
            
            # 使用时间戳防止重名
            safe_name = "".join([c for c in name if c.isalnum() or c in ('_','-')])
            if not safe_name: safe_name = "Asset"
            timestamp = int(time.time())
            
            # 1. 导出模型
            file_name = "{}_{}{}".format(safe_name, timestamp, ext)
            full_path = os.path.join(LIBRARY_ROOT, file_name)
            
            file_type = "mayaBinary" if ext == ".mb" else "FBX export"
            
            try:
                cmds.file(full_path, force=True, options="v=0;", type=file_type, pr=True, es=True)
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", u"导出失败 (检查FBX插件):\n" + str(e))
                return

            # 2. 截图处理
            thumb_file = "thumb_{}_{}.jpg".format(safe_name, timestamp)
            thumb_path = os.path.join(LIBRARY_ROOT, thumb_file)
            
            if do_snapshot:
                self.take_snapshot(selection, thumb_path)
            
            # 3. 生成元数据 JSON
            meta_file = "{}_{}.json".format(safe_name, timestamp)
            meta_path = os.path.join(LIBRARY_ROOT, meta_file)
            
            meta_data = {
                "name": name,
                "file_name": file_name,
                "thumbnail": thumb_file,
                "created_at": timestamp,
                "source_file": cmds.file(q=True, sn=True)
            }
            
            with open(meta_path, 'w') as f:
                json.dump(meta_data, f, indent=4)
            
            self.refresh_library()

    def take_snapshot(self, selection, save_path):
        """智能截图逻辑"""
        current_sel = cmds.ls(sl=True)
        panel = cmds.getPanel(wf=True)
        if "modelPanel" not in panel:
            panel = "modelPanel4" 
            
        try:
            # 开启隔离显示
            cmds.isolateSelect(panel, state=1)
            cmds.isolateSelect(panel, addSelected=True)
            
            # 聚焦
            cmds.viewFit(selection)
            
            # 拍屏
            cmds.playblast(
                completeFilename=save_path, 
                format='image', 
                compression='jpg', 
                showOrnaments=False, 
                viewer=False, 
                frame=cmds.currentTime(q=True),
                percent=100,
                widthHeight=(256, 256), 
                quality=100
            )
        except Exception as e:
            print(u"截图失败: {}".format(e))
        finally:
            # 恢复现场
            cmds.isolateSelect(panel, state=0)
            if current_sel:
                cmds.select(current_sel)

def run():
    global win
    try:
        win.close()
        win.deleteLater()
    except: pass
    
    win = LibraryWindow()
    win.show()

if __name__ == "__main__":
    run()