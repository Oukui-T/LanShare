import os
import sys
import time
import json
import socket
import urllib.parse
import urllib.request
import threading
import subprocess
from typing import Callable, Optional, List, Dict, Any

from core.hash_utils import get_head_hash, get_sample_hash, get_breakpoint_prefix_hash

_direct_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

def get_default_device_name() -> str:
    try:
        return socket.gethostname()
    except Exception:
        return "LanShareClient"

class HttpClient:
    """HTTP 客户端辅助函数 (支持权限验证与设备标识)"""

    @staticmethod
    def get_server_info(server_url: str, timeout: float = 3.0, device_name: str = "") -> Optional[Dict[str, Any]]:
        dev = device_name or get_default_device_name()
        encoded_dev = urllib.parse.quote(dev)
        url = f"{server_url.rstrip('/')}/api/info?device_name={encoded_dev}"
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "LanShareClient/4.2",
                "X-Device-Name": urllib.parse.quote(dev)
            })
            with _direct_opener.open(req, timeout=timeout) as resp:
                if resp.status == 200:
                    return json.loads(resp.read().decode("utf-8"))
        except Exception:
            pass
        return None

    @staticmethod
    def check_auth_status(server_url: str, device_name: str = "", timeout: float = 3.0) -> Dict[str, Any]:
        dev = device_name or get_default_device_name()
        encoded_dev = urllib.parse.quote(dev)
        url = f"{server_url.rstrip('/')}/api/auth/status?device_name={encoded_dev}"
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "LanShareClient/4.2",
                "X-Device-Name": urllib.parse.quote(dev)
            })
            with _direct_opener.open(req, timeout=timeout) as resp:
                if resp.status == 200:
                    return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            return {"auth_status": "error", "message": str(e)}
        return {"auth_status": "unauthorized"}

    @staticmethod
    def submit_verify_code(server_url: str, code: str, device_name: str = "", timeout: float = 5.0) -> Dict[str, Any]:
        dev = device_name or get_default_device_name()
        url = f"{server_url.rstrip('/')}/api/auth/verify"
        payload = json.dumps({
            "device_name": dev,
            "code": code.strip()
        }).encode("utf-8")

        try:
            req = urllib.request.Request(
                url,
                data=payload,
                headers={
                    "User-Agent": "LanShareClient/4.2",
                    "Content-Type": "application/json; charset=utf-8",
                    "X-Device-Name": urllib.parse.quote(dev)
                },
                method="POST"
            )
            with _direct_opener.open(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data
        except urllib.error.HTTPError as he:
            try:
                err_data = json.loads(he.read().decode("utf-8"))
                return err_data
            except Exception:
                return {"success": False, "status": "code_error", "message": f"HTTP {he.code}: {he.reason}"}
        except Exception as e:
            return {"success": False, "status": "error", "message": f"网络通信失败: {e}"}

    @staticmethod
    def poll_auth_status(server_url: str, request_id: str, device_name: str = "", timeout: float = 3.0) -> Dict[str, Any]:
        dev = device_name or get_default_device_name()
        encoded_dev = urllib.parse.quote(dev)
        url = f"{server_url.rstrip('/')}/api/auth/poll?request_id={urllib.parse.quote(request_id)}&device_name={encoded_dev}"
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "LanShareClient/4.2",
                "X-Device-Name": urllib.parse.quote(dev)
            })
            with _direct_opener.open(req, timeout=timeout) as resp:
                if resp.status == 200:
                    return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            return {"status": "error", "message": str(e)}
        return {"status": "pending"}

    @staticmethod
    def get_remote_files(server_url: str, timeout: float = 4.0, device_name: str = "", dir_path: str = "", recursive: bool = False) -> List[Dict[str, Any]]:
        dev = device_name or get_default_device_name()
        encoded_dev = urllib.parse.quote(dev)
        url = f"{server_url.rstrip('/')}/api/files?device_name={encoded_dev}"
        if dir_path:
            url += f"&dir={urllib.parse.quote(dir_path)}"
        if recursive:
            url += "&recursive=1"
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "LanShareClient/4.3",
                "X-Device-Name": urllib.parse.quote(dev)
            })
            with _direct_opener.open(req, timeout=timeout) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    return data.get("files", [])
        except Exception:
            pass
        return []

    @staticmethod
    def get_remote_file_size(server_url: str, rel_path: str, timeout: float = 3.0, device_name: str = "") -> int:
        dev = device_name or get_default_device_name()
        clean_rel = rel_path.replace("\\", "/").lstrip("/")
        encoded = urllib.parse.quote(clean_rel, safe="/")
        url = f"{server_url.rstrip('/')}/{encoded}"
        try:
            req = urllib.request.Request(url, method="HEAD", headers={
                "User-Agent": "LanShareClient/4.3",
                "X-Device-Name": urllib.parse.quote(dev)
            })
            with _direct_opener.open(req, timeout=timeout) as resp:
                if resp.status in (200, 206):
                    return int(resp.headers.get("Content-Length", 0))
        except Exception:
            pass
        return 0

    @staticmethod
    def get_remote_file_probe(server_url: str, rel_path: str, offset: int, device_name: str = "", timeout: float = 3.0) -> Optional[Dict[str, Any]]:
        dev = device_name or get_default_device_name()
        clean_rel = rel_path.replace("\\", "/").lstrip("/")
        encoded_path = urllib.parse.quote(clean_rel, safe="/")
        encoded_dev = urllib.parse.quote(dev)
        url = f"{server_url.rstrip('/')}/api/file/probe?path={encoded_path}&offset={offset}&device_name={encoded_dev}"
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "LanShareClient/4.4",
                "X-Device-Name": urllib.parse.quote(dev)
            })
            with _direct_opener.open(req, timeout=timeout) as resp:
                if resp.status == 200:
                    return json.loads(resp.read().decode("utf-8"))
        except Exception:
            pass
        return None


