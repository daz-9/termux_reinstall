import QtQuick
import QtQuick.Layouts

Rectangle {
    id: card
    required property var hub
    property bool expanded: false
    signal holdToggled()

    readonly property real baseHeight: weatherCompact.implicitHeight + 40
    implicitHeight: baseHeight
    radius: 20
    color: weatherCardArea.pressed ? Theme.colSurface1 : Theme.colSurface
    border.color: card.expanded ? Theme.colBlue : Theme.colSurface1
    border.width: 1

    MouseArea {
        id: weatherCardArea
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
                else hub.refreshWeather();
            }
        }
    }

    // Compact view
    Column {
        id: weatherCompact
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

    // Expanded view (fills upper part with current summary + next 3 days)
    ColumnLayout {
        visible: card.expanded
        anchors.fill: parent
        anchors.margins: 22
        spacing: 14

        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            Text {
                text: hub.weatherIcon
                color: hub.weatherColor(hub.weatherTone)
                font.family: Theme.uiFont
                font.pixelSize: 30
            }
            Text {
                Layout.fillWidth: true
                elide: Text.ElideRight
                text: "Weather · " + hub.weatherLocation
                color: Theme.colText
                font.family: Theme.uiFont
                font.pixelSize: 23
                font.bold: true
            }
            CollapseButton {
                onClicked: card.holdToggled()
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 18
            Text {
                text: hub.weatherIcon
                color: hub.weatherColor(hub.weatherTone)
                font.family: Theme.uiFont
                font.pixelSize: 52
            }
            Text {
                text: hub.weatherTemp
                color: Theme.colText
                font.family: Theme.uiFont
                font.pixelSize: 44
                font.bold: true
            }
            Text {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                maximumLineCount: 2
                elide: Text.ElideRight
                text: hub.weatherDetail
                color: Theme.colSubtext
                font.family: Theme.uiFont
                font.pixelSize: 19
            }
        }

        Text {
            text: "Next 3 Days"
            color: Theme.colSubtext
            font.family: Theme.uiFont
            font.pixelSize: 16
            font.bold: true
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 12

            Repeater {
                model: hub.weatherForecast
                delegate: Rectangle {
                    required property var modelData
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    radius: 16
                    color: Theme.colPopupBase
                    border.color: Theme.colSurface1
                    border.width: 1

                    Column {
                        anchors.centerIn: parent
                        width: parent.width - 20
                        spacing: 8

                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: String(modelData.day || "") + (modelData.date ? (" · " + modelData.date) : "")
                            color: Theme.colBlue
                            font.family: Theme.uiFont
                            font.pixelSize: 17
                            font.bold: true
                        }
                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: String(modelData.icon || "󰖐")
                            color: hub.weatherColor(String(modelData.tone || "subtext"))
                            font.family: Theme.uiFont
                            font.pixelSize: 38
                        }
                        Row {
                            anchors.horizontalCenter: parent.horizontalCenter
                            spacing: 6
                            Text {
                                text: String(modelData.hi || "--°")
                                color: Theme.colText
                                font.family: Theme.uiFont
                                font.pixelSize: 22
                                font.bold: true
                            }
                            Text {
                                text: "/ " + String(modelData.lo || "--°")
                                color: Theme.colSubtext
                                font.family: Theme.uiFont
                                font.pixelSize: 19
                            }
                        }
                        Text {
                            width: parent.width
                            horizontalAlignment: Text.AlignHCenter
                            elide: Text.ElideRight
                            text: String(modelData.cond || "")
                            color: Theme.colSubtext
                            font.family: Theme.uiFont
                            font.pixelSize: 15
                        }
                    }
                }
            }

            Rectangle {
                visible: hub.weatherForecast.length === 0
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: 16
                color: Theme.colPopupBase
                border.color: Theme.colSurface1
                border.width: 1
                Text {
                    anchors.centerIn: parent
                    text: "3-day forecast unavailable — tap Refresh"
                    color: Theme.colSubtext
                    font.family: Theme.uiFont
                    font.pixelSize: 18
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            height: 48
            radius: 16
            color: refreshWeatherArea.pressed ? Theme.colBlue : Theme.colPopupBase
            border.color: Theme.colSurface1
            border.width: 1
            Text {
                anchors.centerIn: parent
                text: "  Refresh Weather"
                color: refreshWeatherArea.pressed ? Theme.colDark : Theme.colText
                font.family: Theme.uiFont
                font.pixelSize: 18
                font.bold: true
            }
            MouseArea {
                id: refreshWeatherArea
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
                    if (!_held) hub.refreshWeather();
                }
            }
        }
    }
}
