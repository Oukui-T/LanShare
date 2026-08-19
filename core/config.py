import os
import sys
from PySide6.QtCore import QSettings

class ConfigManager:
    """管理局域网传输工具的配置信息与目录持久化"""
    
    ORGANIZATION = "LanShare"
    APPLICATION = "LanShareV4"
    
    def __init__(self):
        self.settings = QSettings(self.ORGANIZATION, self.APPLICATION)
        self.default_base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # --- 服务端配置 ---
    def get_server_share_dir(self) -> str:
        val = self.settings.value("server/share_dir", self.default_base_dir)
        if not val or not os.path.exists(str(val)):
            return self.default_base_dir
        return os.path.abspath(str(val))
    
    def set_server_share_dir(self, path: str):
        if path and os.path.exists(path):
            self.settings.setValue("server/share_dir", os.path.abspath(path))
            self.settings.sync()
    
    def get_server_port(self) -> int:
        val = self.settings.value("server/port", 9527)
        try:
            return int(val)
        except (ValueError, TypeError):
            return 9527
    
    def set_server_port(self, port: int):
        self.settings.setValue("server/port", int(port))
        self.settings.sync()

    def get_server_auth_enabled(self) -> bool:
        """获取是否开启连接权限验证 (每次启动默认恒为 True)"""
        return True

    def set_server_auth_enabled(self, enabled: bool):
        """设置是否开启连接权限验证 (会话级临时状态，不持久化保存)"""
        # 清理旧版本可能遗留的键值，防止历史数据干扰
        if self.settings.contains("server/auth_enabled"):
            self.settings.remove("server/auth_enabled")
            self.settings.sync()

    # --- 客户端配置 ---
    def get_client_download_dir(self) -> str:
        val = self.settings.value("client/download_dir", self.default_base_dir)
        if not val or not os.path.exists(str(val)):
            return self.default_base_dir
        return os.path.abspath(str(val))
    
    def set_client_download_dir(self, path: str):
        if path and os.path.exists(path):
            self.settings.setValue("client/download_dir", os.path.abspath(path))
            self.settings.sync()

    def get_client_upload_dir(self) -> str:
        val = self.settings.value("client/upload_dir", self.default_base_dir)
        if not val or not os.path.exists(str(val)):
            return self.default_base_dir
        return os.path.abspath(str(val))
    
    def set_client_upload_dir(self, path: str):
        if path and os.path.exists(path):
            self.settings.setValue("client/upload_dir", os.path.abspath(path))
            self.settings.sync()

    def get_client_history_servers(self) -> list:
        val = self.settings.value("client/history_servers", [])
        if isinstance(val, list):
            return [str(item) for item in val if item]
        elif isinstance(val, str) and val:
            return [val]
        return []
    
    def add_client_history_server(self, server_url: str):
        if not server_url:
            return
        history = self.get_client_history_servers()
        if server_url in history:
            history.remove(server_url)
        history.insert(0, server_url)
        # 仅保留最近 10 个
        history = history[:10]
        self.settings.setValue("client/history_servers", history)
        self.settings.sync()

    # --- 服务端设备白名单配置 ---
    def get_server_whitelist(self) -> list:
        """获取已授权的设备白名单列表 [{'device_name': str, 'ip': str, 'auth_time': int}]"""
        import json
        raw = self.settings.value("server/whitelist_json", "[]")
        try:
            if isinstance(raw, str):
                data = json.loads(raw)
            elif isinstance(raw, list):
                data = raw
            else:
                data = []
            if isinstance(data, list):
                return data
        except Exception:
            pass
        return []

    def set_server_whitelist(self, items: list):
        """保存设备白名单列表"""
        import json
        self.settings.setValue("server/whitelist_json", json.dumps(items, ensure_ascii=False))
        self.settings.sync()

    def add_server_whitelist(self, device_name: str, ip: str) -> bool:
        """将 (device_name, ip) 加入白名单 (若已存在则更新时间)"""
        import time
        if not device_name or not ip:
            return False
        d_name = str(device_name).strip()
        ip_addr = str(ip).strip()
        
        whitelist = self.get_server_whitelist()
        # 严格检查复合键 (device_name, ip)
        updated = False
        for item in whitelist:
            if item.get("device_name", "").strip().lower() == d_name.lower() and item.get("ip", "").strip() == ip_addr:
                item["auth_time"] = int(time.time())
                item["device_name"] = d_name
                item["ip"] = ip_addr
                updated = True
                break
        
        if not updated:
            whitelist.insert(0, {
                "device_name": d_name,
                "ip": ip_addr,
                "auth_time": int(time.time())
            })
            
        self.set_server_whitelist(whitelist)
        return True

    def remove_server_whitelist(self, device_name: str, ip: str) -> bool:
        """从白名单移除指定的 (device_name, ip) 设备"""
        d_name = str(device_name).strip().lower()
        ip_addr = str(ip).strip()
        whitelist = self.get_server_whitelist()
        new_list = [
            item for item in whitelist
            if not (item.get("device_name", "").strip().lower() == d_name and item.get("ip", "").strip() == ip_addr)
        ]
        if len(new_list) != len(whitelist):
            self.set_server_whitelist(new_list)
            return True
        return False

    def clear_server_whitelist(self):
        """清空白名单"""
        self.set_server_whitelist([])

    def is_device_whitelisted(self, device_name: str, ip: str) -> bool:
        """检查 (device_name, ip) 是否在白名单中 (二者必须同时严格匹配)"""
        if not device_name or not ip:
            return False
        d_name = str(device_name).strip().lower()
        ip_addr = str(ip).strip()
        for item in self.get_server_whitelist():
            if item.get("device_name", "").strip().lower() == d_name and item.get("ip", "").strip() == ip_addr:
                return True
        return False

