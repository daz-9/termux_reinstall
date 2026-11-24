import QtQuick
import QtQuick.Layouts

Rectangle {
    id: card
    required property var hub
    property bool expanded: false
    signal holdToggled()

    readonly property real baseHeight: focusCompact.implicitHeight + 40
    implicitHeight: baseHeight
    radius: 20
    color: focusArea.pressed ? Theme.colSurface1 : Theme.colSurface
    border.color: (card.expanded || hub.focusDnd) ? Theme.colMauve : Theme.colSurface1
    border.width: 1

    MouseArea {
        id: focusArea
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
                else hub.toggleFocusDnd();
            }
        }
    }

    // Compact view
    Column {
        id: focusCompact
        visible: !card.expanded
        anchors.fill: parent
        anchors.margins: 20
        spacing: 8

        RowLayout {
            width: parent.width
            Row {
                spacing: 12
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: hub.focusDnd ? "󰂛" : "󰂚"
                    color: hub.focusDnd ? Theme.colMauve : (hub.focusAvailable ? Theme.colTeal : Theme.colPeach)
                    font.family: Theme.uiFont
                    font.pixelSize: 38
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: "Focus"
                    color: Theme.colText
                    font.family: Theme.uiFont
                    font.pixelSize: 32
                    font.bold: true
                }
            }
            Item { Layout.fillWidth: true }
            Text {
                text: hub.focusDnd ? "DND ON" : (hub.focusAvailable ? (hub.focusNotifCount + " notifs") : "Offline")
                color: hub.focusDnd ? Theme.colMauve : Theme.colSubtext
                font.family: Theme.uiFont
                font.pixelSize: 16
                font.bold: true
            }
        }

        Text {
            width: parent.width
            elide: Text.ElideRight
            text: hub.focusAvailable
                ? (hub.focusDnd ? (hub.focusLabel + " · Tap off") : "DND Off · Tap for Priority")
                : hub.focusLabel
            color: Theme.colSubtext
            font.family: Theme.uiFont
            font.pixelSize: 20
        }
    }

    // Expanded view (fills upper part)
    ColumnLayout {
        visible: card.expanded
        anchors.fill: parent
        anchors.margins: 24
        spacing: 18

        RowLayout {
            Layout.fillWidth: true
            Row {
                spacing: 12
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: hub.focusDnd ? "󰂛" : "󰂚"
                    color: hub.focusDnd ? Theme.colMauve : (hub.focusAvailable ? Theme.colTeal : Theme.colPeach)
                    font.family: Theme.uiFont
                    font.pixelSize: 30
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: "Focus & Do Not Disturb"
                    color: Theme.colText
                    font.family: Theme.uiFont
                    font.pixelSize: 24
                    font.bold: true
                }
            }
            Item { Layout.fillWidth: true }
            CollapseButton {
                onClicked: card.holdToggled()
            }
        }

        Item { Layout.fillHeight: true }

        Column {
            Layout.alignment: Qt.AlignHCenter
            spacing: 10
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: hub.focusDnd ? "󰂛" : "󰂚"
                color: hub.focusDnd ? Theme.colMauve : (hub.focusAvailable ? Theme.colTeal : Theme.colPeach)
                font.family: Theme.uiFont
                font.pixelSize: 70
            }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: hub.focusDnd ? "Do Not Disturb On" : "Notifications Active"
                color: Theme.colText
                font.family: Theme.uiFont
                font.pixelSize: 30
                font.bold: true
            }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: hub.focusAvailable
                    ? (hub.focusLabel + " · " + hub.focusNotifCount + " active notifications")
                    : hub.focusLabel
                color: Theme.colSubtext
                font.family: Theme.uiFont
                font.pixelSize: 20
            }
        }

        Item { Layout.fillHeight: true }

        RowLayout {
            Layout.fillWidth: true
            spacing: 14
            Rectangle {
                Layout.fillWidth: true
                height: 52
                radius: 16
                color: toggleFocusArea.pressed ? Theme.colBlue : (hub.focusDnd ? Theme.colMauve : Theme.colPopupBase)
                border.color: hub.focusDnd ? Theme.colMauve : Theme.colSurface1
                border.width: 1
                Text {
                    anchors.centerIn: parent
                    text: hub.focusDnd ? "Disable DND" : "Enable Priority DND"
                    color: (toggleFocusArea.pressed || hub.focusDnd) ? Theme.colDark : Theme.colText
                    font.family: Theme.uiFont
                    font.pixelSize: 20
                    font.bold: true
                }
                MouseArea {
                    id: toggleFocusArea
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
                        if (!_held) hub.toggleFocusDnd();
                    }
                }
            }
            Rectangle {
                implicitWidth: 140
                height: 52
                radius: 16
                color: refreshFocusArea.pressed ? Theme.colBlue : Theme.colPopupBase
                border.color: Theme.colSurface1
                border.width: 1
                Text {
                    anchors.centerIn: parent
                    text: "  Sync"
                    color: refreshFocusArea.pressed ? Theme.colDark : Theme.colSubtext
                    font.family: Theme.uiFont
                    font.pixelSize: 19
                    font.bold: true
                }
                MouseArea {
                    id: refreshFocusArea
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
                        if (!_held) hub.refreshFocus();
                    }
                }
            }
        }
    }
}
