import os
import sys

def init_qt_environment():
    """配置 Qt 插件与 QML 路径环境变量，抑制 Windows GUI 进程下的额外控制台弹窗"""
    # 抑制 Qt 在 Windows GUI 进程无控制台时自动 AllocConsole() 弹出黑框
    os.environ["QT_LOGGING_TO_CONSOLE"] = "0"
    os.environ["QT_FORCE_STDERR_LOGGING"] = "0"
    os.environ["QT_ASSUME_STDERR_HAS_CONSOLE"] = "0"
    os.environ["QT_QUICK_CONTROLS_STYLE"] = "Basic"

    try:
        import PySide6
        pyside_dir = os.path.dirname(PySide6.__file__)
        
        plugins_dir = os.path.join(pyside_dir, "plugins")
        if not os.path.exists(plugins_dir):
            plugins_dir = os.path.join(pyside_dir, "qt-plugins")
            
        platforms_dir = os.path.join(plugins_dir, "platforms")
        qml_dir = os.path.join(pyside_dir, "qml")

        os.environ["QT_PLUGIN_PATH"] = plugins_dir
        os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = platforms_dir
        os.environ["QML2_IMPORT_PATH"] = qml_dir
        os.environ["PATH"] = pyside_dir + ";" + os.environ.get("PATH", "")

        if hasattr(os, "add_dll_directory"):
            try:
                os.add_dll_directory(pyside_dir)
                if os.path.exists(platforms_dir):
                    os.add_dll_directory(platforms_dir)
            except Exception:
                pass

        # 注册静默 Qt 消息处理器，彻底阻止 Qt 在 Windows 上为打印警告而弹出后端黑框
        from PySide6.QtCore import qInstallMessageHandler
        def _silent_qt_msg_handler(mode, context, message):
            pass
        qInstallMessageHandler(_silent_qt_msg_handler)

    except Exception:
        pass
