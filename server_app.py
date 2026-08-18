import os
import sys

# 必须在导入任何 Qt 模块前初始化 Qt 插件环境
from core.qt_bootstrap import init_qt_environment
init_qt_environment()

from core.firewall import is_admin

# Windows 下若未提权，使用 pythonw.exe 发起管理员提权，彻底避免弹出多余的黑框命令行窗口
if sys.platform.startswith("win") and not is_admin():
    import ctypes
    python_dir = os.path.dirname(sys.executable)
    pythonw = os.path.join(python_dir, "pythonw.exe")
    exe = pythonw if os.path.isfile(pythonw) else sys.executable

    params = " ".join([f'"{arg}"' for arg in sys.argv])
    ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, None, 1)
    if ret > 32:
        sys.exit(0)

from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtCore import QCoreApplication, QUrl

from gui.bridge_server import ServerBridge

def main():
    QCoreApplication.setOrganizationName("LanShare")
    QCoreApplication.setApplicationName("LanShareServer")

    app = QApplication(sys.argv)
    app.setFont(QFont("Microsoft YaHei", 9))

    base_dir = os.path.dirname(os.path.abspath(__file__))
    icon_path = os.path.join(base_dir, "icon", "server.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    pyside_qml = os.path.join(base_dir, "PySide6", "qml")
    qml_dir = os.path.join(base_dir, "gui", "qml")

    bridge = ServerBridge()

    engine = QQmlApplicationEngine()
    if os.path.exists(pyside_qml):
        engine.addImportPath(pyside_qml)
    if os.path.exists(qml_dir):
        engine.addImportPath(qml_dir)

    engine.rootContext().setContextProperty("bridge", bridge)

    qml_file = os.path.join(qml_dir, "ServerWindow.qml")
    engine.load(QUrl.fromLocalFile(os.path.abspath(qml_file)))

    if not engine.rootObjects():
        sys.stderr.write("错误: 无法加载 ServerWindow.qml\n")
        sys.exit(-1)

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
