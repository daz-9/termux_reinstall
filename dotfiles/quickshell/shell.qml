import Quickshell
import Quickshell.Io
import QtQuick
import QtQuick.Layouts
import "./components"

ShellRoot {
    id: root

    ListModel {
        id: desktopModel
        ListElement { num: 1; focused: true; occupied: false; urgent: false }
        ListElement { num: 2; focused: false; occupied: false; urgent: false }
        ListElement { num: 3; focused: false; occupied: false; urgent: false }
        ListElement { num: 4; focused: false; occupied: false; urgent: false }
        ListElement { num: 5; focused: false; occupied: false; urgent: false }
        ListElement { num: 6; focused: false; occupied: false; urgent: false }
    }
    property string layoutMode: "T"
    property int volumePct: 50
    property bool muted: false

    property bool sessionOpen: false
    property bool sessionActive: false
    property bool widgetsOpen: false
    property bool widgetsActive: false
    property bool widgetsEverOpened: false
    property bool notifsOpen: false
    property bool notifsActive: false
    property bool notifsEverOpened: false
    readonly property alias hub: widgetHub

    function syncDesktopStates(next) {
        if (next.length === desktopModel.count) {
            for (let i = 0; i < next.length; i++) {
                const cur = desktopModel.get(i);
                const nxt = next[i];
                if (cur.num !== nxt.num || cur.focused !== nxt.focused || cur.occupied !== nxt.occupied || cur.urgent !== nxt.urgent) {
                    desktopModel.set(i, nxt);
                }
            }
        } else {
            desktopModel.clear();
            for (let i = 0; i < next.length; i++) {
                desktopModel.append(next[i]);
            }
        }
    }

    function runCmd(cmd) {
        Quickshell.execDetached(cmd);
    }

    function refreshAudio() {
        if (!audioPollProc.running) {
            audioPollProc.running = true;
        }
    }

    function toggleWidgets() {
        if (root.widgetsOpen) {
            closeWidgets();
        } else {
            closeSession();
            closeNotifications();
            widgetsCloseTimer.stop();
            root.widgetsEverOpened = true;
            root.widgetsActive = true;
            root.widgetsOpen = true;
            hub.onWidgetsOpened();
            syncWatcher();
        }
    }

    function closeWidgets() {
        if (!root.widgetsOpen && !root.widgetsActive) return;
        root.widgetsOpen = false;
        widgetsCloseTimer.restart();
        syncWatcher();
    }

    function toggleNotifications() {
        if (root.notifsOpen) {
            closeNotifications();
        } else {
            closeSession();
            closeWidgets();
            notifsCloseTimer.stop();
            root.notifsEverOpened = true;
            root.notifsActive = true;
            root.notifsOpen = true;
            hub.onNotifsOpened();
            syncWatcher();
        }
    }

    function closeNotifications() {
        if (!root.notifsOpen && !root.notifsActive) return;
        root.notifsOpen = false;
        notifsCloseTimer.restart();
        syncWatcher();
    }

    function toggleSession() {
        if (root.sessionOpen) {
            closeSession();
        } else {
            closeWidgets();
            closeNotifications();
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
        closeNotifications();
        closeSession();
    }

    function syncWatcher() {
        submenuWatcher.running = false;
        if (root.widgetsOpen || root.notifsOpen || root.sessionOpen) {
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
            root.syncDesktopStates(next);
        }
    }

    WidgetHub {
        id: widgetHub
        widgetsOpen: root.widgetsOpen
        notifsOpen: root.notifsOpen
    }

    Timer {
        id: widgetsCloseTimer
        interval: 120
        repeat: false
        onTriggered: {
            if (!root.widgetsOpen) root.widgetsActive = false;
        }
    }

    Timer {
        id: notifsCloseTimer
        interval: 120
        repeat: false
        onTriggered: {
            if (!root.notifsOpen) root.notifsActive = false;
        }
    }

    Timer {
        id: sessionCloseTimer
        interval: 150
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
            if (root.widgetsOpen || root.notifsOpen || root.sessionOpen) {
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
            String((root.widgetsOpen || root.notifsOpen) ? 80 : Math.max(80, 80 + (dockWindow.height > 0 ? dockWindow.height : 1508) - 330)),
            String((root.widgetsOpen || root.notifsOpen) ? widgetsPopup.implicitWidth : sessionPopup.implicitWidth),
            String((root.widgetsOpen || root.notifsOpen) ? widgetsPopup.implicitHeight : sessionPopup.implicitHeight)
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

    Process {
        id: pactlSubProc
        command: ["pactl", "subscribe"]
        running: true
        stdout: SplitParser {
            onRead: line => {
                if (line.indexOf("on sink") >= 0) {
                    root.refreshAudio();
                }
            }
        }
    }

    Timer {
        interval: 10000
        running: !pactlSubProc.running
        repeat: true
        onTriggered: {
            pactlSubProc.running = true;
            root.refreshAudio();
        }
    }

    Timer {
        id: audioSyncDelay
        interval: 150
        repeat: false
        onTriggered: root.refreshAudio()
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
                            root.runCmd(["sh", "-c", "if command -v xfce4-terminal >/dev/null 2>&1; then exec xfce4-terminal; else exec alacritty; fi"]);
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

                // Middle: Touch Workspaces (1-6) + Layout Toggle
                Column {
                    Layout.alignment: Qt.AlignHCenter
                    spacing: dockWindow.compactDock ? 5 : 12

                    Repeater {
                        model: desktopModel
                        delegate: Rectangle {
                            required property int num
                            required property bool focused
                            required property bool occupied
                            required property bool urgent
                            width: 92
                            height: dockWindow.compactDock ? 36 : 58
                            radius: 18
                            color: focused
                                ? Theme.colBlue
                                : (urgent
                                    ? Theme.colRed
                                    : (occupied ? Theme.colSurface : "transparent"))
                            border.color: (!focused && occupied) ? Theme.colSurface1 : "transparent"
                            border.width: 1

                            Behavior on color { ColorAnimation { duration: 80 } }

                            Row {
                                anchors.centerIn: parent
                                spacing: 6
                                Text {
                                    text: String(num)
                                    color: (focused || urgent) ? Theme.colDark : (occupied ? Theme.colText : Theme.colSubtext)
                                    font.family: Theme.uiFont
                                    font.pixelSize: dockWindow.compactDock ? 18 : 24
                                    font.bold: focused || occupied
                                }
                                Rectangle {
                                    visible: occupied && !focused
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
                                onClicked: root.runCmd(["bspc", "desktop", "-f", "^" + num])
                            }
                        }
                    }

                    DockButton {
                        buttonHeight: dockWindow.compactDock ? 42 : 56
                        iconText: root.layoutMode === "M" ? "󰕮" : "󰕳"
                        subText: dockWindow.compactDock ? "" : root.layoutMode
                        iconColor: root.layoutMode === "M" ? Theme.colMauve : Theme.colSubtext
                        iconSize: dockWindow.compactDock ? 20 : 24
                        onClicked: root.runCmd(["bspc", "desktop", "-l", "next"])
                    }
                }

                // Empty Dock Spacer -> 1-touch Widget Hub, 2-touch Notifications
                Item {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.minimumHeight: dockWindow.compactDock ? 38 : 68

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
                            height: dockWindow.compactDock ? 18 : 38
                            radius: 3
                            color: root.widgetsOpen ? Theme.colBlue : (root.notifsOpen ? Theme.colMauve : Theme.colSurface1)
                            Behavior on color { ColorAnimation { duration: 120 } }
                        }
                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: root.notifsOpen ? "󰄽" : "󰄾"
                            color: root.notifsOpen ? Theme.colMauve : Theme.colSubtext
                            font.family: Theme.uiFont
                            font.pixelSize: 20
                        }
                    }

                    MultiPointTouchArea {
                        id: drawerToggleArea
                        anchors.fill: parent
                        property bool _twoTouched: false
                        property bool _held: false
                        touchPoints: [ TouchPoint { id: tp1 }, TouchPoint { id: tp2 } ]
                        Timer {
                            id: drawerHoldTimer
                            interval: 380
                            repeat: false
                            onTriggered: {
                                if (tp1.pressed && !tp2.pressed && !drawerToggleArea._twoTouched) {
                                    drawerToggleArea._held = true;
                                    root.toggleNotifications();
                                }
                            }
                        }
                        onPressed: {
                            if (tp1.pressed && tp2.pressed) {
                                drawerHoldTimer.stop();
                                if (!_held) _twoTouched = true;
                            } else if (tp1.pressed && !_twoTouched && !_held) {
                                drawerHoldTimer.restart();
                            }
                        }
                        onReleased: {
                            if (!tp1.pressed && !tp2.pressed) {
                                drawerHoldTimer.stop();
                                if (_twoTouched) {
                                    _twoTouched = false;
                                    _held = false;
                                    root.toggleNotifications();
                                } else if (_held) {
                                    _held = false;
                                } else {
                                    root.toggleWidgets();
                                }
                            }
                        }
                        onCanceled: {
                            drawerHoldTimer.stop();
                            _twoTouched = false;
                            _held = false;
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

                // Bottom: Window Controls + Volume + Session Power
                Column {
                    Layout.alignment: Qt.AlignHCenter
                    spacing: dockWindow.compactDock ? 5 : 10

                    DockButton {
                        buttonHeight: dockWindow.compactDock ? 36 : 56
                        iconText: ""
                        iconColor: Theme.colText
                        iconSize: dockWindow.compactDock ? 20 : 26
                        onClicked: root.runCmd(["bspc", "node", "-t", "~floating"])
                    }
                    DockButton {
                        buttonHeight: dockWindow.compactDock ? 36 : 56
                        iconText: ""
                        iconColor: Theme.colText
                        iconSize: dockWindow.compactDock ? 20 : 26
                        onClicked: root.runCmd(["bspc", "node", "-t", "~fullscreen"])
                    }
                    DockButton {
                        buttonHeight: dockWindow.compactDock ? 36 : 56
                        iconText: ""
                        iconColor: Theme.colRed
                        iconSize: dockWindow.compactDock ? 22 : 28
                        onClicked: root.runCmd(["bspc", "node", "-c"])
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

        Loader {
            anchors.fill: parent
            active: root.widgetsEverOpened
            sourceComponent: Component {
                WidgetsDrawerContent {
                    hub: root.hub
                    open: root.widgetsOpen
                    onCloseRequested: root.closeWidgets()
                }
            }
        }
    }

    // Android Notifications Drawer (Same size as Widget Hub)
    PopupWindow {
        id: notifsPopup
        anchor.window: dockWindow
        anchor.rect.x: dockWindow.width + 12
        anchor.rect.y: 0
        implicitWidth: 844
        implicitHeight: dockWindow.height > 0 ? dockWindow.height : 1504
        visible: root.notifsActive
        color: "transparent"

        Loader {
            anchors.fill: parent
            active: root.notifsEverOpened
            sourceComponent: Component {
                NotificationsDrawerContent {
                    hub: root.hub
                    open: root.notifsOpen
                    onCloseRequested: root.closeNotifications()
                }
            }
        }
    }

    // Raised Session Menu (Bottom-left submenu of Quit/Power button)
    PopupWindow {
        id: sessionPopup
        anchor.window: dockWindow
        anchor.rect.x: dockWindow.width + 12
        anchor.rect.y: Math.max(0, (dockWindow.height > 0 ? dockWindow.height : 1504) - 330)
        implicitWidth: 330
        implicitHeight: 330
        visible: root.sessionActive
        color: "transparent"

        SessionMenuContent {
            open: root.sessionOpen
            items: [
                { label: "Reload Bars", icon: "", color: Theme.colBlue, cmd: ["sh", "-c", "$HOME/.config/polybar/launch.sh & $HOME/.config/quickshell/launch.sh &"] },
                { label: "Restart WM", icon: "", color: Theme.colTeal, cmd: ["bspc", "wm", "-r"] },
                { label: "Exit X11", icon: "", color: Theme.colRed, cmd: ["bspc", "quit"] }
            ]
            onCloseRequested: root.closeSession()
            onActionTriggered: cmd => {
                root.closeSession();
                root.runCmd(cmd);
            }
        }
    }
}
