import QtQuick
import QtQuick.Layouts

Rectangle {
    required property var hub

    Layout.fillWidth: true
    implicitHeight: calCol.implicitHeight + 44
    radius: 20
    color: Theme.colSurface
    border.color: Theme.colSurface1
    border.width: 1

    Column {
        id: calCol
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
                        anchors.fill: parent
                        onClicked: hub.resetCalendarToday()
                    }
                }
            }
            Item { Layout.fillWidth: true }
            Row {
                spacing: 8
                Rectangle {
                    width: 42
                    height: 42
                    radius: 12
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
                        anchors.fill: parent
                        onClicked: hub.stepCalendarMonth(-1)
                    }
                }
                Rectangle {
                    width: 42
                    height: 42
                    radius: 12
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
                        anchors.fill: parent
                        onClicked: hub.stepCalendarMonth(1)
                    }
                }
            }
        }

        GridLayout {
            width: parent.width
            columns: 7
            columnSpacing: 6
            rowSpacing: 8

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
                        anchors.fill: parent
                        onClicked: hub.toggleCalendarDay(modelData)
                    }
                }
            }
        }
    }
}
