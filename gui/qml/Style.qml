import QtQuick 2.15

QtObject {
    id: style

    // === 现代化 Windows 11 Fluent / Apple 纯净浅色调色盘 ===
    
    // 背景层级
    readonly property color bgApp: "#F3F4F8"          // 柔和浅灰底层画布
    readonly property color bgCard: "#FFFFFF"         // 纯白卡片容器
    readonly property color bgCardHover: "#F8FAFD"    // 卡片/列表悬浮浅淡天蓝
    readonly property color bgInput: "#F9FAFB"        // 输入框与内嵌区域浅底
    readonly property color bgHeader: "#FFFFFF"       // 顶部导航栏

    // 品牌与强调色 (Fluent Royal Blue)
    readonly property color primary: "#0067C0"
    readonly property color primaryHover: "#1878CD"
    readonly property color primaryPressed: "#0055A0"
    readonly property color primaryLight: "#EBF3FC"   // 浅蓝高亮背景
    readonly property color primaryGlow: "#200067C0"

    // 语义状态色
    readonly property color success: "#059669"        // 翠绿 (成功/在线)
    readonly property color successBg: "#ECFDF5"      // 浅绿徽章底
    readonly property color successBorder: "#A7F3D0"
    
    readonly property color warning: "#D97706"        // 琥珀黄 (警告/中断)
    readonly property color warningBg: "#FFFBEB"
    
    readonly property color error: "#DC2626"          // 珊瑚红 (错误/停止)
    readonly property color errorBg: "#FEF2F2"
    readonly property color errorBorder: "#FECACA"

    // 边框与分割线
    readonly property color borderCard: "#E2E8F0"     // 精致细边框
    readonly property color borderHighlight: "#CBD5E1"// 交互加深边框
    readonly property color divider: "#F1F5F9"

    // 文本色阶 (深灰黑至浅灰，极高清晰度与舒适度)
    readonly property color textPrimary: "#0F172A"    // 正文大标题 (深 Slate)
    readonly property color textSecondary: "#475569"  // 二级说明文字
    readonly property color textMuted: "#94A3B8"      // 辅助注释提示
    readonly property color textOnPrimary: "#FFFFFF"  // 按钮主色文字

    // 徽章专属色彩
    readonly property color badgeWifiBg: "#EDE9FE"
    readonly property color badgeWifiText: "#6D28D9"
    readonly property color badgeLanBg: "#E0F2FE"
    readonly property color badgeLanText: "#0369A1"
    readonly property color badgeDirectBg: "#DCFCE7"
    readonly property color badgeDirectText: "#15803D"

    // 字体与圆角规范
    readonly property string fontFamily: "Segoe UI, 'Microsoft YaHei', 'PingFang SC', sans-serif"
    readonly property int radiusSm: 6
    readonly property int radiusMd: 10
    readonly property int radiusLg: 14

    readonly property int spaceSm: 8
    readonly property int spaceMd: 16
    readonly property int spaceLg: 24
}
