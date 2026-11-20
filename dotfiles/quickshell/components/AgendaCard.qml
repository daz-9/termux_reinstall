import QtQuick
import QtQuick.Layouts

Rectangle {
    required property var hub

    Layout.fillWidth: true
    Layout.fillHeight: true
    implicitHeight: agendaCol.implicitHeight + 44
    radius: 20
    color: Theme.colSurface
    border.color: Theme.colSurface1
    border.width: 1

    Column {
        id: agendaCol
        anchors.fill: parent
        anchors.leftMargin: 24
        anchors.rightMargin: 24
        anchors.topMargin: 22
        anchors.bottomMargin: 22
        spacing: 14

        RowLayout {
            width: parent.width
            Row {
                spacing: 12
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: "󰎚"
                    color: Theme.colMauve
                    font.family: Theme.uiFont
                    font.pixelSize: 28
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: hub.calSelectedDateKey.length > 0 ? "Day Events" : "Agenda"
                    color: Theme.colText
                    font.family: Theme.uiFont
                    font.pixelSize: 24
                    font.bold: true
                }
            }
            Item { Layout.fillWidth: true }
            Rectangle {
                implicitWidth: agendaActionLbl.implicitWidth + 24
                height: 36
                radius: 10
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
                    anchors.fill: parent
                    onClicked: {
                        if (hub.calSelectedDateKey.length > 0) {
                            hub.calSelectedDateKey = "";
                        } else {
                            hub.queryCalendarMonth(hub.calViewYear, hub.calViewMonth);
                        }
                    }
                }
            }
        }

        Repeater {
            model: hub.filteredAgendaEvents()
            delegate: Rectangle {
                required property var modelData
                width: parent.width
                height: 54
                radius: 14
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
                        font.pixelSize: 19
                        font.bold: true
                    }
                    Text {
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                        text: String(modelData.title || "")
                        color: Theme.colText
                        font.family: Theme.uiFont
                        font.pixelSize: 20
                    }
                }
            }
        }

        Rectangle {
            visible: hub.filteredAgendaEvents().length === 0
            width: parent.width
            height: 54
            radius: 14
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
                font.pixelSize: 19
            }
        }
    }
}
