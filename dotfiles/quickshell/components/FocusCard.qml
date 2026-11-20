import QtQuick
import QtQuick.Layouts

Rectangle {
    required property var hub

    Layout.fillWidth: true
    implicitHeight: focusCol.implicitHeight + 40
    radius: 20
    color: focusArea.pressed ? Theme.colSurface1 : Theme.colSurface
    border.color: hub.focusDnd ? Theme.colMauve : Theme.colSurface1
    border.width: 1

    Column {
        id: focusCol
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

    MouseArea {
        id: focusArea
        anchors.fill: parent
        onClicked: hub.toggleFocusDnd()
    }
}
