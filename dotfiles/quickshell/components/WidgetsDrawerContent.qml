import QtQuick
import QtQuick.Layouts

Item {
    id: drawerRoot
    required property var hub
    property bool open: false
    property string upperExpanded: ""
    property string lowerExpanded: ""
    signal closeRequested()

    anchors.fill: parent
    clip: true

    onOpenChanged: {
        if (!open) {
            upperExpanded = "";
            lowerExpanded = "";
            drawerBg.swipeX = 0;
        }
    }

    function toggleUpper(id) {
        upperExpanded = (upperExpanded === id ? "" : id);
    }

    function toggleLower(id) {
        lowerExpanded = (lowerExpanded === id ? "" : id);
    }

    Rectangle {
        id: drawerBg
        property real swipeX: 0
        width: parent.width
        height: parent.height
        x: (drawerRoot.open ? 0 : -parent.width) + swipeX
        radius: 24
        color: Theme.colPopupBase
        border.color: Theme.colSurface1
        border.width: 2

        Behavior on x {
            enabled: !drawerDrag.active
            NumberAnimation { duration: 110; easing.type: Easing.OutCubic }
        }

        DragHandler {
            id: drawerDrag
            target: null
            xAxis.enabled: true
            yAxis.enabled: false
            function startsOnCalendar() {
                if (!calendarCard.visible) return false;
                const pt = calendarCard.mapFromItem(drawerBg, centroid.pressPosition.x, centroid.pressPosition.y);
                return pt.x >= 0 && pt.x <= calendarCard.width && pt.y >= 0 && pt.y <= calendarCard.height;
            }
            onTranslationChanged: {
                if (drawerRoot.open && !calendarCard.swiping && !startsOnCalendar()) {
                    drawerBg.swipeX = Math.min(0, translation.x);
                } else {
                    drawerBg.swipeX = 0;
                }
            }
            onActiveChanged: {
                if (!active && drawerRoot.open) {
                    if (!calendarCard.swiping && !startsOnCalendar() && drawerBg.swipeX < -110) {
                        drawerBg.swipeX = 0;
                        drawerRoot.closeRequested();
                    } else {
                        drawerBg.swipeX = 0;
                    }
                }
            }
        }

        MouseArea {
            anchors.fill: parent
            enabled: drawerRoot.upperExpanded.length > 0 || drawerRoot.lowerExpanded.length > 0
            onClicked: {
                drawerRoot.upperExpanded = "";
                drawerRoot.lowerExpanded = "";
            }
        }

        Flickable {
            id: drawerFlick
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
                spacing: 18

                RowLayout {
                    id: headerRow
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

                // Upper Part: Weather, Focus/DND, Termux:API & Shizuku, Wi-Fi
                Item {
                    id: upperPart
                    Layout.fillWidth: true
                    readonly property real row1H: Math.max(weatherCard.baseHeight, focusCard.baseHeight)
                    readonly property real naturalHeight: row1H + 16 + androidCard.baseHeight + 16 + wifiCard.baseHeight
                    readonly property real baseHeight: Math.max(naturalHeight, drawerFlick.height - headerRow.implicitHeight - lowerPart.naturalHeight - 36)
                    readonly property real wifiFillHeight: Math.max(wifiCard.baseHeight, baseHeight - (row1H + 16 + androidCard.baseHeight + 16))
                    implicitHeight: baseHeight
                    state: drawerRoot.upperExpanded

                    WeatherCard {
                        id: weatherCard
                        hub: drawerRoot.hub
                        expanded: drawerRoot.upperExpanded === "weather"
                        x: 0
                        y: 0
                        width: (upperPart.width - 16) / 2
                        height: upperPart.row1H
                        onHoldToggled: drawerRoot.toggleUpper("weather")
                    }

                    FocusCard {
                        id: focusCard
                        hub: drawerRoot.hub
                        expanded: drawerRoot.upperExpanded === "focus"
                        x: (upperPart.width + 16) / 2
                        y: 0
                        width: (upperPart.width - 16) / 2
                        height: upperPart.row1H
                        onHoldToggled: drawerRoot.toggleUpper("focus")
                    }

                    AndroidStatusCard {
                        id: androidCard
                        hub: drawerRoot.hub
                        expanded: drawerRoot.upperExpanded === "android"
                        x: 0
                        y: upperPart.row1H + 16
                        width: upperPart.width
                        height: androidCard.baseHeight
                        onHoldToggled: drawerRoot.toggleUpper("android")
                    }

                    WifiCard {
                        id: wifiCard
                        hub: drawerRoot.hub
                        expanded: drawerRoot.upperExpanded === "wifi"
                        x: 0
                        y: upperPart.row1H + 16 + androidCard.baseHeight + 16
                        width: upperPart.width
                        height: upperPart.wifiFillHeight
                        onHoldToggled: drawerRoot.toggleUpper("wifi")
                    }

                    states: [
                        State {
                            name: "weather"
                            PropertyChanges { target: weatherCard; x: 0; y: 0; width: upperPart.width; height: upperPart.baseHeight; z: 10 }
                            PropertyChanges { target: focusCard; visible: false }
                            PropertyChanges { target: androidCard; visible: false }
                            PropertyChanges { target: wifiCard; visible: false }
                        },
                        State {
                            name: "focus"
                            PropertyChanges { target: focusCard; x: 0; y: 0; width: upperPart.width; height: upperPart.baseHeight; z: 10 }
                            PropertyChanges { target: weatherCard; visible: false }
                            PropertyChanges { target: androidCard; visible: false }
                            PropertyChanges { target: wifiCard; visible: false }
                        },
                        State {
                            name: "android"
                            PropertyChanges { target: androidCard; x: 0; y: 0; width: upperPart.width; height: upperPart.baseHeight; z: 10 }
                            PropertyChanges { target: weatherCard; visible: false }
                            PropertyChanges { target: focusCard; visible: false }
                            PropertyChanges { target: wifiCard; visible: false }
                        },
                        State {
                            name: "wifi"
                            PropertyChanges { target: wifiCard; x: 0; y: 0; width: upperPart.width; height: upperPart.baseHeight; z: 10 }
                            PropertyChanges { target: weatherCard; visible: false }
                            PropertyChanges { target: focusCard; visible: false }
                            PropertyChanges { target: androidCard; visible: false }
                        }
                    ]

                    transitions: Transition {
                        NumberAnimation { properties: "x,y,width,height"; duration: 100; easing.type: Easing.OutCubic }
                    }
                }

                // Lower Part: Media & Calendar (Agenda merged into Calendar when expanded)
                Item {
                    id: lowerPart
                    Layout.fillWidth: true
                    readonly property real naturalHeight: mediaCard.baseHeight + 16 + calendarCard.baseHeight
                    readonly property real availHeight: naturalHeight
                    implicitHeight: naturalHeight
                    state: drawerRoot.lowerExpanded

                    MediaCard {
                        id: mediaCard
                        hub: drawerRoot.hub
                        expanded: drawerRoot.lowerExpanded === "media"
                        x: 0
                        y: 0
                        width: lowerPart.width
                        height: mediaCard.baseHeight
                        onHoldToggled: drawerRoot.toggleLower("media")
                    }

                    CalendarCard {
                        id: calendarCard
                        hub: drawerRoot.hub
                        expanded: drawerRoot.lowerExpanded === "calendar"
                        x: 0
                        y: mediaCard.baseHeight + 16
                        width: lowerPart.width
                        height: calendarCard.baseHeight
                        onHoldToggled: drawerRoot.toggleLower("calendar")
                    }

                    states: [
                        State {
                            name: "media"
                            PropertyChanges { target: mediaCard; x: 0; y: 0; width: lowerPart.width; height: lowerPart.availHeight; z: 10 }
                            PropertyChanges { target: calendarCard; visible: false }
                        },
                        State {
                            name: "calendar"
                            PropertyChanges { target: calendarCard; x: 0; y: 0; width: lowerPart.width; height: lowerPart.availHeight; z: 10 }
                            PropertyChanges { target: mediaCard; visible: false }
                        }
                    ]

                    transitions: Transition {
                        NumberAnimation { properties: "x,y,width,height"; duration: 100; easing.type: Easing.OutCubic }
                    }
                }
            }
        }
    }
}
