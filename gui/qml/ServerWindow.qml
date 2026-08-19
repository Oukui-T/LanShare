import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

ApplicationWindow {
    id: root
    width: 820
    height: 660
    minimumWidth: 720
    minimumHeight: 560
    visible: true
    title: "LanShare 传输服务端"
    color: style.bgApp

    Style { id: style }

    // 当前待审批请求数据
    property string pendingReqId: ""
    property string pendingDeviceName: ""
    property string pendingIp: ""

    // 辅助色彩计算函数，避免代理内部在初次求值时出现 undefined 警告
    function getBadgeBg(lbl) {
        if (!lbl) return "#E0F2FE";
        if (lbl === "WiFi") return "#EDE9FE";
        if (lbl === "网线直连") return "#DCFCE7";
        return "#E0F2FE";
    }

    function getBadgeText(lbl) {
        if (!lbl) return "#0369A1";
        if (lbl === "WiFi") return "#6D28D9";
        if (lbl === "网线直连") return "#15803D";
        return "#0369A1";
    }

    // 全局消息提示条
    Rectangle {
        id: toast
        anchors.top: parent.top
        anchors.topMargin: 12
        anchors.horizontalCenter: parent.horizontalCenter
        width: Math.min(parent.width - 40, toastText.implicitWidth + 40)
        height: 36
        radius: style.radiusSm
        color: toastType === "error" ? style.error : (toastType === "warning" ? style.warning : style.primary)
        opacity: 0
        z: 999
        property string toastType: "info"

        Behavior on opacity { NumberAnimation { duration: 250 } }

        Text {
            id: toastText
            anchors.centerIn: parent
            color: "#FFFFFF"
            font.family: style.fontFamily
            font.pixelSize: 13
            font.bold: true
        }

        function show(type, msg) {
            toastType = type;
            toastText.text = msg;
            opacity = 0.95;
            hideTimer.restart();
        }

        Timer {
            id: hideTimer
            interval: 3000
            onTriggered: toast.opacity = 0
        }
    }

    // 监听桥接器发来的状态消息与弹窗信号
    Connections {
        target: bridge

        function onStatusMessage(type, msg) {
            toast.show(type, msg);
        }

        function onAuthorizationRequested(req_id, device_name, ip) {
            root.pendingReqId = req_id;
            root.pendingDeviceName = device_name;
            root.pendingIp = ip;
            authRequestModal.visible = true;
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: style.spaceMd
        spacing: style.spaceMd

        // 1. 顶部 Header
        Rectangle {
            Layout.fillWidth: true
            height: 60
            color: style.bgCard
            radius: style.radiusMd
            border.color: style.borderCard

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: style.spaceMd
                anchors.rightMargin: style.spaceMd
                spacing: 12

                // 品牌图标
                Rectangle {
                    width: 38
                    height: 38
                    radius: style.radiusSm
                    color: style.primaryLight
                    border.color: style.borderCard
                    Text {
                        anchors.centerIn: parent
                        text: "🌐"
                        font.pixelSize: 20
                    }
                }

                Column {
                    Layout.fillWidth: true
                    spacing: 2
                    Text {
                        text: "LanShare 数据传输服务端"
                        color: style.textPrimary
                        font.family: style.fontFamily
                        font.pixelSize: 16
                        font.bold: true
                    }
                    Text {
                        text: "v4.3.2 权限认证版 · 4位动态验证码 · 设备白名单授权"
                        color: style.textSecondary
                        font.family: style.fontFamily
                        font.pixelSize: 11
                    }
                }

                // 运行状态指示徽章
                Rectangle {
                    width: 88
                    height: 30
                    radius: 15
                    color: bridge && bridge.isRunning ? style.successBg : style.errorBg
                    border.color: bridge && bridge.isRunning ? style.successBorder : style.errorBorder

                    Row {
                        anchors.centerIn: parent
                        spacing: 6
                        Rectangle {
                            width: 8
                            height: 8
                            radius: 4
                            color: bridge && bridge.isRunning ? style.success : style.error
                            anchors.verticalCenter: parent.verticalCenter
                            SequentialAnimation on opacity {
                                running: bridge && bridge.isRunning
                                loops: Animation.Infinite
                                NumberAnimation { from: 0.3; to: 1.0; duration: 700 }
                                NumberAnimation { from: 1.0; to: 0.3; duration: 700 }
                            }
                        }
                        Text {
                            text: bridge && bridge.isRunning ? "运行中" : "已停止"
                            color: bridge && bridge.isRunning ? style.success : style.error
                            font.family: style.fontFamily
                            font.pixelSize: 12
                            font.bold: true
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }
                }

                // 验证码查看与管理按键 (宽度自适应动画)
                Button {
                    id: btnAuthCode
                    Layout.preferredWidth: (bridge && !bridge.authEnabled) ? 140 : 96
                    Layout.preferredHeight: 36
                    font.family: style.fontFamily
                    font.pixelSize: 12
                    font.bold: true

                    Behavior on Layout.preferredWidth {
                        NumberAnimation { duration: 150; easing.type: Easing.InOutQuad }
                    }

                    background: Rectangle {
                        radius: style.radiusSm
                        color: btnAuthCode.hovered ? style.primaryLight : ((bridge && !bridge.authEnabled) ? style.bgCardHover : style.bgInput)
                        border.color: btnAuthCode.hovered ? style.primary : ((bridge && !bridge.authEnabled) ? style.warningBorder : style.borderCard)
                        border.width: 1
                        Behavior on color { ColorAnimation { duration: 150 } }
                    }

                    padding: 0
                    leftPadding: 0
                    rightPadding: 0
                    topPadding: 0
                    bottomPadding: 0

                    contentItem: Item {
                        anchors.fill: parent
                        Row {
                            anchors.centerIn: parent
                            spacing: 6
                            Text {
                                text: (bridge && bridge.authEnabled) ? "🔐" : "🔓"
                                font.pixelSize: 13
                                anchors.verticalCenter: parent.verticalCenter
                            }
                            Text {
                                text: (bridge && bridge.authEnabled) ? "验证码" : "验证码 (免密)"
                                font.family: style.fontFamily
                                font.pixelSize: 12
                                font.bold: true
                                color: (bridge && bridge.authEnabled) ? style.primary : style.warning
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }
                    }

                    onClicked: {
                        authModal.visible = true;
                    }
                }

                // 启停控制按钮
                Button {
                    id: btnToggle
                    Layout.preferredWidth: 104
                    Layout.preferredHeight: 36
                    text: bridge && bridge.isRunning ? "停止服务" : "启动服务"
                    font.family: style.fontFamily
                    font.pixelSize: 13
                    font.bold: true

                    background: Rectangle {
                        radius: style.radiusSm
                        color: bridge && bridge.isRunning ? (btnToggle.hovered ? "#B91C1C" : style.error) : (btnToggle.hovered ? style.primaryHover : style.primary)
                        Behavior on color { ColorAnimation { duration: 150 } }
                    }

                    contentItem: Text {
                        text: btnToggle.text
                        font: btnToggle.font
                        color: "#FFFFFF"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }

                    onClicked: {
                        if (bridge) {
                            if (bridge.isRunning) {
                                bridge.stopServer();
                            } else {
                                bridge.startServer();
                            }
                        }
                    }
                }
            }
        }

        // 2. 共享目录与端口配置卡片
        Rectangle {
            Layout.fillWidth: true
            height: 106
            color: style.bgCard
            radius: style.radiusMd
            border.color: style.borderCard

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: style.spaceMd
                spacing: 10

                // 共享目录配置行
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10

                    Text {
                        text: "📂 共享目录:"
                        color: style.textSecondary
                        font.family: style.fontFamily
                        font.pixelSize: 13
                        font.bold: true
                        Layout.preferredWidth: 84
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        height: 32
                        color: style.bgInput
                        radius: style.radiusSm
                        border.color: style.borderCard

                        Text {
                            anchors.fill: parent
                            anchors.leftMargin: 10
                            anchors.rightMargin: 10
                            verticalAlignment: Text.AlignVCenter
                            text: bridge ? bridge.shareDir : ""
                            color: style.textPrimary
                            font.pixelSize: 12
                            elide: Text.ElideMiddle
                        }
                    }

                    Button {
                        id: btnSelectDir
                        text: "选择目录"
                        font.pixelSize: 12
                        Layout.preferredHeight: 32
                        background: Rectangle {
                            radius: style.radiusSm
                            color: btnSelectDir.hovered ? style.bgCardHover : "#FFFFFF"
                            border.color: style.borderCard
                        }
                        contentItem: Text {
                            text: btnSelectDir.text
                            font: btnSelectDir.font
                            color: style.textPrimary
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                        onClicked: {
                            if (bridge) bridge.selectFolder();
                        }
                    }

                    Button {
                        id: btnOpenDir
                        text: "打开目录"
                        font.pixelSize: 12
                        Layout.preferredHeight: 32
                        background: Rectangle {
                            radius: style.radiusSm
                            color: btnOpenDir.hovered ? style.bgCardHover : "#FFFFFF"
                            border.color: style.borderCard
                        }
                        contentItem: Text {
                            text: btnOpenDir.text
                            font: btnOpenDir.font
                            color: style.textPrimary
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                        onClicked: {
                            if (bridge) bridge.openShareDir();
                        }
                    }
                }

                // 服务端口设置行
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10

                    Text {
                        text: "🔌 服务端口:"
                        color: style.textSecondary
                        font.family: style.fontFamily
                        font.pixelSize: 13
                        font.bold: true
                        Layout.preferredWidth: 84
                    }

                    Rectangle {
                        width: 90
                        height: 30
                        color: style.bgInput
                        radius: style.radiusSm
                        border.color: portInput.activeFocus ? style.primary : style.borderCard

                        TextInput {
                            id: portInput
                            anchors.fill: parent
                            anchors.margins: 4
                            verticalAlignment: TextInput.AlignVCenter
                            horizontalAlignment: TextInput.AlignHCenter
                            text: bridge ? bridge.port.toString() : "9527"
                            color: style.textPrimary
                            font.family: style.fontFamily
                            font.pixelSize: 13
                            font.bold: true
                            inputMethodHints: Qt.ImhDigitsOnly

                            onEditingFinished: {
                                if (bridge) {
                                    var val = parseInt(text.trim());
                                    if (!isNaN(val) && val >= 1 && val <= 65535) {
                                        bridge.port = val;
                                    } else {
                                        text = bridge.port.toString();
                                    }
                                }
                            }
                        }
                    }

                    // 悬浮提示图标
                    Rectangle {
                        width: 16
                        height: 16
                        radius: 8
                        color: "transparent"
                        border.color: portHover.hovered ? style.textSecondary : style.textMuted
                        border.width: 1
                        
                        Text {
                            anchors.centerIn: parent
                            text: "!"
                            color: portHover.hovered ? style.textSecondary : style.textMuted
                            font.pixelSize: 11
                        }
                        
                        HoverHandler {
                            id: portHover
                            cursorShape: Qt.PointingHandCursor
                        }
                        
                        ToolTip.visible: portHover.hovered
                        ToolTip.text: "修改后自动保存并生效，默认推荐 9527"
                        ToolTip.delay: 100
                    }

                    Item { Layout.fillWidth: true }
                }
            }
        }

        // 3. 本机可用 IP 列表
        Rectangle {
            Layout.fillWidth: true
            height: 125
            color: style.bgCard
            radius: style.radiusMd
            border.color: style.borderCard

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: style.spaceMd
                spacing: 8

                RowLayout {
                    Layout.fillWidth: true
                    Text {
                        text: "🌐 本机连接地址 (局域网 IP)"
                        color: style.textPrimary
                        font.family: style.fontFamily
                        font.pixelSize: 13
                        font.bold: true
                    }
                    Item { Layout.fillWidth: true }
                    Button {
                        id: btnRefreshIps
                        text: "🔄 刷新网卡"
                        font.pixelSize: 11
                        Layout.preferredHeight: 24
                        background: Rectangle {
                            radius: 4
                            color: btnRefreshIps.hovered ? style.bgCardHover : "transparent"
                        }
                        contentItem: Text {
                            text: btnRefreshIps.text
                            font: btnRefreshIps.font
                            color: style.primary
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                        onClicked: {
                            if (bridge) bridge.refreshIps();
                        }
                    }
                }

                ListView {
                    id: ipListView
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    orientation: ListView.Horizontal
                    spacing: 10
                    clip: true
                    model: bridge ? bridge.lanIps : []

                    delegate: Rectangle {
                        width: 226
                        height: 56
                        radius: style.radiusSm
                        color: style.bgInput
                        border.color: style.borderCard

                        RowLayout {
                            anchors.fill: parent
                            anchors.margins: 10
                            spacing: 10

                            Rectangle {
                                width: 46
                                height: 24
                                radius: 4
                                color: root.getBadgeBg(modelData ? modelData.label : "")
                                Text {
                                    anchors.centerIn: parent
                                    text: modelData && modelData.label ? modelData.label : "局域网"
                                    color: root.getBadgeText(modelData ? modelData.label : "")
                                    font.pixelSize: 10
                                    font.bold: true
                                }
                            }

                            Column {
                                Layout.fillWidth: true
                                Text {
                                    text: modelData && bridge ? (modelData.ip + ":" + bridge.port) : ""
                                    color: style.textPrimary
                                    font.family: style.fontFamily
                                    font.pixelSize: 13
                                    font.bold: true
                                }
                                Text {
                                    text: bridge && bridge.isRunning ? "UDP 广播在线运行" : "等待启动服务"
                                    color: bridge && bridge.isRunning ? style.success : style.textMuted
                                    font.pixelSize: 10
                                    font.bold: true
                                }
                            }
                        }
                    }
                }
            }
        }

        // 4. 实时活动日志
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: style.bgCard
            radius: style.radiusMd
            border.color: style.borderCard

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: style.spaceMd
                spacing: 8

                RowLayout {
                    Layout.fillWidth: true
                    Text {
                        text: "📋 传输与连接日志"
                        color: style.textPrimary
                        font.family: style.fontFamily
                        font.pixelSize: 13
                        font.bold: true
                    }
                    Item { Layout.fillWidth: true }
                    Text {
                        text: "共 " + (bridge ? bridge.logs.length : 0) + " 条记录"
                        color: style.textMuted
                        font.pixelSize: 11
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    color: "#0F172A"  // 终端日志保持深色高对比度
                    radius: style.radiusSm
                    border.color: "#1E293B"

                    ListView {
                        id: logView
                        anchors.fill: parent
                        anchors.margins: 10
                        clip: true
                        model: bridge ? bridge.logs : []
                        onCountChanged: logView.positionViewAtEnd()

                        delegate: Text {
                            width: logView.width
                            text: modelData ? modelData : ""
                            color: modelData && (modelData.indexOf("错误") !== -1 || modelData.indexOf("拒绝") !== -1 || modelData.indexOf("拦截") !== -1) ? "#F87171" : (modelData && (modelData.indexOf("已启动") !== -1 || modelData.indexOf("成功") !== -1 || modelData.indexOf("批准") !== -1) ? "#34D399" : (modelData && modelData.indexOf("验证码") !== -1 ? "#38BDF8" : "#E2E8F0"))
                            font.family: "Consolas, 'Courier New', monospace"
                            font.pixelSize: 11
                            wrapMode: Text.WrapAnywhere
                        }
                    }
                }
            }
        }
    }

    // ==========================================
    // 弹窗 1: 4 位动态验证码与白名单管理模态窗口
    // ==========================================
    Rectangle {
        id: authModal
        anchors.fill: parent
        color: "#80000000"
        visible: false
        z: 1000

        MouseArea {
            anchors.fill: parent
            onClicked: {} // 阻止点击穿透
        }

        Rectangle {
            id: authCard
            width: 540
            height: 590
            anchors.centerIn: parent
            color: style.bgCard
            radius: style.radiusLg
            border.color: style.borderCard

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 24
                spacing: 14

                // 标题栏
                RowLayout {
                    Layout.fillWidth: true
                    Text {
                        text: (bridge && bridge.authEnabled) ? "🔐 服务端连接权限与验证码" : "🔓 服务端连接权限 (免密模式)"
                        color: style.textPrimary
                        font.family: style.fontFamily
                        font.pixelSize: 17
                        font.bold: true
                    }
                    Item { Layout.fillWidth: true }
                    Button {
                        text: "✖"
                        font.pixelSize: 13
                        background: Rectangle { color: "transparent" }
                        contentItem: Text { text: "✖"; color: style.textMuted; font.bold: true }
                        onClicked: authModal.visible = false
                    }
                }

                // 权限验证开关控制卡片 (Fluent 风格 Switch)
                Rectangle {
                    Layout.fillWidth: true
                    height: 54
                    radius: style.radiusMd
                    color: (bridge && bridge.authEnabled) ? style.primaryLight : style.bgInput
                    border.color: (bridge && bridge.authEnabled) ? style.primary : style.borderCard
                    border.width: 1

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 14
                        anchors.rightMargin: 14
                        spacing: 12

                        Text {
                            text: (bridge && bridge.authEnabled) ? "🛡️" : "🔓"
                            font.pixelSize: 20
                        }

                        Column {
                            Layout.fillWidth: true
                            spacing: 2
                            Text {
                                text: "启用客户端连接权限验证"
                                color: style.textPrimary
                                font.family: style.fontFamily
                                font.pixelSize: 13
                                font.bold: true
                            }
                            Text {
                                text: (bridge && bridge.authEnabled) ? "已开启：客户端连接需输入 4 位动态验证码并经您授权确认" : "已关闭：所有局域网设备均可免密直连，无需输入验证码"
                                color: (bridge && bridge.authEnabled) ? style.primary : style.textMuted
                                font.pixelSize: 11
                            }
                        }

                        // 自定义现代 Switch 开关
                        Rectangle {
                            id: authSwitch
                            width: 48
                            height: 26
                            radius: 13
                            color: (bridge && bridge.authEnabled) ? style.primary : style.textMuted
                            Behavior on color { ColorAnimation { duration: 150 } }

                            Rectangle {
                                width: 20
                                height: 20
                                radius: 10
                                color: "#FFFFFF"
                                anchors.verticalCenter: parent.verticalCenter
                                x: (bridge && bridge.authEnabled) ? (parent.width - width - 3) : 3
                                Behavior on x { NumberAnimation { duration: 150; easing.type: Easing.InOutQuad } }
                            }

                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    if (bridge) bridge.toggleAuthEnabled();
                                }
                            }
                        }
                    }
                }

                // 核心大号验证码展示卡片
                Rectangle {
                    Layout.fillWidth: true
                    height: 116
                    radius: style.radiusMd
                    color: (bridge && bridge.authEnabled) ? style.bgCard : style.bgInput
                    border.color: (bridge && bridge.authEnabled) ? style.primary : style.borderCard
                    border.width: (bridge && bridge.authEnabled) ? 1 : 1
                    opacity: (bridge && bridge.authEnabled) ? 1.0 : 0.55

                    ColumnLayout {
                        anchors.centerIn: parent
                        spacing: 6

                        Text {
                            text: (bridge && bridge.authEnabled) ? (bridge.authCode || "----") : "---- (已免密)"
                            color: (bridge && bridge.authEnabled) ? style.primary : style.textMuted
                            font.family: "Consolas, 'Courier New', monospace"
                            font.pixelSize: (bridge && bridge.authEnabled) ? 38 : 28
                            font.bold: true
                            font.letterSpacing: (bridge && bridge.authEnabled) ? 8 : 4
                            horizontalAlignment: Text.AlignHCenter
                            Layout.alignment: Qt.AlignHCenter
                        }

                        RowLayout {
                            spacing: 12
                            Layout.alignment: Qt.AlignHCenter

                            // 倒计时指示
                            Text {
                                text: (bridge && bridge.authEnabled) ? ("⏱️ " + (bridge ? bridge.codeRemainingSeconds : 0) + " 秒后自动轮换") : "⚪ 当前无需验证码即可连接"
                                color: style.textSecondary
                                font.pixelSize: 11
                                font.bold: true
                            }

                            // 手动立即刷新按键
                            Button {
                                id: btnManualRefresh
                                text: "🔄 立即刷新"
                                font.pixelSize: 11
                                font.bold: true
                                enabled: bridge && bridge.authEnabled
                                Layout.preferredHeight: 24
                                background: Rectangle {
                                    radius: 4
                                    color: btnManualRefresh.hovered ? "#FFFFFF" : "transparent"
                                    border.color: btnManualRefresh.enabled ? style.primary : style.borderCard
                                    border.width: 1
                                }
                                contentItem: Text {
                                    text: btnManualRefresh.text
                                    font: btnManualRefresh.font
                                    color: btnManualRefresh.enabled ? style.primary : style.textMuted
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                }
                                onClicked: {
                                    if (bridge) bridge.refreshAuthCode();
                                }
                            }
                        }
                    }
                }

                // 倒计时进度条
                Rectangle {
                    Layout.fillWidth: true
                    height: 4
                    radius: 2
                    color: style.borderCard
                    visible: bridge && bridge.authEnabled

                    Rectangle {
                        height: parent.height
                        radius: 2
                        color: style.primary
                        width: parent.width * (bridge ? (bridge.codeRemainingSeconds / 120.0) : 0)
                        Behavior on width { NumberAnimation { duration: 200 } }
                    }
                }

                // 白名单管理区域
                RowLayout {
                    Layout.fillWidth: true
                    Text {
                        text: "📋 已授权设备白名单 (" + (bridge ? bridge.whitelist.length : 0) + ")"
                        color: style.textPrimary
                        font.family: style.fontFamily
                        font.pixelSize: 13
                        font.bold: true
                    }
                    Item { Layout.fillWidth: true }
                    Button {
                        text: "清空白名单"
                        font.pixelSize: 11
                        visible: bridge && bridge.whitelist.length > 0
                        background: Rectangle { color: "transparent" }
                        contentItem: Text { text: "清空白名单"; color: style.error; font.pixelSize: 11 }
                        onClicked: {
                            if (bridge) bridge.clearAllWhitelist();
                        }
                    }
                }

                // 白名单设备列表
                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    radius: style.radiusSm
                    color: style.bgInput
                    border.color: style.borderCard
                    clip: true

                    ListView {
                        id: whitelistView
                        anchors.fill: parent
                        anchors.margins: 8
                        spacing: 6
                        model: bridge ? bridge.whitelist : []

                        delegate: Rectangle {
                            width: whitelistView.width
                            height: 40
                            radius: 4
                            color: "#FFFFFF"
                            border.color: style.borderCard

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 10
                                anchors.rightMargin: 10
                                spacing: 10

                                Text {
                                    text: "💻"
                                    font.pixelSize: 14
                                }

                                Column {
                                    Layout.fillWidth: true
                                    Text {
                                        text: modelData.deviceName + " (" + modelData.ip + ")"
                                        color: style.textPrimary
                                        font.pixelSize: 12
                                        font.bold: true
                                    }
                                    Text {
                                        text: "授权时间: " + modelData.authTime
                                        color: style.textMuted
                                        font.pixelSize: 10
                                    }
                                }

                                Button {
                                    text: "移出"
                                    font.pixelSize: 10
                                    Layout.preferredHeight: 22
                                    background: Rectangle {
                                        radius: 3
                                        color: style.errorBg
                                        border.color: style.errorBorder
                                    }
                                    contentItem: Text {
                                        text: "移出"
                                        color: style.error
                                        font.pixelSize: 10
                                        horizontalAlignment: Text.AlignHCenter
                                        verticalAlignment: Text.AlignVCenter
                                    }
                                    onClicked: {
                                        if (bridge) bridge.removeWhitelistDevice(modelData.deviceName, modelData.ip);
                                    }
                                }
                            }
                        }

                        // 空列表提示
                        Text {
                            anchors.centerIn: parent
                            text: "暂无已授权设备，新设备首次连接需输入上方验证码"
                            color: style.textMuted
                            font.pixelSize: 11
                            visible: !bridge || bridge.whitelist.length === 0
                        }
                    }
                }

                // 底部关闭按钮
                Button {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 38
                    text: "完成"
                    font.family: style.fontFamily
                    font.pixelSize: 13
                    font.bold: true
                    background: Rectangle {
                        radius: style.radiusSm
                        color: style.primary
                    }
                    contentItem: Text {
                        text: "完成"
                        color: "#FFFFFF"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        font.bold: true
                    }
                    onClicked: authModal.visible = false
                }
            }
        }
    }

    // ==========================================
    // 弹窗 2: 新设备连接请求人工确认弹窗
    // ==========================================
    Rectangle {
        id: authRequestModal
        anchors.fill: parent
        color: "#90000000"
        visible: false
        z: 1100

        MouseArea {
            anchors.fill: parent
            onClicked: {} // 拦截点击
        }

        Rectangle {
            width: 440
            height: 290
            anchors.centerIn: parent
            color: style.bgCard
            radius: style.radiusLg
            border.color: style.warning

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 24
                spacing: 16

                RowLayout {
                    spacing: 10
                    Text {
                        text: "🔔"
                        font.pixelSize: 24
                    }
                    Column {
                        Text {
                            text: "新设备连接授权请求"
                            color: style.textPrimary
                            font.family: style.fontFamily
                            font.pixelSize: 16
                            font.bold: true
                        }
                        Text {
                            text: "该设备已正确输入 4 位动态验证码，请确认是否允许接入"
                            color: style.textSecondary
                            font.pixelSize: 11
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    height: 80
                    radius: style.radiusSm
                    color: style.bgInput
                    border.color: style.borderCard

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 6

                        RowLayout {
                            Text { text: "💻 设备名称:"; color: style.textSecondary; font.pixelSize: 12; font.bold: true; Layout.preferredWidth: 80 }
                            Text { text: root.pendingDeviceName; color: style.textPrimary; font.pixelSize: 13; font.bold: true }
                        }

                        RowLayout {
                            Text { text: "🌐 IP 地址:"; color: style.textSecondary; font.pixelSize: 12; font.bold: true; Layout.preferredWidth: 80 }
                            Text { text: root.pendingIp; color: style.primary; font.pixelSize: 13; font.bold: true }
                        }
                    }
                }

                Text {
                    text: "💡 提示：点击允许后，该设备将加入白名单，后续连接无需再次验证。"
                    color: style.textMuted
                    font.pixelSize: 11
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 12

                    Button {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 38
                        text: "✖ 拒绝"
                        font.pixelSize: 12
                        font.bold: true
                        background: Rectangle {
                            radius: style.radiusSm
                            color: style.errorBg
                            border.color: style.errorBorder
                        }
                        contentItem: Text {
                            text: "✖ 拒绝"
                            color: style.error
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                            font.bold: true
                        }
                        onClicked: {
                            authRequestModal.visible = false;
                            if (bridge) bridge.confirmAuthRequest(root.pendingReqId, false);
                        }
                    }

                    Button {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 38
                        text: "✔ 允许并加入白名单"
                        font.pixelSize: 12
                        font.bold: true
                        background: Rectangle {
                            radius: style.radiusSm
                            color: style.success
                        }
                        contentItem: Text {
                            text: "✔ 允许并加入白名单"
                            color: "#FFFFFF"
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                            font.bold: true
                        }
                        onClicked: {
                            authRequestModal.visible = false;
                            if (bridge) bridge.confirmAuthRequest(root.pendingReqId, true);
                        }
                    }
                }
            }
        }
    }
}
