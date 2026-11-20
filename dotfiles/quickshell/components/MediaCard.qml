import QtQuick
import QtQuick.Layouts

Rectangle {
    required property var hub

    Layout.fillWidth: true
    implicitHeight: spotifyCol.implicitHeight + 44
    radius: 20
    color: Theme.colSurface
    border.color: Theme.colSurface1
    border.width: 1

    Column {
        id: spotifyCol
        anchors.fill: parent
        anchors.leftMargin: 24
        anchors.rightMargin: 24
        anchors.topMargin: 22
        anchors.bottomMargin: 22
        spacing: 18

        Row {
            width: parent.width
            spacing: 20
            Rectangle {
                width: 112
                height: 112
                radius: 18
                color: Theme.colSurface1
                Text {
                    anchors.centerIn: parent
                    text: hub.mediaPackage.indexOf("spotify") >= 0 ? "󰓇" : "󰎄"
                    color: hub.mediaPackage.indexOf("spotify") >= 0 ? Theme.colGreen : (hub.mediaPlaying ? Theme.colBlue : Theme.colSubtext)
                    font.family: Theme.uiFont
                    font.pixelSize: 54
                }
                MouseArea {
                    anchors.fill: parent
                    onClicked: hub.refreshMedia()
                }
            }
            Column {
                width: parent.width - 132
                anchors.verticalCenter: parent.verticalCenter
                spacing: 6
                Text {
                    width: parent.width
                    elide: Text.ElideRight
                    text: hub.mediaApp.toUpperCase() + " · " + hub.mediaState
                    color: hub.mediaPlaying ? Theme.colGreen : (hub.mediaAvailable ? Theme.colBlue : Theme.colPeach)
                    font.family: Theme.uiFont
                    font.pixelSize: 16
                    font.bold: true
                }
                Text {
                    width: parent.width
                    elide: Text.ElideRight
                    text: hub.mediaTitle
                    color: Theme.colText
                    font.family: Theme.uiFont
                    font.pixelSize: 27
                    font.bold: true
                }
                Text {
                    width: parent.width
                    elide: Text.ElideRight
                    text: hub.mediaArtist + (hub.mediaAlbum.length > 0 ? " · " + hub.mediaAlbum : "")
                    color: Theme.colSubtext
                    font.family: Theme.uiFont
                    font.pixelSize: 22
                }
            }
        }

        Column {
            width: parent.width
            spacing: 8
            Rectangle {
                width: parent.width
                height: 10
                radius: 5
                color: Theme.colSurface1
                Rectangle {
                    width: hub.mediaPlaying
                        ? parent.width * Math.min(1.0, Math.max(0.08, (hub.mediaPosSec % 240) / 240.0))
                        : (hub.mediaPosSec > 0 ? parent.width * Math.min(1.0, Math.max(0.08, (hub.mediaPosSec % 240) / 240.0)) : 0)
                    height: parent.height
                    radius: 5
                    color: hub.mediaPlaying ? Theme.colGreen : Theme.colBlue
                    Behavior on width { NumberAnimation { duration: 250 } }
                }
            }
            RowLayout {
                width: parent.width
                Text {
                    text: hub.mediaPosText
                    color: Theme.colSubtext
                    font.family: Theme.uiFont
                    font.pixelSize: 19
                    font.bold: true
                }
                Item { Layout.fillWidth: true }
                Text {
                    text: hub.mediaPlaying ? "Playing" : (hub.mediaState === "PAUSED" ? "Paused" : hub.mediaApp)
                    color: Theme.colSubtext
                    font.family: Theme.uiFont
                    font.pixelSize: 19
                    font.bold: true
                }
            }
        }

        Row {
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: 28
            Rectangle {
                anchors.verticalCenter: parent.verticalCenter
                width: 56
                height: 56
                radius: 16
                color: prevArea.pressed ? Theme.colSurface1 : "transparent"
                Text {
                    anchors.centerIn: parent
                    text: "󰒮"
                    color: prevArea.pressed ? Theme.colText : Theme.colSubtext
                    font.family: Theme.uiFont
                    font.pixelSize: 32
                }
                MouseArea {
                    id: prevArea
                    anchors.fill: parent
                    onClicked: hub.sendMediaAction("previous")
                }
            }
            Rectangle {
                width: 62
                height: 62
                radius: 31
                color: playArea.pressed ? Theme.colBlue : (hub.mediaPlaying ? Theme.colGreen : Theme.colBlue)
                scale: playArea.pressed ? 0.92 : 1.0
                Behavior on scale { NumberAnimation { duration: 80 } }
                Text {
                    anchors.centerIn: parent
                    text: hub.mediaPlaying ? "󰏤" : "󰐊"
                    color: Theme.colDark
                    font.family: Theme.uiFont
                    font.pixelSize: 30
                }
                MouseArea {
                    id: playArea
                    anchors.fill: parent
                    onClicked: hub.sendMediaAction("play-pause")
                }
            }
            Rectangle {
                anchors.verticalCenter: parent.verticalCenter
                width: 56
                height: 56
                radius: 16
                color: nextArea.pressed ? Theme.colSurface1 : "transparent"
                Text {
                    anchors.centerIn: parent
                    text: "󰒭"
                    color: nextArea.pressed ? Theme.colText : Theme.colSubtext
                    font.family: Theme.uiFont
                    font.pixelSize: 32
                }
                MouseArea {
                    id: nextArea
                    anchors.fill: parent
                    onClicked: hub.sendMediaAction("next")
                }
            }
        }
    }
}
