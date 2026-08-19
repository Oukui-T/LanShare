import os
import sys
import time
import json
import socket
import select
import threading
import subprocess
from typing import List, Dict, Any, Tuple

DISCOVERY_PORT = 8088
MAGIC_DISCOVER = "LANSHARE_DISCOVER:4.0"
MAGIC_OFFER_PREFIX = "LANSHARE_OFFER:"

_LAN_IPS_CACHE = None
_LAN_IPS_LAST_TIME = 0.0

def get_lan_ips(force_refresh: bool = False) -> List[Tuple[str, str]]:
    """获取本机所有可用局域网 IPv4 及网卡类型 (极速解析，零弹窗)"""
    global _LAN_IPS_CACHE, _LAN_IPS_LAST_TIME
    now = time.time()
    if not force_refresh and _LAN_IPS_CACHE is not None and (now - _LAN_IPS_LAST_TIME < 15.0):
        return _LAN_IPS_CACHE

    if sys.platform.startswith("win"):
        try:
            res = _win_lan_ips()
            if res:
                _LAN_IPS_CACHE = res
                _LAN_IPS_LAST_TIME = now
                return res
        except Exception:
            pass
    res = _generic_lan_ips()
    _LAN_IPS_CACHE = res
    _LAN_IPS_LAST_TIME = now
    return res

def _win_lan_ips() -> List[Tuple[str, str]]:
    """通过 Windows 极速 ipconfig 获取所有网卡 IP，耗时 <0.02s，杜绝 PowerShell 弹窗与卡顿"""
    CREATE_NO_WINDOW = 0x08000000
    try:
        out = subprocess.check_output(
            ["ipconfig"],
            creationflags=CREATE_NO_WINDOW,
            stderr=subprocess.DEVNULL
        )
        text = out.decode("gbk", errors="replace")
    except Exception:
        return _generic_lan_ips()

    current_adapter = ""
    result = []
    seen = set()
    for line in text.splitlines():
        line = line.strip()
        if "适配器" in line or "adapter" in line.lower():
            current_adapter = line.lower()
        elif "IPv4" in line or "ip address" in line.lower():
            parts = line.split(":")
            if len(parts) >= 2:
                ip = parts[1].strip().split("(")[0].strip()
                if ip and not ip.startswith("127.") and ip not in seen:
                    seen.add(ip)
                    if "wlan" in current_adapter or "wi-fi" in current_adapter or "无线" in current_adapter:
                        label = "WiFi"
                    elif ip.startswith("169.254."):
                        label = "网线直连"
                    elif "ethernet" in current_adapter or "以太网" in current_adapter or "本地连接" in current_adapter:
                        label = "有线网"
                    else:
                        label = "局域网"
                    result.append((label, ip))
    return result if result else _generic_lan_ips()

def _generic_lan_ips() -> List[Tuple[str, str]]:
    ips = []
    seen = set()
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127.") and ip not in seen:
                seen.add(ip)
                label = "网线直连" if ip.startswith("169.254.") else "局域网"
                ips.append((label, ip))
    except Exception:
        pass
    return ips


class DiscoveryServer(threading.Thread):
    """服务端 UDP 广播发现应答后台线程"""

    def __init__(self, http_port: int, get_share_dir_func):
        super().__init__(daemon=True)
        self.http_port = http_port
        self.get_share_dir_func = get_share_dir_func
        self._running = False
        self._sock = None

    def start_service(self):
        self._running = True
        self.start()

    def stop_service(self):
        self._running = False
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass

    def run(self):
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._sock.bind(("0.0.0.0", DISCOVERY_PORT))
            self._sock.settimeout(1.0)
        except Exception as e:
            sys.stderr.write(f"UDP Discovery Server 绑定失败: {e}\n")
            return

        while self._running:
            try:
                data, addr = self._sock.recvfrom(2048)
                msg = data.decode("utf-8", errors="ignore").strip()
                if msg.startswith("LANSHARE_DISCOVER"):
                    share_dir = self.get_share_dir_func()
                    payload = {
                        "version": "4.0",
                        "hostname": socket.gethostname(),
                        "port": self.http_port,
                        "share_dir_name": os.path.basename(share_dir) or share_dir,
                        "ips": [ip for _, ip in get_lan_ips()]
                    }
                    resp = (MAGIC_OFFER_PREFIX + json.dumps(payload, ensure_ascii=False)).encode("utf-8")
                    self._sock.sendto(resp, addr)
            except socket.timeout:
                continue
            except (ConnectionResetError, OSError):
                continue
            except Exception:
                if not self._running:
                    break


class DiscoveryClient:
    """客户端零权限局域网服务发现工具"""

    @staticmethod
    def scan_servers(timeout: float = 0.8) -> List[Dict[str, Any]]:
        """向局域网广播发现探针，收集在线服务器列表"""
        discovered = {}
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(0.2)

        probe_data = MAGIC_DISCOVER.encode("utf-8")
        
        # 1. 广播至通用受限广播地址及本地回环 (支持单机测试)
        broadcast_targets = [
            ("255.255.255.255", DISCOVERY_PORT),
            ("127.0.0.1", DISCOVERY_PORT)
        ]
        
        # 2. 补充各物理网卡定向广播地址 (适配双机网线直连 169.254.255.255 及多网卡)
        for _, ip in get_lan_ips():
            parts = ip.split(".")
            if len(parts) == 4:
                if ip.startswith("169.254."):
                    broadcast_targets.append(("169.254.255.255", DISCOVERY_PORT))
                else:
                    broadcast_targets.append((f"{parts[0]}.{parts[1]}.{parts[2]}.255", DISCOVERY_PORT))
        
        start_time = time.time()
        for target in set(broadcast_targets):
            try:
                sock.sendto(probe_data, target)
            except Exception:
                pass

        while time.time() - start_time < timeout:
            try:
                data, addr = sock.recvfrom(4096)
                elapsed_ms = int((time.time() - start_time) * 1000)
                text = data.decode("utf-8", errors="ignore").strip()
                if text.startswith(MAGIC_OFFER_PREFIX):
                    json_str = text[len(MAGIC_OFFER_PREFIX):]
                    info = json.loads(json_str)
                    server_ip = addr[0]
                    server_port = info.get("port", 9527)
                    key = f"{server_ip}:{server_port}"
                    if key not in discovered:
                        discovered[key] = {
                            "ip": server_ip,
                            "port": server_port,
                            "hostname": info.get("hostname", "未知主机"),
                            "share_name": info.get("share_dir_name", "默认共享"),
                            "version": info.get("version", "4.0"),
                            "url": f"http://{server_ip}:{server_port}",
                            "latency_ms": elapsed_ms
                        }
            except socket.timeout:
                continue
            except (ConnectionResetError, OSError):
                continue
            except Exception:
                break

        sock.close()
        return list(discovered.values())
