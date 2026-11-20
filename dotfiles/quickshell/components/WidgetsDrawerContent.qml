import QtQuick
import QtQuick.Layouts

Item {
    id: drawerRoot
    required property var hub
    property bool open: false
    signal closeRequested()

    anchors.fill: parent
    clip: true

    Rectangle {
        id: drawerBg
        width: parent.width
        height: parent.height
        x: drawerRoot.open ? 0 : -44
        opacity: drawerRoot.open ? 1.0 : 0.0
        radius: 24
        color: Theme.colPopupBase
        border.color: Theme.colSurface1
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

                RowLayout {
                    Layout.fillWidth: true
                    Row {
                        spacing: 14
                        Layout.fillWidth: true
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: "󰀻"
                            color: Theme.colBlue
                            font.family: Theme.uiFont
                            font.pixelSize: 34
                        }
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: "Widgets"
                            color: Theme.colText
                            font.family: Theme.uiFont
                            font.pixelSize: 30
                            font.bold: true
                        }
                    }
                    Rectangle {
                        width: 48
                        height: 48
                        radius: 16
                        color: closeBtnArea.pressed ? Theme.colBlue : Theme.colSurface
                        border.color: Theme.colSurface1
                        border.width: 1
                        Text {
                            anchors.centerIn: parent
                            text: ""
                            color: closeBtnArea.pressed ? Theme.colDark : Theme.colSubtext
                            font.family: Theme.uiFont
                            font.pixelSize: 22
                        }
                        MouseArea {
                            id: closeBtnArea
                            anchors.fill: parent
                            onClicked: drawerRoot.closeRequested()
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 18

                    WeatherCard { hub: drawerRoot.hub }
                    FocusCard { hub: drawerRoot.hub }
                }

                AndroidStatusCard { hub: drawerRoot.hub }
                MediaCard { hub: drawerRoot.hub }
                CalendarCard { hub: drawerRoot.hub }
                AgendaCard { hub: drawerRoot.hub }
            }
        }
    }
}
