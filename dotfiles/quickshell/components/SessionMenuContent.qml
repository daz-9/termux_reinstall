import QtQuick

Item {
    id: menuRoot
    property bool open: false
    property var items: []
    signal actionTriggered(var cmd)

    anchors.fill: parent
    clip: true

    Rectangle {
        width: parent.width
        height: 330
        y: menuRoot.open ? 0 : 28
        opacity: menuRoot.open ? 1.0 : 0.0
        radius: 22
        color: Theme.colPopupBase
        border.color: Theme.colSurface1
        border.width: 2

        Behavior on y { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }
        Behavior on opacity { NumberAnimation { duration: 130 } }

        Column {
            anchors.fill: parent
            anchors.margins: 18
            spacing: 18

            Repeater {
                model: menuRoot.items
                delegate: Rectangle {
                    required property var modelData
                    width: parent.width
                    height: 86
                    radius: 16
                    color: popArea.pressed ? Theme.colBlue : Theme.colSurface
                    Row {
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.left: parent.left
                        anchors.leftMargin: 20
                        spacing: 16
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: modelData.icon
                            color: popArea.pressed ? Theme.colDark : modelData.color
                            font.family: Theme.uiFont
                            font.pixelSize: 26
                        }
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: modelData.label
                            color: popArea.pressed ? Theme.colDark : Theme.colText
                            font.family: Theme.uiFont
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
                        onClicked: menuRoot.actionTriggered(modelData.cmd)
                    }
                }
            }
        }
    }
}
