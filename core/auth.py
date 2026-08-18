import time
import uuid
import random
import string
import threading
from typing import Optional, Callable, Dict, List, Tuple, Any

from core.config import ConfigManager

# 4 位验证码字符池 (采用高辨识度英数混合，排除 0/O, 1/I 等易混淆字符)
AUTH_CHARS = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
CODE_REFRESH_INTERVAL = 120.0  # 2 分钟 (120 秒)
AUTH_REQUEST_TIMEOUT = 60.0    # 待审批请求 60 秒超时

class AuthCodeManager:
    """4 位动态验证码管理器 (支持 120s 自动轮换与手动刷新)"""

    def __init__(self, on_code_changed: Optional[Callable[[str, int], None]] = None):
        self._current_code = ""
        self._last_refresh_time = 0.0
        self._on_code_changed = on_code_changed
        self._lock = threading.Lock()
        self._running = False
        self._timer_thread: Optional[threading.Thread] = None
        self.refresh(is_manual=False)

    def start(self):
        with self._lock:
            if self._running:
                return
            self._running = True
            self._timer_thread = threading.Thread(target=self._loop, daemon=True)
            self._timer_thread.start()

    def stop(self):
        with self._lock:
            self._running = False

    def _loop(self):
        while self._running:
            time.sleep(1.0)
            with self._lock:
                now = time.time()
                elapsed = now - self._last_refresh_time
                if elapsed >= CODE_REFRESH_INTERVAL:
                    self._generate_code_locked()
                
            # 每秒触发倒计时更新通知
            if self._on_code_changed:
                try:
                    self._on_code_changed(self.get_code(), self.get_remaining_seconds())
                except Exception:
                    pass

    def _generate_code_locked(self):
        self._current_code = "".join(random.choices(AUTH_CHARS, k=4))
        self._last_refresh_time = time.time()

    def refresh(self, is_manual: bool = False) -> str:
        with self._lock:
            self._generate_code_locked()
            code = self._current_code
            rem = int(CODE_REFRESH_INTERVAL)
        if self._on_code_changed:
            try:
                self._on_code_changed(code, rem)
            except Exception:
                pass
        return code

    def get_code(self) -> str:
        with self._lock:
            return self._current_code

    def get_remaining_seconds(self) -> int:
        with self._lock:
            elapsed = time.time() - self._last_refresh_time
            rem = max(0, int(CODE_REFRESH_INTERVAL - elapsed))
            return rem

    def validate(self, input_code: str) -> bool:
        if not input_code:
            return False
        clean_input = input_code.strip().replace(" ", "").upper()
        with self._lock:
            return clean_input == self._current_code.upper()


class PendingAuthRequest:
    """挂起等待服务端用户确认的客户端授权请求"""

    def __init__(self, request_id: str, device_name: str, ip: str):
        self.request_id = request_id
        self.device_name = device_name
        self.ip = ip
        self.created_time = time.time()
        self.status = "pending"  # "pending", "approved", "rejected", "expired"
        self.event = threading.Event()

    def is_expired(self) -> bool:
        return time.time() - self.created_time > AUTH_REQUEST_TIMEOUT