class DownloadWorker(threading.Thread):
    """基于底层 curl.exe 构建的下载核心 (支持相对路径与 X-Device-Name 权限请求头)"""

    def __init__(
        self,
        server_url: str,
        filename: str,
        local_dir: str,
        rel_path: str = "",
        expected_size: int = 0,
        device_name: str = "",
        on_progress: Optional[Callable[[int, int, float, str], None]] = None,
        on_finished: Optional[Callable[[bool, str], None]] = None,
        on_breakpoint_prompt: Optional[Callable[[str, int, int], str]] = None
    ):
        super().__init__(daemon=True)
        self.server_url = server_url.rstrip("/")
        self.filename = filename
        self.rel_path = (rel_path or filename).replace("\\", "/").strip("/")
        self.local_dir = local_dir
        self.expected_size = expected_size
        self.device_name = device_name or get_default_device_name()
        self.on_progress = on_progress
        self.on_finished = on_finished
        self.on_breakpoint_prompt = on_breakpoint_prompt
        self._is_cancelled = False
        self._proc = None

    def cancel(self):
        self._is_cancelled = True
        if self._proc:
            try:
                self._proc.kill()
                self._proc.wait(timeout=2.0)
            except Exception:
                pass

    def run(self):
        dest_path = os.path.join(self.local_dir, self.rel_path.replace("/", os.sep))
        try:
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        except Exception as e:
            if self.on_finished: self.on_finished(False, f"无法创建目录: {e}")
            return

        encoded_path = urllib.parse.quote(self.rel_path, safe="/")
        target_url = f"{self.server_url}/{encoded_path}"

        remote_size = self.expected_size if self.expected_size > 0 else HttpClient.get_remote_file_size(self.server_url, self.rel_path, device_name=self.device_name)
        local_size = os.path.getsize(dest_path) if os.path.exists(dest_path) else 0

        overwrite_flag = False
        if local_size > 0 and remote_size > 0 and local_size < remote_size:
            if local_size <= 4096:
                overwrite_flag = True
            else:
                probe = HttpClient.get_remote_file_probe(self.server_url, self.rel_path, local_size, self.device_name)
                if probe:
                    remote_head = probe.get("head_hash", "")
                    remote_prefix = probe.get("prefix_hash", "")
                    local_head = get_head_hash(dest_path)
                    local_prefix = get_breakpoint_prefix_hash(dest_path, local_size)
                    
                    if local_head and local_prefix and local_head == remote_head and local_prefix == remote_prefix:
                        if self.on_breakpoint_prompt:
                            choice = self.on_breakpoint_prompt(self.filename, local_size, remote_size)
                            if choice == "skip":
                                if self.on_finished: self.on_finished(True, f"已跳过传输 ({remote_size} 字节)")
                                return
                            elif choice == "overwrite":
                                overwrite_flag = True
                    else:
                        overwrite_flag = True
        elif remote_size > 0 and local_size == remote_size:
            if self.on_progress: self.on_progress(remote_size, remote_size, 0.0, "文件已完整存在")
            if self.on_finished: self.on_finished(True, f"文件已完整存在 ({remote_size} 字节)")
            return

        if overwrite_flag:
            try:
                os.remove(dest_path)
            except Exception:
                pass

        try:
            CREATE_NO_WINDOW = 0x08000000
            max_retries = 10
            retry_count = 0
            encoded_device_name = urllib.parse.quote(self.device_name)
            
            while retry_count < max_retries and not self._is_cancelled:
                cmd = [
                    "curl.exe", "--noproxy", "*", "-f", "-C", "-", "-o", dest_path,
                    "-H", f"X-Device-Name: {encoded_device_name}",
                    "-s", "--show-error", target_url
                ]
                self._proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=CREATE_NO_WINDOW
                )

                last_time = time.time()
                last_size = os.path.getsize(dest_path) if os.path.exists(dest_path) else 0

                while self._proc.poll() is None:
                    if self._is_cancelled:
                        break
                    
                    time.sleep(0.2)
                    now = time.time()
                    current_size = os.path.getsize(dest_path) if os.path.exists(dest_path) else 0
                    
                    if now - last_time >= 0.5:
                        speed = (current_size - last_size) / (now - last_time)
                        last_size = current_size
                        last_time = now
                        if self.on_progress:
                            self.on_progress(current_size, max(remote_size, current_size), speed, "正在下载...")

                if self._is_cancelled:
                    break

                stderr_out = self._proc.stderr.read().decode("utf-8", errors="ignore").strip()
                final_local_size = os.path.getsize(dest_path) if os.path.exists(dest_path) else 0

                if self._proc.returncode == 0 and (remote_size == 0 or final_local_size == remote_size):
                    break  # Success!
                
                # Retry on failure
                retry_count += 1
                time.sleep(1.0)

            if self._is_cancelled:
                if self.on_finished: self.on_finished(False, "下载已由用户取消")
                return

            if self._proc.returncode == 0 and (remote_size == 0 or final_local_size == remote_size):
                probe = HttpClient.get_remote_file_probe(self.server_url, self.rel_path, 0, self.device_name)
                if probe:
                    remote_sample = probe.get("sample_hash", "")
                    local_sample = get_sample_hash(dest_path)
                    if remote_sample and local_sample and remote_sample != local_sample:
                        if self.on_finished: self.on_finished(False, "文件传输完成但特征校验失败 (文件可能已损坏)")
                        return
                
                if self.on_progress: self.on_progress(final_local_size, final_local_size, 0.0, "下载完成")
                if self.on_finished: self.on_finished(True, f"下载成功 ({final_local_size} 字节)")
            else:
                if self.on_finished: self.on_finished(False, f"传输异常(重试{retry_count}次): 本地({final_local_size}) != 远程({remote_size})\n错误信息: {stderr_out}")

        except Exception as e:
            if self.on_finished: self.on_finished(False, f"下载进程崩溃: {e}")


