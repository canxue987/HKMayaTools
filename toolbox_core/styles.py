# -*- coding: utf-8 -*-

# 全局样式 (Tooltip, QWidget, Menu, ScrollBar)
GLOBAL_STYLES = """
    QToolTip {
        color: #ffffff; background-color: #2a2a2a; border: 1px solid #888; padding: 4px; border-radius: 2px;
    }
    QWidget {
        font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
    }
    QMenu {
        background-color: #2F2F2F;
        border: 1px solid #555;
        border-radius: 4px;
        padding: 4px;
    }
    QMenu::item {
        background-color: transparent;
        color: #DDD;
        padding: 6px 24px;
        border-radius: 3px;
        font-size: 13px;
    }
    QMenu::item:selected {
        background-color: #5285A6;
        color: #FFF;
    }
    QMenu::separator {
        height: 1px;
        background: #444;
        margin: 4px 10px;
    }
    /* 侧边栏容器 */
    QWidget#SidebarContainer {
        background-color: #2B2B2B;
        border-right: 1px solid #444;
    }
    /* 分类列表 */
    QListWidget {
        background-color: transparent;
        border: none;
        outline: none;
    }
    QListWidget::item {
        background-color: transparent;
        color: #AAA;
        padding: 4px 0px; 
        margin-bottom: 2px;
        border-left: 3px solid transparent;
    }
    QListWidget::item:hover {
        background-color: #353535;
        color: #DDD;
    }
    QListWidget::item:selected {
        background-color: #3A3A3A;
        color: #FFF;
        font-weight: bold;
        border-left: 3px solid #64B5F6;
    }
    /* 侧边栏按钮 */
    QPushButton#SideBtn {
        background-color: transparent;
        color: #666;
        border: none;
        border-radius: 0px;
        font-size: 14px;
        font-weight: bold;
        border-top: 1px solid #333;
    }
    QPushButton#SideBtn:hover {
        background-color: #444;
        color: #FFF;
    }
    QPushButton#SideBtn:pressed {
        background-color: #222;
        color: #888;
    }
"""

# 弹窗通用样式
DIALOG_STYLES = """
    QDialog {
        background-color: #2B2B2B;
    }
    QLabel {
        color: #BBBBBB;
        font-family: "Microsoft YaHei", sans-serif;
        font-size: 12px;
    }
    QLineEdit, QComboBox {
        background-color: #1E1E1E;
        border: 1px solid #444;
        border-radius: 4px;
        color: #EEEEEE;
        padding: 6px;
        font-size: 13px;
    }
    QLineEdit:focus, QComboBox:focus, QTextEdit:focus {
        border: 1px solid #5285A6;
    }
    QTextEdit {
        background-color: #1E1E1E;
        border: 1px solid #444;
        border-radius: 4px;
        color: #A9B7C6; 
        padding: 6px;
        font-family: "Consolas", "Monospace", sans-serif;
        font-size: 12px;
    }
    QPushButton {
        background-color: #3A3A3A;
        border: 1px solid #555;
        color: #EEE;
        border-radius: 4px;
        padding: 6px 15px;
    }
    QPushButton:hover {
        background-color: #454545;
        border-color: #777;
    }
    QPushButton:disabled, QComboBox:disabled {
        background-color: #252525;
        color: #666;
        border-color: #333;
    }
"""

# 图标预览按钮样式
ICON_PREVIEW_BTN = """
    QPushButton {
        background-color: #222;
        border: 1px dashed #555;
        border-radius: 6px;
    }
    QPushButton:hover {
        border-color: #888;
        background-color: #2A2A2A;
    }
"""

# 绿色确认按钮
BTN_GREEN = """
    QPushButton { 
        background-color: #2E7D32; 
        color: white; 
        font-weight: bold; 
        border: none;
        border-radius: 4px;
    }
    QPushButton:hover { background-color: #388E3C; }
    QPushButton:pressed { background-color: #1B5E20; }
"""

# 灰色按钮
BTN_GRAY = """
    QPushButton { 
        background-color: #555; 
        color: #EEE; 
        font-weight: bold; 
        border: none;
        border-radius: 4px; 
    }
    QPushButton:hover { background-color: #666; }
"""

# 【新增】帮助页面样式
HELP_CONTENT_STYLE = """
    QTextBrowser {
        background-color: #2B2B2B;
        border: none;
        color: #DDDDDD;
        font-family: "Microsoft YaHei", sans-serif;
        font-size: 12px; /* 字号改小到 12px */
        line-height: 1.2; /* 行高改为 1.2 倍，非常紧凑 */
        padding: 8px;     /* 内边距进一步减小 */
    }
"""

# 【新增】侧边栏帮助按钮样式 (问号按钮)
# 继承自 SideBtn，但可以有微调
SIDE_HELP_BTN = """
    QPushButton {
        background-color: transparent;
        color: #888; 
        border: none;
        border-radius: 0px;
        font-size: 16px; 
        font-weight: bold;
        border-top: 1px solid #333;
    }
    QPushButton:hover {
        background-color: #444;
        color: #64B5F6; /* 悬停变蓝 */
    }
"""

# === 【新增】原生控件流帮助页样式 ===
# 标题
HELP_TITLE_LBL = """
    QLabel {
        color: #64B5F6;
        font-family: "Microsoft YaHei";
        font-weight: bold;
        font-size: 14px;
        margin-top: 10px; /* 标题上方留点空 */
        margin-bottom: 2px;
    }
"""

# 普通正文
HELP_BODY_LBL = """
    QLabel {
        color: #BBBBBB;
        font-family: "Microsoft YaHei";
        font-size: 12px;
        line-height: 1.2;
    }
"""

# 强调/高亮文字
HELP_HIGHLIGHT_LBL = """
    QLabel {
        color: #FFEB3B;
        font-family: "Microsoft YaHei";
        font-weight: bold;
        font-size: 12px;
    }
"""

# 列表项 (带缩进)
HELP_ITEM_LBL = """
    QLabel {
        color: #999999;
        font-family: "Microsoft YaHei";
        font-size: 11px;
        margin-left: 10px; /* 强制左侧缩进 */
    }
"""