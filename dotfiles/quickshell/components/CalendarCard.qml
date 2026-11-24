import QtQuick
import QtQuick.Layouts

Rectangle {
    id: card
    required property var hub
    property bool expanded: false
    signal holdToggled()

    readonly property var visibleEvents: hub.filteredAgendaEvents()
    readonly property real baseHeight: calHeaderRow.implicitHeight + 14 + calGrid.implicitHeight + 44
    readonly property bool swiping: calSwipe.active
    property real swipeX: 0
    property real _rawSwipeX: 0
    implicitHeight: baseHeight
    radius: 20
    clip: true
    color: Theme.colSurface
    border.color: card.expanded ? Theme.colBlue : Theme.colSurface1
    border.width: 1

    Behavior on swipeX {
        enabled: !calSwipe.active
        NumberAnimation { duration: 100; easing.type: Easing.OutCubic }
    }

    DragHandler {
        id: calSwipe
        target: null
        xAxis.enabled: true
        yAxis.enabled: false
        grabPermissions: PointerHandler.CanTakeOverFromItems | PointerHandler.CanTakeOverFromHandlersOfDifferentType | PointerHandler.CanTakeOverFromHandlersOfSameType
        onTranslationChanged: {
            card._rawSwipeX = translation.x;
            card.swipeX = Math.max(-48, Math.min(48, translation.x));
        }
        onActiveChanged: {
            if (!active) {
                if (card._rawSwipeX <= -56) {
                    hub.stepCalendarMonth(1);
                } else if (card._rawSwipeX >= 56) {
                    hub.stepCalendarMonth(-1);
                }
                card._rawSwipeX = 0;
                card.swipeX = 0;
            }
        }
    }

    MouseArea {
        anchors.fill: parent
        pressAndHoldInterval: 380
        onPressAndHold: card.holdToggled()
        onClicked: {
            if (card.expanded) card.holdToggled();
        }
    }

    ColumnLayout {
        id: calCol
        anchors.fill: parent
        anchors.leftMargin: 24
        anchors.rightMargin: 24
        anchors.topMargin: 22
        anchors.bottomMargin: 22
        spacing: 14

        RowLayout {
            id: calHeaderRow
            Layout.fillWidth: true
            spacing: 10
            Row {
                spacing: 12
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: "󰃭"
                    color: Theme.colBlue
                    font.family: Theme.uiFont
                    font.pixelSize: 28
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: hub.calMonthTitle
                    color: titleArea.pressed ? Theme.colBlue : Theme.colText
                    font.family: Theme.uiFont
                    font.pixelSize: 24
                    font.bold: true
                    MouseArea {
                        id: titleArea
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
                            if (!_held) hub.resetCalendarToday();
                        }
                    }
                }
            }
            Item { Layout.fillWidth: true }
            CollapseButton {
                visible: card.expanded
                onClicked: card.holdToggled()
            }
            Row {
                spacing: 10
                Rectangle {
                    width: 44
                    height: 44
                    radius: 16
                    color: prevMonthArea.pressed ? Theme.colBlue : Theme.colPopupBase
                    border.color: Theme.colSurface1
                    border.width: 1
                    Text {
                        anchors.centerIn: parent
                        text: "󰅁"
                        color: prevMonthArea.pressed ? Theme.colDark : Theme.colSubtext
                        font.family: Theme.uiFont
                        font.pixelSize: 22
                    }
                    MouseArea {
                        id: prevMonthArea
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
                            if (!_held) hub.stepCalendarMonth(-1);
                        }
                    }
                }
                Rectangle {
                    width: 44
                    height: 44
                    radius: 16
                    color: nextMonthArea.pressed ? Theme.colBlue : Theme.colPopupBase
                    border.color: Theme.colSurface1
                    border.width: 1
                    Text {
                        anchors.centerIn: parent
                        text: "󰅂"
                        color: nextMonthArea.pressed ? Theme.colDark : Theme.colSubtext
                        font.family: Theme.uiFont
                        font.pixelSize: 22
                    }
                    MouseArea {
                        id: nextMonthArea
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
                            if (!_held) hub.stepCalendarMonth(1);
                        }
                    }
                }
            }
        }

        GridLayout {
            id: calGrid
            Layout.fillWidth: true
            columns: 7
            columnSpacing: 6
            rowSpacing: 8
            transform: Translate { x: card.swipeX }

            Repeater {
                model: hub.calendarHeaders
                delegate: Item {
                    required property string modelData
                    Layout.fillWidth: true
                    implicitHeight: 42
                    Text {
                        anchors.centerIn: parent
                        text: modelData
                        color: Theme.colSubtext
                        font.family: Theme.uiFont
                        font.pixelSize: 21
                        font.bold: true
                    }
                }
            }

            Repeater {
                model: hub.calGridCells
                delegate: Rectangle {
                    required property var modelData
                    readonly property bool selected: hub.calSelectedDateKey.length > 0 && hub.calSelectedDateKey === modelData.key
                    Layout.fillWidth: true
                    implicitHeight: 48
                    radius: 14
                    color: modelData.cls === "today"
                        ? Theme.colBlue
                        : (selected ? Theme.colSurface1 : (dayArea.pressed && modelData.cls !== "muted" ? Theme.colPopupBase : "transparent"))
                    border.color: selected && modelData.cls !== "today" ? Theme.colBlue : "transparent"
                    border.width: selected && modelData.cls !== "today" ? 2 : 0

                    Column {
                        anchors.centerIn: parent
                        spacing: 2
                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: modelData.d
                            color: modelData.cls === "today"
                                ? Theme.colDark
                                : (modelData.cls === "muted"
                                    ? Theme.colSurface1
                                    : (modelData.cls === "wknd" ? Theme.colSubtext : Theme.colText))
                            font.family: Theme.uiFont
                            font.pixelSize: 22
                            font.bold: modelData.cls === "today" || selected
                        }
                        Rectangle {
                            visible: modelData.hasEvent
                            anchors.horizontalCenter: parent.horizontalCenter
                            width: 6
                            height: 6
                            radius: 3
                            color: modelData.cls === "today" ? Theme.colDark : Theme.colMauve
                        }
                    }

                    MouseArea {
                        id: dayArea
                        property bool _held: false
                        anchors.fill: parent
                        anchors.leftMargin: -3
                        anchors.rightMargin: -3
                        anchors.topMargin: -4
                        anchors.bottomMargin: -4
                        pressAndHoldInterval: 380
                        onPressed: _held = false
                        onPressAndHold: {
                            _held = true;
                            card.holdToggled();
                        }
                        onClicked: {
                            if (!_held) hub.toggleCalendarDay(modelData);
                        }
                    }
                }
            }
        }

        // Merged Agenda (only visible when Calendar is expanded)
        Rectangle {
            visible: card.expanded
            Layout.fillWidth: true
            height: 2
            radius: 1
            color: Theme.colSurface1
        }

        RowLayout {
            visible: card.expanded
            Layout.fillWidth: true
            Row {
                spacing: 12
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: "󰎚"
                    color: Theme.colMauve
                    font.family: Theme.uiFont
                    font.pixelSize: 26
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: hub.calSelectedDateKey.length > 0 ? "Day Events" : "Agenda"
                    color: Theme.colText
                    font.family: Theme.uiFont
                    font.pixelSize: 22
                    font.bold: true
                }
            }
            Item { Layout.fillWidth: true }
            Rectangle {
                implicitWidth: agendaActionLbl.implicitWidth + 24
                height: 42
                radius: 16
                color: agendaActionArea.pressed ? Theme.colBlue : Theme.colPopupBase
                border.color: Theme.colSurface1
                border.width: 1
                Text {
                    id: agendaActionLbl
                    anchors.centerIn: parent
                    text: hub.calSelectedDateKey.length > 0 ? "Show Upcoming" : "Refresh"
                    color: agendaActionArea.pressed ? Theme.colDark : Theme.colSubtext
                    font.family: Theme.uiFont
                    font.pixelSize: 17
                    font.bold: true
                }
                MouseArea {
                    id: agendaActionArea
                    property bool _held: false
                    anchors.fill: parent
                    anchors.margins: -5
                    pressAndHoldInterval: 380
                    onPressed: _held = false
                    onPressAndHold: {
                        _held = true;
                        card.holdToggled();
                    }
                    onClicked: {
                        if (!_held) {
                            if (hub.calSelectedDateKey.length > 0) {
                                hub.calSelectedDateKey = "";
                            } else {
                                hub.queryCalendarMonth(hub.calViewYear, hub.calViewMonth);
                            }
                        }
                    }
                }
            }
        }

        Flickable {
            visible: card.expanded
            Layout.fillWidth: true
            Layout.fillHeight: true
            contentWidth: width
            contentHeight: agendaListCol.implicitHeight
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            interactive: contentHeight > height

            Column {
                id: agendaListCol
                width: parent.width
                spacing: 10

                Repeater {
                    model: card.expanded ? card.visibleEvents : []
                    delegate: Rectangle {
                        required property var modelData
                        width: parent.width
                        height: 52
                        radius: 16
                        color: Theme.colPopupBase
                        border.color: Theme.colSurface1
                        border.width: 1
                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 16
                            anchors.rightMargin: 16
                            spacing: 14
                            Text {
                                text: hub.formatEventWhen(modelData)
                                color: hub.eventColor(modelData)
                                font.family: Theme.uiFont
                                font.pixelSize: 18
                                font.bold: true
                            }
                            Text {
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                                text: String(modelData.title || "")
                                color: Theme.colText
                                font.family: Theme.uiFont
                                font.pixelSize: 19
                            }
                        }
                    }
                }

                Rectangle {
                    visible: card.visibleEvents.length === 0
                    width: parent.width
                    height: 52
                    radius: 16
                    color: Theme.colPopupBase
                    border.color: Theme.colSurface1
                    border.width: 1
                    Text {
                        anchors.centerIn: parent
                        text: hub.calendarOk
                            ? (hub.calSelectedDateKey.length > 0 ? "No events on selected day" : "No upcoming events")
                            : "Start Shizuku to sync Android Calendar"
                        color: Theme.colSubtext
                        font.family: Theme.uiFont
                        font.pixelSize: 18
                    }
                }
            }
        }
    }
}
