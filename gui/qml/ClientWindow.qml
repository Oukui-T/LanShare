import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

ApplicationWindow {
    id: root
    width: 900
    height: 700
    minimumWidth: 800
    minimumHeight: 600
    visible: true
    title: "LanShare 传输客户端"
    color: root.style.bgApp

    // 显式挂载 Style 属性于根节点，杜绝 Delegate 作用域下的 undefined 警告
    readonly property Style style: Style {}

    // 全局消息提示条
    Rectangle {
        id: toast
        anchors.top: parent.top
        anchors.topMargin: 12
        anchors.horizontalCenter: parent.horizontalCenter
        width: Math.min(parent.width - 40, toastText.implicitWidth + 40)
        height: 36
        radius: root.style.radiusSm
        color: toastType === "error" ? root.style.error : (toastType === "warning" ? root.style.warning : root.style.primary)
        opacity: 0
        z: 999
        property string toastType: "info"

        Behavior on opacity { NumberAnimation { duration: 250 } }

        Text {
            id: toastText
            anchors.centerIn: parent
            color: "#FFFFFF"
            font.family: root.style.fontFamily
            font.pixelSize: 13
            font.bold: true
        }

        Timer {
            id: toastTimer
            interval: 3500
            onTriggered: toast.opacity = 0
        }
    }

    Connections {
        target: bridge
        function onStatusMessage(type, msg) {
            toast.toastType = type;
            toastText.text = msg;
            toast.opacity = 0.95;
            toastTimer.restart();
        }
        function onBreakpointPromptRequested(filename, local_size, remote_size) {
            breakpointDialog.openDialog(filename, local_size, remote_size);
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: root.style.spaceMd
        spacing: root.style.spaceMd

        // 1. 顶部智能统一服务器地址栏 (可直接输入/粘贴 IP，也可下拉选择在线服务与历史记录)
        Rectangle {
            Layout.fillWidth: true
            height: 64
            color: root.style.bgCard
            radius: root.style.radiusMd
            border.color: root.style.borderCard

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: root.style.spaceMd
                anchors.rightMargin: root.style.spaceMd
                spacing: 12

                // 品牌图标
                Rectangle {
                    width: 38
                    height: 38
                    radius: root.style.radiusSm
                    color: root.style.primaryLight
                    border.color: root.style.borderCard
                    Text {
                        anchors.centerIn: parent
                        text: "🚀"
                        font.pixelSize: 20
                    }
                }

                // 连接状态标识
                Column {
                    Layout.preferredWidth: 150
                    spacing: 2
                    Text {
                        text: "目标服务端:"
                        color: root.style.textSecondary
                        font.family: root.style.fontFamily
                        font.pixelSize: 11
                    }
                    Text {
                        text: bridge ? bridge.serverStatusLabel : "⚪ 未连接"
                        color: bridge && bridge.isConnected ? root.style.success : (bridge && bridge.isConnecting ? root.style.warning : root.style.textMuted)
                        font.family: root.style.fontFamily
                        font.pixelSize: 13
                        font.bold: true
                        elide: Text.ElideRight
                    }
                }

                // 统一智能可编辑地址下拉框 (输入框与自动发现/历史列表二合一)
                ComboBox {
                    id: addressCombo
                    Layout.fillWidth: true
                    Layout.preferredHeight: 36
                    editable: true
                    model: bridge ? bridge.serverOptions : []
                    textRole: "display"

                    // 同步输入内容
                    editText: bridge ? bridge.targetAddress : ""

                    delegate: ItemDelegate {
                        width: addressCombo.width
                        contentItem: RowLayout {
                            spacing: 8
                            Text {
                                text: modelData ? modelData.display : ""
                                color: root.style.textPrimary
                                font.family: root.style.fontFamily
                                font.pixelSize: 12
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }
                            Text {
                                visible: modelData && modelData.latency_ms > 0
                                text: modelData ? (modelData.latency_ms + " ms") : ""
                                color: root.style.textMuted
                                font.pixelSize: 11
                            }
                        }
                    }

                    onActivated: {
                        if (bridge && model && index >= 0 && index < model.length) {
                            var item = model[index];
                            if (item && item.address) {
                                addressCombo.editText = item.address;
                                bridge.connectAddress(item.address);
                            }
                        }
                    }

                    // 回车直连
                    onAccepted: {
                        if (bridge) {
                            bridge.connectAddress(addressCombo.editText);
                        }
                    }

                    background: Rectangle {
                        radius: root.style.radiusSm
                        color: root.style.bgInput
                        border.color: addressCombo.activeFocus ? root.style.primary : root.style.borderCard
                        border.width: addressCombo.activeFocus ? 2 : 1
                    }
                }

                // 连接按钮
                Button {
                    id: btnConnect
                    Layout.preferredWidth: 80
                    Layout.preferredHeight: 36
                    text: bridge && bridge.isConnecting ? "连接中..." : "🔗 连接"
                    enabled: bridge && !bridge.isConnecting
                    font.family: root.style.fontFamily
                    font.pixelSize: 12
                    font.bold: true

                    background: Rectangle {
                        radius: root.style.radiusSm
                        color: btnConnect.enabled ? (btnConnect.hovered ? root.style.primaryHover : root.style.primary) : root.style.borderCard
                    }
                    contentItem: Text {
                        text: btnConnect.text
                        color: "#FFFFFF"
                        font: btnConnect.font
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    onClicked: {
                        if (bridge) {
                            bridge.connectAddress(addressCombo.editText);
                        }
                    }
                }

                // 自动扫描发现按钮
                Button {
                    id: btnScan
                    Layout.preferredWidth: 100
                    Layout.preferredHeight: 36
                    text: bridge && bridge.isScanning ? "🔍 扫描中..." : "🔍 局域网探测"
                    enabled: bridge && !bridge.isScanning
                    font.family: root.style.fontFamily
                    font.pixelSize: 12
                    font.bold: true

                    background: Rectangle {
                        radius: root.style.radiusSm
                        color: btnScan.hovered ? root.style.bgCardHover : "#FFFFFF"
                        border.color: root.style.primary
                        border.width: 1
                    }
                    contentItem: Text {
                        text: btnScan.text
                        color: root.style.primary
                        font: btnScan.font
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    onClicked: {
                        if (bridge) {
                            bridge.scanServers();
                        }
                    }
                }
            }
        }

        // 2. 主体功能区：多标签页 (从服务端下载 / 向服务端推送)
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: root.style.bgCard
            radius: root.style.radiusMd
            border.color: root.style.borderCard

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: root.style.spaceMd
                spacing: 12

                // 顶部切换 Tab
                TabBar {
                    id: tabNav
                    Layout.fillWidth: true
                    currentIndex: 0
                    background: Rectangle { color: "transparent" }

                    onCurrentIndexChanged: {
                        if (bridge) {
                            if (currentIndex === 0) {
                                bridge.refreshRemoteFiles();
                            } else if (currentIndex === 1) {
                                bridge.refreshLocalUploadFiles();
                            }
                        }
                    }

                    TabButton {
                        text: "📥 从服务端下载 (" + (bridge ? bridge.remoteFiles.length : 0) + ")"
                        font.family: root.style.fontFamily
                        font.pixelSize: 13
                        font.bold: tabNav.currentIndex === 0
                        width: 200
                        height: 38

                        onClicked: {
                            if (bridge) bridge.refreshRemoteFiles();
                        }

                        background: Rectangle {
                            color: "transparent"
                            Rectangle {
                                anchors.bottom: parent.bottom
                                width: parent.width
                                height: 3
                                color: tabNav.currentIndex === 0 ? root.style.primary : "transparent"
                                radius: 1.5
                            }
                        }
                        contentItem: Text {
                            text: parent.text
                            font: parent.font
                            color: tabNav.currentIndex === 0 ? root.style.primary : root.style.textSecondary
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                    }

                    TabButton {
                        text: "📤 向服务端推送 (" + (bridge ? bridge.localUploadFiles.length : 0) + ")"
                        font.family: root.style.fontFamily
                        font.pixelSize: 13
                        font.bold: tabNav.currentIndex === 1
                        width: 200
                        height: 38

                        onClicked: {
                            if (bridge) bridge.refreshLocalUploadFiles();
                        }

                        background: Rectangle {
                            color: "transparent"
                            Rectangle {
                                anchors.bottom: parent.bottom
                                width: parent.width
                                height: 3
                                color: tabNav.currentIndex === 1 ? root.style.primary : "transparent"
                                radius: 1.5
                            }
                        }
                        contentItem: Text {
                            text: parent.text
                            font: parent.font
                            color: tabNav.currentIndex === 1 ? root.style.primary : root.style.textSecondary
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                    }
                }

                // 标签页内容容器
                StackLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    currentIndex: tabNav.currentIndex

                    // ==========================================
                    // === TAB 1: 从服务端下载 (支持文件与子目录浏览) ===
                    // ==========================================
                    ColumnLayout {
                        spacing: 10

                        // 1. 本地下载保存目录设置栏
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8

                            Text {
                                text: "保存目录:"
                                color: root.style.textPrimary
                                font.pixelSize: 12
                                font.bold: true
                            }

                            Rectangle {
                                Layout.fillWidth: true
                                height: 32
                                color: root.style.bgInput
                                radius: root.style.radiusSm
                                border.color: root.style.borderCard

                                Text {
                                    anchors.fill: parent
                                    anchors.leftMargin: 10
                                    anchors.rightMargin: 10
                                    verticalAlignment: Text.AlignVCenter
                                    text: bridge ? bridge.downloadDir : ""
                                    color: root.style.textPrimary
                                    font.pixelSize: 11
                                    elide: Text.ElideMiddle
                                }
                            }

                            Button {
                                id: btnChangeDownDir
                                text: "📂 更改目录"
                                font.pixelSize: 11
                                Layout.preferredHeight: 32
                                background: Rectangle {
                                    radius: 4
                                    color: btnChangeDownDir.hovered ? root.style.bgCardHover : "#FFFFFF"
                                    border.color: root.style.borderCard
                                }
                                contentItem: Text {
                                    text: btnChangeDownDir.text
                                    font: btnChangeDownDir.font
                                    color: root.style.textPrimary
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                }
                                onClicked: {
                                    if (bridge) bridge.selectDownloadDir();
                                }
                            }

                            Button {
                                id: btnOpenDownDir
                                text: "📂 打开目录"
                                font.pixelSize: 11
                                Layout.preferredHeight: 32
                                background: Rectangle {
                                    radius: 4
                                    color: btnOpenDownDir.hovered ? root.style.bgCardHover : "#FFFFFF"
                                    border.color: root.style.borderCard
                                }
                                contentItem: Text {
                                    text: btnOpenDownDir.text
                                    font: btnOpenDownDir.font
                                    color: root.style.textPrimary
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                }
                                onClicked: {
                                    if (bridge) bridge.openDownloadDir();
                                }
                            }
                        }

                        // 2. 远端共享目录路径与导航控制栏
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8

                            Text {
                                text: "远端位置:"
                                color: root.style.textPrimary
                                font.pixelSize: 12
                                font.bold: true
                            }

                            Rectangle {
                                Layout.fillWidth: true
                                height: 32
                                color: root.style.bgInput
                                radius: root.style.radiusSm
                                border.color: root.style.borderCard

                                Text {
                                    anchors.fill: parent
                                    anchors.leftMargin: 10
                                    anchors.rightMargin: 10
                                    verticalAlignment: Text.AlignVCenter
                                    text: "🌐 /" + (bridge && bridge.remoteCurrentDir ? bridge.remoteCurrentDir : "")
                                    color: root.style.primary
                                    font.pixelSize: 11
                                    font.bold: true
                                    elide: Text.ElideMiddle
                                }
                            }

                            Button {
                                id: btnUpRemoteDir
                                text: "⬆ 返回上级"
                                font.pixelSize: 11
                                enabled: bridge ? bridge.canGoUpRemoteDir : false
                                Layout.preferredHeight: 32
                                background: Rectangle {
                                    radius: 4
                                    color: btnUpRemoteDir.enabled ? (btnUpRemoteDir.hovered ? root.style.bgCardHover : "#FFFFFF") : root.style.bgInput
                                    border.color: btnUpRemoteDir.enabled ? root.style.borderCard : root.style.divider
                                }
                                contentItem: Text {
                                    text: btnUpRemoteDir.text
                                    font: btnUpRemoteDir.font
                                    color: btnUpRemoteDir.enabled ? root.style.textPrimary : root.style.textMuted
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                }
                                onClicked: {
                                    if (bridge) bridge.goUpRemoteDir();
                                }
                            }

                            Button {
                                id: btnRefreshRemote
                                text: "🔄 刷新"
                                font.pixelSize: 11
                                Layout.preferredHeight: 32
                                background: Rectangle {
                                    radius: 4
                                    color: btnRefreshRemote.hovered ? root.style.bgCardHover : "#FFFFFF"
                                    border.color: root.style.borderCard
                                }
                                contentItem: Text {
                                    text: btnRefreshRemote.text
                                    font: btnRefreshRemote.font
                                    color: root.style.primary
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                }
                                onClicked: {
                                    if (bridge) bridge.refreshRemoteFiles();
                                }
                            }
                        }

                        // 文件列表表头
                        Rectangle {
                            Layout.fillWidth: true
                            height: 32
                            color: root.style.bgInput
                            radius: 4

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 12
                                anchors.rightMargin: 18
                                spacing: 12

                                Text {
                                    text: "名称"
                                    font.pixelSize: 12
                                    font.bold: true
                                    color: root.style.textSecondary
                                    Layout.fillWidth: true
                                }
                                Text {
                                    text: "文件大小"
                                    font.pixelSize: 12
                                    font.bold: true
                                    color: root.style.textSecondary
                                    Layout.preferredWidth: 100
                                    horizontalAlignment: Text.AlignRight
                                }
                                Text {
                                    text: "修改时间"
                                    font.pixelSize: 12
                                    font.bold: true
                                    color: root.style.textSecondary
                                    Layout.preferredWidth: 140
                                    horizontalAlignment: Text.AlignHCenter
                                }
                                Text {
                                    text: "操作"
                                    font.pixelSize: 12
                                    font.bold: true
                                    color: root.style.textSecondary
                                    Layout.preferredWidth: 80
                                    horizontalAlignment: Text.AlignHCenter
                                }
                            }
                        }

                        // 远程文件与文件夹列表 (带右侧平滑滚动条)
                        ListView {
                            id: remoteListView
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            clip: true
                            model: bridge ? bridge.remoteFiles : []
                            spacing: 4

                            ScrollBar.vertical: ScrollBar {
                                id: remoteScroll
                                active: remoteListView.moving || remoteScroll.hovered || remoteScroll.pressed
                                policy: ScrollBar.AsNeeded
                                width: 8
                                contentItem: Rectangle {
                                    implicitWidth: 6
                                    radius: 3
                                    color: remoteScroll.pressed ? root.style.primary : (remoteScroll.hovered ? root.style.primaryHover : root.style.borderHighlight)
                                    opacity: remoteScroll.active ? 0.85 : 0.4
                                    Behavior on opacity { NumberAnimation { duration: 150 } }
                                }
                                background: Rectangle {
                                    implicitWidth: 8
                                    color: "transparent"
                                }
                            }

                            delegate: Rectangle {
                                width: remoteListView.width - (remoteScroll.visible ? 10 : 0)
                                height: 42
                                radius: 4
                                color: rowHover.containsMouse ? root.style.bgCardHover : (index % 2 === 0 ? "#FFFFFF" : root.style.bgApp)
                                border.color: root.style.borderCard

                                MouseArea {
                                    id: rowHover
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    onDoubleClicked: {
                                        if (modelData && modelData.is_dir) {
                                            if (bridge) bridge.enterRemoteDir(modelData.name);
                                        } else if (modelData && !modelData.is_dir) {
                                            if (bridge && bridge.isConnected) {
                                                bridge.startDownload(modelData.name, modelData.rel_path);
                                            }
                                        }
                                    }
                                }

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: 12
                                    anchors.rightMargin: 12
                                    spacing: 12

                                    Text {
                                        text: modelData && modelData.is_dir ? ("📁 " + modelData.name) : ("📄 " + (modelData ? modelData.name : ""))
                                        font.pixelSize: 12
                                        font.bold: modelData && modelData.is_dir ? true : false
                                        color: modelData && modelData.is_dir ? root.style.primary : root.style.textPrimary
                                        elide: Text.ElideRight
                                        Layout.fillWidth: true
                                    }
                                    Text {
                                        text: (modelData && modelData.size_formatted) ? modelData.size_formatted : ""
                                        font.pixelSize: 12
                                        color: modelData && modelData.is_dir ? root.style.textMuted : root.style.textSecondary
                                        Layout.preferredWidth: 100
                                        horizontalAlignment: Text.AlignRight
                                    }
                                    Text {
                                        text: (modelData && modelData.mtime_formatted) ? modelData.mtime_formatted : ""
                                        font.pixelSize: 11
                                        color: root.style.textMuted
                                        Layout.preferredWidth: 140
                                        horizontalAlignment: Text.AlignHCenter
                                    }

                                    // 操作按钮：统一显示下载按钮 (文件单下，文件夹整包递归下载)
                                    Button {
                                        id: btnDownload
                                        Layout.preferredWidth: 80
                                        Layout.preferredHeight: 28
                                        text: "📥 下载"
                                        enabled: bridge && bridge.isConnected
                                        font.pixelSize: 11
                                        font.bold: true

                                        background: Rectangle {
                                            radius: 4
                                            color: btnDownload.enabled ? (btnDownload.hovered ? root.style.primaryHover : root.style.primary) : root.style.borderCard
                                        }
                                        contentItem: Text {
                                            text: btnDownload.text
                                            color: btnDownload.enabled ? "#FFFFFF" : root.style.textMuted
                                            font: btnDownload.font
                                            horizontalAlignment: Text.AlignHCenter
                                            verticalAlignment: Text.AlignVCenter
                                        }
                                        onClicked: {
                                            if (bridge && modelData) {
                                                if (modelData.is_dir) {
                                                    bridge.startDownloadFolder(modelData.name, modelData.rel_path);
                                                } else {
                                                    bridge.startDownload(modelData.name, modelData.rel_path);
                                                }
                                            }
                                        }
                                    }
                                }
                            }

                            // 空列表占位提示
                            Rectangle {
                                anchors.centerIn: parent
                                width: 320
                                height: 120
                                visible: remoteListView.count === 0
                                color: "transparent"

                                Column {
                                    anchors.centerIn: parent
                                    spacing: 8
                                    Text {
                                        anchors.horizontalCenter: parent.horizontalCenter
                                        text: bridge && bridge.isConnected ? "📂 当前目录为空" : (bridge && bridge.authNeeded ? "🔒 尚未通过服务端权限验证" : "⚪ 尚未连接到服务端")
                                        font.pixelSize: 14
                                        font.bold: true
                                        color: root.style.textMuted
                                    }
                                    Text {
                                        anchors.horizontalCenter: parent.horizontalCenter
                                        text: bridge && bridge.isConnected ? "该文件夹内暂无文件或子目录" : (bridge && bridge.authNeeded ? "请在弹出的窗口中输入 4 位动态验证码并等待服务端授权" : "请在上方输入/选择服务端地址并点击「连接」")
                                        font.pixelSize: 12
                                        color: root.style.textMuted
                                    }
                                }
                            }
                        }
                    }

                    // ==========================================
                    // === TAB 2: 向服务端推送 (展示文件与文件夹) ===
                    // ==========================================
                    ColumnLayout {
                        spacing: 10

                        // 本地来源目录设置栏
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8

                            Text {
                                text: "推送目录:"
                                color: root.style.textPrimary
                                font.pixelSize: 12
                                font.bold: true
                            }

                            Rectangle {
                                Layout.fillWidth: true
                                height: 32
                                color: root.style.bgInput
                                radius: root.style.radiusSm
                                border.color: root.style.borderCard

                                Text {
                                    anchors.fill: parent
                                    anchors.leftMargin: 10
                                    anchors.rightMargin: 10
                                    verticalAlignment: Text.AlignVCenter
                                    text: bridge ? bridge.uploadDir : ""
                                    color: root.style.textPrimary
                                    font.pixelSize: 11
                                    elide: Text.ElideMiddle
                                }
                            }

                            Button {
                                id: btnUpLevel
                                text: "⬆ 返回上级"
                                font.pixelSize: 11
                                enabled: bridge ? bridge.canGoUpLocalDir : false
                                Layout.preferredHeight: 32
                                background: Rectangle {
                                    radius: 4
                                    color: btnUpLevel.enabled ? (btnUpLevel.hovered ? root.style.bgCardHover : "#FFFFFF") : root.style.bgInput
                                    border.color: btnUpLevel.enabled ? root.style.borderCard : root.style.divider
                                }
                                contentItem: Text {
                                    text: btnUpLevel.text
                                    font: btnUpLevel.font
                                    color: btnUpLevel.enabled ? root.style.textPrimary : root.style.textMuted
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                }
                                onClicked: {
                                    if (bridge) bridge.goUpLocalDir();
                                }
                            }

                            Button {
                                id: btnChangeUpDir
                                text: "📂 更改目录"
                                font.pixelSize: 11
                                Layout.preferredHeight: 32
                                background: Rectangle {
                                    radius: 4
                                    color: btnChangeUpDir.hovered ? root.style.bgCardHover : "#FFFFFF"
                                    border.color: root.style.borderCard
                                }
                                contentItem: Text {
                                    text: btnChangeUpDir.text
                                    font: btnChangeUpDir.font
                                    color: root.style.textPrimary
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                }
                                onClicked: {
                                    if (bridge) bridge.selectUploadDir();
                                }
                            }

                            Button {
                                id: btnOpenUpDir
                                text: "📂 打开目录"
                                font.pixelSize: 11
                                Layout.preferredHeight: 32
                                background: Rectangle {
                                    radius: 4
                                    color: btnOpenUpDir.hovered ? root.style.bgCardHover : "#FFFFFF"
                                    border.color: root.style.borderCard
                                }
                                contentItem: Text {
                                    text: btnOpenUpDir.text
                                    font: btnOpenUpDir.font
                                    color: root.style.textPrimary
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                }
                                onClicked: {
                                    if (bridge) bridge.openUploadDir();
                                }
                            }

                            Button {
                                id: btnRefreshLocal
                                text: "🔄 刷新"
                                font.pixelSize: 11
                                Layout.preferredHeight: 32
                                background: Rectangle {
                                    radius: 4
                                    color: btnRefreshLocal.hovered ? root.style.bgCardHover : "#FFFFFF"
                                    border.color: root.style.borderCard
                                }
                                contentItem: Text {
                                    text: btnRefreshLocal.text
                                    font: btnRefreshLocal.font
                                    color: root.style.primary
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                }
                                onClicked: {
                                    if (bridge) bridge.refreshLocalUploadFiles();
                                }
                            }
                        }

                        // 文件列表表头
                        Rectangle {
                            Layout.fillWidth: true
                            height: 32
                            color: root.style.bgInput
                            radius: 4

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 12
                                anchors.rightMargin: 18
                                spacing: 12

                                Text {
                                    text: "名称"
                                    font.pixelSize: 12
                                    font.bold: true
                                    color: root.style.textSecondary
                                    Layout.fillWidth: true
                                }
                                Text {
                                    text: "大小 / 类型"
                                    font.pixelSize: 12
                                    font.bold: true
                                    color: root.style.textSecondary
                                    Layout.preferredWidth: 100
                                    horizontalAlignment: Text.AlignRight
                                }
                                Text {
                                    text: "修改时间"
                                    font.pixelSize: 12
                                    font.bold: true
                                    color: root.style.textSecondary
                                    Layout.preferredWidth: 140
                                    horizontalAlignment: Text.AlignHCenter
                                }
                                Text {
                                    text: "操作"
                                    font.pixelSize: 12
                                    font.bold: true
                                    color: root.style.textSecondary
                                    Layout.preferredWidth: 80
                                    horizontalAlignment: Text.AlignHCenter
                                }
                            }
                        }

                        // 本地待推送文件及文件夹列表 (带右侧平滑滚动条)
                        ListView {
                            id: localListView
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            clip: true
                            model: bridge ? bridge.localUploadFiles : []
                            spacing: 4

                            ScrollBar.vertical: ScrollBar {
                                id: localScroll
                                active: localListView.moving || localScroll.hovered || localScroll.pressed
                                policy: ScrollBar.AsNeeded
                                width: 8
                                contentItem: Rectangle {
                                    implicitWidth: 6
                                    radius: 3
                                    color: localScroll.pressed ? root.style.primary : (localScroll.hovered ? root.style.primaryHover : root.style.borderHighlight)
                                    opacity: localScroll.active ? 0.85 : 0.4
                                    Behavior on opacity { NumberAnimation { duration: 150 } }
                                }
                                background: Rectangle {
                                    implicitWidth: 8
                                    color: "transparent"
                                }
                            }

                            delegate: Rectangle {
                                width: localListView.width - (localScroll.visible ? 10 : 0)
                                height: 42
                                radius: 4
                                color: localRowHover.containsMouse ? root.style.bgCardHover : (index % 2 === 0 ? "#FFFFFF" : root.style.bgApp)
                                border.color: root.style.borderCard

                                MouseArea {
                                    id: localRowHover
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    onDoubleClicked: {
                                        if (modelData && modelData.is_dir) {
                                            if (bridge) bridge.enterLocalDir(modelData.name);
                                        } else if (modelData && !modelData.is_dir) {
                                            if (bridge && bridge.isConnected && !bridge.isTransferring) {
                                                bridge.startUploadByName(modelData.name);
                                            }
                                        }
                                    }
                                }

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: 12
                                    anchors.rightMargin: 12
                                    spacing: 12

                                    Text {
                                        text: modelData && modelData.is_dir ? ("📁 " + modelData.name) : ("📄 " + (modelData ? modelData.name : ""))
                                        font.pixelSize: 12
                                        font.bold: modelData && modelData.is_dir ? true : false
                                        color: modelData && modelData.is_dir ? root.style.primary : root.style.textPrimary
                                        elide: Text.ElideRight
                                        Layout.fillWidth: true
                                    }
                                    Text {
                                        text: (modelData && modelData.size_formatted) ? modelData.size_formatted : ""
                                        font.pixelSize: 12
                                        color: modelData && modelData.is_dir ? root.style.textMuted : root.style.textSecondary
                                        Layout.preferredWidth: 100
                                        horizontalAlignment: Text.AlignRight
                                    }
                                    Text {
                                        text: (modelData && modelData.mtime_formatted) ? modelData.mtime_formatted : ""
                                        font.pixelSize: 11
                                        color: root.style.textMuted
                                        Layout.preferredWidth: 140
                                        horizontalAlignment: Text.AlignHCenter
                                    }

                                    // 操作按钮：统一显示推送按钮 (文件单推，文件夹整包递归推送)
                                    Button {
                                        id: btnUploadRow
                                        Layout.preferredWidth: 80
                                        Layout.preferredHeight: 28
                                        text: "🚀 推送"
                                        enabled: bridge && bridge.isConnected
                                        font.pixelSize: 11
                                        font.bold: true

                                        background: Rectangle {
                                            radius: 4
                                            color: btnUploadRow.enabled ? (btnUploadRow.hovered ? root.style.primaryHover : root.style.primary) : root.style.borderCard
                                        }
                                        contentItem: Text {
                                            text: btnUploadRow.text
                                            color: btnUploadRow.enabled ? "#FFFFFF" : root.style.textMuted
                                            font: btnUploadRow.font
                                            horizontalAlignment: Text.AlignHCenter
                                            verticalAlignment: Text.AlignVCenter
                                        }
                                        onClicked: {
                                            if (bridge && modelData) {
                                                if (modelData.is_dir) {
                                                    bridge.startUploadFolderByName(modelData.name);
                                                } else {
                                                    bridge.startUploadByName(modelData.name);
                                                }
                                            }
                                        }
                                    }
                                }
                            }

                            // 空列表占位提示
                            Rectangle {
                                anchors.centerIn: parent
                                width: 360
                                height: 120
                                visible: localListView.count === 0
                                color: "transparent"

                                Column {
                                    anchors.centerIn: parent
                                    spacing: 8
                                    Text {
                                        anchors.horizontalCenter: parent.horizontalCenter
                                        text: "📂 当前目录暂无文件或文件夹"
                                        font.pixelSize: 14
                                        font.bold: true
                                        color: root.style.textMuted
                                    }
                                    Text {
                                        anchors.horizontalCenter: parent.horizontalCenter
                                        text: "可点击「更改目录」切换文件夹，或放入文件后点击「刷新」"
                                        font.pixelSize: 12
                                        color: root.style.textMuted
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        // 3. 底部实时传输 HUD 仪表盘 (含已耗时与预估剩余时间、任务排队列表与自适应伸缩)
        Rectangle {
            id: hudContainer
            Layout.fillWidth: true
            Layout.preferredHeight: (bridge && (bridge.isTransferring || (bridge.transferResultText && bridge.transferResultText.length > 0) || bridge.queueCount > 0)) ? (bridge.isQueueExpanded && bridge.queueCount > 0 ? 230 : 104) : 0
            visible: Layout.preferredHeight > 0
            clip: true
            color: root.style.bgCard
            radius: root.style.radiusMd
            border.color: bridge && bridge.transferSuccess ? root.style.successBorder : (bridge && bridge.transferResultText ? root.style.errorBorder : root.style.borderHighlight)
            border.width: 1.5

            Behavior on Layout.preferredHeight {
                NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
            }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: root.style.spaceSm
                spacing: 6

                // 顶部信息与操作行
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    // 任务名称
                    Text {
                        text: bridge ? ((bridge.transferType === "download" ? "📥 下载任务: " : (bridge.transferType === "upload" ? "📤 推送任务: " : "📋 传输状态: ")) + (bridge.transferFileName || "进行中")) : ""
                        color: root.style.textPrimary
                        font.family: root.style.fontFamily
                        font.pixelSize: 13
                        font.bold: true
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }

                    // 实时传输速率
                    Rectangle {
                        visible: bridge ? bridge.isTransferring : false
                        color: root.style.successBg
                        border.color: root.style.successBorder
                        radius: 4
                        implicitHeight: 24
                        implicitWidth: speedText.implicitWidth + 14

                        Text {
                            id: speedText
                            anchors.centerIn: parent
                            text: bridge ? ("🚀 " + bridge.transferSpeedFormatted) : ""
                            color: root.style.success
                            font.pixelSize: 11
                            font.bold: true
                        }
                    }

                    // 文件夹多文件进度计数徽章 (仅在传输文件夹时呈现，单文件传输绝不呈现)
                    Rectangle {
                        id: folderCountBadge
                        visible: bridge ? (bridge.isTransferring && bridge.isFolderTransfer) : false
                        color: root.style.primaryLight
                        border.color: root.style.primary
                        border.width: 1
                        radius: 4
                        implicitHeight: 24
                        implicitWidth: folderCountText.implicitWidth + 14

                        Text {
                            id: folderCountText
                            anchors.centerIn: parent
                            text: bridge ? ("📁 进度: " + bridge.batchCompletedCount + " / " + bridge.batchTotalCount) : ""
                            color: root.style.primary
                            font.pixelSize: 11
                            font.bold: true
                        }
                    }

                    // 时间统计 (已耗时 / 预估剩余)
                    Rectangle {
                        visible: bridge ? bridge.isTransferring : false
                        color: root.style.primaryLight
                        border.color: root.style.borderHighlight
                        radius: 4
                        implicitHeight: 24
                        implicitWidth: timeText.implicitWidth + 14

                        Text {
                            id: timeText
                            anchors.centerIn: parent
                            text: bridge ? ("⏳ " + bridge.elapsedTimeFormatted + " · ⏱️ 剩余 " + bridge.remainingTimeFormatted) : ""
                            color: root.style.primary
                            font.pixelSize: 11
                            font.bold: true
                        }
                    }

                    // 队列展开/折叠徽章按钮
                    Button {
                        id: btnToggleQueue
                        visible: bridge ? (bridge.queueCount > 0) : false
                        Layout.preferredHeight: 24
                        font.pixelSize: 11
                        font.bold: true
                        text: bridge ? ("📋 排队 (" + bridge.queueCount + ") " + (bridge.isQueueExpanded ? "▴" : "▾")) : ""
                        
                        background: Rectangle {
                            radius: 4
                            color: btnToggleQueue.hovered ? root.style.primaryLight : root.style.bgInput
                            border.color: root.style.primary
                            border.width: 1
                        }
                        contentItem: Text {
                            text: btnToggleQueue.text
                            font: btnToggleQueue.font
                            color: root.style.primary
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                        onClicked: {
                            if (bridge) {
                                if (typeof bridge.toggleQueueExpanded === "function") {
                                    bridge.toggleQueueExpanded();
                                } else {
                                    bridge.isQueueExpanded = !bridge.isQueueExpanded;
                                }
                            }
                        }
                    }

                    // 取消当前任务按钮
                    Button {
                        id: btnCancel
                        text: "✖ 取消"
                        visible: bridge ? bridge.isTransferring : false
                        Layout.preferredHeight: 24
                        font.pixelSize: 11
                        background: Rectangle {
                            radius: 4
                            color: btnCancel.hovered ? root.style.errorBg : "#FFFFFF"
                            border.color: root.style.errorBorder
                        }
                        contentItem: Text {
                            text: btnCancel.text
                            font: btnCancel.font
                            color: root.style.error
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                        onClicked: {
                            if (bridge) bridge.cancelTransfer();
                        }
                    }

                    // 全部取消按钮 (有排队任务时展示)
                    Button {
                        id: btnCancelAll
                        text: "✖ 全部取消"
                        visible: bridge ? (bridge.isTransferring && bridge.queueCount > 0) : false
                        Layout.preferredHeight: 24
                        font.pixelSize: 11
                        background: Rectangle {
                            radius: 4
                            color: btnCancelAll.hovered ? root.style.errorBg : "#FFFFFF"
                            border.color: root.style.errorBorder
                        }
                        contentItem: Text {
                            text: btnCancelAll.text
                            font: btnCancelAll.font
                            color: root.style.error
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                        onClicked: {
                            if (bridge) bridge.cancelAllTransfers();
                        }
                    }

                    // 关闭提示按钮 (传输结束时展示)
                    Button {
                        id: btnDismiss
                        text: "✖ 关闭提示"
                        visible: bridge ? (!bridge.isTransferring && bridge.transferResultText.length > 0 && bridge.queueCount === 0) : false
                        Layout.preferredHeight: 24
                        font.pixelSize: 11
                        background: Rectangle {
                            radius: 4
                            color: btnDismiss.hovered ? root.style.bgCardHover : "#FFFFFF"
                            border.color: root.style.borderCard
                        }
                        contentItem: Text {
                            text: btnDismiss.text
                            font: btnDismiss.font
                            color: root.style.textSecondary
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                        onClicked: {
                            if (bridge) bridge.dismissTransfer();
                        }
                    }
                }

                // 进度条
                Rectangle {
                    Layout.fillWidth: true
                    height: 6
                    radius: 3
                    color: root.style.bgInput

                    Rectangle {
                        width: parent.width * (bridge ? bridge.transferProgress : 0)
                        height: parent.height
                        radius: 3
                        color: bridge && bridge.transferSuccess ? root.style.success : (bridge && !bridge.isTransferring && bridge.transferResultText ? root.style.error : root.style.primary)
                        Behavior on width { NumberAnimation { duration: 150 } }
                    }
                }

                // 状态文字与百分比
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    Text {
                        text: {
                            if (!bridge) return "";
                            if (bridge.isTransferring) {
                                return bridge.transferStatusText;
                            }
                            return bridge.transferStatusText + (bridge.transferResultText ? (" · " + bridge.transferResultText) : "");
                        }
                        color: bridge && bridge.transferSuccess ? root.style.success : (bridge && !bridge.isTransferring && !bridge.transferSuccess && bridge.transferResultText ? root.style.error : root.style.textSecondary)
                        font.pixelSize: 12
                        font.bold: bridge && !bridge.isTransferring
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }

                    Text {
                        text: Math.round((bridge ? bridge.transferProgress : 0) * 100) + "%"
                        color: root.style.textPrimary
                        font.pixelSize: 11
                        font.bold: true
                    }
                }

                // 可展开排队列表面板
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    visible: bridge ? (bridge.isQueueExpanded && bridge.queueCount > 0) : false
                    spacing: 4

                    Rectangle {
                        Layout.fillWidth: true
                        height: 1
                        color: root.style.borderCard
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8

                        Text {
                            text: bridge ? ("📋 等待传输排队清单 (共 " + bridge.queueCount + " 项):") : ""
                            font.pixelSize: 11
                            font.bold: true
                            color: root.style.textSecondary
                            Layout.fillWidth: true
                        }

                        Button {
                            id: btnClearQueue
                            text: "🗑️ 清空等待队列"
                            Layout.preferredHeight: 20
                            font.pixelSize: 10
                            background: Rectangle {
                                radius: 3
                                color: btnClearQueue.hovered ? root.style.bgCardHover : "transparent"
                                border.color: root.style.borderCard
                            }
                            contentItem: Text {
                                text: btnClearQueue.text
                                font: btnClearQueue.font
                                color: root.style.textMuted
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                            onClicked: {
                                if (bridge) bridge.clearQueue();
                            }
                        }
                    }

                    ListView {
                        id: queueListView
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        model: bridge ? bridge.transferQueue : []
                        spacing: 4

                        ScrollBar.vertical: ScrollBar {
                            id: queueScroll
                            policy: ScrollBar.AsNeeded
                            contentItem: Rectangle {
                                implicitWidth: 4
                                radius: 2
                                color: queueScroll.pressed ? root.style.primary : (queueScroll.hovered ? root.style.primaryHover : root.style.borderHighlight)
                                opacity: queueScroll.active ? 0.85 : 0.4
                            }
                        }

                        delegate: Rectangle {
                            width: queueListView.width - (queueScroll.visible ? 8 : 0)
                            height: 28
                            radius: 4
                            color: root.style.bgApp
                            border.color: root.style.borderCard

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 8
                                anchors.rightMargin: 8
                                spacing: 8

                                Text {
                                    text: modelData ? ((index + 1) + ". " + (modelData.type === "download" ? "📥" : "🚀")) : ""
                                    font.pixelSize: 11
                                }

                                Text {
                                    text: modelData ? modelData.filename : ""
                                    font.pixelSize: 11
                                    color: root.style.textPrimary
                                    elide: Text.ElideRight
                                    Layout.fillWidth: true
                                }

                                Text {
                                    text: modelData ? modelData.size_formatted : ""
                                    font.pixelSize: 11
                                    color: root.style.textSecondary
                                    Layout.preferredWidth: 70
                                    horizontalAlignment: Text.AlignRight
                                }

                                Rectangle {
                                    Layout.preferredWidth: 50
                                    Layout.preferredHeight: 18
                                    radius: 3
                                    color: root.style.primaryLight
                                    border.color: root.style.borderHighlight

                                    Text {
                                        anchors.centerIn: parent
                                        text: "⏳ 排队中"
                                        font.pixelSize: 9
                                        color: root.style.primary
                                    }
                                }

                                Button {
                                    id: btnRemoveQueue
                                    text: "✖"
                                    Layout.preferredWidth: 20
                                    Layout.preferredHeight: 20
                                    font.pixelSize: 10
                                    background: Rectangle {
                                        radius: 3
                                        color: btnRemoveQueue.hovered ? root.style.errorBg : "transparent"
                                    }
                                    contentItem: Text {
                                        text: btnRemoveQueue.text
                                        font: btnRemoveQueue.font
                                        color: btnRemoveQueue.hovered ? root.style.error : root.style.textMuted
                                        horizontalAlignment: Text.AlignHCenter
                                        verticalAlignment: Text.AlignVCenter
                                    }
                                    onClicked: {
                                        if (bridge) bridge.removeQueueItem(index);
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // ==========================================
    // 权限验证输入与状态模态弹窗
    // ==========================================
    Rectangle {
        id: clientAuthModal
        anchors.fill: parent
        color: "#85000000"
        visible: bridge && bridge.authNeeded
        z: 1000

        onVisibleChanged: {
            if (visible) {
                authCodeInput.text = "";
                authCodeInput.forceActiveFocus();
            }
        }

        MouseArea {
            anchors.fill: parent
            onClicked: {} // 阻止穿透
        }

        Rectangle {
            width: 460
            height: 380
            anchors.centerIn: parent
            color: root.style.bgCard
            radius: root.style.radiusLg
            border.color: root.style.borderCard

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 28
                spacing: 16

                // 标题栏
                RowLayout {
                    spacing: 10
                    Text {
                        text: "🔐"
                        font.pixelSize: 22
                    }
                    Column {
                        Layout.fillWidth: true
                        Text {
                            text: "服务端连接身份验证"
                            color: root.style.textPrimary
                            font.family: root.style.fontFamily
                            font.pixelSize: 16
                            font.bold: true
                        }
                        Text {
                            text: "目标服务端: " + (bridge ? bridge.targetAddress : "")
                            color: root.style.textSecondary
                            font.pixelSize: 11
                        }
                    }
                    Button {
                        text: "✖"
                        font.pixelSize: 13
                        background: Rectangle { color: "transparent" }
                        contentItem: Text { text: "✖"; color: root.style.textMuted; font.bold: true }
                        onClicked: {
                            if (bridge) bridge.cancelAuth();
                        }
                    }
                }

                Text {
                    text: "该服务端已开启安全访问控制。请输入服务端当前显示的 4 位动态验证码以申请连接："
                    color: root.style.textSecondary
                    font.pixelSize: 12
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }

                // 4 位验证码输入框容器
                Rectangle {
                    Layout.fillWidth: true
                    height: 64
                    radius: root.style.radiusMd
                    color: root.style.bgInput
                    border.color: authCodeInput.activeFocus ? root.style.primary : (bridge && bridge.authStatus === "code_error" ? root.style.error : root.style.borderCard)
                    border.width: authCodeInput.activeFocus ? 2 : 1

                    TextInput {
                        id: authCodeInput
                        anchors.fill: parent
                        anchors.margins: 8
                        verticalAlignment: TextInput.AlignVCenter
                        horizontalAlignment: TextInput.AlignHCenter
                        color: root.style.primary
                        font.family: "Consolas, 'Courier New', monospace"
                        font.pixelSize: 32
                        font.bold: true
                        font.letterSpacing: 12
                        maximumLength: 4
                        focus: clientAuthModal.visible
                        enabled: !bridge || (bridge.authStatus !== "verifying" && bridge.authStatus !== "waiting_confirmation")

                        onTextChanged: {
                            var upper = text.toUpperCase();
                            if (text !== upper) text = upper;
                        }

                        onAccepted: {
                            if (bridge && text.trim().length === 4) {
                                bridge.submitAuthCode(text.trim());
                            }
                        }
                    }
                }

                // 动态状态提示区域
                Rectangle {
                    Layout.fillWidth: true
                    height: 36
                    radius: 4
                    color: {
                        if (!bridge) return "transparent";
                        if (bridge.authStatus === "verifying") return root.style.primaryLight;
                        if (bridge.authStatus === "waiting_confirmation") return root.style.warningBg;
                        if (bridge.authStatus === "code_error" || bridge.authStatus === "rejected" || bridge.authStatus === "expired") return root.style.errorBg;
                        return "transparent";
                    }

                    RowLayout {
                        anchors.centerIn: parent
                        spacing: 8

                        Text {
                            text: {
                                if (!bridge) return "";
                                if (bridge.authStatus === "verifying") return "🔄 正在校验验证码...";
                                if (bridge.authStatus === "waiting_confirmation") return "⏳ 验证码正确！等待服务端管理员确认授权...";
                                if (bridge.authStatus === "code_error") return "❌ " + (bridge.authErrorMessage || "验证码错误，请重新输入");
                                if (bridge.authStatus === "rejected") return "🚫 服务端管理员已拒绝本次连接请求";
                                if (bridge.authStatus === "expired") return "⏱️ 请求已超时，请重试";
                                return "💻 本机设备标识: " + (bridge ? bridge.deviceName : "");
                            }
                            color: {
                                if (!bridge) return root.style.textMuted;
                                if (bridge.authStatus === "verifying") return root.style.primary;
                                if (bridge.authStatus === "waiting_confirmation") return root.style.warning;
                                if (bridge.authStatus === "code_error" || bridge.authStatus === "rejected" || bridge.authStatus === "expired") return root.style.error;
                                return root.style.textMuted;
                            }
                            font.pixelSize: 11
                            font.bold: bridge && bridge.authStatus !== "idle"
                        }
                    }
                }

                // 底部操作按键
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 12

                    Button {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 38
                        text: "✖ 取消"
                        font.pixelSize: 12
                        background: Rectangle {
                            radius: root.style.radiusSm
                            color: root.style.bgInput
                            border.color: root.style.borderCard
                        }
                        contentItem: Text {
                            text: "✖ 取消"
                            color: root.style.textSecondary
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                        onClicked: {
                            if (bridge) bridge.cancelAuth();
                        }
                    }

                    Button {
                        id: btnSubmitAuth
                        Layout.fillWidth: true
                        Layout.preferredHeight: 38
                        text: "🚀 提交验证"
                        font.pixelSize: 12
                        font.bold: true
                        enabled: bridge && (bridge.authStatus !== "verifying" && bridge.authStatus !== "waiting_confirmation") && authCodeInput.text.trim().length === 4

                        background: Rectangle {
                            radius: root.style.radiusSm
                            color: btnSubmitAuth.enabled ? (btnSubmitAuth.hovered ? root.style.primaryHover : root.style.primary) : root.style.borderCard
                        }
                        contentItem: Text {
                            text: btnSubmitAuth.text
                            color: btnSubmitAuth.enabled ? "#FFFFFF" : root.style.textMuted
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                            font.bold: true
                        }
                        onClicked: {
                            if (bridge) bridge.submitAuthCode(authCodeInput.text.trim());
                        }
                    }
                }
            }
        }
    }

    // Fluent 风格的模态断点决策弹窗
    Dialog {
        id: breakpointDialog
        width: 480
        height: 280
        x: Math.round((parent.width - width) / 2)
        y: Math.round((parent.height - height) / 2)
        modal: true
        closePolicy: Popup.NoAutoClose
        title: "检测到文件续传中断"

        property string currentFilename: ""
        property int currentLocalSize: 0
        property int currentRemoteSize: 0

        function openDialog(filename, local_size, remote_size) {
            currentFilename = filename;
            currentLocalSize = local_size;
            currentRemoteSize = remote_size;
            open();
        }

        function formatBytes(bytes) {
            if (bytes < 1024) return bytes + " B";
            if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
            if (bytes < 1024 * 1024 * 1024) return (bytes / 1024 / 1024).toFixed(2) + " MB";
            return (bytes / 1024 / 1024 / 1024).toFixed(2) + " GB";
        }

        background: Rectangle {
            color: root.style.bgApp
            radius: root.style.radiusMd
            border.color: root.style.borderCard
        }

        header: Rectangle {
            color: "transparent"
            height: 50
            Text {
                anchors.left: parent.left
                anchors.leftMargin: 20
                anchors.verticalCenter: parent.verticalCenter
                text: breakpointDialog.title
                font.pixelSize: 16
                font.bold: true
                color: root.style.textPrimary
            }
        }

        contentItem: ColumnLayout {
            spacing: 15
            anchors.margins: 20

            Text {
                Layout.fillWidth: true
                text: "正在传输的文件在目标端已存在部分内容，您希望如何处理？"
                color: root.style.textSecondary
                font.pixelSize: 13
                wrapMode: Text.WordWrap
            }

            Rectangle {
                Layout.fillWidth: true
                height: 80
                color: root.style.bgInput
                radius: root.style.radiusSm
                border.color: root.style.borderCard
                
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 5
                    
                    Text {
                        text: "文件名称: " + breakpointDialog.currentFilename
                        color: root.style.textPrimary
                        font.pixelSize: 12
                        font.bold: true
                        elide: Text.ElideMiddle
                        Layout.fillWidth: true
                    }
                    Text {
                        text: "完整大小: " + breakpointDialog.formatBytes(breakpointDialog.currentRemoteSize)
                        color: root.style.textSecondary
                        font.pixelSize: 12
                    }
                    Text {
                        text: "已传大小: " + breakpointDialog.formatBytes(breakpointDialog.currentLocalSize) + "  (" + Math.round(breakpointDialog.currentLocalSize / Math.max(1, breakpointDialog.currentRemoteSize) * 100) + "%)"
                        color: root.style.primary
                        font.pixelSize: 12
                        font.bold: true
                    }
                }
            }
        }

        footer: Rectangle {
            color: "transparent"
            height: 60
            RowLayout {
                anchors.fill: parent
                anchors.margins: 15
                spacing: 10

                Button {
                    Layout.fillWidth: true
                    font.pixelSize: 13
                    font.bold: true
                    background: Rectangle {
                        color: root.style.textSecondary
                        radius: root.style.radiusSm
                    }
                    contentItem: Text {
                        text: "⏭️ 跳过"
                        color: "white"
                        font.bold: true
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    onClicked: {
                        if (bridge) bridge.resolveBreakpointPrompt("skip");
                        breakpointDialog.close();
                    }
                }

                Button {
                    Layout.fillWidth: true
                    font.pixelSize: 13
                    font.bold: true
                    background: Rectangle {
                        color: root.style.error
                        radius: root.style.radiusSm
                    }
                    contentItem: Text {
                        text: "🗑️ 覆盖重传"
                        color: "white"
                        font.bold: true
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    onClicked: {
                        if (bridge) bridge.resolveBreakpointPrompt("overwrite");
                        breakpointDialog.close();
                    }
                }

                Button {
                    Layout.fillWidth: true
                    text: "▶️ 断点续传"
                    font.pixelSize: 13
                    font.bold: true
                    background: Rectangle {
                        color: root.style.primary
                        radius: root.style.radiusSm
                    }
                    contentItem: Text {
                        text: "▶️ 断点续传"
                        color: "white"
                        font.bold: true
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    onClicked: {
                        if (bridge) bridge.resolveBreakpointPrompt("resume");
                        breakpointDialog.close();
                    }
                }
            }
        }
    }

    Component.onCompleted: {
        if (bridge) bridge.scanServers();
    }
}
