import os
import re
import sys
import json
import socket
import urllib.parse
import threading
from typing import Callable, Optional, List, Dict, Any
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from core.auth import ServerAuthManager
from core.hash_utils import get_head_hash, get_breakpoint_prefix_hash, get_sample_hash

__version__ = "4.2"
DISCONNECT_ERRNOS = {10053, 10054, 10058}

def _is_disconnect(exc: BaseException) -> bool:
    if isinstance(exc, (ConnectionResetError, BrokenPipeError, ConnectionAbortedError)):
        return True
    if isinstance(exc, OSError) and getattr(exc, "winerror", None) in DISCONNECT_ERRNOS:
        return True
    if isinstance(exc, socket.timeout):
        return True
    return False

class LanShareRequestHandler(SimpleHTTPRequestHandler):
    server_version = f"LanShareServer/{__version__}"
    share_dir = "."
    log_callback: Optional[Callable[[str], None]] = None
    auth_mgr: Optional[ServerAuthManager] = None

    def log_message(self, fmt, *args):
        # 屏蔽默认 stderr 输出
        pass

    def _notify_log(self, msg: str):
        full_msg = f"[{self.address_string()}] {msg}"
        if LanShareRequestHandler.log_callback:
            try:
                LanShareRequestHandler.log_callback(full_msg)
            except Exception:
                pass
        if sys.stderr:
            sys.stderr.write(full_msg + "\n")

    def _send_json(self, data: Any, code: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _get_device_name(self, parsed_query: Optional[dict] = None) -> str:
        d_name = self.headers.get("X-Device-Name", "")
        if not d_name and parsed_query:
            d_name = parsed_query.get("device_name", [""])[0]
        return urllib.parse.unquote(d_name).strip()

    def _is_client_authorized(self, device_name: str) -> bool:
        if not LanShareRequestHandler.auth_mgr:
            return True
        if not LanShareRequestHandler.auth_mgr.is_auth_enabled():
            return True
        client_ip = self.client_address[0]
        return LanShareRequestHandler.auth_mgr.is_client_authorized(device_name, client_ip)

    def do_HEAD(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path.startswith("/api/"):
            return self.do_GET()
        return self._serve_download(head_only=True)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        device_name = self._get_device_name(query)
        client_ip = self.client_address[0]
        
        # 1. API: 服务器信息与认证状态检查
        if path == "/api/info":
            auth_enabled = LanShareRequestHandler.auth_mgr.is_auth_enabled() if LanShareRequestHandler.auth_mgr else False
            is_auth = self._is_client_authorized(device_name)
            if not auth_enabled:
                if device_name:
                    self._notify_log(f"设备「{device_name}」连接服务 (权限验证已关闭，免密接入)")
            elif is_auth and device_name:
                self._notify_log(f"已授权设备「{device_name}」访问服务信息")
            elif not is_auth and device_name:
                self._notify_log(f"设备「{device_name}」请求连接，需要验证码验证")

            self._send_json({
                "status": "ok",
                "version": __version__,
                "hostname": socket.gethostname(),
                "share_dir": LanShareRequestHandler.share_dir,
                "auth_status": "authorized" if is_auth else "unauthorized",
                "auth_enabled": auth_enabled
            })
            return

        # 2. API: 客户端查询自身当前授权状态
        if path == "/api/auth/status":
            is_auth = self._is_client_authorized(device_name)
            self._send_json({
                "auth_status": "authorized" if is_auth else "unauthorized",
                "device_name": device_name,
                "ip": client_ip
            })
            return

        # 3. API: 客户端长轮询授权申请结果
        if path == "/api/auth/poll":
            req_id = query.get("request_id", [""])[0]
            if not LanShareRequestHandler.auth_mgr:
                self._send_json({"status": "approved", "device_name": device_name, "ip": client_ip})
                return
            res = LanShareRequestHandler.auth_mgr.poll_request_status(req_id, timeout=2.0)
            self._send_json(res)
            return

        # 3.5 API: 探测特定文件的断点哈希信息
        if path == "/api/file/probe":
            if not self._is_client_authorized(device_name):
                self._send_json({"error": "unauthorized"}, code=403)
                return
            
            target_file = urllib.parse.unquote(query.get("path", [""])[0]).strip().strip("/\\")
            if not target_file:
                self._send_json({"error": "invalid path"}, code=400)
                return
                
            base_dir = os.path.abspath(LanShareRequestHandler.share_dir)
            full_path = os.path.abspath(os.path.join(base_dir, target_file))
            try:
                if os.path.commonpath([base_dir, full_path]) != base_dir or not os.path.exists(full_path):
                    self._send_json({"error": "not found", "size": 0}, code=404)
                    return
            except ValueError:
                self._send_json({"error": "invalid path"}, code=400)
                return
                
            offset = int(query.get("offset", ["0"])[0])
            st = os.stat(full_path)
            self._send_json({
                "size": st.st_size,
                "head_hash": get_head_hash(full_path),
                "prefix_hash": get_breakpoint_prefix_hash(full_path, offset) if offset > 0 else "",
                "sample_hash": get_sample_hash(full_path)
            })
            return

        # 4. API: 共享文件清单列表 (严格安全权限拦截与子目录遍历)
        if path == "/api/files":
            if not self._is_client_authorized(device_name):
                self._notify_log(f"【安全拦截】拒绝未授权设备「{device_name or '未知'}」获取共享文件列表 (403 Forbidden)")
                self._send_json({
                    "error": "未通过权限验证，拒绝访问共享文件列表",
                    "auth_status": "unauthorized"
                }, code=403)
                return

            base_dir = os.path.abspath(LanShareRequestHandler.share_dir)
            sub_dir = urllib.parse.unquote(query.get("dir", [""])[0]).strip().strip("/\\")
            if sub_dir:
                target_dir = os.path.abspath(os.path.join(base_dir, sub_dir))
            else:
                target_dir = base_dir

            # 安全防御：防止路径穿越 (Path Traversal) 攻击
            try:
                if os.path.commonpath([base_dir, target_dir]) != base_dir or not os.path.exists(target_dir):
                    self._send_json({"error": "目录不存在或无权访问", "files": [], "current_dir": "", "can_go_up": False}, code=404)
                    return
            except ValueError:
                self._send_json({"error": "无效目录路径", "files": [], "current_dir": "", "can_go_up": False}, code=400)
                return

            dirs_list = []
            files_list = []
            rel_current = os.path.relpath(target_dir, base_dir).replace("\\", "/")
            if rel_current == ".":
                rel_current = ""

            is_recursive = query.get("recursive", ["0"])[0].lower() in ("1", "true", "yes")
            if is_recursive and os.path.isdir(target_dir):
                all_files = []
                for root, dirs, files in os.walk(target_dir):
                    for entry in sorted(files):
                        full_path = os.path.join(root, entry)
                        rel_item_path = os.path.relpath(full_path, base_dir).replace("\\", "/")
                        try:
                            st = os.stat(full_path)
                            all_files.append({
                                "name": entry,
                                "rel_path": rel_item_path,
                                "size": st.st_size,
                                "mtime": int(st.st_mtime),
                                "is_dir": False,
                                "head_hash": get_head_hash(full_path),
                                "sample_hash": get_sample_hash(full_path)
                            })
                        except OSError:
                            pass
                self._send_json({
                    "files": all_files,
                    "current_dir": rel_current,
                    "can_go_up": bool(rel_current)
                })
                return

            if os.path.isdir(target_dir):
                for entry in sorted(os.listdir(target_dir)):
                    full_path = os.path.join(target_dir, entry)
                    rel_item_path = os.path.relpath(full_path, base_dir).replace("\\", "/")
                    try:
                        st = os.stat(full_path)
                        if os.path.isdir(full_path):
                            dirs_list.append({
                                "name": entry,
                                "rel_path": rel_item_path,
                                "size": 0,
                                "mtime": int(st.st_mtime),
                                "is_dir": True
                            })
                        elif os.path.isfile(full_path):
                            files_list.append({
                                "name": entry,
                                "rel_path": rel_item_path,
                                "size": st.st_size,
                                "mtime": int(st.st_mtime),
                                "is_dir": False,
                                "head_hash": get_head_hash(full_path),
                                "sample_hash": get_sample_hash(full_path)
                            })
                    except OSError:
                        pass

            formatted_list = dirs_list + files_list

            self._send_json({
                "files": formatted_list,
                "current_dir": rel_current,
                "can_go_up": bool(rel_current)
            })
            return

        # 5. 静态文件下载 (支持多级相对路径 + 完全对齐稳定传输架构 + 严格权限防护)
        self._serve_download(head_only=False)

    def _serve_download(self, head_only: bool = False):
        parsed = urllib.parse.urlparse(self.path)
        unquoted = urllib.parse.unquote(parsed.path.lstrip("/"))
        base_dir = os.path.abspath(LanShareRequestHandler.share_dir)
        full_path = os.path.abspath(os.path.join(base_dir, unquoted))
        filename = os.path.basename(full_path)

        # 安全防路径穿越检查
        try:
            if os.path.commonpath([base_dir, full_path]) != base_dir:
                self.send_error(403, "Access denied: Path traversal forbidden")
                return
        except ValueError:
            self.send_error(400, "Bad Request: Invalid path")
            return

        device_name = self._get_device_name()
        if not self._is_client_authorized(device_name):
            self._notify_log(f"【安全拦截】拒绝未授权设备「{device_name or '未知'}」下载文件: {unquoted} (403 Forbidden)")
            self.send_error(403, "Access denied: Device not authorized")
            return

        if not os.path.isfile(full_path):
            self.send_error(404, "File not found")
            return

        try:
            f = open(full_path, "rb")
        except OSError:
            self.send_error(403, "Access denied")
            return

        try:
            fs = os.fstat(f.fileno())
            file_size = fs.st_size
            start = 0
            end = file_size - 1
            status = 200
            content_range = None

            range_header = self.headers.get("Range")
            if range_header:
                m = re.match(r"bytes=(\d+)-(\d*)$", range_header.strip())
                if m:
                    start = int(m.group(1))
                    if m.group(2):
                        end = int(m.group(2))
                    if start >= file_size:
                        f.close()
                        self.send_response(416, "Requested Range Not Satisfiable")
                        self.send_header("Content-Range", f"bytes */{file_size}")
                        self.send_header("Content-Length", "0")
                        self.end_headers()
                        return
                    if end > file_size - 1:
                        end = file_size - 1
                    status = 206
                    content_range = f"bytes {start}-{end}/{file_size}"

            self.send_response(status)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(end - start + 1))
            if content_range:
                self.send_header("Content-Range", content_range)
            self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
            self.end_headers()

            if head_only:
                f.close()
                return

            if filename:
                self._notify_log(f"客户端开始下载: {filename} ({start}-{end}/{file_size})")

            f.seek(start)
            try:
                remaining = file_size - start
                while remaining > 0:
                    chunk = f.read(min(65536, remaining))
                    if not chunk:
                        break
                    
                    written = False
                    retries = 0
                    while not written and retries < 100:
                        try:
                            self.wfile.write(chunk)
                            written = True
                        except OSError as we:
                            if getattr(we, "winerror", None) == 10055:  # WSAENOBUFS
                                import time
                                time.sleep(0.01)
                                retries += 1
                            else:
                                raise we
                    if not written:
                        raise OSError("WSAENOBUFS 重试次数超限")
                        
                    remaining -= len(chunk)
            finally:
                f.close()

            if filename:
                self._notify_log(f"【下载完成】{filename}")
        except Exception as e:
            f.close()
            import traceback
            err_str = traceback.format_exc()
            if _is_disconnect(e):
                self._notify_log(f"客户端下载中断: {filename}")
            else:
                self._notify_log(f"传输内部错误: {e}")
                if sys.stderr:
                    sys.stderr.write(f"Download Error: {e}\n{err_str}\n")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # 1. 验证码校验请求
        if path == "/api/auth/verify":
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length).decode("utf-8")
                payload = json.loads(body)
            except Exception as e:
                self._send_json({"success": False, "message": f"请求数据解析失败: {e}"}, code=400)
                return

            device_name = payload.get("device_name", "")
            code = payload.get("code", "")
            client_ip = self.client_address[0]

            if not LanShareRequestHandler.auth_mgr:
                self._send_json({"success": True, "status": "approved", "message": "无需验证"})
                return

            success, msg, req_id = LanShareRequestHandler.auth_mgr.submit_verification(device_name, client_ip, code)
            if success and not req_id:
                self._send_json({"success": True, "status": "approved", "message": msg})
            elif success and req_id:
                self._send_json({"success": True, "status": "pending", "request_id": req_id, "message": msg})
            else:
                self._send_json({"success": False, "status": "code_error", "message": msg}, code=400)
            return

        # 2. 文件上传请求
        self._handle_upload()

    def do_PUT(self):
        self._handle_upload()

    def _handle_upload(self):
        parsed = urllib.parse.urlparse(self.path)
        raw_path = urllib.parse.unquote(parsed.path.lstrip("/"))
        if raw_path.startswith("upload/"):
            rel_path = raw_path[len("upload/"):].lstrip("/")
        else:
            rel_path = raw_path

        if not rel_path:
            self.send_error(400, "Invalid filename or path")
            return

        base_dir = os.path.abspath(LanShareRequestHandler.share_dir)
        safe_file_path = os.path.abspath(os.path.join(base_dir, rel_path))

        # 严格路径穿越 (Path Traversal) 防御校验
        try:
            common = os.path.commonpath([base_dir, safe_file_path])
            if common != base_dir:
                self._notify_log(f"【安全警告】拦截到来自 {self.client_address[0]} 的非法越界上传请求: {rel_path}")
                self.send_error(403, "Forbidden: Path Traversal Prohibited")
                return
        except ValueError:
            self.send_error(400, "Bad Request: Invalid path")
            return

        device_name = self._get_device_name()
        if not self._is_client_authorized(device_name):
            self._notify_log(f"【安全拦截】拒绝未授权设备「{device_name or '未知'}」上传文件: {rel_path} (403 Forbidden)")
            self.send_error(403, "Access denied: Device not authorized")
            return

        cl_header = self.headers.get("Content-Length")
        if cl_header is None:
            self.send_error(411, "Length Required")
            return
            
        try:
            length = int(cl_header)
        except (TypeError, ValueError):
            self.send_error(400, "Invalid Content-Length")
            return

        if length < 0:
            self.send_error(400, "Invalid Content-Length")
            return

        start = 0
        cr = self.headers.get("Content-Range")
        if cr:
            m = re.match(r"bytes\s+(\d+)-(\d+)/(\d+|\*)", cr.strip())
            if not m:
                self.send_error(400, "Bad Content-Range")
                return
            start = int(m.group(1))

        # 自动递归创建目标子目录
        os.makedirs(os.path.dirname(safe_file_path), exist_ok=True)
        dest_path = safe_file_path

        self._notify_log(f"客户端开始上传: {rel_path} (起始偏移={start}, 字节数={length})")

        try:
            # 判断是否需要覆盖写入 (由请求头 X-Overwrite 或 URL 查询参数或 0 字节文件触发)
            parsed_url = urllib.parse.urlparse(self.path)
            query_params = urllib.parse.parse_qs(parsed_url.query)
            overwrite_flag = self.headers.get("X-Overwrite", "0") == "1" or query_params.get("overwrite", ["0"])[0] == "1"
            
            if length == 0 or overwrite_flag:
                if os.path.exists(dest_path):
                    try:
                        os.remove(dest_path)
                    except Exception as e:
                        self._notify_log(f"【覆盖警告】删除旧文件失败: {e}")
                start = 0

            if start > 0:
                if not os.path.exists(dest_path):
                    self.send_error(500, "No base file for resume")
                    return
                out_f = open(dest_path, "r+b")
            else:
                out_f = open(dest_path, "wb")

            with out_f:
                out_f.seek(start)
                remaining = length
                while remaining > 0:
                    read_len = min(65536, remaining)
                    chunk = self.rfile.read(read_len)
                    if not chunk:
                        break
                    out_f.write(chunk)
                    remaining -= len(chunk)

            if remaining == 0:
                self._notify_log(f"【上传完成】{rel_path}")
                self.send_response(201, "Created")
                self.send_header("Content-Length", "0")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
            else:
                self.send_error(400, f"Incomplete upload: missing {remaining} bytes")
                self._notify_log(f"上传未完成: {rel_path} 剩余 {remaining} 字节")
        except Exception as e:
            if _is_disconnect(e):
                self._notify_log(f"客户端上传中断: {rel_path}")
            else:
                self._notify_log(f"上传异常: {rel_path} -> {e}")
                try:
                    self.send_error(500, f"Upload error: {e}")
                except Exception:
                    pass


