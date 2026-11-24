import QtQuick

Item {
    id: menuRoot
    property bool open: false
    property var items: []
    signal actionTriggered(var cmd)
    signal closeRequested()

    anchors.fill: parent
    clip: true

    onOpenChanged: {
        if (!open) menuCard.swipeY = 0;
    }

    Rectangle {
        id: menuCard
        property real swipeY: 0
        width: parent.width
        height: 330
        y: (menuRoot.open ? 0 : parent.height) + swipeY
        radius: 22
        color: Theme.colPopupBase
        border.color: Theme.colSurface1
        border.width: 2

        Behavior on y {
            enabled: !sessionDrag.active
            NumberAnimation { duration: 140; easing.type: Easing.OutCubic }
        }

        DragHandler {
            id: sessionDrag
            target: null
            xAxis.enabled: false
            yAxis.enabled: true
            onTranslationChanged: {
                if (menuRoot.open) {
                    menuCard.swipeY = Math.max(0, translation.y);
                }
            }
            onActiveChanged: {
                if (!active && menuRoot.open) {
                    if (menuCard.swipeY > 64) {
                        menuCard.swipeY = 0;
                        menuRoot.closeRequested();
                    } else {
                        menuCard.swipeY = 0;
                    }
                }
            }
        }

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
