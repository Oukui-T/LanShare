import os
import sys
import struct
from typing import Optional

def _parse_lnk_binary(lnk_path: str) -> Optional[str]:
    """
    基于微软官方 [MS-SHLLINK] 规范纯二进制解析 Windows .lnk 快捷方式文件。
    零外部依赖、零进程开销、跨线程安全。
    """
    try:
        if not os.path.isfile(lnk_path):
            return None
            
        with open(lnk_path, "rb") as f:
            content = f.read()
            
        # 1. 验证 LNK 头部固定 76 字节，且前 4 字节为 HeaderSize = 0x0000004C (76)
        if len(content) < 76 or content[:4] != b"\x4c\x00\x00\x00":
            return None
            
        # 2. 读取 LinkFlags (偏移 0x14 - 0x18)
        flags = struct.unpack("<I", content[0x14:0x18])[0]
        has_link_target_id_list = bool(flags & 0x01)
        has_link_info = bool(flags & 0x02)
        
        pos = 76
        # 若存在 LinkTargetIDList，跳过该结构
        if has_link_target_id_list:
            if len(content) < pos + 2:
                return None
            id_list_size = struct.unpack("<H", content[pos:pos+2])[0]
            pos += 2 + id_list_size
            
        # 若存在 LinkInfo 结构，从中提取绝对路径
        if has_link_info:
            if len(content) < pos + 28:
                return None
            link_info_size = struct.unpack("<I", content[pos:pos+4])[0]
            link_info_header_size = struct.unpack("<I", content[pos+4:pos+8])[0]
            local_base_path_offset = struct.unpack("<I", content[pos+16:pos+20])[0]
            
            # Windows Vista+ 扩展支持 Unicode 路径
            unicode_offset = None
            if link_info_header_size >= 36:
                unicode_offset = struct.unpack("<I", content[pos+28:pos+32])[0]
                
            if unicode_offset and unicode_offset > 0 and pos + unicode_offset < len(content):
                raw_u = content[pos + unicode_offset : pos + link_info_size]
                target = raw_u.split(b"\x00\x00")[0].decode("utf-16le", errors="ignore")
                if target and (os.path.exists(target) or "\\" in target):
                    return target
            elif local_base_path_offset and local_base_path_offset > 0 and pos + local_base_path_offset < len(content):
                raw_a = content[pos + local_base_path_offset : pos + link_info_size]
                target = raw_a.split(b"\x00")[0].decode("gbk", errors="ignore")
                if target and (os.path.exists(target) or "\\" in target):
                    return target
    except Exception:
        pass
    return None


def _parse_lnk_com(lnk_path: str) -> Optional[str]:
    """使用 Windows COM 接口作为备用解析手段"""
    if not sys.platform.startswith("win"):
        return None
    try:
        import subprocess
        # 使用 powershell 安全调度 WScript.Shell
        cmd = [
            "powershell", "-NoProfile", "-NonInteractive", "-Command",
            f"$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('{lnk_path}'); $s.TargetPath"
        ]
        res = subprocess.check_output(cmd, creationflags=0x08000000, text=True, timeout=2.0).strip()
        if res and os.path.exists(res):
            return res
    except Exception:
        pass
    return None


def resolve_real_directory(path: Optional[str]) -> Optional[str]:
    """
    智能解析给定的路径：
    1. 若是 Windows .lnk 快捷方式文件：提取其映射的真实 Target 路径；
       - 若 Target 是目录：返回该目录的真实绝对路径；
       - 若 Target 是文件：返回该文件所在的父目录；
    2. 若是 Windows 符号链接 (Symlink) 或目录联接 (Junction)：解开 realpath；
    3. 若是普通目录：返回规范化绝对路径；
    4. 若最终解析出来的路径不存在或无效，返回 None。
    """
    if not path:
        return None
        
    cleaned = os.path.abspath(str(path).strip().strip('"\''))
    
    # 1. 检查是否为 .lnk 快捷方式文件
    if cleaned.lower().endswith(".lnk") or (os.path.isfile(cleaned) and not os.path.isdir(cleaned)):
        target = _parse_lnk_binary(cleaned)
        if not target or not os.path.exists(target):
            target = _parse_lnk_com(cleaned)
            
        if target and os.path.exists(target):
            target = os.path.abspath(os.path.realpath(target))
            if os.path.isdir(target):
                return target
            elif os.path.isfile(target):
                return os.path.dirname(target)
                
    # 2. 普通路径或软链接/Junction 展开
    if os.path.exists(cleaned):
        real = os.path.abspath(os.path.realpath(cleaned))
        if os.path.isdir(real):
            return real
        elif os.path.isfile(real):
            return os.path.dirname(real)
            
    return None


def pick_directory_or_shortcut(parent=None, title="选择目录", initial_dir="") -> Optional[str]:
    """
    弹出支持选择普通文件夹或 Windows 快捷方式 (.lnk) 的交互对话框，
    自动将所选项穿透解析为最终的真实物理目录。
    """
    from PySide6.QtWidgets import QFileDialog

    init_path = initial_dir if (initial_dir and os.path.exists(initial_dir)) else os.path.expanduser("~")

    dialog = QFileDialog(parent, title, init_path)
    dialog.setFileMode(QFileDialog.FileMode.Directory)
    dialog.setOption(QFileDialog.Option.ShowDirsOnly, False)
    dialog.setOption(QFileDialog.Option.DontResolveSymlinks, False)

    if dialog.exec():
        selected = dialog.selectedFiles()
        if selected:
            chosen = selected[0]
            real_dir = resolve_real_directory(chosen)
            if real_dir and os.path.isdir(real_dir):
                return real_dir
    return None