class UploadWorker(threading.Thread):
    """基于底层 curl.exe 构建的上传核心 (支持 X-Device-Name 权限请求头与代理旁路直连)"""

    def __init__(
        self,
        server_url: str,
        local_filepath: str,
        rel_path: Optional[str] = None,
        device_name: str = "",
        on_progress: Optional[Callable[[int, int, float, str], None]] = None,
        on_finished: Optional[Callable[[bool, str], None]] = None,
        on_breakpoint_prompt: Optional[Callable[[str, int, int], str]] = None
    ):
        super().__init__(daemon=True)
        self.server_url = server_url.rstrip("/")
        self.local_filepath = local_filepath
        self.filename = os.path.basename(local_filepath)
        self.rel_path = (rel_path or self.filename).replace("\\", "/").lstrip("/")
        self.device_name = device_name or get_default_device_name()
        self.on_progress = on_progress
        self.on_finished = on_finished
        self.on_breakpoint_prompt = on_breakpoint_prompt
        self._is_cancelled = False
        self._proc = None

    def cancel(self):
        self._is_cancelled = True
        if self._proc:
            try:
                self._proc.kill()
                self._proc.wait(timeout=2.0)
            except Exception:
                pass

    def run(self):
        if not os.path.isfile(self.local_filepath):
            if self.on_finished: self.on_finished(False, "本地待上传文件不存在")
            return

        local_size = os.path.getsize(self.local_filepath)
        encoded_rel_path = "/".join([urllib.parse.quote(p) for p in self.rel_path.split("/")])
        
        remote_size = HttpClient.get_remote_file_size(self.server_url, self.rel_path, device_name=self.device_name)
        
        overwrite_flag = False
        if remote_size > 0 and local_size > 0 and remote_size < local_size:
            if remote_size <= 4096:
                overwrite_flag = True
            else:
                probe = HttpClient.get_remote_file_probe(self.server_url, self.rel_path, remote_size, self.device_name)
                if probe:
                    remote_head = probe.get("head_hash", "")
                    remote_prefix = probe.get("prefix_hash", "")
                    local_head = get_head_hash(self.local_filepath)
                    local_prefix = get_breakpoint_prefix_hash(self.local_filepath, remote_size)
                    
                    if local_head and local_prefix and local_head == remote_head and local_prefix == remote_prefix:
                        if self.on_breakpoint_prompt:
                            choice = self.on_breakpoint_prompt(self.filename, remote_size, local_size)
                            if choice == "skip":
                                if self.on_finished: self.on_finished(True, f"已跳过推送 ({local_size} 字节)")
                                return
                            elif choice == "overwrite":
                                overwrite_flag = True
                    else:
                        overwrite_flag = True
        elif remote_size > 0 and remote_size == local_size:
            if self.on_progress: self.on_progress(local_size, local_size, 0.0, "服务端已存在完整文件")
            if self.on_finished: self.on_finished(True, f"推送上传成功 ({local_size} 字节)")
            return

        base_target_url = f"{self.server_url}/upload/{encoded_rel_path}"
        
        try:
            CREATE_NO_WINDOW = 0x08000000
            max_retries = 10
            retry_count = 0
            encoded_device_name = urllib.parse.quote(self.device_name)
            
            while retry_count < max_retries and not self._is_cancelled:
                current_remote = HttpClient.get_remote_file_size(self.server_url, self.rel_path, device_name=self.device_name)
                cmd = [
                    "curl.exe", "--noproxy", "*", "-f", "-T", self.local_filepath,
                    "-H", f"X-Device-Name: {encoded_device_name}"
                ]
                
                target_url = base_target_url
                if overwrite_flag:
                    target_url += "?overwrite=1"
                    # 一旦发起覆盖操作，禁止使用 -C 断点参数，必须从头传输整个文件
                    # 同时单次消耗掉此标志位：如果传输意外中断，下次重试时将自然降级为普通的断点续传，防止无限删文件
                    overwrite_flag = False
                else:
                    if current_remote > 0 and current_remote < local_size:
                        cmd.extend(["-C", str(current_remote)])
                        
                cmd.extend(["-s", "--show-error", target_url])

                self._proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=CREATE_NO_WINDOW
                )

                last_time = time.time()
                last_size = current_remote

                while self._proc.poll() is None:
                    if self._is_cancelled:
                        break
                    
                    time.sleep(0.5)
                    now = time.time()
                    polled_remote = HttpClient.get_remote_file_size(self.server_url, self.rel_path, timeout=1.0, device_name=self.device_name)
                    
                    if polled_remote > last_size:
                        speed = (polled_remote - last_size) / (now - last_time)
                        last_size = polled_remote
                        last_time = now
                        if self.on_progress:
                            self.on_progress(polled_remote, local_size, speed, "正在上传...")

                if self._is_cancelled:
                    break

                stderr_out = self._proc.stderr.read().decode("utf-8", errors="ignore").strip()
                final_remote = HttpClient.get_remote_file_size(self.server_url, self.rel_path, device_name=self.device_name)

                # 严格判定：进程退出码必须为 0，且服务端实际收到的文件大小必须等于本地文件大小（空文件除外）
                if self._proc.returncode == 0 and (local_size == 0 or final_remote == local_size):
                    break  # Success!
                
                # Retry on failure
                retry_count += 1
                time.sleep(1.0)

            if self._is_cancelled:
                if self.on_finished: self.on_finished(False, "上传已由用户取消")
                return

            if self._proc.returncode == 0 and (local_size == 0 or final_remote == local_size):
                probe = HttpClient.get_remote_file_probe(self.server_url, self.rel_path, 0, self.device_name)
                if probe:
                    remote_sample = probe.get("sample_hash", "")
                    local_sample = get_sample_hash(self.local_filepath)
                    if remote_sample and local_sample and remote_sample != local_sample:
                        if self.on_finished: self.on_finished(False, "文件推送完成但远端特征校验失败 (文件可能已损坏)")
                        return
                
                if self.on_progress: self.on_progress(local_size, local_size, 0.0, "上传完成")
                if self.on_finished: self.on_finished(True, f"推送上传成功 ({local_size} 字节)")
            else:
                if self.on_finished: self.on_finished(False, f"传输异常(重试{retry_count}次): 远端({final_remote}) != 本地({local_size})\n错误信息: {stderr_out}")

        except Exception as e:
            if self.on_finished: self.on_finished(False, f"上传进程崩溃: {e}")
