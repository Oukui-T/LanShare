# 局域网大文件传输工具 V4.0 (GUI 增强版) 架构与设计规格书

## 1. 概述与设计背景
本项目旨在提供一套针对局域网（包含常规家庭/办公 WiFi 路由器网络、有线交换机网络以及双机网线无因特网直连场景）的高性能、免第三方软件、支持双向断点续传的传输工具。

本版本（V4.0）对现有命令行脚本进行全面升级：
1. 使用 **Python 3.7+ / PySide6 + QML (Qt Quick)** 构建现代、流畅、美观的可视化桌面应用。
2. 保持严格的**权限隔离与不对称架构**：
   - **服务端**：具有管理员权限，自动处理 Windows 防火墙入站规则，提供 HTTP 文件读写与 UDP 发现应答。
   - **客户端**：严格运行在普通用户权限（零提权弹窗、零管理员依赖），支持自动发现局域网中所有在线服务端并一键连接。
3. 最终通过 **Nuitka** 编译封装为两个独立的 Windows 独立可执行文件（`.exe`）。

---

## 2. 核心功能与架构分工

### 2.1 服务端（LanShare Server）
- **权限与环境**：运行在有管理员权限的电脑上，Nuitka 打包时声明 `--windows-uac-admin`。
- **防火墙自动化**：启动时自动调用 `netsh advfirewall` 放行指定 TCP/UDP 端口；关闭或退出时支持规则管理。
- **共享目录管理与持久化**：
  - 启动时自动读取上次保存的共享目录；首次运行时默认为程序所在目录。
  - 用户可在界面中直接输入路径，或点击按钮唤起 Windows 原生文件夹选择对话框（`QFileDialog`）。
  - 选择新目录后实时更新共享文件列表并自动持久化保存到配置文件（`QSettings` / `config.json`）。
- **HTTP 核心传输引擎**：
  - `/api/info`：返回服务器基础信息（主机名、版本、当前端口、在线状态）。
  - `/api/files`：返回当前共享目录下的文件清单（包含相对路径、文件名、字节大小、最后修改时间）。
  - `GET / HEAD`：提供大文件下载，完整支持 `Range: bytes=start-end` 头部，返回 `206 Partial Content` 实现断点下载。
  - `POST / PUT`：接收客户端上传，完整支持 `Content-Range: bytes start-end/total`，支持 `seek` 追加断点上传。
- **UDP 服务自发现应答器**：
  - 独立后台线程监听局域网广播端口（默认 UDP 8088）。
  - 接收到客户端发出的 `LANSHARE_DISCOVER` 探针后，立即向客户端单播返回服务器签名、IP、端口及机器标识。
- **图形界面 (QML)**：
  - 服务状态与端口指示、本机所有网卡 IP 清单展示（标注 WiFi/有线/直连）。
  - 共享目录选择与一键打开。
  - 实时传输日志卡片与活动连接监控。
  - 支持系统托盘最小化。

### 2.2 客户端（LanShare Client）
- **权限与环境**：运行在普通用户权限电脑上，Nuitka 打包声明 `--windows-uac-uiaccess=no`，绝不触发 UAC 提权。
- **零权限网络发现引擎**：
  - **UDP 广播探针**：0.1 秒内向 `255.255.255.255:8088` 发送发现包，收集所有在线的服务端 IP 列表。
  - **多网卡/直连网段探测**：利用 `QNetworkInterface` 探测本机全部网卡（包含 `169.254.x.x` 直连网段），即使在网络禁用广播时也可进行网段快扫。
  - **目标选择与历史记录**：在 QML 界面展示可用服务器列表与延迟，支持一键切换与手动 IP 输入。
- **下载与上传目录持久化**：
  - 提供 Windows 原生文件夹选择对话框选择本地存储目录与发送目录。
  - 自动记忆并持久化上次使用的下载目录与发送目录。
- **可视化文件浏览与拉取（Pull）**：
  - 从选中的服务器异步请求 `/api/files`，在 QML 视图中以卡片/列表形式直观展示服务端文件（带图标、格式、大小、时间）。
  - 支持搜索与一键下载，底层调用多线程断点续传下载引擎。
- **可视化文件推送（Push）**：
  - 支持文件选择对话框与文件拖拽上传。
  - 探测服务端同名文件状态，自动支持断点续传并校验传输完整性。
- **传输监控与仪表盘**：
  - 实时显示传输百分比进度条、瞬时速率（MB/s）、已用时间、预估剩余时间。
  - 传输完成后自动执行字节大小比对校验并展示成功/失败状态。

---

## 3. 持久化与数据存储规范

配置持久化采用轻量级 `QSettings`（存储在 Windows 注册表 `HKCU\Software\LanShare` 或项目同级 `lanshare_config.ini`）：
- `server/last_share_dir`：服务端上次使用的共享目录。
- `server/port`：服务端上次监听端口（默认 8080）。
- `client/last_download_dir`：客户端上次保存下载文件的目录。
- `client/last_upload_dir`：客户端上次选择上传文件的目录。
- `client/history_servers`：客户端历史连接过的服务端 IP:端口 列表。

---

## 4. 界面（QML）设计规范
- **设计风格**：Fluent 2.0 / Modern Flat，支持优雅暗色与浅色模式。
- **组件库与动效**：基于 QtQuick.Controls 2 构建，包含流体卡片、悬浮过渡动画、发光进度条和状态徽章。
- **响应式布局**：支持自由拉伸窗口大小，适配不同分辨率屏幕。

---

## 5. Nuitka 编译与构建规格

1. **依赖环境**：
   - Python 3.7+ 虚拟环境（已配置在 `.venv`）。
   - 安装依赖：`pyside6`, `nuitka`, `zstandard`。
2. **服务端打包命令**：
   ```bash
   nuitka --standalone --windows-console-mode=disable --windows-uac-admin --enable-plugin=pyside6 --include-data-dir=gui/qml=qml --output-dir=dist/server server_app.py
   ```
3. **客户端打包命令**：
   ```bash
   nuitka --standalone --windows-console-mode=disable --windows-uac-uiaccess=no --enable-plugin=pyside6 --include-data-dir=gui/qml=qml --output-dir=dist/client client_app.py
   ```
