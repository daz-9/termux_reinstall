import QtQuick
import QtQuick.Layouts

Rectangle {
    id: card
    required property var hub
    property bool expanded: false
    signal holdToggled()

    readonly property real baseHeight: androidBaseMeasure.implicitHeight + 40
    implicitHeight: baseHeight
    radius: 20
    color: Theme.colSurface
    border.color: card.expanded ? Theme.colBlue : Theme.colSurface1
    border.width: 1

    // Invisible compact height reference so baseHeight stays constant when expanded
    Column {
        id: androidBaseMeasure
        visible: false
        width: card.width - 48
        spacing: 14
        Item { width: 1; height: 40 }
        RowLayout {
            width: parent.width
            spacing: 14
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 124
            }
        }
    }

    MouseArea {
        anchors.fill: parent
        pressAndHoldInterval: 380
        onPressAndHold: card.holdToggled()
        onClicked: {
            if (card.expanded) card.holdToggled();
        }
    }

    ColumnLayout {
        id: androidStatusCol
        anchors.fill: parent
        anchors.leftMargin: 24
        anchors.rightMargin: 24
        anchors.topMargin: 20
        anchors.bottomMargin: 20
        spacing: card.expanded ? 14 : 14

        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            Row {
                spacing: 12
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: ""
                    color: (hub.termuxApiOk && hub.shizukuOk) ? Theme.colGreen : ((hub.termuxApiOk || hub.shizukuOk) ? Theme.colPeach : Theme.colRed)
                    font.family: Theme.uiFont
                    font.pixelSize: 28
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: "Termux:API & Shizuku"
                    color: Theme.colText
                    font.family: Theme.uiFont
                    font.pixelSize: 24
                    font.bold: true
                }
            }
            Item { Layout.fillWidth: true }
            CollapseButton {
                visible: card.expanded
                onClicked: card.holdToggled()
            }
            Rectangle {
                implicitWidth: refreshRow.implicitWidth + 24
                height: 44
                radius: 16
                color: refreshBtnArea.pressed ? Theme.colBlue : Theme.colPopupBase
                border.color: Theme.colSurface1
                border.width: 1
                Row {
                    id: refreshRow
                    anchors.centerIn: parent
                    spacing: 8
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: ""
                        color: refreshBtnArea.pressed ? Theme.colDark : Theme.colBlue
                        font.family: Theme.uiFont
                        font.pixelSize: 18
                    }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: hub.androidProbing ? "Checking" : "Refresh"
                        color: refreshBtnArea.pressed ? Theme.colDark : Theme.colSubtext
                        font.family: Theme.uiFont
                        font.pixelSize: 18
                        font.bold: true
                    }
                }
                MouseArea {
                    id: refreshBtnArea
                    property bool _held: false
                    anchors.fill: parent
                    anchors.margins: -5
                    pressAndHoldInterval: 380
                    onPressed: _held = false
                    onPressAndHold: {
                        _held = true;
                        card.holdToggled();
                    }
                    onClicked: {
                        if (!_held) hub.refreshAndroidStatus();
                    }
                }
            }
        }

        // Compact 2-tile row
        RowLayout {
            visible: !card.expanded
            Layout.fillWidth: true
            spacing: 14

            // Termux:API Tile
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: apiTileCol.implicitHeight + 32
                radius: 16
                color: apiTileArea.pressed ? Theme.colBlue : Theme.colPopupBase
                border.color: hub.termuxApiOk ? Theme.colGreen : Theme.colSurface1
                border.width: 1

                Column {
                    id: apiTileCol
                    anchors.fill: parent
                    anchors.margins: 16
                    spacing: 6

                    RowLayout {
                        width: parent.width
                        Row {
                            spacing: 10
                            Rectangle {
                                anchors.verticalCenter: parent.verticalCenter
                                width: 12
                                height: 12
                                radius: 6
                                color: apiTileArea.pressed ? Theme.colDark : (hub.termuxApiOk ? Theme.colGreen : (hub.termuxApiState === "Missing" ? Theme.colRed : Theme.colPeach))
                            }
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                text: "Termux:API"
                                color: apiTileArea.pressed ? Theme.colDark : Theme.colText
                                font.family: Theme.uiFont
                                font.pixelSize: 21
                                font.bold: true
                            }
                        }
                        Item { Layout.fillWidth: true }
                        Text {
                            visible: hub.termuxApiVer.length > 0
                            text: "v" + hub.termuxApiVer
                            color: apiTileArea.pressed ? Theme.colDark : Theme.colSubtext
                            font.family: Theme.uiFont
                            font.pixelSize: 17
                        }
                    }

                    Text {
                        width: parent.width
                        elide: Text.ElideRight
                        text: hub.termuxApiState
                        color: apiTileArea.pressed ? Theme.colDark : (hub.termuxApiOk ? Theme.colGreen : (hub.termuxApiState === "Missing" ? Theme.colRed : Theme.colPeach))
                        font.family: Theme.uiFont
                        font.pixelSize: 23
                        font.bold: true
                    }

                    Text {
                        width: parent.width
                        elide: Text.ElideRight
                        text: hub.termuxApiDetail
                        color: apiTileArea.pressed ? Theme.colDark : Theme.colSubtext
                        font.family: Theme.uiFont
                        font.pixelSize: 18
                    }
                }

                MouseArea {
                    id: apiTileArea
                    property bool _held: false
                    anchors.fill: parent
                    pressAndHoldInterval: 380
                    onPressed: _held = false
                    onPressAndHold: {
                        _held = true;
                        card.holdToggled();
                    }
                    onClicked: {
                        if (!_held) hub.startTermuxApi();
                    }
                }
            }

            // Shizuku Tile
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: shzTileCol.implicitHeight + 32
                radius: 16
                color: shzTileArea.pressed ? Theme.colBlue : Theme.colPopupBase
                border.color: hub.shizukuOk ? Theme.colGreen : Theme.colSurface1
                border.width: 1

                Column {
                    id: shzTileCol
                    anchors.fill: parent
                    anchors.margins: 16
                    spacing: 6

                    RowLayout {
                        width: parent.width
                        Row {
                            spacing: 10
                            Rectangle {
                                anchors.verticalCenter: parent.verticalCenter
                                width: 12
                                height: 12
                                radius: 6
                                color: shzTileArea.pressed ? Theme.colDark : (hub.shizukuOk ? Theme.colGreen : (hub.shizukuState === "No rish" ? Theme.colRed : Theme.colPeach))
                            }
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                text: "Shizuku"
                                color: shzTileArea.pressed ? Theme.colDark : Theme.colText
                                font.family: Theme.uiFont
                                font.pixelSize: 21
                                font.bold: true
                            }
                        }
                        Item { Layout.fillWidth: true }
                        Text {
                            visible: hub.shizukuVer.length > 0
                            text: "v" + hub.shizukuVer
                            color: shzTileArea.pressed ? Theme.colDark : Theme.colSubtext
                            font.family: Theme.uiFont
                            font.pixelSize: 17
                        }
                    }

                    Text {
                        width: parent.width
                        elide: Text.ElideRight
                        text: hub.shizukuState
                        color: shzTileArea.pressed ? Theme.colDark : (hub.shizukuOk ? Theme.colGreen : (hub.shizukuState === "No rish" ? Theme.colRed : Theme.colPeach))
                        font.family: Theme.uiFont
                        font.pixelSize: 23
                        font.bold: true
                    }

                    Text {
                        width: parent.width
                        elide: Text.ElideRight
                        text: hub.shizukuDetail
                        color: shzTileArea.pressed ? Theme.colDark : Theme.colSubtext
                        font.family: Theme.uiFont
                        font.pixelSize: 18
                    }
                }

                MouseArea {
                    id: shzTileArea
                    property bool _held: false
                    anchors.fill: parent
                    pressAndHoldInterval: 380
                    onPressed: _held = false
                    onPressAndHold: {
                        _held = true;
                        card.holdToggled();
                    }
                    onClicked: {
                        if (!_held) hub.refreshAndroidStatus();
                    }
                }
            }
        }

        // Expanded Diagnostics View
        RowLayout {
            visible: card.expanded
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 14

            // Termux:API Diagnostics Panel
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: 16
                color: Theme.colPopupBase
                border.color: hub.termuxApiOk ? Theme.colGreen : Theme.colSurface1
                border.width: 1

                ColumnLayout {
                    id: apiDiagCol
                    anchors.fill: parent
                    anchors.margins: 16
                    spacing: 8

                    RowLayout {
                        Layout.fillWidth: true
                        Row {
                            spacing: 10
                            Rectangle {
                                anchors.verticalCenter: parent.verticalCenter
                                width: 12
                                height: 12
                                radius: 6
                                color: hub.termuxApiOk ? Theme.colGreen : Theme.colRed
                            }
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                text: "Termux:API"
                                color: Theme.colText
                                font.family: Theme.uiFont
                                font.pixelSize: 20
                                font.bold: true
                            }
                        }
                        Item { Layout.fillWidth: true }
                        Text {
                            text: hub.termuxApiVer.length > 0 ? ("v" + hub.termuxApiVer) : "--"
                            color: Theme.colSubtext
                            font.family: Theme.uiFont
                            font.pixelSize: 16
                        }
                    }

                    Text {
                        text: hub.termuxApiState
                        color: hub.termuxApiOk ? Theme.colGreen : (hub.termuxApiState === "Missing" ? Theme.colRed : Theme.colPeach)
                        font.family: Theme.uiFont
                        font.pixelSize: 24
                        font.bold: true
                    }

                    Repeater {
                        model: [
                            { k: "Bridge", v: hub.termuxApiDetail },
                            { k: "Power", v: hub.apiBatPower.length > 0 ? hub.apiBatPower : "--" },
                            { k: "Health", v: hub.apiBatHealth.length > 0 ? hub.apiBatHealth : "--" },
                            { k: "Tools", v: (hub.apiCmds.length > 0 ? hub.apiCmds : "--") + (hub.androidSysVer.length > 0 ? (" · " + hub.androidSysVer) : "") }
                        ]
                        delegate: Column {
                            required property var modelData
                            Layout.fillWidth: true
                            spacing: 2
                            Text {
                                text: modelData.k
                                color: Theme.colSubtext
                                font.family: Theme.uiFont
                                font.pixelSize: 14
                            }
                            Text {
                                width: parent.width
                                elide: Text.ElideRight
                                text: modelData.v
                                color: Theme.colText
                                font.family: Theme.uiFont
                                font.pixelSize: 17
                                font.bold: true
                            }
                        }
                    }

                    Item { Layout.fillHeight: true }
                }
            }

            // Shizuku Diagnostics Panel
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: 16
                color: Theme.colPopupBase
                border.color: hub.shizukuOk ? Theme.colGreen : Theme.colSurface1
                border.width: 1

                ColumnLayout {
                    id: shzDiagCol
                    anchors.fill: parent
                    anchors.margins: 16
                    spacing: 8

                    RowLayout {
                        Layout.fillWidth: true
                        Row {
                            spacing: 10
                            Rectangle {
                                anchors.verticalCenter: parent.verticalCenter
                                width: 12
                                height: 12
                                radius: 6
                                color: hub.shizukuOk ? Theme.colGreen : Theme.colPeach
                            }
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                text: "Shizuku"
                                color: Theme.colText
                                font.family: Theme.uiFont
                                font.pixelSize: 20
                                font.bold: true
                            }
                        }
                        Item { Layout.fillWidth: true }
                        Text {
                            text: hub.shizukuVer.length > 0 ? ("v" + hub.shizukuVer) : "--"
                            color: Theme.colSubtext
                            font.family: Theme.uiFont
                            font.pixelSize: 16
                        }
                    }

                    Text {
                        text: hub.shizukuState
                        color: hub.shizukuOk ? Theme.colGreen : (hub.shizukuState === "No rish" ? Theme.colRed : Theme.colPeach)
                        font.family: Theme.uiFont
                        font.pixelSize: 24
                        font.bold: true
                    }

                    Repeater {
                        model: [
                            { k: "Server", v: hub.shizukuDetail },
                            { k: "Footprint", v: (hub.shzRssMb > 0 ? (hub.shzRssMb + " MB RSS") : "--") + (hub.shzUptime.length > 0 ? (" · Up " + hub.shzUptime) : "") },
                            { k: "ADB", v: "adbd " + (hub.shzAdbd.length > 0 ? hub.shzAdbd : "--") + (hub.shzAdbTcpOpen ? (" · :" + hub.shzAdbPort + " open") : " · TCP closed") + (hub.shzAdbWifi.length > 0 ? (" · WiFi " + hub.shzAdbWifi) : "") },
                            { k: "Security", v: (hub.shzSelinux.length > 0 ? ("SELinux " + hub.shzSelinux) : "SELinux --") + (hub.shzDexMode.length > 0 ? (" · dex " + hub.shzDexMode) : "") }
                        ]
                        delegate: Column {
                            required property var modelData
                            Layout.fillWidth: true
                            spacing: 2
                            Text {
                                text: modelData.k
                                color: Theme.colSubtext
                                font.family: Theme.uiFont
                                font.pixelSize: 14
                            }
                            Text {
                                width: parent.width
                                elide: Text.ElideRight
                                text: modelData.v
                                color: Theme.colText
                                font.family: Theme.uiFont
                                font.pixelSize: 17
                                font.bold: true
                            }
                        }
                    }

                    Item { Layout.fillHeight: true }
                }
            }
        }

        // Expanded Quick Actions Row
        RowLayout {
            visible: card.expanded
            Layout.fillWidth: true
            spacing: 12

            Repeater {
                model: [
                    { lbl: "Start API", act: "start_api", col: Theme.colGreen },
                    { lbl: "Open Shizuku", act: "open_shz", col: Theme.colBlue },
                    { lbl: "Dev Settings", act: "dev_cfg", col: Theme.colMauve }
                ]
                delegate: Rectangle {
                    required property var modelData
                    Layout.fillWidth: true
                    height: 46
                    radius: 16
                    color: actArea.pressed ? Theme.colBlue : Theme.colPopupBase
                    border.color: Theme.colSurface1
                    border.width: 1
                    Text {
                        anchors.centerIn: parent
                        text: modelData.lbl
                        color: actArea.pressed ? Theme.colDark : modelData.col
                        font.family: Theme.uiFont
                        font.pixelSize: 17
                        font.bold: true
                    }
                    MouseArea {
                        id: actArea
                        property bool _held: false
                        anchors.fill: parent
                        anchors.margins: -4
                        pressAndHoldInterval: 380
                        onPressed: _held = false
                        onPressAndHold: {
                            _held = true;
                            card.holdToggled();
                        }
                        onClicked: {
                            if (!_held) {
                                if (modelData.act === "start_api") hub.startTermuxApi();
                                else if (modelData.act === "open_shz") hub.openShizukuApp();
                                else if (modelData.act === "dev_cfg") hub.openDevSettings();
                            }
                        }
                    }
                }
            }
        }
    }
}
