import Quickshell
import Quickshell.Io
import QtQuick
import QtQuick.Layouts

ShellRoot {
    id: root

    property var desktopStates: [
        { num: 1, focused: true, occupied: false, urgent: false },
        { num: 2, focused: false, occupied: false, urgent: false },
        { num: 3, focused: false, occupied: false, urgent: false },
        { num: 4, focused: false, occupied: false, urgent: false },
        { num: 5, focused: false, occupied: false, urgent: false },
        { num: 6, focused: false, occupied: false, urgent: false }
    ]
    property string layoutMode: "T"
    property int volumePct: 50
    property bool muted: false

    property bool sessionOpen: false
    property bool sessionActive: false
    property bool widgetsOpen: false
    property bool widgetsActive: false
__ANDROID_STATUS_PROPS__
__MEDIA_PROPS__
__WEATHER_PROPS__
__FOCUS_PROPS__
__CALENDAR_PROPS__
    readonly property color colBase: "#e61e1e2e"
    readonly property color colPopupBase: "#f21e1e2e"
    readonly property color colSurface: "#313244"
    readonly property color colSurface1: "#45475a"
    readonly property color colText: "#cdd6f4"
    readonly property color colSubtext: "#a6adc8"
    readonly property color colBlue: "#89b4fa"
    readonly property color colMauve: "#cba6f7"
    readonly property color colTeal: "#94e2d5"
    readonly property color colGreen: "#a6e3a1"
    readonly property color colPeach: "#fab387"
    readonly property color colRed: "#f38ba8"
    readonly property color colDark: "#1e1e2e"
    readonly property string uiFont: "JetBrainsMono Nerd Font"

    function runCmd(cmd) {
        Quickshell.execDetached(cmd);
    }

    function refreshAudio() {
        if (!audioPollProc.running) {
            audioPollProc.running = true;
        }
    }

__ANDROID_STATUS_FN__
__MEDIA_FN__
__WEATHER_FN__
__CALENDAR_FN__
    function toggleWidgets() {
        if (root.widgetsOpen) {
            closeWidgets();
        } else {
            closeSession();
            widgetsCloseTimer.stop();
            root.widgetsActive = true;
            root.widgetsOpen = true;
            root.refreshAndroidStatus();
            root.refreshMedia();
            root.refreshFocus();
            root.rebuildCalendarGrid();
            root.queryCalendarMonth(root.calViewYear, root.calViewMonth);
            root.refreshWeatherIfStale();
            syncWatcher();
        }
    }

    function closeWidgets() {
        if (!root.widgetsOpen && !root.widgetsActive) return;
        root.widgetsOpen = false;
        widgetsCloseTimer.restart();
        syncWatcher();
    }

    function toggleSession() {
        if (root.sessionOpen) {
            closeSession();
        } else {
            closeWidgets();
            sessionCloseTimer.stop();
            root.sessionActive = true;
            root.sessionOpen = true;
            syncWatcher();
        }
    }

    function closeSession() {
        if (!root.sessionOpen && !root.sessionActive) return;
        root.sessionOpen = false;
        sessionCloseTimer.restart();
        syncWatcher();
    }

    function closeAllMenus() {
        closeWidgets();
        closeSession();
    }

    function syncWatcher() {
        submenuWatcher.running = false;
        if (root.widgetsOpen || root.sessionOpen) {
            watcherRestartTimer.restart();
        } else {
            watcherRestartTimer.stop();
        }
    }

    function parseReport(line) {
        const parts = line.trim().split(":");
        if (parts.length < 2) return;
        const next = [];
        for (let i = 0; i < parts.length; i++) {
            const p = parts[i];
            if (!p || p.length < 2) continue;
            const tag = p[0];
            const name = p.slice(1);
            if ("FfOoUu".indexOf(tag) >= 0) {
                const n = parseInt(name, 10);
                if (!isNaN(n)) {
                    next.push({
                        num: n,
                        focused: ("FOU".indexOf(tag) >= 0),
                        occupied: ("Oo".indexOf(tag) >= 0),
                        urgent: ("Uu".indexOf(tag) >= 0)
                    });
                }
            } else if (tag === "L") {
                root.layoutMode = name;
            }
        }
        if (next.length > 0) {
            root.desktopStates = next;
        }
    }

    Timer {
        id: widgetsCloseTimer
        interval: 190
        repeat: false
        onTriggered: {
            if (!root.widgetsOpen) root.widgetsActive = false;
        }
    }

    Timer {
        id: sessionCloseTimer
        interval: 170
        repeat: false
        onTriggered: {
            if (!root.sessionOpen) root.sessionActive = false;
        }
    }

    Timer {
        id: watcherRestartTimer
        interval: 30
        repeat: false
        onTriggered: {
            if (root.widgetsOpen || root.sessionOpen) {
                submenuWatcher.running = true;
            }
        }
    }

    Process {
        id: submenuWatcher
        command: [
            Quickshell.env("HOME") + "/.local/bin/qs-native",
            "submenu-watch",
            String(dockWindow.width),
            String(dockWindow.height > 0 ? dockWindow.height : 1508),
            String(dockWindow.width + 12),
            String(root.widgetsOpen ? 80 : Math.max(80, 80 + (dockWindow.height > 0 ? dockWindow.height : 1508) - 368)),
            String(root.widgetsOpen ? widgetsPopup.implicitWidth : sessionPopup.implicitWidth),
            String(root.widgetsOpen ? widgetsPopup.implicitHeight : sessionPopup.implicitHeight)
        ]
        stdout: SplitParser {
            onRead: data => {
                if (data.trim() === "CLOSE") {
                    root.closeAllMenus();
                }
            }
        }
    }

    Process {
        id: bspwmSub
        command: ["bspc", "subscribe", "report"]
        running: true
        stdout: SplitParser {
            onRead: data => root.parseReport(data)
        }
    }

    Process {
        id: audioPollProc
        command: ["sh", "-c", "pactl get-sink-volume @DEFAULT_SINK@ 2>/dev/null; echo ---; pactl get-sink-mute @DEFAULT_SINK@ 2>/dev/null"]
        running: true
        stdout: StdioCollector {
            onStreamFinished: {
                const sections = this.text.split("---");
                if (sections.length >= 1) {
                    const m = sections[0].match(/([0-9]+)%/);
                    if (m) root.volumePct = parseInt(m[1], 10);
                }
                if (sections.length >= 2) {
                    root.muted = (sections[1].indexOf("yes") >= 0);
                }
            }
        }
    }

__ANDROID_STATUS_PROCS__
__MEDIA_PROCS__
__WEATHER_PROCS__
    Timer {
        interval: 4000
        running: true
        repeat: true
        onTriggered: root.refreshAudio()
    }

    Timer {
        id: audioSyncDelay
        interval: 150
        repeat: false
        onTriggered: root.refreshAudio()
    }

    component DockButton: Rectangle {
        id: btn
        property string iconText: ""
        property string subText: ""
        property color iconColor: root.colText
        property color baseColor: root.colSurface
        property color activeColor: root.colSurface1
        property bool active: false
        property int iconSize: 28
        property int buttonHeight: 60
        signal clicked()

        implicitWidth: 92
        implicitHeight: btn.buttonHeight
        radius: 18
        color: area.pressed ? root.colBlue : (btn.active ? btn.activeColor : btn.baseColor)
        scale: area.pressed ? 0.92 : 1.0

        Behavior on scale { NumberAnimation { duration: 80 } }
        Behavior on color { ColorAnimation { duration: 100 } }

        Column {
            anchors.centerIn: parent
            spacing: 1
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: btn.iconText
                color: area.pressed ? root.colDark : btn.iconColor
                font.family: root.uiFont
                font.pixelSize: btn.iconSize
                lineHeight: 1.0
            }
            Text {
                visible: btn.subText.length > 0
                anchors.horizontalCenter: parent.horizontalCenter
                text: btn.subText
                color: area.pressed ? root.colDark : root.colSubtext
                font.family: root.uiFont
                font.pixelSize: 13
                font.bold: true
            }
        }

        MouseArea {
            id: area
            anchors.fill: parent
            anchors.leftMargin: -16
            anchors.rightMargin: -12
            anchors.topMargin: -4
            anchors.bottomMargin: -4
            onClicked: btn.clicked()
        }
    }

    PanelWindow {
        id: dockWindow
        anchors {
            left: true
            top: true
            bottom: true
        }
        margins {
            left: 0
            top: 80
            bottom: 12
        }
        implicitWidth: 128
        color: "transparent"

        readonly property bool compactDock: height > 0 && height < 1200

        Rectangle {
            id: barBg
            anchors.fill: parent
            anchors.leftMargin: 12
            radius: 24
            color: root.colBase
            border.color: root.colSurface
            border.width: 2

            ColumnLayout {
                anchors.fill: parent
                anchors.topMargin: dockWindow.compactDock ? 8 : 14
                anchors.bottomMargin: dockWindow.compactDock ? 8 : 14
                spacing: dockWindow.compactDock ? 4 : 8

                // Top: Touch Launchers
                Column {
                    Layout.alignment: Qt.AlignHCenter
                    spacing: dockWindow.compactDock ? 6 : 12

                    DockButton {
                        iconText: "󰀻"
                        iconColor: root.colBlue
                        iconSize: dockWindow.compactDock ? 26 : 34
                        buttonHeight: dockWindow.compactDock ? 44 : 66
                        onClicked: {
                            root.closeAllMenus();
                            root.runCmd(["rofi", "-show", "drun"]);
                        }
                    }
                    DockButton {
                        iconText: ""
                        iconColor: root.colTeal
                        iconSize: dockWindow.compactDock ? 24 : 30
                        buttonHeight: dockWindow.compactDock ? 44 : 66
                        onClicked: {
                            root.closeAllMenus();
                            root.runCmd(["sh", "-c", "if command -v xfce4-terminal >/dev/null 2>&1; then exec xfce4-terminal; else exec alacritty; fi"]);
                        }
                    }
                    DockButton {
                        iconText: ""
                        iconColor: root.colMauve
                        iconSize: dockWindow.compactDock ? 24 : 30
                        buttonHeight: dockWindow.compactDock ? 44 : 66
                        onClicked: {
                            root.closeAllMenus();
                            root.runCmd(["rofi", "-show", "window"]);
                        }
                    }
                }

                Rectangle {
                    Layout.alignment: Qt.AlignHCenter
                    width: 60
                    height: 2
                    radius: 1
                    color: root.colSurface1
                }

                // Middle: Touch Workspaces (1-6) + Layout Toggle
                Column {
                    Layout.alignment: Qt.AlignHCenter
                    spacing: dockWindow.compactDock ? 5 : 12

                    Repeater {
                        model: root.desktopStates
                        delegate: Rectangle {
                            required property var modelData
                            width: 92
                            height: dockWindow.compactDock ? 36 : 58
                            radius: 18
                            scale: wsArea.pressed ? 0.92 : 1.0
                            color: modelData.focused
                                ? root.colBlue
                                : (modelData.urgent
                                    ? root.colRed
                                    : (modelData.occupied ? root.colSurface : "transparent"))
                            border.color: (!modelData.focused && modelData.occupied) ? root.colSurface1 : "transparent"
                            border.width: 1

                            Behavior on scale { NumberAnimation { duration: 80 } }
                            Behavior on color { ColorAnimation { duration: 100 } }

                            Row {
                                anchors.centerIn: parent
                                spacing: 6
                                Text {
                                    text: String(modelData.num)
                                    color: (modelData.focused || modelData.urgent) ? root.colDark : (modelData.occupied ? root.colText : root.colSubtext)
                                    font.family: root.uiFont
                                    font.pixelSize: dockWindow.compactDock ? 18 : 24
                                    font.bold: modelData.focused || modelData.occupied
                                }
                                Rectangle {
                                    visible: modelData.occupied && !modelData.focused
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: 8
                                    height: 8
                                    radius: 4
                                    color: root.colBlue
                                }
                            }

                            MouseArea {
                                id: wsArea
                                anchors.fill: parent
                                anchors.leftMargin: -16
                                anchors.rightMargin: -12
                                anchors.topMargin: -4
                                anchors.bottomMargin: -4
                                onClicked: root.runCmd(["bspc", "desktop", "-f", "^" + modelData.num])
                            }
                        }
                    }

                    DockButton {
                        buttonHeight: dockWindow.compactDock ? 42 : 56
                        iconText: root.layoutMode === "M" ? "󰕮" : "󰕳"
                        subText: dockWindow.compactDock ? "" : root.layoutMode
                        iconColor: root.layoutMode === "M" ? root.colMauve : root.colSubtext
                        iconSize: dockWindow.compactDock ? 20 : 24
                        onClicked: root.runCmd(["bspc", "desktop", "-l", "next"])
                    }
                }

                // Empty Dock Spacer -> Click to Toggle Widget Drawer
                Item {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.minimumHeight: dockWindow.compactDock ? 32 : 60

                    Column {
                        anchors.centerIn: parent
                        spacing: 6
                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: root.widgetsOpen ? "󰅁" : "󰅂"
                            color: root.widgetsOpen ? root.colBlue : root.colSubtext
                            font.family: root.uiFont
                            font.pixelSize: 22
                        }
                        Rectangle {
                            anchors.horizontalCenter: parent.horizontalCenter
                            width: 6
                            height: dockWindow.compactDock ? 20 : 44
                            radius: 3
                            color: root.widgetsOpen ? root.colBlue : root.colSurface1
                            Behavior on color { ColorAnimation { duration: 120 } }
                        }
                    }

                    MouseArea {
                        id: drawerToggleArea
                        anchors.fill: parent
                        onClicked: root.toggleWidgets()
                    }
                }

                Rectangle {
                    Layout.alignment: Qt.AlignHCenter
                    width: 60
                    height: 2
                    radius: 1
                    color: root.colSurface1
                }

                // Bottom: Window Controls + Volume + Session Power
                Column {
                    Layout.alignment: Qt.AlignHCenter
                    spacing: dockWindow.compactDock ? 5 : 10

                    DockButton {
                        buttonHeight: dockWindow.compactDock ? 36 : 56
                        iconText: ""
                        iconColor: root.colText
                        iconSize: dockWindow.compactDock ? 20 : 26
                        onClicked: root.runCmd(["bspc", "node", "-t", "~floating"])
                    }
                    DockButton {
                        buttonHeight: dockWindow.compactDock ? 36 : 56
                        iconText: ""
                        iconColor: root.colText
                        iconSize: dockWindow.compactDock ? 20 : 26
                        onClicked: root.runCmd(["bspc", "node", "-t", "~fullscreen"])
                    }
                    DockButton {
                        buttonHeight: dockWindow.compactDock ? 36 : 56
                        iconText: ""
                        iconColor: root.colRed
                        iconSize: dockWindow.compactDock ? 22 : 28
                        onClicked: root.runCmd(["bspc", "node", "-c"])
                    }

                    Rectangle {
                        anchors.horizontalCenter: parent.horizontalCenter
                        width: 60
                        height: 2
                        radius: 1
                        color: root.colSurface1
                    }

                    DockButton {
                        buttonHeight: dockWindow.compactDock ? 34 : 50
                        iconText: "󰐕"
                        iconColor: root.colText
                        iconSize: dockWindow.compactDock ? 20 : 26
                        onClicked: {
                            root.runCmd(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "+5%"]);
                            audioSyncDelay.restart();
                        }
                    }
                    DockButton {
                        buttonHeight: dockWindow.compactDock ? 46 : 66
                        iconText: root.muted ? "󰝟" : "󰕾"
                        subText: root.muted ? "MUTE" : (root.volumePct + "%")
                        iconColor: root.muted ? root.colRed : root.colGreen
                        iconSize: dockWindow.compactDock ? 20 : 24
                        onClicked: {
                            root.runCmd(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"]);
                            audioSyncDelay.restart();
                        }
                    }
                    DockButton {
                        buttonHeight: dockWindow.compactDock ? 34 : 50
                        iconText: "󰍴"
                        iconColor: root.colText
                        iconSize: dockWindow.compactDock ? 20 : 26
                        onClicked: {
                            root.runCmd(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "-5%"]);
                            audioSyncDelay.restart();
                        }
                    }

                    DockButton {
                        id: sessionBtn
                        buttonHeight: dockWindow.compactDock ? 42 : 62
                        iconText: ""
                        iconColor: root.sessionOpen ? root.colDark : root.colRed
                        baseColor: root.sessionOpen ? root.colRed : root.colSurface
                        iconSize: dockWindow.compactDock ? 22 : 28
                        onClicked: root.toggleSession()
                    }
                }
            }
        }
    }

    // Large Readable Widget Drawer (1/3 screen width, full dock height)
    PopupWindow {
        id: widgetsPopup
        anchor.window: dockWindow
        anchor.rect.x: dockWindow.width + 12
        anchor.rect.y: 0
        implicitWidth: 844
        implicitHeight: dockWindow.height > 0 ? dockWindow.height : 1504
        visible: root.widgetsActive
        color: "transparent"

        Item {
            anchors.fill: parent
            clip: true

            Rectangle {
                id: drawerBg
                width: parent.width
                height: parent.height
                x: root.widgetsOpen ? 0 : -44
                opacity: root.widgetsOpen ? 1.0 : 0.0
                radius: 24
                color: root.colPopupBase
                border.color: root.colSurface1
                border.width: 2

                Behavior on x { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
                Behavior on opacity { NumberAnimation { duration: 140 } }

                Flickable {
                    anchors.fill: parent
                    anchors.margins: 28
                    contentWidth: width
                    contentHeight: drawerCol.implicitHeight
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds
                    interactive: contentHeight > height

                    ColumnLayout {
                        id: drawerCol
                        width: parent.width
                        spacing: 20

                        // Header
                        RowLayout {
                            Layout.fillWidth: true
                            Row {
                                spacing: 14
                                Layout.fillWidth: true
                                Text {
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: "󰀻"
                                    color: root.colBlue
                                    font.family: root.uiFont
                                    font.pixelSize: 34
                                }
                                Text {
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: "Widgets"
                                    color: root.colText
                                    font.family: root.uiFont
                                    font.pixelSize: 30
                                    font.bold: true
                                }
                            }
                            Rectangle {
                                width: 48
                                height: 48
                                radius: 16
                                color: closeBtnArea.pressed ? root.colBlue : root.colSurface
                                border.color: root.colSurface1
                                border.width: 1
                                Text {
                                    anchors.centerIn: parent
                                    text: ""
                                    color: closeBtnArea.pressed ? root.colDark : root.colSubtext
                                    font.family: root.uiFont
                                    font.pixelSize: 22
                                }
                                MouseArea {
                                    id: closeBtnArea
                                    anchors.fill: parent
                                    onClicked: root.closeWidgets()
                                }
                            }
                        }

                        // Quick Widget Spaces Row
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 18

__WEATHER_CARD__

__FOCUS_CARD__
                        }

__ANDROID_STATUS_CARD__
__MEDIA_CARD__

__CALENDAR_CARD__

__AGENDA_CARD__
                    }
                }
            }
        }
    }

    // Raised Session Menu (Bottom-left submenu of Quit/Power button)
    PopupWindow {
        id: sessionPopup
        anchor.window: dockWindow
        anchor.rect.x: dockWindow.width + 12
        anchor.rect.y: Math.max(0, (dockWindow.height > 0 ? dockWindow.height : 1504) - 368)
        implicitWidth: 330
        implicitHeight: 368
        visible: root.sessionActive
        color: "transparent"

        Item {
            anchors.fill: parent
            clip: true

            Rectangle {
                width: parent.width
                height: 330
                y: root.sessionOpen ? 0 : 28
                opacity: root.sessionOpen ? 1.0 : 0.0
                radius: 22
                color: root.colPopupBase
                border.color: root.colSurface1
                border.width: 2

                Behavior on y { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }
                Behavior on opacity { NumberAnimation { duration: 130 } }

                Column {
                    anchors.fill: parent
                    anchors.margins: 18
                    spacing: 18

                    Repeater {
                        model: [
                            { label: "Reload Bars", icon: "", color: root.colBlue, cmd: ["sh", "-c", "$HOME/.config/polybar/launch.sh & $HOME/.config/quickshell/launch.sh &"] },
                            { label: "Restart WM", icon: "", color: root.colTeal, cmd: ["bspc", "wm", "-r"] },
                            { label: "Exit X11", icon: "", color: root.colRed, cmd: ["bspc", "quit"] }
                        ]
                        delegate: Rectangle {
                            required property var modelData
                            width: parent.width
                            height: 86
                            radius: 16
                            color: popArea.pressed ? root.colBlue : root.colSurface
                            Row {
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.left: parent.left
                                anchors.leftMargin: 20
                                spacing: 16
                                Text {
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: modelData.icon
                                    color: popArea.pressed ? root.colDark : modelData.color
                                    font.family: root.uiFont
                                    font.pixelSize: 26
                                }
                                Text {
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: modelData.label
                                    color: popArea.pressed ? root.colDark : root.colText
                                    font.family: root.uiFont
                                    font.pixelSize: 21
                                    font.bold: true
                                }
                            }
                            MouseArea {
                                id: popArea
                                anchors.fill: parent
                                anchors.leftMargin: -18
                                anchors.rightMargin: -18
                                anchors.topMargin: -9
                                anchors.bottomMargin: -9
                                onClicked: {
                                    root.closeSession();
                                    root.runCmd(modelData.cmd);
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