class LanShareThreadingServer(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        exc = sys.exc_info()[1]
        if _is_disconnect(exc):
            if sys.stderr:
                sys.stderr.write(f"[{client_address[0]}] 客户端已断开连接\n")
        else:
            super().handle_error(request, client_address)


class HttpShareServer:
    """局域网 HTTP 文件共享与 API 服务端封装"""

    def __init__(
        self,
        bind_ip: str = "0.0.0.0",
        port: int = 8080,
        share_dir: str = ".",
        log_callback: Optional[Callable[[str], None]] = None,
        auth_manager: Optional[ServerAuthManager] = None
    ):
        self.bind_ip = bind_ip
        self.port = port
        self.share_dir = os.path.abspath(share_dir)
        self._server: Optional[LanShareThreadingServer] = None
        self._thread: Optional[threading.Thread] = None
        self._is_running = False
        self._log_callback: Optional[Callable[[str], None]] = log_callback
        
        self.auth_mgr = auth_manager or ServerAuthManager(log_callback=log_callback)
        LanShareRequestHandler.auth_mgr = self.auth_mgr
        if log_callback:
            LanShareRequestHandler.log_callback = log_callback

    def set_log_callback(self, cb: Callable[[str], None]):
        self._log_callback = cb
        LanShareRequestHandler.log_callback = cb
        if self.auth_mgr:
            self.auth_mgr.set_log_callback(cb)

    def set_auth_manager(self, auth_mgr: ServerAuthManager):
        self.auth_mgr = auth_mgr
        LanShareRequestHandler.auth_mgr = auth_mgr

    def set_share_dir(self, path: str):
        if path and os.path.exists(path):
            self.share_dir = os.path.abspath(path)
            LanShareRequestHandler.share_dir = self.share_dir

    def is_running(self) -> bool:
        return self._is_running

    def start(self) -> bool:
        if self._is_running:
            return True

        LanShareRequestHandler.share_dir = self.share_dir
        LanShareRequestHandler.log_callback = self._log_callback
        LanShareRequestHandler.auth_mgr = self.auth_mgr

        try:
            self._server = LanShareThreadingServer((self.bind_ip, self.port), LanShareRequestHandler)
            self._is_running = True
            
            self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
            self._thread.start()
            return True
        except Exception as e:
            self._is_running = False
            if self._log_callback:
                self._log_callback(f"启动 HTTP 服务失败 (端口 {self.port}): {e}")
            return False

    def stop(self):
        if not self._is_running:
            return

        self._is_running = False
        if self._server:
            try:
                self._server.shutdown()
                self._server.server_close()
            except Exception:
                pass
            self._server = None
        self._thread = None

# 保持向后兼容别名
HttpFileServer = HttpShareServer
