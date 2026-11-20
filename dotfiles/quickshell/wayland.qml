import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import QtQuick
import QtQuick.Layouts
import "./components"

ShellRoot {
    id: root

    readonly property bool isSway: (Quickshell.env("SWAYSOCK") || "").length > 0
    property var desktopStates: [
        { num: 1, focused: true, occupied: false, urgent: false },
        { num: 2, focused: false, occupied: false, urgent: false },
        { num: 3, focused: false, occupied: false, urgent: false },
        { num: 4, focused: false, occupied: false, urgent: false },
        { num: 5, focused: false, occupied: false, urgent: false },
        { num: 6, focused: false, occupied: false, urgent: false }
    ]
    property int volumePct: 50
    property bool muted: false
    property int cpuPct: 0
    property string memUsed: "0.0"
    property string memTotal: "0.0"
    property int memPct: 0
    property int batPct: -1
    property string batStatus: "UNKNOWN"
    property real tempC: -1
    property string batWatts: ""
    property bool wifiOk: false
    property int wifiRate: 0
    property string focusedTitle: {
        if (root.isSway) return swayFocusedTitle;
        const tl = ToplevelManager.activeToplevel;
        return (tl && tl.title && tl.title.length > 0) ? String(tl.title) : "Ready";
    }
    property string swayFocusedTitle: "Ready"
    property string clockText: Qt.formatDateTime(new Date(), "ddd d MMM  HH:mm")

    property bool sessionOpen: false
    property bool sessionActive: false
    property bool widgetsOpen: false
    property bool widgetsActive: false

    function runCmd(cmd) {
        Quickshell.execDetached(cmd);
    }

    function refreshAudio() {
        if (!audioPollProc.running) {
            audioPollProc.running = true;
        }
    }

    function refreshSwayWorkspaces() {
        if (root.isSway && !swayWsPoll.running) {
            swayWsPoll.running = true;
        }
        if (root.isSway && !swayTreePoll.running) {
            swayTreePoll.running = true;
        }
    }

    function findFocusedTitle(node) {
        if (!node) return "";
        if (node.focused && node.name && node.type !== "workspace" && node.type !== "output" && node.type !== "root") {
            return String(node.name);
        }
        const kids = (node.nodes || []).concat(node.floating_nodes || []);
        for (let i = 0; i < kids.length; i++) {
            const t = findFocusedTitle(kids[i]);
            if (t.length > 0) return t;
        }
        return "";
    }

    function toggleWidgets() {
        if (root.widgetsOpen) {
            closeWidgets();
        } else {
            closeSession();
            widgetsCloseTimer.stop();
            root.widgetsActive = true;
            root.widgetsOpen = true;
            hub.onWidgetsOpened();
        }
    }

    function closeWidgets() {
        if (!root.widgetsOpen && !root.widgetsActive) return;
        root.widgetsOpen = false;
        widgetsCloseTimer.restart();
    }

    function toggleSession() {
        if (root.sessionOpen) {
            closeSession();
        } else {
            closeWidgets();
            sessionCloseTimer.stop();
            root.sessionActive = true;
            root.sessionOpen = true;
        }
    }

    function closeSession() {
        if (!root.sessionOpen && !root.sessionActive) return;
        root.sessionOpen = false;
        sessionCloseTimer.restart();
    }

    function closeAllMenus() {
        closeWidgets();
        closeSession();
    }

    WidgetHub {
        id: hub
        widgetsOpen: root.widgetsOpen
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

    // LabWC live ext_workspace_manager_v1 stream + activation
    Process {
        id: wlWsProc
        command: [Quickshell.env("HOME") + "/.local/bin/qs-native", "wl-workspaces"]
        running: !root.isSway
        stdinEnabled: true
        stdout: SplitParser {
            onRead: line => {
                try {
                    const list = JSON.parse(line);
                    if (Array.isArray(list) && list.length > 0) {
                        root.desktopStates = list;
                    }
                } catch (e) {}
            }
        }
    }

    // Sway live workspace & window events
    Process {
        id: swaySub
        command: ["swaymsg", "-t", "subscribe", "-m", "[\"workspace\",\"window\"]"]
        running: root.isSway
        stdout: SplitParser {
            onRead: _ => root.refreshSwayWorkspaces()
        }
    }

    Process {
        id: swayTreePoll
        command: ["swaymsg", "-t", "get_tree"]
        running: root.isSway
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    const tree = JSON.parse(this.text || "{}");
                    const t = root.findFocusedTitle(tree);
                    root.swayFocusedTitle = t.length > 0 ? t : "Ready";
                } catch (e) {}
            }
        }
    }

    Process {
        id: swayWsPoll
        command: ["swaymsg", "-t", "get_workspaces"]
        running: root.isSway
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    const list = JSON.parse(this.text || "[]");
                    const byNum = {};
                    for (let i = 0; i < list.length; i++) {
                        byNum[list[i].num] = list[i];
                    }
                    const next = [];
                    for (let n = 1; n <= 6; n++) {
                        const ws = byNum[n];
                        next.push({
                            num: n,
                            focused: ws ? Boolean(ws.focused) : false,
                            occupied: Boolean(ws),
                            urgent: ws ? Boolean(ws.urgent) : false
                        });
                    }
                    root.desktopStates = next;
                } catch (e) {}
            }
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

    Process {
        id: sysDiagProc
        command: [Quickshell.env("HOME") + "/.local/bin/qs-native", "sys-diag"]
        running: true
        stdout: SplitParser {
            onRead: line => {
                try {
                    const d = JSON.parse(line);
                    if (d.cpu !== undefined) root.cpuPct = d.cpu;
                    if (d.mem_used !== undefined) root.memUsed = String(d.mem_used);
                    if (d.mem_total !== undefined) root.memTotal = String(d.mem_total);
                    if (d.mem_pct !== undefined) root.memPct = d.mem_pct;
                    if (d.bat_pct !== undefined) root.batPct = d.bat_pct;
                    if (d.bat_status !== undefined) root.batStatus = String(d.bat_status);
                    if (d.temp_c !== null && d.temp_c !== undefined) root.tempC = d.temp_c;
                    if (d.watts !== undefined) root.batWatts = String(d.watts);
                    if (d.wifi_ok !== undefined) root.wifiOk = Boolean(d.wifi_ok);
                    if (d.wifi_rate !== undefined) root.wifiRate = d.wifi_rate;
                } catch (e) {}
            }
        }
    }

    Timer {
        interval: 1000
        running: true
        repeat: true
        onTriggered: {
            root.clockText = Qt.formatDateTime(new Date(), "ddd d MMM  HH:mm");
        }
    }

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

    // Top Status Bar (Wayland layer-shell replacement for Polybar)
    PanelWindow {
        id: topBarWindow
        anchors {
            left: true
            top: true
            right: true
        }
        margins {
            left: 12
            right: 12
            top: 10
        }
        implicitHeight: 54
        color: "transparent"
        WlrLayershell.layer: WlrLayer.Top

        Rectangle {
            id: topBarBg
            anchors.fill: parent
            radius: 18
            color: Theme.colBase
            border.color: Theme.colSurface
            border.width: 2

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 18
                anchors.rightMargin: 18
                spacing: 12

                Rectangle {
                    id: wmPill
                    radius: 12
                    color: Theme.colSurface
                    implicitHeight: 36
                    implicitWidth: wmRow.implicitWidth + 24
                    Row {
                        id: wmRow
                        anchors.centerIn: parent
                        spacing: 8
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: "󰍙"
                            color: Theme.colBlue
                            font.family: Theme.uiFont
                            font.pixelSize: 18
                        }
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: root.isSway ? "SWAY" : "LABWC"
                            color: Theme.colText
                            font.family: Theme.uiFont
                            font.pixelSize: 15
                            font.bold: true
                        }
                    }
                }

                Text {
                    Layout.fillWidth: true
                    Layout.maximumWidth: Math.max(80, topBarBg.width / 2 - wmPill.width - clockPill.width / 2 - 48)
                    elide: Text.ElideRight
                    text: root.focusedTitle
                    color: root.focusedTitle === "Ready" ? Theme.colSubtext : Theme.colText
                    font.family: Theme.uiFont
                    font.pixelSize: 15
                }

                Item { Layout.fillWidth: true }

                Row {
                    spacing: 8

                    // CPU %
                    Rectangle {
                        radius: 12
                        color: Theme.colSurface
                        implicitHeight: 36
                        implicitWidth: cpuRow.implicitWidth + 22
                        Row {
                            id: cpuRow
                            anchors.centerIn: parent
                            spacing: 7
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                text: ""
                                color: root.cpuPct >= 80 ? Theme.colRed : (root.cpuPct >= 50 ? Theme.colPeach : Theme.colTeal)
                                font.family: Theme.uiFont
                                font.pixelSize: 16
                            }
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                text: root.cpuPct + "%"
                                color: Theme.colText
                                font.family: Theme.uiFont
                                font.pixelSize: 15
                                font.bold: true
                            }
                        }
                    }

                    // RAM
                    Rectangle {
                        radius: 12
                        color: Theme.colSurface
                        implicitHeight: 36
                        implicitWidth: memRow.implicitWidth + 22
                        Row {
                            id: memRow
                            anchors.centerIn: parent
                            spacing: 7
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                text: "󰍛"
                                color: root.memPct >= 85 ? Theme.colRed : Theme.colMauve
                                font.family: Theme.uiFont
                                font.pixelSize: 16
                            }
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                text: root.memUsed + "/" + root.memTotal + "G (" + root.memPct + "%)"
                                color: Theme.colText
                                font.family: Theme.uiFont
                                font.pixelSize: 15
                                font.bold: true
                            }
                        }
                    }

                    // Battery Temperature
                    Rectangle {
                        visible: root.tempC >= 0
                        radius: 12
                        color: Theme.colSurface
                        implicitHeight: 36
                        implicitWidth: tempRow.implicitWidth + 22
                        Row {
                            id: tempRow
                            anchors.centerIn: parent
                            spacing: 6
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                text: "󰔏"
                                color: root.tempC >= 43 ? Theme.colRed : (root.tempC >= 38 ? Theme.colPeach : Theme.colTeal)
                                font.family: Theme.uiFont
                                font.pixelSize: 16
                            }
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                text: root.tempC.toFixed(1) + "°C"
                                color: Theme.colText
                                font.family: Theme.uiFont
                                font.pixelSize: 15
                                font.bold: true
                            }
                        }
                    }

                    // Wi-Fi
                    Rectangle {
                        radius: 12
                        color: Theme.colSurface
                        implicitHeight: 36
                        implicitWidth: wifiRow.implicitWidth + 22
                        Row {
                            id: wifiRow
                            anchors.centerIn: parent
                            spacing: 7
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                text: root.wifiOk ? "󰖩" : "󰖪"
                                color: root.wifiOk ? Theme.colBlue : Theme.colSubtext
                                font.family: Theme.uiFont
                                font.pixelSize: 16
                            }
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                text: root.wifiOk ? (root.wifiRate > 0 ? root.wifiRate + "M" : "Wi-Fi") : "Off"
                                color: root.wifiOk ? Theme.colText : Theme.colSubtext
                                font.family: Theme.uiFont
                                font.pixelSize: 15
                                font.bold: true
                            }
                        }
                    }

                    // Volume
                    Rectangle {
                        radius: 12
                        color: Theme.colSurface
                        implicitHeight: 36
                        implicitWidth: volRow.implicitWidth + 22
                        Row {
                            id: volRow
                            anchors.centerIn: parent
                            spacing: 7
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                text: root.muted ? "󰝟" : "󰕾"
                                color: root.muted ? Theme.colRed : Theme.colGreen
                                font.family: Theme.uiFont
                                font.pixelSize: 16
                            }
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                text: root.muted ? "MUTE" : (root.volumePct + "%")
                                color: Theme.colText
                                font.family: Theme.uiFont
                                font.pixelSize: 15
                                font.bold: true
                            }
                        }
                    }

                    // Battery % + Power Draw
                    Rectangle {
                        radius: 12
                        color: Theme.colSurface
                        implicitHeight: 36
                        implicitWidth: batRow.implicitWidth + 22
                        Row {
                            id: batRow
                            anchors.centerIn: parent
                            spacing: 7
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                text: root.batStatus === "CHARGING" ? "" : (root.batPct >= 85 ? "" : (root.batPct >= 60 ? "" : (root.batPct >= 35 ? "" : (root.batPct >= 15 ? "" : ""))))
                                color: root.batStatus === "CHARGING" || root.batPct >= 85 ? Theme.colGreen : (root.batPct >= 35 ? Theme.colText : (root.batPct >= 15 ? Theme.colPeach : Theme.colRed))
                                font.family: Theme.uiFont
                                font.pixelSize: 16
                            }
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                text: root.batPct >= 0 ? (root.batPct + "%" + (root.batWatts.length > 0 ? " " + root.batWatts : "")) : "BAT --"
                                color: Theme.colText
                                font.family: Theme.uiFont
                                font.pixelSize: 15
                                font.bold: true
                            }
                        }
                    }
                }
            }

            Rectangle {
                id: clockPill
                anchors.centerIn: parent
                radius: 12
                color: Theme.colSurface
                height: 36
                width: clockRow.implicitWidth + 24
                Row {
                    id: clockRow
                    anchors.centerIn: parent
                    spacing: 8
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: ""
                        color: Theme.colBlue
                        font.family: Theme.uiFont
                        font.pixelSize: 16
                    }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: root.clockText
                        color: Theme.colBlue
                        font.family: Theme.uiFont
                        font.pixelSize: 16
                        font.bold: true
                    }
                }
            }
        }
    }

    // Left Touch Dock
    PanelWindow {
        id: dockWindow
        anchors {
            left: true
            top: true
            bottom: true
        }
        margins {
            left: 0
            top: 12
            bottom: 12
        }
        implicitWidth: 128
        color: "transparent"
        WlrLayershell.layer: WlrLayer.Top

        readonly property bool compactDock: height > 0 && height < 1200

        Rectangle {
            id: barBg
            anchors.fill: parent
            anchors.leftMargin: 12
            radius: 24
            color: Theme.colBase
            border.color: Theme.colSurface
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
                        iconColor: Theme.colBlue
                        iconSize: dockWindow.compactDock ? 26 : 34
                        buttonHeight: dockWindow.compactDock ? 44 : 66
                        onClicked: {
                            root.closeAllMenus();
                            root.runCmd(["rofi", "-show", "drun"]);
                        }
                    }
                    DockButton {
                        iconText: ""
                        iconColor: Theme.colTeal
                        iconSize: dockWindow.compactDock ? 24 : 30
                        buttonHeight: dockWindow.compactDock ? 44 : 66
                        onClicked: {
                            root.closeAllMenus();
                            root.runCmd(["sh", "-c", "if command -v foot >/dev/null 2>&1; then exec foot; elif command -v xfce4-terminal >/dev/null 2>&1; then exec xfce4-terminal; else exec alacritty; fi"]);
                        }
                    }
                    DockButton {
                        iconText: ""
                        iconColor: Theme.colMauve
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
                    color: Theme.colSurface1
                }

                // Middle: Workspaces (1-6) + Layout Toggle
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
                                ? Theme.colBlue
                                : (modelData.urgent
                                    ? Theme.colRed
                                    : (modelData.occupied ? Theme.colSurface : "transparent"))
                            border.color: (!modelData.focused && modelData.occupied) ? Theme.colSurface1 : "transparent"
                            border.width: 1

                            Behavior on scale { NumberAnimation { duration: 80 } }
                            Behavior on color { ColorAnimation { duration: 100 } }

                            Row {
                                anchors.centerIn: parent
                                spacing: 6
                                Text {
                                    text: String(modelData.num)
                                    color: (modelData.focused || modelData.urgent) ? Theme.colDark : (modelData.occupied ? Theme.colText : Theme.colSubtext)
                                    font.family: Theme.uiFont
                                    font.pixelSize: dockWindow.compactDock ? 18 : 24
                                    font.bold: modelData.focused || modelData.occupied
                                }
                                Rectangle {
                                    visible: modelData.occupied && !modelData.focused
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: 8
                                    height: 8
                                    radius: 4
                                    color: Theme.colBlue
                                }
                            }

                            MouseArea {
                                id: wsArea
                                anchors.fill: parent
                                anchors.leftMargin: -16
                                anchors.rightMargin: -12
                                anchors.topMargin: -4
                                anchors.bottomMargin: -4
                                onClicked: {
                                    if (root.isSway) {
                                        root.runCmd(["swaymsg", "workspace", "number", String(modelData.num)]);
                                    } else {
                                        wlWsProc.write(String(modelData.num) + "\n");
                                    }
                                }
                            }
                        }
                    }

                    DockButton {
                        visible: root.isSway
                        buttonHeight: dockWindow.compactDock ? 42 : 56
                        iconText: "󰕳"
                        subText: dockWindow.compactDock ? "" : "LAY"
                        iconColor: Theme.colSubtext
                        iconSize: dockWindow.compactDock ? 20 : 24
                        onClicked: root.runCmd(["swaymsg", "layout", "toggle", "tabbed", "split"])
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
                            color: root.widgetsOpen ? Theme.colBlue : Theme.colSubtext
                            font.family: Theme.uiFont
                            font.pixelSize: 22
                        }
                        Rectangle {
                            anchors.horizontalCenter: parent.horizontalCenter
                            width: 6
                            height: dockWindow.compactDock ? 20 : 44
                            radius: 3
                            color: root.widgetsOpen ? Theme.colBlue : Theme.colSurface1
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
                    color: Theme.colSurface1
                }

                // Bottom: Window Controls + Volume + Session Power
                Column {
                    Layout.alignment: Qt.AlignHCenter
                    spacing: dockWindow.compactDock ? 5 : 10

                    DockButton {
                        buttonHeight: dockWindow.compactDock ? 36 : 56
                        iconText: ""
                        iconColor: Theme.colText
                        iconSize: dockWindow.compactDock ? 20 : 26
                        onClicked: {
                            if (root.isSway) {
                                root.runCmd(["swaymsg", "floating", "toggle"]);
                            } else if (ToplevelManager.activeToplevel) {
                                ToplevelManager.activeToplevel.maximized = !ToplevelManager.activeToplevel.maximized;
                            }
                        }
                    }
                    DockButton {
                        buttonHeight: dockWindow.compactDock ? 36 : 56
                        iconText: ""
                        iconColor: Theme.colText
                        iconSize: dockWindow.compactDock ? 20 : 26
                        onClicked: {
                            if (root.isSway) {
                                root.runCmd(["swaymsg", "fullscreen", "toggle"]);
                            } else if (ToplevelManager.activeToplevel) {
                                ToplevelManager.activeToplevel.fullscreen = !ToplevelManager.activeToplevel.fullscreen;
                            }
                        }
                    }
                    DockButton {
                        buttonHeight: dockWindow.compactDock ? 36 : 56
                        iconText: ""
                        iconColor: Theme.colRed
                        iconSize: dockWindow.compactDock ? 22 : 28
                        onClicked: {
                            if (root.isSway) {
                                root.runCmd(["swaymsg", "kill"]);
                            } else if (ToplevelManager.activeToplevel) {
                                ToplevelManager.activeToplevel.close();
                            }
                        }
                    }

                    Rectangle {
                        anchors.horizontalCenter: parent.horizontalCenter
                        width: 60
                        height: 2
                        radius: 1
                        color: Theme.colSurface1
                    }

                    DockButton {
                        buttonHeight: dockWindow.compactDock ? 34 : 50
                        iconText: "󰐕"
                        iconColor: Theme.colText
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
                        iconColor: root.muted ? Theme.colRed : Theme.colGreen
                        iconSize: dockWindow.compactDock ? 20 : 24
                        onClicked: {
                            root.runCmd(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"]);
                            audioSyncDelay.restart();
                        }
                    }
                    DockButton {
                        buttonHeight: dockWindow.compactDock ? 34 : 50
                        iconText: "󰍴"
                        iconColor: Theme.colText
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
                        iconColor: root.sessionOpen ? Theme.colDark : Theme.colRed
                        baseColor: root.sessionOpen ? Theme.colRed : Theme.colSurface
                        iconSize: dockWindow.compactDock ? 22 : 28
                        onClicked: root.toggleSession()
                    }
                }
            }
        }
    }

    // Native Wayland Outside-Click / Escape Dismiss Backdrop
    PanelWindow {
        id: dismissBackdrop
        anchors {
            left: true
            right: true
            top: true
            bottom: true
        }
        visible: root.widgetsActive || root.sessionActive
        color: "transparent"
        exclusionMode: ExclusionMode.Ignore
        WlrLayershell.layer: WlrLayer.Top
        WlrLayershell.keyboardFocus: WlrKeyboardFocus.OnDemand

        MouseArea {
            anchors.fill: parent
            onClicked: root.closeAllMenus()
        }
        Shortcut {
            sequence: "Escape"
            onActivated: root.closeAllMenus()
        }
    }

    // Large Readable Widget Drawer (Overlay layer matching dock height)
    PanelWindow {
        id: widgetsPopup
        anchors {
            left: true
            top: true
            bottom: true
        }
        margins {
            left: 140
            top: 76
            bottom: 12
        }
        implicitWidth: 844
        visible: root.widgetsActive
        color: "transparent"
        exclusionMode: ExclusionMode.Ignore
        WlrLayershell.layer: WlrLayer.Overlay

        WidgetsDrawerContent {
            hub: hub
            open: root.widgetsOpen
            onCloseRequested: root.closeWidgets()
        }
    }

    // Raised Session Menu (Bottom-left overlay)
    PanelWindow {
        id: sessionPopup
        anchors {
            left: true
            bottom: true
        }
        margins {
            left: 140
            bottom: 12
        }
        implicitWidth: 330
        implicitHeight: 368
        visible: root.sessionActive
        color: "transparent"
        exclusionMode: ExclusionMode.Ignore
        WlrLayershell.layer: WlrLayer.Overlay

        SessionMenuContent {
            open: root.sessionOpen
            items: [
                { label: "Reload Shell", icon: "", color: Theme.colBlue, cmd: ["sh", "-c", "$HOME/.config/quickshell/launch-wayland.sh &"] },
                { label: "Reload WM", icon: "", color: Theme.colTeal, cmd: root.isSway ? ["swaymsg", "reload"] : ["labwc", "--reconfigure"] },
                { label: "Exit Wayland", icon: "", color: Theme.colRed, cmd: root.isSway ? ["swaymsg", "exit"] : ["labwc", "--exit"] }
            ]
            onActionTriggered: cmd => {
                root.closeSession();
                root.runCmd(cmd);
            }
        }
    }
}
