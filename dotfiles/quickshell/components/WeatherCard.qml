import QtQuick
import QtQuick.Layouts

Rectangle {
    required property var hub

    Layout.fillWidth: true
    implicitHeight: weatherCol.implicitHeight + 40
    radius: 20
    color: weatherCardArea.pressed ? Theme.colSurface1 : Theme.colSurface
    border.color: Theme.colSurface1
    border.width: 1

    Column {
        id: weatherCol
        anchors.fill: parent
        anchors.margins: 20
        spacing: 8

        RowLayout {
            width: parent.width
            Row {
                spacing: 12
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: hub.weatherIcon
                    color: hub.weatherColor(hub.weatherTone)
                    font.family: Theme.uiFont
                    font.pixelSize: 38
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: hub.weatherTemp
                    color: Theme.colText
                    font.family: Theme.uiFont
                    font.pixelSize: 32
                    font.bold: true
                }
            }
            Item { Layout.fillWidth: true }
            Text {
                text: hub.weatherLocation
                color: Theme.colBlue
                font.family: Theme.uiFont
                font.pixelSize: 16
                font.bold: true
            }
        }

        Text {
            width: parent.width
            elide: Text.ElideRight
            text: hub.weatherDetail
            color: Theme.colSubtext
            font.family: Theme.uiFont
            font.pixelSize: 20
        }
    }

    MouseArea {
        id: weatherCardArea
        anchors.fill: parent
        onClicked: hub.refreshWeather()
    }
}
