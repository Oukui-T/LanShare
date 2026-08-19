import os
import sys
import time
import socket
import subprocess
import threading
from typing import List, Dict, Any, Optional

from PySide6.QtCore import QObject, Signal, Slot, Property
from PySide6.QtWidgets import QFileDialog

from core.config import ConfigManager
from core.discovery import DiscoveryClient
from core.http_client import HttpClient, DownloadWorker, UploadWorker, get_default_device_name
from core.shortcut_resolver import pick_directory_or_shortcut

def format_size(bytes_size: int) -> str:
    if bytes_size < 1024:
        return f"{bytes_size} B"
    elif bytes_size < 1024 * 1024:
        return f"{bytes_size / 1024:.1f} KB"
    elif bytes_size < 1024 * 1024 * 1024:
        return f"{bytes_size / (1024 * 1024):.2f} MB"
    else:
        return f"{bytes_size / (1024 * 1024 * 1024):.2f} GB"

def format_speed(speed_bytes_sec: float) -> str:
    return f"{format_size(int(speed_bytes_sec))}/s"

def format_duration(seconds: int) -> str:
    if seconds < 0:
        return "--:--"
    s = int(seconds)
    if s < 3600:
        m = s // 60
        sec = s % 60
        return f"{m:02d}:{sec:02d}"
    else:
        h = s // 3600
        m = (s % 3600) // 60
        sec = s % 60
        return f"{h:02d}:{m:02d}:{sec:02d}"

def parse_host_port(raw: str, default_port: int = 9527):
    """智能解析用户输入的地址，自动分离 IP 和端口，未输端口时默认 9527"""
    s = (raw or "").strip().replace("http://", "").replace("https://", "").rstrip("/")
    if not s:
        return "", default_port
    if ":" in s:
        parts = s.split(":", 1)
        ip = parts[0].strip()
        try:
            port = int(parts[1].strip())
        except ValueError:
            port = default_port
        return ip, port
    else:
        return s, default_port

