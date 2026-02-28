# -*- coding: utf-8 -*-
import maya.cmds as cmds
import maya.mel as mel

def recover_windows():
    """
    核心逻辑：
    无UI模式，直接遍历并重置窗口位置。
    """
    # 1. 获取所有窗口
    all_windows = cmds.lsUI(windows=True)
    
    # 2. 定义安全坐标 (主屏幕左上角稍微往里一点，避免被顶部菜单遮挡)
    safe_top = 200
    safe_left = 200
    
    count = 0
    # 排除列表：主窗口、以及一些不想被移动的特定面板
    # 注意：大部分停靠窗口虽然在列表里，但通过 window 命令编辑位置通常无效或被忽略，
    # 我们主要针对的是那些独立弹出的窗口 (如 UV编辑器, 曲线编辑器, 插件窗口)
    ignored_windows = ["MayaWindow", "ColorEditor", "CommandWindow"] 

    for win in all_windows:
        if win in ignored_windows:
            continue
            
        # 3. 智能检测
        # 很多内部窗口是隐藏的，没必要移动它们
        if not cmds.window(win, q=True, visible=True):
            continue
            
        # 检查是否是主窗口 (防止 lsUI 返回奇怪的东西)
        if win == "MayaWindow": 
            continue

        try:
            # 4. 强制归位
            # topLeftCorner flag 可以将窗口移动到指定屏幕坐标
            cmds.window(win, edit=True, topLeftCorner=[safe_top, safe_left])
            
            # 如果窗口支持，顺便重置一下大小，防止它缩成一个点
            # 只有可缩放的窗口才重置大小，避免破坏定长窗口
            if cmds.window(win, q=True, sizeable=True):
                 # 获取当前宽高，如果太小（比如变成1x1了），就恢复默认
                 w = cmds.window(win, q=True, w=True)
                 h = cmds.window(win, q=True, h=True)
                 if w < 100 or h < 100:
                     cmds.window(win, edit=True, widthHeight=[400, 500])
            
            count += 1
        except:
            # 有些窗口可能是被锁定的或者实际上是 Panel，移动失败直接忽略
            pass

    # 5. 反馈结果 (HUD 提示，而不是弹窗)
    msg = u"<span style='color: #88FF88; font-weight: bold;'>成功重置 {} 个窗口位置</span>".format(count)
    if count == 0:
        msg = u"<span style='color: #FFFF88;'>未检测到迷路窗口</span>"
        
    cmds.inViewMessage(amg=msg, pos='midCenter', fade=True, alpha=0.7)
    print(u"窗口找回工具执行完毕，共处理: {} 个".format(count))

# --- 统一入口 ---

def run():
    """
    直接运行逻辑，不再通过UI
    """
    recover_windows()

def run_ui():
    """
    兼容旧接口，但也直接执行逻辑
    """
    recover_windows()

if __name__ == "__main__":
    run()