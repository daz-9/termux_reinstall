import QtQuick
import QtQuick.Layouts

Rectangle {
    id: card
    required property var hub
    property bool expanded: false
    signal holdToggled()

    readonly property real baseHeight: wifiHeaderRow.implicitHeight + 10 + wifiMetaText.implicitHeight + 36
    implicitHeight: baseHeight
    radius: 20
    color: cardArea.pressed ? Theme.colSurface1 : Theme.colSurface
    border.color: hub.wifiOk ? Theme.colBlue : Theme.colSurface1
    border.width: 1

    onExpandedChanged: {
        if (expanded) hub.scanWifiIfStale();
    }

    function metaLine() {
        if (!hub.wifiOk) {
            return hub.wifiEnabled ? "Tap Settings to choose a network" : "Tap Off to enable Wi-Fi";
        }
        const parts = [];
        if (hub.wifiIp.length > 0) parts.push(hub.wifiIp);
        if (hub.wifiRate > 0) parts.push(hub.wifiRate + " Mbps");
        if (hub.wifiBand.length > 0) parts.push(hub.wifiBand);
        if (hub.wifiRssi < 0) parts.push(hub.wifiRssi + " dBm");
        return parts.length > 0 ? parts.join(" · ") : "Connected";
    }

    MouseArea {
        id: cardArea
        property bool _held: false
        anchors.fill: parent
        pressAndHoldInterval: 380
        onPressed: _held = false
        onPressAndHold: {
            _held = true;
            card.holdToggled();
        }
        onClicked: {
            if (!_held) {
                if (card.expanded) card.holdToggled();
                else hub.refreshWifi();
            }
        }
    }

    // Compact view
    ColumnLayout {
        id: wifiCompact
        visible: !card.expanded
        anchors.fill: parent
        anchors.leftMargin: 24
        anchors.rightMargin: 24
        anchors.topMargin: 18
        anchors.bottomMargin: 18
        spacing: 10

        RowLayout {
            id: wifiHeaderRow
            Layout.fillWidth: true
            spacing: 10

            Text {
                text: hub.wifiIcon()
                color: hub.wifiOk ? Theme.colBlue : Theme.colSubtext
                font.family: Theme.uiFont
                font.pixelSize: 26
            }
            Text {
                Layout.fillWidth: true
                elide: Text.ElideRight
                text: hub.wifiOk
                    ? (hub.wifiSsid.length > 0 ? hub.wifiSsid : "Wi-Fi Connected")
                    : (hub.wifiEnabled ? "Disconnected" : "Wi-Fi Off")
                color: Theme.colText
                font.family: Theme.uiFont
                font.pixelSize: 22
                font.bold: true
            }

            Rectangle {
                implicitWidth: 46
                height: 44
                radius: 16
                color: settingsArea.pressed ? Theme.colBlue : Theme.colPopupBase
                border.color: Theme.colSurface1
                border.width: 1
                Text {
                    anchors.centerIn: parent
                    text: "󰒓"
                    color: settingsArea.pressed ? Theme.colDark : Theme.colSubtext
                    font.family: Theme.uiFont
                    font.pixelSize: 20
                }
                MouseArea {
                    id: settingsArea
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
                        if (!_held) hub.openWifiSettings();
                    }
                }
            }

            Rectangle {
                implicitWidth: toggleRow.implicitWidth + 26
                height: 44
                radius: 16
                color: toggleArea.pressed ? Theme.colBlue : Theme.colPopupBase
                border.color: hub.wifiEnabled ? Theme.colGreen : Theme.colSurface1
                border.width: 1
                Row {
                    id: toggleRow
                    anchors.centerIn: parent
                    spacing: 8
                    Rectangle {
                        anchors.verticalCenter: parent.verticalCenter
                        width: 10
                        height: 10
                        radius: 5
                        color: toggleArea.pressed ? Theme.colDark : (hub.wifiEnabled ? Theme.colGreen : Theme.colSubtext)
                    }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: hub.wifiEnabled ? "On" : "Off"
                        color: toggleArea.pressed ? Theme.colDark : (hub.wifiEnabled ? Theme.colText : Theme.colSubtext)
                        font.family: Theme.uiFont
                        font.pixelSize: 18
                        font.bold: true
                    }
                }
                MouseArea {
                    id: toggleArea
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
                        if (!_held) hub.toggleWifi();
                    }
                }
            }
        }

        Text {
            id: wifiMetaText
            visible: card.height < 180 || !hub.wifiOk
            Layout.fillWidth: true
            elide: Text.ElideRight
            text: card.metaLine()
            color: Theme.colSubtext
            font.family: Theme.uiFont
            font.pixelSize: 18
        }

        RowLayout {
            visible: card.height >= 180 && hub.wifiOk
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 10

            Repeater {
                model: [
                    { lbl: "IP", val: hub.wifiIp.length > 0 ? hub.wifiIp : "--", col: Theme.colText },
                    { lbl: "Speed", val: hub.wifiRate > 0 ? (hub.wifiRate + " Mbps") : "--", col: Theme.colBlue },
                    { lbl: "Band", val: hub.wifiBand.length > 0 ? hub.wifiBand : "--", col: Theme.colTeal },
                    { lbl: "Signal", val: hub.wifiRssi < 0 ? (hub.wifiRssi + " dBm") : "--", col: Theme.colGreen }
                ]
                delegate: Rectangle {
                    required property var modelData
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    radius: 14
                    color: Theme.colPopupBase
                    border.color: Theme.colSurface1
                    border.width: 1
                    Column {
                        anchors.centerIn: parent
                        width: parent.width - 14
                        spacing: 3
                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: modelData.lbl
                            color: Theme.colSubtext
                            font.family: Theme.uiFont
                            font.pixelSize: 14
                        }
                        Text {
                            width: parent.width
                            horizontalAlignment: Text.AlignHCenter
                            elide: Text.ElideRight
                            text: modelData.val
                            color: modelData.col
                            font.family: Theme.uiFont
                            font.pixelSize: 17
                            font.bold: true
                        }
                    }
                }
            }
        }
    }

    // Expanded view (fills upper part with nearby networks list)
    ColumnLayout {
        visible: card.expanded
        anchors.fill: parent
        anchors.margins: 22
        spacing: 12

        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            Text {
                text: hub.wifiIcon()
                color: hub.wifiOk ? Theme.colBlue : Theme.colSubtext
                font.family: Theme.uiFont
                font.pixelSize: 28
            }
            Text {
                Layout.fillWidth: true
                elide: Text.ElideRight
                text: hub.wifiOk
                    ? (hub.wifiSsid.length > 0 ? hub.wifiSsid : "Wi-Fi Connected")
                    : (hub.wifiEnabled ? "Disconnected" : "Wi-Fi Off")
                color: Theme.colText
                font.family: Theme.uiFont
                font.pixelSize: 23
                font.bold: true
            }

            CollapseButton {
                onClicked: card.holdToggled()
            }

            Rectangle {
                implicitWidth: scanBtnLbl.implicitWidth + 22
                height: 44
                radius: 16
                color: expScanArea.pressed ? Theme.colBlue : Theme.colPopupBase
                border.color: Theme.colSurface1
                border.width: 1
                Text {
                    id: scanBtnLbl
                    anchors.centerIn: parent
                    text: hub.wifiScanning ? "Scanning" : "  Scan"
                    color: expScanArea.pressed ? Theme.colDark : Theme.colBlue
                    font.family: Theme.uiFont
                    font.pixelSize: 16
                    font.bold: true
                }
                MouseArea {
                    id: expScanArea
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
                        if (!_held) {
                            hub.refreshWifi();
                            hub.scanWifi(true);
                        }
                    }
                }
            }

            Rectangle {
                implicitWidth: 44
                height: 44
                radius: 16
                color: expSettingsArea.pressed ? Theme.colBlue : Theme.colPopupBase
                border.color: Theme.colSurface1
                border.width: 1
                Text {
                    anchors.centerIn: parent
                    text: "󰒓"
                    color: expSettingsArea.pressed ? Theme.colDark : Theme.colSubtext
                    font.family: Theme.uiFont
                    font.pixelSize: 19
                }
                MouseArea {
                    id: expSettingsArea
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
                        if (!_held) hub.openWifiSettings();
                    }
                }
            }

            Rectangle {
                implicitWidth: expToggleLbl.implicitWidth + 22
                height: 44
                radius: 16
                color: expToggleArea.pressed ? Theme.colBlue : Theme.colPopupBase
                border.color: hub.wifiEnabled ? Theme.colGreen : Theme.colSurface1
                border.width: 1
                Text {
                    id: expToggleLbl
                    anchors.centerIn: parent
                    text: hub.wifiEnabled ? "On" : "Off"
                    color: expToggleArea.pressed ? Theme.colDark : (hub.wifiEnabled ? Theme.colGreen : Theme.colSubtext)
                    font.family: Theme.uiFont
                    font.pixelSize: 16
                    font.bold: true
                }
                MouseArea {
                    id: expToggleArea
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
                        if (!_held) hub.toggleWifi();
                    }
                }
            }
        }

        Text {
            Layout.fillWidth: true
            elide: Text.ElideRight
            text: card.metaLine()
            color: hub.wifiOk ? Theme.colBlue : Theme.colSubtext
            font.family: Theme.uiFont
            font.pixelSize: 17
        }

        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            MouseArea {
                anchors.fill: parent
                pressAndHoldInterval: 380
                onPressAndHold: card.holdToggled()
                onClicked: card.holdToggled()
            }

            Flickable {
                anchors.fill: parent
                contentWidth: width
                contentHeight: netCol.implicitHeight
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                interactive: contentHeight > height

                Column {
                    id: netCol
                    width: parent.width
                    spacing: 8

                    Repeater {
                        model: card.expanded ? hub.wifiNetworks : []
                        delegate: Rectangle {
                            required property var modelData
                            readonly property bool isCurrent: hub.wifiSsid.length > 0 && modelData.ssid === hub.wifiSsid
                            width: parent.width
                            height: 48
                            radius: 16
                            color: netArea.pressed ? Theme.colBlue : Theme.colPopupBase
                            border.color: isCurrent ? Theme.colBlue : Theme.colSurface1
                            border.width: 1

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 16
                                anchors.rightMargin: 16
                                spacing: 12

                                Text {
                                    text: hub.wifiRssiIcon(Number(modelData.rssi) || -90)
                                    color: netArea.pressed ? Theme.colDark : (isCurrent ? Theme.colBlue : Theme.colText)
                                    font.family: Theme.uiFont
                                    font.pixelSize: 20
                                }
                                Text {
                                    Layout.fillWidth: true
                                    elide: Text.ElideRight
                                    text: String(modelData.ssid || "")
                                    color: netArea.pressed ? Theme.colDark : Theme.colText
                                    font.family: Theme.uiFont
                                    font.pixelSize: 18
                                    font.bold: true
                                }
                                Text {
                                    visible: Boolean(modelData.saved)
                                    text: "Saved"
                                    color: netArea.pressed ? Theme.colDark : Theme.colGreen
                                    font.family: Theme.uiFont
                                    font.pixelSize: 15
                                    font.bold: true
                                }
                                Text {
                                    visible: String(modelData.band || "").length > 0
                                    text: String(modelData.band || "")
                                    color: netArea.pressed ? Theme.colDark : Theme.colSubtext
                                    font.family: Theme.uiFont
                                    font.pixelSize: 15
                                }
                                Text {
                                    text: modelData.secure ? "󰌾" : "󰿆"
                                    color: netArea.pressed ? Theme.colDark : (modelData.secure ? Theme.colPeach : Theme.colTeal)
                                    font.family: Theme.uiFont
                                    font.pixelSize: 17
                                }
                                Text {
                                    text: (Number(modelData.rssi) || 0) + " dBm"
                                    color: netArea.pressed ? Theme.colDark : Theme.colSubtext
                                    font.family: Theme.uiFont
                                    font.pixelSize: 15
                                }
                            }

                            MouseArea {
                                id: netArea
                                property bool _held: false
                                anchors.fill: parent
                                anchors.topMargin: -3
                                anchors.bottomMargin: -3
                                pressAndHoldInterval: 380
                                onPressed: _held = false
                                onPressAndHold: {
                                    _held = true;
                                    card.holdToggled();
                                }
                                onClicked: {
                                    if (!_held) hub.connectWifiNetwork(modelData);
                                }
                            }
                        }
                    }

                    Rectangle {
                        visible: hub.wifiNetworks.length === 0
                        width: parent.width
                        height: 56
                        radius: 16
                        color: Theme.colPopupBase
                        border.color: Theme.colSurface1
                        border.width: 1
                        Text {
                            anchors.centerIn: parent
                            text: hub.wifiScanning ? "Scanning nearby networks..." : hub.wifiScanNote
                            color: Theme.colSubtext
                            font.family: Theme.uiFont
                            font.pixelSize: 17
                        }
                    }
                }
            }
        }
    }
}
