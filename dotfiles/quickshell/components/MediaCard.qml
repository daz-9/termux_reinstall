import QtQuick
import QtQuick.Layouts

Rectangle {
    id: card
    required property var hub
    property bool expanded: false
    signal holdToggled()

    readonly property real baseHeight: spotifyCol.implicitHeight + 44
    implicitHeight: baseHeight
    radius: 20
    color: Theme.colSurface
    border.color: card.expanded ? Theme.colBlue : Theme.colSurface1
    border.width: 1

    MouseArea {
        anchors.fill: parent
        pressAndHoldInterval: 380
        onPressAndHold: card.holdToggled()
        onClicked: {
            if (card.expanded) card.holdToggled();
        }
    }

    // Compact view
    Column {
        id: spotifyCol
        visible: !card.expanded
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
                color: artArea.pressed ? Theme.colBlue : Theme.colSurface1
                Text {
                    anchors.centerIn: parent
                    text: hub.mediaPackage.indexOf("spotify") >= 0 ? "󰓇" : "󰎄"
                    color: artArea.pressed ? Theme.colDark : (hub.mediaPackage.indexOf("spotify") >= 0 ? Theme.colGreen : (hub.mediaPlaying ? Theme.colBlue : Theme.colSubtext))
                    font.family: Theme.uiFont
                    font.pixelSize: 54
                }
                MouseArea {
                    id: artArea
                    property bool _held: false
                    anchors.fill: parent
                    pressAndHoldInterval: 380
                    onPressed: _held = false
                    onPressAndHold: {
                        _held = true;
                        card.holdToggled();
                    }
                    onClicked: {
                        if (!_held) hub.refreshMedia();
                    }
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
                color: prevArea.pressed ? Theme.colBlue : "transparent"
                Text {
                    anchors.centerIn: parent
                    text: "󰒮"
                    color: prevArea.pressed ? Theme.colDark : Theme.colSubtext
                    font.family: Theme.uiFont
                    font.pixelSize: 32
                }
                MouseArea {
                    id: prevArea
                    property bool _held: false
                    anchors.fill: parent
                    anchors.margins: -6
                    pressAndHoldInterval: 380
                    onPressed: _held = false
                    onPressAndHold: {
                        _held = true;
                        card.holdToggled();
                    }
                    onClicked: {
                        if (!_held) hub.sendMediaAction("previous");
                    }
                }
            }
            Rectangle {
                width: 62
                height: 62
                radius: 31
                color: playArea.pressed ? Theme.colBlue : (hub.mediaPlaying ? Theme.colGreen : Theme.colBlue)
                Text {
                    anchors.centerIn: parent
                    text: hub.mediaPlaying ? "󰏤" : "󰐊"
                    color: Theme.colDark
                    font.family: Theme.uiFont
                    font.pixelSize: 30
                }
                MouseArea {
                    id: playArea
                    property bool _held: false
                    anchors.fill: parent
                    anchors.margins: -6
                    pressAndHoldInterval: 380
                    onPressed: _held = false
                    onPressAndHold: {
                        _held = true;
                        card.holdToggled();
                    }
                    onClicked: {
                        if (!_held) hub.sendMediaAction("play-pause");
                    }
                }
            }
            Rectangle {
                anchors.verticalCenter: parent.verticalCenter
                width: 56
                height: 56
                radius: 16
                color: nextArea.pressed ? Theme.colBlue : "transparent"
                Text {
                    anchors.centerIn: parent
                    text: "󰒭"
                    color: nextArea.pressed ? Theme.colDark : Theme.colSubtext
                    font.family: Theme.uiFont
                    font.pixelSize: 32
                }
                MouseArea {
                    id: nextArea
                    property bool _held: false
                    anchors.fill: parent
                    anchors.margins: -6
                    pressAndHoldInterval: 380
                    onPressed: _held = false
                    onPressAndHold: {
                        _held = true;
                        card.holdToggled();
                    }
                    onClicked: {
                        if (!_held) hub.sendMediaAction("next");
                    }
                }
            }
        }
    }

    // Expanded view (fills lower part)
    ColumnLayout {
        visible: card.expanded
        anchors.fill: parent
        anchors.margins: 28
        spacing: 24

        RowLayout {
            Layout.fillWidth: true
            Text {
                text: hub.mediaApp.toUpperCase() + " · " + hub.mediaState
                color: hub.mediaPlaying ? Theme.colGreen : (hub.mediaAvailable ? Theme.colBlue : Theme.colPeach)
                font.family: Theme.uiFont
                font.pixelSize: 20
                font.bold: true
            }
            Item { Layout.fillWidth: true }
            CollapseButton {
                onClicked: card.holdToggled()
            }
        }

        Item { Layout.fillHeight: true }

        Rectangle {
            Layout.alignment: Qt.AlignHCenter
            width: 196
            height: 196
            radius: 24
            color: expArtArea.pressed ? Theme.colBlue : Theme.colPopupBase
            border.color: hub.mediaPlaying ? Theme.colGreen : Theme.colSurface1
            border.width: 2
            Text {
                anchors.centerIn: parent
                text: hub.mediaPackage.indexOf("spotify") >= 0 ? "󰓇" : "󰎄"
                color: expArtArea.pressed ? Theme.colDark : (hub.mediaPackage.indexOf("spotify") >= 0 ? Theme.colGreen : (hub.mediaPlaying ? Theme.colBlue : Theme.colSubtext))
                font.family: Theme.uiFont
                font.pixelSize: 96
            }
            MouseArea {
                id: expArtArea
                property bool _held: false
                anchors.fill: parent
                pressAndHoldInterval: 380
                onPressed: _held = false
                onPressAndHold: {
                    _held = true;
                    card.holdToggled();
                }
                onClicked: {
                    if (!_held) hub.refreshMedia();
                }
            }
        }

        Column {
            Layout.fillWidth: true
            spacing: 10
            Text {
                width: parent.width
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
                maximumLineCount: 2
                elide: Text.ElideRight
                text: hub.mediaTitle
                color: Theme.colText
                font.family: Theme.uiFont
                font.pixelSize: 34
                font.bold: true
            }
            Text {
                width: parent.width
                horizontalAlignment: Text.AlignHCenter
                elide: Text.ElideRight
                text: hub.mediaArtist
                color: Theme.colSubtext
                font.family: Theme.uiFont
                font.pixelSize: 24
            }
            Text {
                visible: hub.mediaAlbum.length > 0
                width: parent.width
                horizontalAlignment: Text.AlignHCenter
                elide: Text.ElideRight
                text: hub.mediaAlbum
                color: Theme.colBlue
                font.family: Theme.uiFont
                font.pixelSize: 20
            }
        }

        Column {
            Layout.fillWidth: true
            spacing: 10
            Rectangle {
                width: parent.width
                height: 14
                radius: 7
                color: Theme.colSurface1
                Rectangle {
                    width: hub.mediaPlaying
                        ? parent.width * Math.min(1.0, Math.max(0.08, (hub.mediaPosSec % 240) / 240.0))
                        : (hub.mediaPosSec > 0 ? parent.width * Math.min(1.0, Math.max(0.08, (hub.mediaPosSec % 240) / 240.0)) : 0)
                    height: parent.height
                    radius: 7
                    color: hub.mediaPlaying ? Theme.colGreen : Theme.colBlue
                }
            }
            RowLayout {
                width: parent.width
                Text {
                    text: hub.mediaPosText
                    color: Theme.colSubtext
                    font.family: Theme.uiFont
                    font.pixelSize: 20
                    font.bold: true
                }
                Item { Layout.fillWidth: true }
                Text {
                    text: hub.mediaPlaying ? "Playing" : (hub.mediaState === "PAUSED" ? "Paused" : hub.mediaApp)
                    color: Theme.colSubtext
                    font.family: Theme.uiFont
                    font.pixelSize: 20
                    font.bold: true
                }
            }
        }

        Row {
            Layout.alignment: Qt.AlignHCenter
            spacing: 38
            Rectangle {
                anchors.verticalCenter: parent.verticalCenter
                width: 72
                height: 72
                radius: 18
                color: expPrevArea.pressed ? Theme.colBlue : Theme.colPopupBase
                border.color: Theme.colSurface1
                border.width: 1
                Text {
                    anchors.centerIn: parent
                    text: "󰒮"
                    color: expPrevArea.pressed ? Theme.colDark : Theme.colText
                    font.family: Theme.uiFont
                    font.pixelSize: 38
                }
                MouseArea {
                    id: expPrevArea
                    property bool _held: false
                    anchors.fill: parent
                    anchors.margins: -6
                    pressAndHoldInterval: 380
                    onPressed: _held = false
                    onPressAndHold: {
                        _held = true;
                        card.holdToggled();
                    }
                    onClicked: {
                        if (!_held) hub.sendMediaAction("previous");
                    }
                }
            }
            Rectangle {
                width: 86
                height: 86
                radius: 43
                color: expPlayArea.pressed ? Theme.colBlue : (hub.mediaPlaying ? Theme.colGreen : Theme.colBlue)
                Text {
                    anchors.centerIn: parent
                    text: hub.mediaPlaying ? "󰏤" : "󰐊"
                    color: Theme.colDark
                    font.family: Theme.uiFont
                    font.pixelSize: 40
                }
                MouseArea {
                    id: expPlayArea
                    property bool _held: false
                    anchors.fill: parent
                    anchors.margins: -6
                    pressAndHoldInterval: 380
                    onPressed: _held = false
                    onPressAndHold: {
                        _held = true;
                        card.holdToggled();
                    }
                    onClicked: {
                        if (!_held) hub.sendMediaAction("play-pause");
                    }
                }
            }
            Rectangle {
                anchors.verticalCenter: parent.verticalCenter
                width: 72
                height: 72
                radius: 18
                color: expNextArea.pressed ? Theme.colBlue : Theme.colPopupBase
                border.color: Theme.colSurface1
                border.width: 1
                Text {
                    anchors.centerIn: parent
                    text: "󰒭"
                    color: expNextArea.pressed ? Theme.colDark : Theme.colText
                    font.family: Theme.uiFont
                    font.pixelSize: 38
                }
                MouseArea {
                    id: expNextArea
                    property bool _held: false
                    anchors.fill: parent
                    anchors.margins: -6
                    pressAndHoldInterval: 380
                    onPressed: _held = false
                    onPressAndHold: {
                        _held = true;
                        card.holdToggled();
                    }
                    onClicked: {
                        if (!_held) hub.sendMediaAction("next");
                    }
                }
            }
        }

        Item { Layout.fillHeight: true }
    }
}
