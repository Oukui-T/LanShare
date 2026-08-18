import os
import sys

# 必须在导入任何 Qt 模块前初始化 Qt 插件环境
from core.qt_bootstrap import init_qt_environment
init_qt_environment()

from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtCore import QCoreApplication, QUrl

from gui.bridge_client import ClientBridge

def main():
    QCoreApplication.setOrganizationName("LanShare")
    QCoreApplication.setApplicationName("LanShareClient")

    app = QApplication(sys.argv)
    app.setFont(QFont("Microsoft YaHei", 9))

    base_dir = os.path.dirname(os.path.abspath(__file__))
    icon_path = os.path.join(base_dir, "icon", "client.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    pyside_qml = os.path.join(base_dir, "PySide6", "qml")
    qml_dir = os.path.join(base_dir, "gui", "qml")

    bridge = ClientBridge()

    engine = QQmlApplicationEngine()
    if os.path.exists(pyside_qml):
        engine.addImportPath(pyside_qml)
    if os.path.exists(qml_dir):
        engine.addImportPath(qml_dir)

    def on_warning(warnings):
        for w in warnings:
            print("[QML 引擎日志]:", w.toString())

    engine.warnings.connect(on_warning)
    engine.rootContext().setContextProperty("bridge", bridge)

    qml_file = os.path.join(qml_dir, "ClientWindow.qml")
    qml_url = QUrl.fromLocalFile(os.path.abspath(qml_file))
    print(f"正在载入 QML: {qml_url.toString()}")
    engine.load(qml_url)

    if not engine.rootObjects():
        sys.stderr.write("错误: 无法加载 ClientWindow.qml\n")
        sys.exit(-1)

    print("客户端 QML 界面加载成功，进入主事件循环。")
    app.aboutToQuit.connect(bridge.cleanup)
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