class ClientBridge(QObject):
    """客户端 Python-QML 交互桥接对象 (支持 4 位动态验证码与服务端确认授权流程)"""

    # 跨线程安全信号
    _sigScanDone = Signal(list)
    _sigConnectDone = Signal(str, int, dict, bool, str)
    _sigAuthSubmitDone = Signal(bool, str, str, str)  # (success, status, req_id, msg)
    _sigAuthPollDone = Signal(bool, str, str)         # (success, status, err_msg)
    _sigFilesDone = Signal(list)
    _sigLocalFilesDone = Signal(list)
    _sigProgress = Signal(int, int, float, str)
    _sigFinished = Signal(bool, str)
    _sigFolderTasksReady = Signal(list, bool, str)    # (tasks, is_folder, folder_name)
    
    breakpointPromptRequested = Signal(str, int, int) # (filename, local_size, remote_size)

    # QML 属性变更通知
    targetAddressChanged = Signal()
    serverOptionsChanged = Signal()
    currentServerUrlChanged = Signal()
    currentServerInfoChanged = Signal()
    isConnectedChanged = Signal()
    remoteFilesChanged = Signal()
    remoteCurrentDirChanged = Signal()
    canGoUpRemoteDirChanged = Signal()
    localUploadFilesChanged = Signal()
    downloadDirChanged = Signal()
    uploadDirChanged = Signal()
    
    isScanningChanged = Signal()
    isConnectingChanged = Signal()
    isTransferringChanged = Signal()
    
    transferProgressChanged = Signal()
    transferTimeChanged = Signal()
    transferQueueChanged = Signal()
    isQueueExpandedChanged = Signal()
    isFolderTransferChanged = Signal()
    batchTotalCountChanged = Signal()
    batchCompletedCountChanged = Signal()
    batchRemainingCountChanged = Signal()

    # 权限认证属性通知
    authNeededChanged = Signal()
    authStatusChanged = Signal()
    authErrorMessageChanged = Signal()
    deviceNameChanged = Signal()

    statusMessage = Signal(str, str)  # (type: "info"|"warning"|"error", msg)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cfg = ConfigManager()
        self._download_dir = self.cfg.get_client_download_dir()
        self._upload_dir = self.cfg.get_client_upload_dir()
        self._device_name = get_default_device_name()
        
        # 确保下载和上传默认目录物理存在
        try:
            os.makedirs(self._download_dir, exist_ok=True)
            os.makedirs(self._upload_dir, exist_ok=True)
        except Exception:
            pass

        self._history_servers = self.cfg.get_client_history_servers()
        
        self._discovered_servers = []
        self._server_options = []
        self._target_address = ""
        self._current_server_url = ""
        self._current_server_info = {}
        self._is_connected = False
        self._remote_files = []
        self._remote_current_dir = ""
        self._local_upload_files = []
        
        self._is_scanning = False
        self._is_connecting = False
        self._is_transferring = False

        # 权限认证状态 ("idle", "verifying", "waiting_confirmation", "approved", "rejected", "code_error")
        self._auth_needed = False
        self._auth_status = "idle"
        self._auth_error_message = ""
        self._current_auth_req_id = ""
        self._auth_poll_thread = None
        
        self._breakpoint_choice_event = threading.Event()
        self._breakpoint_choice = "resume"
        self._pending_breakpoint_events = []
        self._breakpoint_prompt_active = False

        self._transfer_queue = []
        self._is_polling_cancelled = False
        
        # 传输状态与时间统计
        self._transfer_type = ""
        self._transfer_filename = ""
        self._transfer_progress = 0.0
        self._transfer_speed = ""
        self._transfer_status = ""
        self._transfer_result = ""
        self._transfer_success = False
        
        self._transfer_start_time = 0.0
        self._elapsed_time_str = "00:00"
        self._remaining_time_str = "--:--"
        
        # 任务排队与文件夹传输批次统计
        self._transfer_queue = []
        self._current_task = None
        self._is_queue_expanded = False
        self._is_folder_transfer = False
        self._batch_total_count = 0
        self._batch_completed_count = 0

        self._active_worker = None

        # 连接跨线程内部信号
        self._sigScanDone.connect(self._on_scan_done)
        self._sigConnectDone.connect(self._on_connect_done)
        self._sigAuthSubmitDone.connect(self._on_auth_submit_done)
        self._sigAuthPollDone.connect(self._on_auth_poll_done)
        self._sigFilesDone.connect(self._on_files_done)
        self._sigLocalFilesDone.connect(self._on_local_files_done)
        self._sigProgress.connect(self._on_progress_update)
        self._sigFinished.connect(self._on_finished_update)
        self._sigFolderTasksReady.connect(self._on_folder_tasks_ready)

        # 初始加载历史选项与本地待上传文件
        self._rebuild_server_options()
        if self._server_options:
            self._target_address = self._server_options[0]["address"]
        
        self.refreshLocalUploadFiles()

    def _rebuild_server_options(self):
        """合并局域网扫描发现的服务端与历史连接记录"""
        options = []
        seen_addresses = set()

        for s in self._discovered_servers:
            addr = f"{s['ip']}:{s['port']}"
            seen_addresses.add(addr)
            options.append({
                "type": "discovered",
                "display": f"🟢 {s['hostname']} ({addr})",
                "address": addr,
                "hostname": s.get("hostname", ""),
                "latency_ms": s.get("latency_ms", 0)
            })

        for h in self._history_servers:
            h_clean = h.replace("http://", "").replace("https://", "").rstrip("/")
            if h_clean and h_clean not in seen_addresses:
                seen_addresses.add(h_clean)
                options.append({
                    "type": "history",
                    "display": f"🕒 {h_clean}",
                    "address": h_clean,
                    "hostname": "",
                    "latency_ms": 0
                })

        self._server_options = options
        self.serverOptionsChanged.emit()

    # --- Properties 供 QML 绑定 ---

    @Property(str, notify=targetAddressChanged)
    def targetAddress(self) -> str:
        return self._target_address

    @targetAddress.setter
    def targetAddress(self, val: str):
        val = (val or "").strip()
        if val != self._target_address:
            self._target_address = val
            self.targetAddressChanged.emit()

    @Property(list, notify=serverOptionsChanged)
    def serverOptions(self) -> list:
        return self._server_options

    @Property(str, notify=currentServerUrlChanged)
    def currentServerUrl(self) -> str:
        return self._current_server_url

    @Property(dict, notify=currentServerInfoChanged)
    def currentServerInfo(self) -> dict:
        return self._current_server_info

    @Property(bool, notify=isConnectedChanged)
    def isConnected(self) -> bool:
        return self._is_connected

    @Property(list, notify=remoteFilesChanged)
    def remoteFiles(self) -> list:
        return self._remote_files

    @Property(str, notify=remoteCurrentDirChanged)
    def remoteCurrentDir(self) -> str:
        return self._remote_current_dir

    @Property(bool, notify=canGoUpRemoteDirChanged)
    def canGoUpRemoteDir(self) -> bool:
        return bool(self._remote_current_dir)

    @Property(list, notify=localUploadFilesChanged)
    def localUploadFiles(self) -> list:
        return self._local_upload_files

    @Property(str, notify=downloadDirChanged)
    def downloadDir(self) -> str:
        return self._download_dir

    @downloadDir.setter
    def downloadDir(self, val: str):
        if val and os.path.exists(val):
            self._download_dir = os.path.abspath(val)
            self.cfg.set_client_download_dir(self._download_dir)
            self.downloadDirChanged.emit()

    @Property(str, notify=uploadDirChanged)
    def uploadDir(self) -> str:
        return self._upload_dir

    @uploadDir.setter
    def uploadDir(self, val: str):
        if val and os.path.exists(val):
            self._upload_dir = os.path.abspath(val)
            self.cfg.set_client_upload_dir(self._upload_dir)
            self.uploadDirChanged.emit()
            self.refreshLocalUploadFiles()

    @Property(bool, notify=isScanningChanged)
    def isScanning(self) -> bool:
        return self._is_scanning

    @Property(bool, notify=isConnectingChanged)
    def isConnecting(self) -> bool:
        return self._is_connecting

    @Property(bool, notify=isTransferringChanged)
    def isTransferring(self) -> bool:
        return self._is_transferring

    @Property(str, notify=transferProgressChanged)
    def transferType(self) -> str:
        return self._transfer_type

    @Property(str, notify=transferProgressChanged)
    def transferFileName(self) -> str:
        return self._transfer_filename

    @Property(float, notify=transferProgressChanged)
    def transferProgress(self) -> float:
        return self._transfer_progress

    @Property(str, notify=transferProgressChanged)
    def transferSpeedFormatted(self) -> str:
        return self._transfer_speed

    @Property(str, notify=transferProgressChanged)
    def transferStatusText(self) -> str:
        return self._transfer_status

    @Property(str, notify=transferProgressChanged)
    def transferResultText(self) -> str:
        return self._transfer_result

    @Property(bool, notify=transferProgressChanged)
    def transferSuccess(self) -> bool:
        return self._transfer_success

    @Property(str, notify=transferTimeChanged)
    def elapsedTimeFormatted(self) -> str:
        return self._elapsed_time_str

    @Property(str, notify=transferTimeChanged)
    def remainingTimeFormatted(self) -> str:
        return self._remaining_time_str

    @Property(list, notify=transferQueueChanged)
    def transferQueue(self) -> list:
        return self._transfer_queue

    @Property(int, notify=transferQueueChanged)
    def queueCount(self) -> int:
        return len(self._transfer_queue)

    @Property(bool, notify=isQueueExpandedChanged)
    def isQueueExpanded(self) -> bool:
        return self._is_queue_expanded

    @isQueueExpanded.setter
    def isQueueExpanded(self, val: bool):
        if val != self._is_queue_expanded:
            self._is_queue_expanded = val
            self.isQueueExpandedChanged.emit()

    @Property(bool, notify=isFolderTransferChanged)
    def isFolderTransfer(self) -> bool:
        return self._is_folder_transfer

    @Property(int, notify=batchTotalCountChanged)
    def batchTotalCount(self) -> int:
        return self._batch_total_count

    @Property(int, notify=batchCompletedCountChanged)
    def batchCompletedCount(self) -> int:
        return self._batch_completed_count

    @Property(int, notify=batchRemainingCountChanged)
    def batchRemainingCount(self) -> int:
        return max(0, self._batch_total_count - self._batch_completed_count)

    # 权限验证相关属性
    @Property(bool, notify=authNeededChanged)
    def authNeeded(self) -> bool:
        return self._auth_needed

    @Property(str, notify=authStatusChanged)
    def authStatus(self) -> str:
        return self._auth_status

    @Property(str, notify=authErrorMessageChanged)
    def authErrorMessage(self) -> str:
        return self._auth_error_message

    @Property(str, notify=deviceNameChanged)
    def deviceName(self) -> str:
        return self._device_name

    # --- Slots 供 QML 调用 ---

    @Slot(str)
    def connectAddress(self, raw_address: str):
        """统一连接入口：自动解析 IP 与端口并连接"""
        ip, port = parse_host_port(raw_address)
        if not ip:
            self.statusMessage.emit("warning", "请输入有效的服务端 IP 地址")
            return

        addr_str = f"{ip}:{port}"
        server_url = f"http://{addr_str}"
        
        self._target_address = addr_str
        self._current_server_url = server_url
        self.targetAddressChanged.emit()
        self.currentServerUrlChanged.emit()

        self._is_connecting = True
        self.isConnectingChanged.emit()

        def _bg_connect():
            info = HttpClient.get_server_info(server_url, timeout=3.0, device_name=self._device_name)
            if info:
                self._sigConnectDone.emit(ip, port, info, True, "")
            else:
                self._sigConnectDone.emit(ip, port, {}, False, f"未能连接到 {addr_str}，请检查服务端是否开启或防火墙已放行")

        threading.Thread(target=_bg_connect, daemon=True).start()

    def _on_connect_done(self, ip: str, port: int, info: dict, success: bool, err_msg: str):
        self._is_connecting = False
        self.isConnectingChanged.emit()

        if success:
            addr = f"{ip}:{port}"
            self._target_address = addr
            self._current_server_url = f"http://{addr}"
            self._current_server_info = info
            self._remote_current_dir = ""
            self.remoteCurrentDirChanged.emit()
            self.canGoUpRemoteDirChanged.emit()

            self.cfg.add_client_history_server(addr)
            self._history_servers = self.cfg.get_client_history_servers()
            self._rebuild_server_options()

            self.targetAddressChanged.emit()
            self.currentServerUrlChanged.emit()
            self.currentServerInfoChanged.emit()

            auth_status = info.get("auth_status", "authorized")
            hostname = info.get("hostname", "未知服务端")

            if auth_status == "authorized":
                # 已在白名单中，免密直连
                self._auth_needed = False
                self._auth_status = "approved"
                self._is_connected = True
                self.authNeededChanged.emit()
                self.authStatusChanged.emit()
                self.isConnectedChanged.emit()

                self.statusMessage.emit("info", f"【连接成功】已连接至 {hostname} ({addr})")
                self.refreshRemoteFiles()
            else:
                # 需要权限验证，唤起验证码输入弹窗，封锁共享文件列表
                self._is_connected = False
                self._remote_files = []
                self._auth_needed = True
                self._auth_status = "idle"
                self._auth_error_message = ""
                self.isConnectedChanged.emit()
                self.remoteFilesChanged.emit()
                self.authNeededChanged.emit()
                self.authStatusChanged.emit()
                self.authErrorMessageChanged.emit()

                self.statusMessage.emit("warning", f"【需要验证】服务端 {hostname} 要求输入 4 位动态验证码")
        else:
            self._is_connected = False
            self._auth_needed = False
            self._current_server_info = {}
            self._remote_current_dir = ""
            self.remoteCurrentDirChanged.emit()
            self.canGoUpRemoteDirChanged.emit()
            self.isConnectedChanged.emit()
            self.authNeededChanged.emit()
            self.currentServerInfoChanged.emit()
            self.statusMessage.emit("error", err_msg)

    @Slot(str)
    def submitAuthCode(self, code: str):
        """提交 4 位动态验证码"""
        if not self._current_server_url:
            return

        clean_code = (code or "").strip().replace(" ", "")
        if len(clean_code) < 4:
            self._auth_error_message = "请输入完整的 4 位验证码"
            self._auth_status = "code_error"
            self.authStatusChanged.emit()
            self.authErrorMessageChanged.emit()
            return

        self._auth_status = "verifying"
        self._auth_error_message = ""
        self.authStatusChanged.emit()
        self.authErrorMessageChanged.emit()

        def _bg_verify():
            res = HttpClient.submit_verify_code(self._current_server_url, clean_code, device_name=self._device_name)
            success = res.get("success", False)
            status = res.get("status", "code_error")
            req_id = res.get("request_id", "")
            msg = res.get("message", "")
            self._sigAuthSubmitDone.emit(success, status, req_id, msg)

        threading.Thread(target=_bg_verify, daemon=True).start()

    def _on_auth_submit_done(self, success: bool, status: str, req_id: str, msg: str):
        if success and status == "approved":
            # 直接通过授权
            self._handle_auth_approved()
        elif success and status == "pending":
            # 验证码正确，等待管理员确认
            self._auth_status = "waiting_confirmation"
            self._current_auth_req_id = req_id
            self.authStatusChanged.emit()
            self._start_polling_approval(req_id)
        else:
            # 验证码错误
            self._auth_status = "code_error"
            self._auth_error_message = msg or "验证码错误或已失效"
            self.authStatusChanged.emit()
            self.authErrorMessageChanged.emit()

    def _start_polling_approval(self, req_id: str):
        """启动后台轮询等待服务端管理员确认"""
        self._is_polling_cancelled = False

        def _bg_poll():
            start_t = time.time()
            while time.time() - start_t < 60.0 and not self._is_polling_cancelled:
                res = HttpClient.poll_auth_status(self._current_server_url, req_id, device_name=self._device_name, timeout=2.0)
                st = res.get("status")
                if st == "approved":
                    self._sigAuthPollDone.emit(True, "approved", "")
                    return
                elif st == "rejected":
                    self._sigAuthPollDone.emit(False, "rejected", "服务端管理员已拒绝本次连接请求")
                    return
                elif st == "expired":
                    self._sigAuthPollDone.emit(False, "expired", "连接请求已超时未响应")
                    return
                time.sleep(1.0)
            
            if not self._is_polling_cancelled:
                self._sigAuthPollDone.emit(False, "expired", "等待服务端确认超时")

        self._auth_poll_thread = threading.Thread(target=_bg_poll, daemon=True)
        self._auth_poll_thread.start()

    def _on_auth_poll_done(self, success: bool, status: str, err_msg: str):
        if success and status == "approved":
            self._handle_auth_approved()
        else:
            self._auth_status = status
            self._auth_error_message = err_msg
            self.authStatusChanged.emit()
            self.authErrorMessageChanged.emit()
            self.statusMessage.emit("error", err_msg)

    def _handle_auth_approved(self):
        """授权成功处理：关闭弹窗，建立连接，加载共享文件"""
        self._auth_status = "approved"
        self._auth_needed = False
        self._is_connected = True
        self.authStatusChanged.emit()
        self.authNeededChanged.emit()
        self.isConnectedChanged.emit()

        hostname = self._current_server_info.get("hostname", "服务端")
        self.statusMessage.emit("info", f"【授权成功】已成功连接至 {hostname}，已加入白名单")
        self.refreshRemoteFiles()

    @Slot()
    def cancelAuth(self):
        """取消身份验证弹窗并断开连接"""
        self._is_polling_cancelled = True
        self._auth_needed = False
        self._auth_status = "idle"
        self._auth_error_message = ""
        self._is_connected = False
        self.authNeededChanged.emit()
        self.authStatusChanged.emit()
        self.authErrorMessageChanged.emit()
        self.isConnectedChanged.emit()

    @Slot()
    def retryAuth(self):
        """重置验证状态重新输入"""
        self._auth_status = "idle"
        self._auth_error_message = ""
        self.authStatusChanged.emit()
        self.authErrorMessageChanged.emit()

    @Slot()
    def scanServers(self):
        """后台异步 UDP 局域网扫描服务端"""
        if self._is_scanning:
            return

        self._is_scanning = True
        self.isScanningChanged.emit()

        def _bg_scan():
            servers = DiscoveryClient.scan_servers(timeout=1.2)
            self._sigScanDone.emit(servers)

        threading.Thread(target=_bg_scan, daemon=True).start()

    def _on_scan_done(self, servers: list):
        self._discovered_servers = servers
        self._is_scanning = False
        self.isScanningChanged.emit()
        self._rebuild_server_options()

        if servers:
            first = servers[0]
            first_addr = f"{first['ip']}:{first['port']}"
            self.statusMessage.emit("info", f"局域网发现 {len(servers)} 个在线服务端，正在自动连接 {first['hostname']}...")
            self.connectAddress(first_addr)
        else:
            self.statusMessage.emit("warning", "UDP 广播未发现活跃服务端，可直接在上方输入 IP 地址连接")

    @Slot(str)
    def enterRemoteDir(self, dir_name: str):
        """进入指定的远端子目录"""
        clean = (dir_name or "").strip("/\\")
        if not clean:
            return
        if self._remote_current_dir:
            self._remote_current_dir = f"{self._remote_current_dir}/{clean}".strip("/")
        else:
            self._remote_current_dir = clean
        self.remoteCurrentDirChanged.emit()
        self.canGoUpRemoteDirChanged.emit()
        self.refreshRemoteFiles()

    @Slot()
    def goUpRemoteDir(self):
        """返回上一级远端目录"""
        if self._remote_current_dir:
            parts = self._remote_current_dir.split("/")
            parts.pop()
            self._remote_current_dir = "/".join(parts)
            self.remoteCurrentDirChanged.emit()
            self.canGoUpRemoteDirChanged.emit()
            self.refreshRemoteFiles()

    @Slot()
    def refreshRemoteFiles(self):
        """刷新服务端共享文件与子目录列表 (支持多级目录层级)"""
        if not self._current_server_url or not self._is_connected:
            return

        cur_dir = self._remote_current_dir

        def _bg_refresh():
            files = HttpClient.get_remote_files(
                self._current_server_url,
                timeout=3.5,
                device_name=self._device_name,
                dir_path=cur_dir
            )
            dirs = []
            regular_files = []
            for f in files:
                mtime_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(f.get("mtime", 0)))
                if f.get("is_dir"):
                    dirs.append({
                        "name": f["name"],
                        "rel_path": f.get("rel_path", f["name"]),
                        "is_dir": True,
                        "size": 0,
                        "size_formatted": "文件夹",
                        "mtime": mtime_str,
                        "mtime_formatted": mtime_str
                    })
                else:
                    sz = f.get("size", 0)
                    regular_files.append({
                        "name": f["name"],
                        "rel_path": f.get("rel_path", f["name"]),
                        "is_dir": False,
                        "size": sz,
                        "size_formatted": format_size(sz),
                        "mtime": mtime_str,
                        "mtime_formatted": mtime_str
                    })
            formatted = dirs + regular_files
            self._sigFilesDone.emit(formatted)

        threading.Thread(target=_bg_refresh, daemon=True).start()

    def _on_files_done(self, files: list):
        self._remote_files = files
        self.remoteFilesChanged.emit()

    @Property(str, notify=isConnectedChanged)
    def serverStatusLabel(self) -> str:
        if self._is_connected:
            return "🟢 已连接"
        elif self._is_connecting:
            return "⏳ 连接中..."
        elif self._auth_needed:
            return "🔐 等待验证"
        return "⚪ 未连接"

    @Property(bool, notify=uploadDirChanged)
    def canGoUpLocalDir(self) -> bool:
        parent = os.path.dirname(self._upload_dir)
        return bool(parent and os.path.isdir(parent) and parent != self._upload_dir)

    @Slot()
    def refreshLocalUploadFiles(self):
        """刷新本地待推送目录下的所有普通文件"""
        cur_dir = self._upload_dir

        def _bg_local():
            dirs = []
            files = []
            if cur_dir and os.path.exists(cur_dir):
                for entry in sorted(os.listdir(cur_dir)):
                    full_p = os.path.join(cur_dir, entry)
                    try:
                        t_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(full_p)))
                        if os.path.isdir(full_p):
                            dirs.append({
                                "name": entry,
                                "path": full_p,
                                "is_dir": True,
                                "size": 0,
                                "size_formatted": "文件夹",
                                "mtime": t_str,
                                "mtime_formatted": t_str
                            })
                        elif os.path.isfile(full_p):
                            sz = os.path.getsize(full_p)
                            files.append({
                                "name": entry,
                                "path": full_p,
                                "is_dir": False,
                                "size": sz,
                                "size_formatted": format_size(sz),
                                "mtime": t_str,
                                "mtime_formatted": t_str
                            })
                    except OSError:
                        pass
            formatted = dirs + files
            self._sigLocalFilesDone.emit(formatted)

        threading.Thread(target=_bg_local, daemon=True).start()

    def _on_local_files_done(self, files: list):
        self._local_upload_files = files
        self.localUploadFilesChanged.emit()

    @Slot(str)
    def enterLocalDir(self, dir_name: str):
        new_path = os.path.abspath(os.path.join(self._upload_dir, dir_name))
        if os.path.isdir(new_path):
            self.uploadDir = new_path

    @Slot()
    def goUpLocalDir(self):
        parent = os.path.dirname(self._upload_dir)
        if parent and os.path.isdir(parent) and parent != self._upload_dir:
            self.uploadDir = parent

    @Slot()
    def selectDownloadDir(self):
        """弹出本地文件下载保存目录选择对话框 (支持快捷方式穿透解析)"""
        chosen = pick_directory_or_shortcut(
            parent=None,
            title="选择文件下载保存目录",
            initial_dir=self._download_dir
        )
        if chosen:
            self.downloadDir = chosen

    @Slot()
    def selectUploadDir(self):
        """弹出本地文件推送来源目录选择对话框 (支持快捷方式穿透解析)"""
        chosen = pick_directory_or_shortcut(
            parent=None,
            title="选择文件推送来源目录",
            initial_dir=self._upload_dir
        )
        if chosen:
            self.uploadDir = chosen

    @Slot()
    def openDownloadDir(self):
        if os.path.exists(self._download_dir):
            if sys.platform.startswith("win"):
                os.startfile(self._download_dir)
            else:
                subprocess.Popen(["xdg-open", self._download_dir])

    @Slot()
    def openUploadDir(self):
        if os.path.exists(self._upload_dir):
            if sys.platform.startswith("win"):
                os.startfile(self._upload_dir)
            else:
                subprocess.Popen(["xdg-open", self._upload_dir])

    def _queue_tasks(self, task_list: List[dict], is_folder: bool = False):
        """统一的任务入队与调度分发函数"""
        if not task_list:
            return

        for t in task_list:
            if "is_folder" not in t:
                t["is_folder"] = is_folder

        if not self._is_transferring:
            self._is_folder_transfer = is_folder
            self._batch_total_count = len(task_list)
            self._batch_completed_count = 0
            self.isFolderTransferChanged.emit()
            self.batchTotalCountChanged.emit()
            self.batchCompletedCountChanged.emit()
            self.batchRemainingCountChanged.emit()

            first_task = task_list[0]
            self._transfer_queue.extend(task_list[1:])
            self.transferQueueChanged.emit()
            self._start_task(first_task)
        else:
            if is_folder:
                self._is_folder_transfer = True
                self.isFolderTransferChanged.emit()
            self._batch_total_count += len(task_list)
            self.batchTotalCountChanged.emit()
            self.batchRemainingCountChanged.emit()
            self._transfer_queue.extend(task_list)
            self.transferQueueChanged.emit()

    @Slot(str)
    @Slot(str, str)
    def startDownload(self, filename: str, rel_path: str = ""):
        if not self._current_server_url or not filename:
            return

        actual_rel_path = (rel_path or filename).replace("\\", "/").strip("/")

        if self._is_transferring and self._current_task and self._current_task.get("type") == "download" and self._current_task.get("rel_path") == actual_rel_path:
            self.statusMessage.emit("warning", f"「{filename}」正在下载中")
            return

        if any(item.get("type") == "download" and item.get("rel_path") == actual_rel_path for item in self._transfer_queue):
            self.statusMessage.emit("warning", f"「{filename}」已在下载排队列表中")
            return

        expected_size = 0
        for rf in self._remote_files:
            if rf.get("name") == filename or rf.get("rel_path") == actual_rel_path:
                expected_size = rf.get("size", 0)
                break

        task = {
            "id": str(time.time()),
            "type": "download",
            "type_label": "下载",
            "type_icon": "📥",
            "filename": filename,
            "rel_path": actual_rel_path,
            "path": filename,
            "size": expected_size,
            "size_formatted": format_size(expected_size),
            "status": "waiting"
        }
        self._queue_tasks([task], is_folder=False)
        if self._is_transferring and self._current_task != task:
            self.statusMessage.emit("info", f"已加入下载队列: {filename} (排队等待中: {len(self._transfer_queue)})")

    @Slot(str)
    @Slot(str, str)
    def startDownloadFolder(self, folder_name: str, rel_path: str = ""):
        """从服务端递归获取整个文件夹下的全部子文件并加入下载队列"""
        if not self._current_server_url or not folder_name:
            return

        target_rel = (rel_path or folder_name).replace("\\", "/").strip("/")
        self.statusMessage.emit("info", f"正在检索文件夹「{folder_name}」内的全部文件...")

        def _bg_fetch_folder():
            files = HttpClient.get_remote_files(
                self._current_server_url,
                dir_path=target_rel,
                recursive=True,
                device_name=self._device_name
            )
            tasks = []
            if files:
                t_now = time.time()
                for i, f_info in enumerate(files):
                    if f_info.get("is_dir"):
                        continue
                    f_name = f_info.get("name", "")
                    f_rel = f_info.get("rel_path", f_name)
                    f_size = f_info.get("size", 0)
                    tasks.append({
                        "id": f"{t_now}_{i}",
                        "type": "download",
                        "type_label": "下载",
                        "type_icon": "📥",
                        "filename": f_name,
                        "rel_path": f_rel,
                        "path": f_name,
                        "size": f_size,
                        "size_formatted": format_size(f_size),
                        "status": "waiting"
                    })

            self._sigFolderTasksReady.emit(tasks, True, folder_name)

        threading.Thread(target=_bg_fetch_folder, daemon=True).start()

    def _on_folder_tasks_ready(self, tasks: list, is_folder: bool, folder_name: str):
        if not tasks:
            self.statusMessage.emit("warning", f"远端文件夹「{folder_name}」为空或无可用文件")
            return
        self.statusMessage.emit("info", f"已将文件夹「{folder_name}」共 {len(tasks)} 个文件加入下载队列")
        self._queue_tasks(tasks, is_folder=is_folder)

    @Slot(str)
    def startUpload(self, filepath: str):
        if not self._current_server_url or not filepath or not os.path.isfile(filepath):
            return

        filename = os.path.basename(filepath)
        rel_path = filename
        if self._upload_dir and os.path.abspath(filepath).startswith(os.path.abspath(self._upload_dir)):
            rel_path = os.path.relpath(filepath, self._upload_dir).replace("\\", "/")

        if self._is_transferring and self._current_task and self._current_task.get("type") == "upload" and self._current_task.get("path") == filepath:
            self.statusMessage.emit("warning", f"「{filename}」正在推送中")
            return

        if any(item.get("type") == "upload" and item.get("path") == filepath for item in self._transfer_queue):
            self.statusMessage.emit("warning", f"「{filename}」已在推送排队列表中")
            return

        task_size = os.path.getsize(filepath) if os.path.exists(filepath) else 0

        task = {
            "id": str(time.time()),
            "type": "upload",
            "type_label": "推送",
            "type_icon": "🚀",
            "filename": filename,
            "rel_path": rel_path,
            "path": filepath,
            "size": task_size,
            "size_formatted": format_size(task_size),
            "status": "waiting"
        }
        self._queue_tasks([task], is_folder=False)
        if self._is_transferring and self._current_task != task:
            self.statusMessage.emit("info", f"已加入推送队列: {filename} (排队等待中: {len(self._transfer_queue)})")

    @Slot(str)
    def startUploadByName(self, filename: str):
        full_path = os.path.join(self._upload_dir, filename)
        if os.path.isfile(full_path):
            self.startUpload(full_path)
        elif os.path.isdir(full_path):
            self.startUploadFolderByName(filename)

    @Slot(str)
    def startUploadFolderByName(self, folder_name: str):
        """本地递归遍历整个文件夹下的全部子文件并加入推送队列"""
        if not self._current_server_url or not folder_name:
            return

        folder_path = os.path.join(self._upload_dir, folder_name)
        if not os.path.isdir(folder_path):
            self.statusMessage.emit("warning", f"本地文件夹不存在: {folder_name}")
            return

        tasks = []
        t_now = time.time()
        i = 0
        for root, dirs, files in os.walk(folder_path):
            for f in sorted(files):
                full_file_path = os.path.join(root, f)
                rel_path = os.path.relpath(full_file_path, self._upload_dir).replace("\\", "/")
                task_size = os.path.getsize(full_file_path) if os.path.exists(full_file_path) else 0
                tasks.append({
                    "id": f"{t_now}_{i}",
                    "type": "upload",
                    "type_label": "推送",
                    "type_icon": "🚀",
                    "filename": f,
                    "rel_path": rel_path,
                    "path": full_file_path,
                    "size": task_size,
                    "size_formatted": format_size(task_size),
                    "status": "waiting"
                })
                i += 1

        if not tasks:
            self.statusMessage.emit("warning", f"文件夹「{folder_name}」为空，无文件可推送")
            return

        self.statusMessage.emit("info", f"已将文件夹「{folder_name}」共 {len(tasks)} 个文件加入推送队列")
        self._queue_tasks(tasks, is_folder=True)

    @Slot()
    def toggleQueueExpanded(self):
        """切换排队列表的展开/折叠状态"""
        self._is_queue_expanded = not self._is_queue_expanded
        self.isQueueExpandedChanged.emit()

    @Slot(bool)
    def setQueueExpanded(self, expanded: bool):
        """设置排队列表展开/折叠状态"""
        if self._is_queue_expanded != expanded:
            self._is_queue_expanded = expanded
            self.isQueueExpandedChanged.emit()

    @Slot(int)
    def removeQueueItem(self, index: int):
        if 0 <= index < len(self._transfer_queue):
            removed = self._transfer_queue.pop(index)
            if not self._transfer_queue:
                self._is_queue_expanded = False
                self.isQueueExpandedChanged.emit()
            self.transferQueueChanged.emit()
            self.batchRemainingCountChanged.emit()
            self.statusMessage.emit("info", f"已从队列移出: {removed.get('filename')}")

    @Slot()
    def clearQueue(self):
        if self._transfer_queue:
            count = len(self._transfer_queue)
            self._transfer_queue.clear()
            self._is_queue_expanded = False
            self.isQueueExpandedChanged.emit()
            if not self._is_transferring:
                self._is_folder_transfer = False
                self._batch_total_count = 0
                self._batch_completed_count = 0
                self.isFolderTransferChanged.emit()
                self.batchTotalCountChanged.emit()
                self.batchCompletedCountChanged.emit()
            self.transferQueueChanged.emit()
            self.batchRemainingCountChanged.emit()
            self.statusMessage.emit("info", f"已清空全部排队任务 ({count} 个)")

    def _start_task(self, task: dict):
        self._current_task = task
        self._transfer_type = task["type"]
        self._transfer_filename = task["filename"]
        self._is_folder_transfer = task.get("is_folder", False)
        self._transfer_progress = 0.0
        self._transfer_speed = "--/s"
        self._transfer_status = f"正在启动{'下载' if task['type'] == 'download' else '推送'}..."
        self._transfer_result = ""
        self._transfer_success = False
        
        self._transfer_start_time = time.time()
        self._elapsed_time_str = "00:00"
        self._remaining_time_str = "--:--"
        
        self._is_transferring = True

        self.isTransferringChanged.emit()
        self.isFolderTransferChanged.emit()
        self.batchRemainingCountChanged.emit()
        self.transferProgressChanged.emit()
        self.transferTimeChanged.emit()
        self.transferQueueChanged.emit()

        def _on_progress(transferred: int, total: int, speed: float, status_text: str):
            self._sigProgress.emit(transferred, total, speed, status_text)

        def _on_finished(success: bool, msg: str):
            self._sigFinished.emit(success, msg)

        if task["type"] == "download":
            self._active_worker = DownloadWorker(
                server_url=self._current_server_url,
                filename=task["filename"],
                local_dir=self._download_dir,
                rel_path=task.get("rel_path", task["filename"]),
                expected_size=task.get("size", 0),
                device_name=self._device_name,
                on_progress=_on_progress,
                on_finished=_on_finished,
                on_breakpoint_prompt=self._ask_breakpoint_sync
            )
        else:
            self._active_worker = UploadWorker(
                server_url=self._current_server_url,
                local_filepath=task["path"],
                rel_path=task.get("rel_path", task["filename"]),
                device_name=self._device_name,
                on_progress=_on_progress,
                on_finished=_on_finished,
                on_breakpoint_prompt=self._ask_breakpoint_sync
            )
        self._active_worker.start()

    def _on_progress_update(self, transferred: int, total: int, speed: float, status_text: str):
        self._transfer_progress = (transferred / total) if total > 0 else 0.0
        self._transfer_speed = format_speed(speed)
        self._transfer_status = f"{status_text} ({format_size(transferred)} / {format_size(total)})"
        
        elapsed = int(time.time() - self._transfer_start_time)
        self._elapsed_time_str = format_duration(elapsed)
        
        if speed > 1024 and total > transferred:
            remaining = int((total - transferred) / speed)
            self._remaining_time_str = format_duration(remaining)
        elif total > 0 and transferred >= total:
            self._remaining_time_str = "00:00"
        else:
            self._remaining_time_str = "计算中..."

        self.transferProgressChanged.emit()
        self.transferTimeChanged.emit()

    def _on_finished_update(self, success: bool, msg: str):
        curr_type = self._transfer_type
        curr_name = self._transfer_filename

        self._batch_completed_count += 1
        self.batchCompletedCountChanged.emit()
        self.batchRemainingCountChanged.emit()

        if success:
            self.statusMessage.emit("info", f"【传输成功】{curr_name}")
            if curr_type == "upload":
                self.refreshRemoteFiles()
        else:
            if "取消" in msg:
                self.statusMessage.emit("warning", f"【已取消】{curr_name}")
            else:
                self.statusMessage.emit("error", f"【传输失败】{curr_name}: {msg}")

        if self._transfer_queue:
            self._transfer_result = ""
            next_task = self._transfer_queue.pop(0)
            self.transferQueueChanged.emit()
            self.batchRemainingCountChanged.emit()
            self._start_task(next_task)
        else:
            self._is_transferring = False
            self._is_folder_transfer = False
            self._is_queue_expanded = False
            self._active_worker = None
            self._current_task = None
            self._transfer_success = success
            self._transfer_result = msg
            self._transfer_speed = ""
            self._transfer_status = "全部传输已完成" if success else ("下载失败" if curr_type == "download" else "推送失败")
            self._remaining_time_str = "00:00" if success else "--:--"

            self.isTransferringChanged.emit()
            self.isFolderTransferChanged.emit()
            self.isQueueExpandedChanged.emit()
            self.batchRemainingCountChanged.emit()
            self.transferProgressChanged.emit()
            self.transferTimeChanged.emit()
            self.transferQueueChanged.emit()

    @Slot(str)
    def resolveBreakpointPrompt(self, choice: str):
        self._breakpoint_choice = choice
        self._breakpoint_choice_event.set()

    def _ask_breakpoint_sync(self, filename: str, local_size: int, remote_size: int) -> str:
        """阻塞当前 worker 线程并弹出交互，排队处理并发"""
        event = threading.Event()
        result = ["resume"]
        
        self._pending_breakpoint_events.append({
            "filename": filename,
            "local_size": local_size,
            "remote_size": remote_size,
            "event": event,
            "result": result
        })
        
        if not self._breakpoint_prompt_active:
            self._process_next_breakpoint()
            
        event.wait()
        return result[0]
        
    def _process_next_breakpoint(self):
        if not self._pending_breakpoint_events:
            self._breakpoint_prompt_active = False
            return
            
        self._breakpoint_prompt_active = True
        item = self._pending_breakpoint_events[0]
        
        self._breakpoint_choice_event.clear()
        self._breakpoint_choice = "resume"
        
        self.breakpointPromptRequested.emit(item["filename"], item["local_size"], item["remote_size"])
        
        def wait_user():
            self._breakpoint_choice_event.wait()
            item["result"][0] = self._breakpoint_choice
            item["event"].set()
            self._pending_breakpoint_events.pop(0)
            self._process_next_breakpoint()
            
        threading.Thread(target=wait_user, daemon=True).start()

    @Slot()
    def cancelTransfer(self):
        if self._active_worker:
            self._active_worker.cancel()
        else:
            curr_name = self._transfer_filename
            if self._transfer_queue:
                self.statusMessage.emit("warning", f"已跳过/取消当前任务: {curr_name}")
                next_task = self._transfer_queue.pop(0)
                self.transferQueueChanged.emit()
                self.batchRemainingCountChanged.emit()
                self._start_task(next_task)
            else:
                self._is_transferring = False
                self._is_folder_transfer = False
                self._is_queue_expanded = False
                self._current_task = None
                self._transfer_status = "传输已取消"
                self._transfer_result = "用户取消了本次传输"
                self.isTransferringChanged.emit()
                self.isFolderTransferChanged.emit()
                self.isQueueExpandedChanged.emit()
                self.batchRemainingCountChanged.emit()
                self.transferProgressChanged.emit()
                self.transferTimeChanged.emit()
                self.transferQueueChanged.emit()
                self.statusMessage.emit("warning", "已取消传输")

    @Slot()
    def dismissTransfer(self):
        """点击『关闭提示』按钮时收起状态栏并重置结果"""
        self._transfer_result = ""
        self._transfer_status = ""
        self._is_folder_transfer = False
        self._batch_total_count = 0
        self._batch_completed_count = 0
        self.transferProgressChanged.emit()
        self.isFolderTransferChanged.emit()
        self.batchTotalCountChanged.emit()
        self.batchCompletedCountChanged.emit()
        self.batchRemainingCountChanged.emit()

    @Slot()
    def cancelAllTransfers(self):
        if self._transfer_queue:
            self._transfer_queue.clear()
            self.transferQueueChanged.emit()
        
        if self._active_worker:
            self._active_worker.cancel()
            self.statusMessage.emit("warning", "已发出取消指令，正在终止全部任务...")
        else:
            self._is_folder_transfer = False
            self._is_queue_expanded = False
            self._batch_total_count = 0
            self._batch_completed_count = 0
            self.isFolderTransferChanged.emit()
            self.isQueueExpandedChanged.emit()
            self.batchTotalCountChanged.emit()
            self.batchCompletedCountChanged.emit()
            self.batchRemainingCountChanged.emit()
            self.statusMessage.emit("warning", "已取消全部排队与当前传输任务")

    def cleanup(self):
        """应用程序退出时清理资源，终止所有 active worker 进程"""
        if self._transfer_queue:
            self._transfer_queue.clear()
        if self._active_worker:
            try:
                self._active_worker.cancel()
            except Exception:
                pass
            self._active_worker = None