class ServerAuthManager:
    """服务端权限与设备白名单综合管理器 (白名单生命周期随 App 运行会话保持，重启 App 自动清空)"""

    def __init__(
        self,
        config_manager: Optional[ConfigManager] = None,
        log_callback: Optional[Callable[[str], None]] = None,
        on_request_created: Optional[Callable[[str, str, str], None]] = None
    ):
        self.cfg = config_manager or ConfigManager()
        self.log_callback = log_callback
        self.on_request_created = on_request_created
        self._pending_requests: Dict[str, PendingAuthRequest] = {}
        # 会话级白名单：在服务端 App 运行生命周期内有效；不关界面重新开启/热重启服务时依然保留；重新打开 App 时自动清空
        self._whitelist: List[Dict[str, Any]] = []
        # 是否开启连接权限验证控制 (每次打开服务端均强制默认开启验证码保护)
        self._is_auth_enabled: bool = True
        self._lock = threading.Lock()

        # 初始化 4 位动态验证码管理器
        self.code_mgr = AuthCodeManager(on_code_changed=self._on_code_timer_tick)
        self.code_mgr.start()

    def is_auth_enabled(self) -> bool:
        """获取当前是否开启了权限验证"""
        return self._is_auth_enabled

    def set_auth_enabled(self, enabled: bool):
        """开启或关闭权限验证 (会话级临时生效，保证每次重新打开服务器均默认需要验证码)"""
        self._is_auth_enabled = bool(enabled)
        status_text = "已开启" if enabled else "已关闭"
        self.log(f"【安全权限设置】管理员{status_text}了连接权限验证保护")

    def set_log_callback(self, cb: Callable[[str], None]):
        self.log_callback = cb

    def set_on_request_created(self, cb: Callable[[str, str, str], None]):
        self.on_request_created = cb

    def log(self, msg: str):
        if self.log_callback:
            try:
                self.log_callback(msg)
            except Exception:
                pass

    def _on_code_timer_tick(self, code: str, remaining_seconds: int):
        if remaining_seconds == int(CODE_REFRESH_INTERVAL):
            self.log(f"【动态验证码更新】当前有效验证码: [ {code} ] (有效时长: 2 分钟)")

    def manual_refresh_code(self) -> str:
        code = self.code_mgr.refresh(is_manual=True)
        self.log(f"【用户手动刷新验证码】新验证码已生成: [ {code} ] (有效时长: 2 分钟)")
        return code

    def get_current_code(self) -> str:
        return self.code_mgr.get_code()

    def get_code_remaining_seconds(self) -> int:
        return self.code_mgr.get_remaining_seconds()

    def is_client_authorized(self, device_name: str, ip: str) -> bool:
        """核心校验：检查 (device_name, ip) 是否在当前会话白名单中 (二者严格复合匹配)"""
        if not self._is_auth_enabled:
            return True  # 权限验证已关闭，所有设备免密直接放行
        if not device_name or not ip:
            return False
        d_name = str(device_name).strip().lower()
        ip_addr = str(ip).strip()
        with self._lock:
            for item in self._whitelist:
                if item.get("device_name", "").strip().lower() == d_name and item.get("ip", "").strip() == ip_addr:
                    return True
        return False

    def add_whitelist(self, device_name: str, ip: str) -> bool:
        """将 (device_name, ip) 加入当前会话白名单"""
        if not device_name or not ip:
            return False
        d_name = str(device_name).strip()
        ip_addr = str(ip).strip()
        with self._lock:
            for item in self._whitelist:
                if item.get("device_name", "").strip().lower() == d_name.lower() and item.get("ip", "").strip() == ip_addr:
                    item["auth_time"] = int(time.time())
                    item["device_name"] = d_name
                    item["ip"] = ip_addr
                    return True
            self._whitelist.insert(0, {
                "device_name": d_name,
                "ip": ip_addr,
                "auth_time": int(time.time())
            })
        return True

    def submit_verification(self, device_name: str, ip: str, code: str) -> Tuple[bool, str, Optional[str]]:
        """客户端提交验证码校验"""
        d_name = (device_name or "未知设备").strip()
        ip_addr = (ip or "").strip()

        # 1. 如果已经在当前会话白名单中，直接通过
        if self.is_client_authorized(d_name, ip_addr):
            self.log(f"[{ip_addr}] 设备「{d_name}」已在白名单中，自动允许接入")
            return True, "已在白名单中", None

        # 2. 校验验证码
        if not self.code_mgr.validate(code):
            self.log(f"[{ip_addr}] 设备「{d_name}」验证码校验失败 (提交: '{code}' != 当前码)")
            return False, "验证码错误或已失效，请确认后重试", None

        # 3. 验证码正确，创建待确认审批请求
        req_id = str(uuid.uuid4())[:8]
        req = PendingAuthRequest(req_id, d_name, ip_addr)
        
        with self._lock:
            self._cleanup_expired_locked()
            self._pending_requests[req_id] = req

        self.log(f"[{ip_addr}] 设备「{d_name}」验证码校验成功，正在等待服务端管理员授权确认...")

        # 4. 触发服务端 UI 弹窗通知
        if self.on_request_created:
            try:
                self.on_request_created(req_id, d_name, ip_addr)
            except Exception:
                pass

        return True, "验证码正确，等待服务端确认", req_id

    def poll_request_status(self, request_id: str, timeout: float = 2.0) -> Dict[str, Any]:
        """客户端长轮询授权结果"""
        with self._lock:
            req = self._pending_requests.get(request_id)

        if not req:
            return {"status": "not_found", "message": "授权请求不存在或已过期"}

        if req.is_expired() and req.status == "pending":
            req.status = "expired"
            self.log(f"[{req.ip}] 设备「{req.device_name}」的授权请求已超时未响应")

        if req.status == "pending":
            req.event.wait(timeout)

        return {
            "status": req.status,
            "device_name": req.device_name,
            "ip": req.ip
        }

    def approve_request(self, request_id: str) -> bool:
        """服务端用户批准客户端接入并加入当前会话白名单"""
        with self._lock:
            req = self._pending_requests.get(request_id)
            if not req or req.status != "pending":
                return False
            req.status = "approved"
            req.event.set()

        self.add_whitelist(req.device_name, req.ip)
        self.log(f"[{req.ip}] 管理员已批准设备「{req.device_name}」的连接请求，已成功加入白名单")
        return True

    def reject_request(self, request_id: str) -> bool:
        """服务端用户拒绝客户端接入"""
        with self._lock:
            req = self._pending_requests.get(request_id)
            if not req or req.status != "pending":
                return False
            req.status = "rejected"
            req.event.set()

        self.log(f"[{req.ip}] 管理员已拒绝设备「{req.device_name}」的连接请求")
        return True

    def _cleanup_expired_locked(self):
        """清理已超时的请求"""
        to_del = [k for k, v in self._pending_requests.items() if v.is_expired() and v.status == "pending"]
        for k in to_del:
            del self._pending_requests[k]

    def get_whitelist(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [dict(item) for item in self._whitelist]

    def remove_whitelist_item(self, device_name: str, ip: str) -> bool:
        d_name = str(device_name).strip().lower()
        ip_addr = str(ip).strip()
        with self._lock:
            prev_len = len(self._whitelist)
            self._whitelist = [
                item for item in self._whitelist
                if not (item.get("device_name", "").strip().lower() == d_name and item.get("ip", "").strip() == ip_addr)
            ]
            ok = len(self._whitelist) != prev_len
        if ok:
            self.log(f"已将设备「{device_name}」({ip}) 从白名单中移除")
        return ok

    def clear_whitelist(self):
        with self._lock:
            self._whitelist.clear()
        self.log("已清空当前会话已授权设备白名单")

