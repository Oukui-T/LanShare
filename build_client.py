import os
import sys
import shutil
import subprocess

def create_console_debug_exe(gui_exe_path, debug_exe_path):
    """通过修改 PE 文件的 Subsystem 标志，快速生成带控制台的调试版可执行文件"""
    try:
        import pefile
        pe = pefile.PE(gui_exe_path)
        # 3 = IMAGE_SUBSYSTEM_WINDOWS_CUI (控制台程序)
        pe.OPTIONAL_HEADER.Subsystem = pefile.SUBSYSTEM_TYPE["IMAGE_SUBSYSTEM_WINDOWS_CUI"]
        pe.write(debug_exe_path)
        print(f"[OK] 成功生成带控制台调试版: {os.path.basename(debug_exe_path)}")
    except Exception as e:
        print(f"[WARNING] 生成调试版 exe 失败: {e}")

def copy_qt_runtime(dist_dir):
    """补齐 PySide6 QML 插件目录及所有 Qt6 核心动态链接库"""
    try:
        import PySide6
        pyside_dir = os.path.dirname(PySide6.__file__)
        
        # 1. 复制 QML 插件库
        src_qml = os.path.join(pyside_dir, "qml")
        dst_qml = os.path.join(dist_dir, "PySide6", "qml")
        if os.path.exists(src_qml):
            if os.path.exists(dst_qml):
                shutil.rmtree(dst_qml)
            shutil.copytree(src_qml, dst_qml)
            print("[OK] 已补全 PySide6 QML 核心插件库")

        # 2. 补齐 QML 插件所需的全部 Qt6 动态链接库
        copied_dlls = 0
        for f in os.listdir(pyside_dir):
            if f.startswith("Qt6") and f.endswith(".dll"):
                src_dll = os.path.join(pyside_dir, f)
                dst_dll = os.path.join(dist_dir, f)
                if not os.path.exists(dst_dll):
                    shutil.copy2(src_dll, dst_dll)
                    copied_dlls += 1
        print(f"[OK] 已补全 {copied_dlls} 个 Qt6 运行时支持库")
    except Exception as e:
        print("[WARNING] 补全 Qt 运行时异常:", e)

def build():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    python_exe = sys.executable

    # 清理旧的分发目录以防文件句柄冲突
    dist_client_dir = os.path.join("dist", "client")
    if os.path.exists(dist_client_dir):
        try:
            shutil.rmtree(dist_client_dir, ignore_errors=True)
        except Exception:
            pass
    
    cmd = [
        python_exe, "-m", "nuitka",
        "--standalone",
        "--windows-console-mode=disable",
        "--windows-icon-from-ico=icon/client.ico",
        "--windows-dependency-tool=pefile",
        "--enable-plugin=pyside6",
        "--include-data-dir=gui/qml=gui/qml",
        "--include-data-dir=icon=icon",
        "--output-dir=dist/client",
        "--output-filename=LanShareClient.exe",
        "--assume-yes-for-downloads",
        "--show-progress",
        "client_app.py"
    ]
    print("==================================================")
    print(" 正在使用 Nuitka 编译客户端 (生成 GUI 版与调试版)...")
    print("==================================================")
    print("执行命令:", " ".join(cmd))
    subprocess.run(cmd, check=True)
    
    dist_dir = os.path.join("dist", "client", "client_app.dist")
    gui_exe = os.path.join(dist_dir, "LanShareClient.exe")
    debug_exe = os.path.join(dist_dir, "LanShareClient_debug.exe")
    
    # 1. 补齐 Qt6 与 QML 运行环境
    copy_qt_runtime(dist_dir)
        
    # 2. 生成带控制台的调试版可执行文件
    if os.path.exists(gui_exe):
        create_console_debug_exe(gui_exe, debug_exe)

    print("\n==================================================")
    print("[OK] 客户端封装完成！生成了两个版本的可执行文件：")
    print(f" 1. 纯 GUI 模式 (无黑框): {gui_exe}")
    print(f" 2. 带后台调试 (有控制台): {debug_exe}")
    print("==================================================")

if __name__ == "__main__":
    build()
