import sys
import subprocess
import ctypes

RULE_NAME = "LanShareHttpServer"
CREATE_NO_WINDOW = 0x08000000 if sys.platform.startswith("win") else 0

def is_admin() -> bool:
    """判断当前进程是否拥有管理员权限"""
    if not sys.platform.startswith("win"):
        return True
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def add_firewall_rule(port: int, rule_name: str = RULE_NAME) -> bool:
    """为指定端口添加入站放行规则 (TCP 及 UDP 发现)，完全不弹出黑框命令行"""
    if not sys.platform.startswith("win"):
        return True
    
    if not is_admin():
        return False
    
    try:
        # 先清理同名规则
        remove_firewall_rule(rule_name)
        
        # 添加 TCP 规则
        cmd_tcp = [
            "netsh", "advfirewall", "firewall", "add", "rule",
            f"name={rule_name}_TCP",
            "dir=in", "action=allow", "protocol=TCP", f"localport={port}"
        ]
        subprocess.run(
            cmd_tcp,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW
        )
        
        # 添加 UDP 广播规则 (端口 8088)
        cmd_udp = [
            "netsh", "advfirewall", "firewall", "add", "rule",
            f"name={rule_name}_UDP",
            "dir=in", "action=allow", "protocol=UDP", "localport=8088"
        ]
        subprocess.run(
            cmd_udp,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW
        )
        return True
    except Exception as e:
        sys.stderr.write(f"添加防火墙规则失败: {e}\n")
        return False

def remove_firewall_rule(rule_name: str = RULE_NAME) -> bool:
    """清理创建的防火墙规则，完全不弹出黑框命令行"""
    if not sys.platform.startswith("win"):
        return True
    if not is_admin():
        return False
    try:
        subprocess.run(
            ["netsh", "advfirewall", "firewall", "delete", "rule", f"name={rule_name}_TCP"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW
        )
        subprocess.run(
            ["netsh", "advfirewall", "firewall", "delete", "rule", f"name={rule_name}_UDP"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW
        )
        return True
    except Exception:
        return False
