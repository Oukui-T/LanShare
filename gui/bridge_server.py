import os
import sys
import time
import datetime
import subprocess
import threading
from typing import List, Dict, Any

from PySide6.QtCore import QObject, Signal, Slot, Property
from PySide6.QtWidgets import QFileDialog

from core.config import ConfigManager
from core.firewall import add_firewall_rule, remove_firewall_rule, is_admin
from core.discovery import DiscoveryServer, get_lan_ips
from core.http_server import HttpFileServer
from core.auth import ServerAuthManager
from core.shortcut_resolver import pick_directory_or_shortcut

class ServerBridge(QObject):
    """服务端 Python-QML 交互桥接对象 (支持 4 位动态验证码与设备白名单授权)"""

    # 基础与网络信号
    shareDirChanged = Signal()
    portChanged = Signal()
    isRunningChanged = Signal()
    lanIpsChanged = Signal()
    logsChanged = Signal()
    statusMessage = Signal(str, str)  # (type: "info"|"warning"|"error", msg)

    # 权限验证相关信号
    authCodeChanged = Signal()
    codeRemainingSecondsChanged = Signal()
    whitelistChanged = Signal()
    authEnabledChanged = Signal()
    authorizationRequested = Signal(str, str, str)  # (req_id, device_name, ip)
    _sigAuthTimerTick = Signal(str, int)
    _sigAuthRequested = Signal(str, str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cfg = ConfigManager()
        self._share_dir = self.cfg.get_server_share_dir()
        self._port = self.cfg.get_server_port()
        self._is_running = False
        self._lan_ips = []
        self._logs = []
        
        self._http_server = None
        self._discovery_server = None

        # 初始化权限管理器
        self._auth_mgr = ServerAuthManager(
            config_manager=self.cfg,
            log_callback=self.addLog,
            on_request_created=self._on_auth_request_created
        )
        # 连接验证码计时器更新信号至 Qt 主线程
        self._sigAuthTimerTick.connect(self._handle_auth_timer_tick)
        self._sigAuthRequested.connect(self._handle_auth_requested)
        self._auth_mgr.code_mgr._on_code_changed = self._on_code_timer_changed

        self._auth_code = self._auth_mgr.get_current_code()
        self._code_remaining_seconds = self._auth_mgr.get_code_remaining_seconds()

        # 初始同步获取网卡 IP 并显示
        self._refresh_ips_internal(log_result=False)

    def _on_code_timer_changed(self, code: str, remaining_seconds: int):
        self._sigAuthTimerTick.emit(code, remaining_seconds)

    def _handle_auth_timer_tick(self, code: str, remaining_seconds: int):
        self._auth_code = code
        self._code_remaining_seconds = remaining_seconds
        self.authCodeChanged.emit()
        self.codeRemainingSecondsChanged.emit()
        if remaining_seconds == 120:
            self.addLog(f"【动态验证码更新】当前有效验证码: [ {code} ] (有效时长: 2 分钟)")

    def _on_auth_request_created(self, req_id: str, device_name: str, ip: str):
        self._sigAuthRequested.emit(req_id, device_name, ip)

    def _handle_auth_requested(self, req_id: str, device_name: str, ip: str):
        self.authorizationRequested.emit(req_id, device_name, ip)
        self.statusMessage.emit("warning", f"收到设备「{device_name}」({ip}) 的连接授权请求")

    # --- Properties ---

    @Property(str, notify=shareDirChanged)
    def shareDir(self) -> str:
        return self._share_dir

    @shareDir.setter
    def shareDir(self, val: str):
        if val and os.path.exists(val):
            self._share_dir = os.path.abspath(val)
            self.cfg.set_server_share_dir(self._share_dir)
            if self._http_server:
                self._http_server.set_share_dir(self._share_dir)
            self.shareDirChanged.emit()
            self.addLog(f"已更改共享目录为: {self._share_dir}")

    @Property(int, notify=portChanged)
    def port(self) -> int:
        return self._port

    @port.setter
    def port(self, val: int):
        val = int(val) if val else 8080
        if 1 <= val <= 65535 and val != self._port:
            old_port = self._port
            self._port = int(val)
            self.cfg.set_server_port(self._port)
            self.portChanged.emit()
            self._refresh_ips_internal(log_result=False)

            if self._is_running:
                self.addLog(f"端口由 {old_port} 更改为 {self._port}，正在热重启服务...")
                self._restart_server()
            else:
                self.addLog(f"服务端口已设置为: {self._port} (将在点击启动服务时生效)")

    @Property(bool, notify=isRunningChanged)
    def isRunning(self) -> bool:
        return self._is_running

    @Property(list, notify=lanIpsChanged)
    def lanIps(self) -> list:
        return self._lan_ips

    @Property(list, notify=logsChanged)
    def logs(self) -> list:
        return self._logs

    @Property(str, notify=authCodeChanged)
    def authCode(self) -> str:
        return self._auth_code

    @Property(int, notify=codeRemainingSecondsChanged)
    def codeRemainingSeconds(self) -> int:
        return self._code_remaining_seconds

    @Property(list, notify=whitelistChanged)
    def whitelist(self) -> list:
        raw = self._auth_mgr.get_whitelist()
        res = []
        for item in raw:
            auth_t = item.get("auth_time", 0)
            time_str = datetime.datetime.fromtimestamp(auth_t).strftime("%Y-%m-%d %H:%M") if auth_t else "未知"
            res.append({
                "deviceName": item.get("device_name", ""),
                "ip": item.get("ip", ""),
                "authTime": time_str
            })
        return res

    @Property(bool, notify=authEnabledChanged)
    def authEnabled(self) -> bool:
        return self._auth_mgr.is_auth_enabled()

    # --- Slots ---

    @Slot(bool)
    def setAuthEnabled(self, enabled: bool):
        """开启或关闭客户端连接权限验证"""
        self._auth_mgr.set_auth_enabled(enabled)
        self.authEnabledChanged.emit()
        st = "开启" if enabled else "关闭"
        self.statusMessage.emit("info", f"已{st}客户端连接权限验证")

    @Slot()
    def toggleAuthEnabled(self):
        """切换权限验证开启/关闭状态"""
        curr = self._auth_mgr.is_auth_enabled()
        self.setAuthEnabled(not curr)

    @Slot()
    def refreshAuthCode(self):
        """用户手动刷新 4 位动态验证码"""
        new_code = self._auth_mgr.manual_refresh_code()
        self._auth_code = new_code
        self._code_remaining_seconds = 120
        self.authCodeChanged.emit()
        self.codeRemainingSecondsChanged.emit()
        self.statusMessage.emit("info", f"验证码已刷新为: {new_code}")

    @Slot(str, bool)
    def confirmAuthRequest(self, req_id: str, allow: bool):
        """服务端用户确认或拒绝客户端授权请求"""
        if allow:
            ok = self._auth_mgr.approve_request(req_id)
            if ok:
                self.whitelistChanged.emit()
                self.statusMessage.emit("info", "已允许该设备连接并加入白名单")
        else:
            self._auth_mgr.reject_request(req_id)
            self.statusMessage.emit("warning", "已拒绝该设备的连接请求")

    @Slot(str, str)
    def removeWhitelistDevice(self, device_name: str, ip: str):
        """从白名单移除指定的已授权设备"""
        ok = self._auth_mgr.remove_whitelist_item(device_name, ip)
        if ok:
            self.whitelistChanged.emit()
            self.statusMessage.emit("info", f"已将「{device_name}」({ip}) 移出白名单")

    @Slot()
    def clearAllWhitelist(self):
        """清空所有已授权设备白名单"""
        self._auth_mgr.clear_whitelist()
        self.whitelistChanged.emit()
        self.statusMessage.emit("info", "已清空白名单")

    @Slot()
    def selectFolder(self):
        """弹出 Windows 文件夹/快捷方式选择对话框"""
        chosen = pick_directory_or_shortcut(
            parent=None,
            title="选择服务端共享目录",
            initial_dir=self._share_dir
        )
        if chosen:
            self.shareDir = chosen

    @Slot()
    def openShareDir(self):
        """在 Windows 资源管理器中打开当前共享目录"""
        if os.path.exists(self._share_dir):
            if sys.platform.startswith("win"):
                os.startfile(self._share_dir)
            else:
                subprocess.Popen(["xdg-open", self._share_dir])

    @Slot()
    def refreshIps(self):
        """刷新本机局域网 IP 列表"""
        self._refresh_ips_internal(log_result=True)

    def _refresh_ips_internal(self, log_result: bool = False):
        raw_ips = get_lan_ips(force_refresh=True)
        res = []
        for label, ip in raw_ips:
            res.append({
                "label": label,
                "ip": ip,
                "port": self._port,
                "url": f"http://{ip}:{self._port}"
            })
        self._lan_ips = res
        self.lanIpsChanged.emit()

        if log_result:
            ip_desc = ", ".join([f"{item['label']} {item['ip']}:{self._port}" for item in res])
            self.addLog(f"已刷新本机网卡 IP (端口: {self._port}): [{ip_desc}]")

    @Slot()
    def startServer(self):
        """启动 HTTP 传输服务与 UDP 发现应答服务"""
        if self._is_running:
            return

        # 1. 自动放行防火墙
        if is_admin():
            ok = add_firewall_rule(self._port)
            if ok:
                self.addLog(f"防火墙规则已配置: 放行 TCP {self._port} 与 UDP 8088 端口")
            else:
                self.addLog("提示: 自动放行防火墙失败，若客户端无法连接请手动检查防火墙设置")
        else:
            self.addLog("提示: 当前未以管理员权限运行，若客户端无法连接请允许防火墙入站")

        # 2. 启动 HTTP Server
        try:
            self._http_server = HttpFileServer(
                bind_ip="0.0.0.0",
                port=self._port,
                share_dir=self._share_dir,
                log_callback=self.addLog,
                auth_manager=self._auth_mgr
            )
            started = self._http_server.start()
            if not started:
                raise RuntimeError(f"HTTP 端口 {self._port} 绑定失败，可能已被其他程序占用")
        except Exception as e:
            self.addLog(f"错误: HTTP 服务启动失败: {e}")
            self.statusMessage.emit("error", f"端口 {self._port} 启动失败: {e}")
            return

        # 3. 启动 UDP 广播发现服务
        try:
            self._discovery_server = DiscoveryServer(
                http_port=self._port,
                get_share_dir_func=lambda: self._share_dir
            )
            self._discovery_server.start_service()
        except Exception as e:
            self.addLog(f"警告: UDP 广播发现服务启动异常: {e}")

        self._is_running = True
        self.isRunningChanged.emit()
        self.addLog(f"【服务端已启动】端口: {self._port} | 共享目录: {self._share_dir} | 动态验证码: [ {self._auth_code} ]")
        self.statusMessage.emit("info", f"服务端已在端口 {self._port} 成功启动")

    @Slot()
    def stopServer(self):
        """停止服务端"""
        if not self._is_running:
            return

        if self._http_server:
            self._http_server.stop()
            self._http_server = None

        if self._discovery_server:
            self._discovery_server.stop_service()
            self._discovery_server = None

        self._is_running = False
        self.isRunningChanged.emit()
        self.addLog(f"【服务端已停止】(端口 {self._port})")
        self.statusMessage.emit("info", "服务端已停止")

    def _restart_server(self):
        """热重启服务端"""
        if self._http_server:
            self._http_server.stop()
            self._http_server = None
        if self._discovery_server:
            self._discovery_server.stop_service()
            self._discovery_server = None
        
        self._is_running = False
        self.startServer()

    def addLog(self, msg: str):
        """添加日志记录并通知 QML 界面刷新"""
        now_str = datetime.datetime.now().strftime("%H:%M:%S")
        entry = f"[{now_str}] {msg}"
        self._logs.append(entry)
        if len(self._logs) > 300:
            self._logs = self._logs[-300:]
        self.logsChanged.emit()
