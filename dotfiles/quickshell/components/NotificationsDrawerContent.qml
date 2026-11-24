import QtQuick
import QtQuick.Layouts

Item {
    id: notifsRoot
    required property var hub
    property bool open: false
    signal closeRequested()

    anchors.fill: parent
    clip: true

    onOpenChanged: {
        if (!open) notifsBg.swipeX = 0;
    }

    Rectangle {
        id: notifsBg
        property real swipeX: 0
        width: parent.width
        height: parent.height
        x: (notifsRoot.open ? 0 : -parent.width) + swipeX
        radius: 24
        color: Theme.colPopupBase
        border.color: Theme.colSurface1
        border.width: 2

        Behavior on x {
            enabled: !notifsDrag.active
            NumberAnimation { duration: 110; easing.type: Easing.OutCubic }
        }

        DragHandler {
            id: notifsDrag
            target: null
            xAxis.enabled: true
            yAxis.enabled: false
            onTranslationChanged: {
                if (notifsRoot.open) {
                    notifsBg.swipeX = Math.min(0, translation.x);
                }
            }
            onActiveChanged: {
                if (!active && notifsRoot.open) {
                    if (notifsBg.swipeX < -110) {
                        notifsBg.swipeX = 0;
                        notifsRoot.closeRequested();
                    } else {
                        notifsBg.swipeX = 0;
                    }
                }
            }
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 28
            spacing: 18

            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                Row {
                    spacing: 14
                    Layout.fillWidth: true
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: hub.focusDnd ? "󰂛" : "󰂚"
                        color: hub.focusDnd ? Theme.colMauve : Theme.colBlue
                        font.family: Theme.uiFont
                        font.pixelSize: 32
                    }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: "Notifications"
                        color: Theme.colText
                        font.family: Theme.uiFont
                        font.pixelSize: 30
                        font.bold: true
                    }
                    Rectangle {
                        anchors.verticalCenter: parent.verticalCenter
                        implicitWidth: cntLbl.implicitWidth + 18
                        height: 30
                        radius: 15
                        color: Theme.colSurface
                        border.color: Theme.colSurface1
                        border.width: 1
                        Text {
                            id: cntLbl
                            anchors.centerIn: parent
                            text: String(hub.notifItems.length)
                            color: Theme.colBlue
                            font.family: Theme.uiFont
                            font.pixelSize: 16
                            font.bold: true
                        }
                    }
                }

                // Quick DND Toggle Pill
                Rectangle {
                    implicitWidth: dndPillLbl.implicitWidth + 24
                    height: 44
                    radius: 16
                    color: dndPillArea.pressed ? Theme.colBlue : (hub.focusDnd ? Theme.colMauve : Theme.colSurface)
                    border.color: hub.focusDnd ? Theme.colMauve : Theme.colSurface1
                    border.width: 1
                    Text {
                        id: dndPillLbl
                        anchors.centerIn: parent
                        text: hub.focusDnd ? "DND ON" : "DND Off"
                        color: (dndPillArea.pressed || hub.focusDnd) ? Theme.colDark : Theme.colSubtext
                        font.family: Theme.uiFont
                        font.pixelSize: 17
                        font.bold: true
                    }
                    MouseArea {
                        id: dndPillArea
                        anchors.fill: parent
                        anchors.margins: -4
                        onClicked: hub.toggleFocusDnd()
                    }
                }

                // Refresh Pill
                Rectangle {
                    width: 46
                    height: 44
                    radius: 16
                    color: refreshNotifArea.pressed ? Theme.colBlue : Theme.colSurface
                    border.color: Theme.colSurface1
                    border.width: 1
                    Text {
                        anchors.centerIn: parent
                        text: ""
                        color: refreshNotifArea.pressed ? Theme.colDark : Theme.colBlue
                        font.family: Theme.uiFont
                        font.pixelSize: 20
                    }
                    MouseArea {
                        id: refreshNotifArea
                        anchors.fill: parent
                        anchors.margins: -4
                        onClicked: hub.refreshNotifications()
                    }
                }

                // Close Pill
                Rectangle {
                    width: 48
                    height: 48
                    radius: 16
                    color: closeNotifArea.pressed ? Theme.colBlue : Theme.colSurface
                    border.color: Theme.colSurface1
                    border.width: 1
                    Text {
                        anchors.centerIn: parent
                        text: ""
                        color: closeNotifArea.pressed ? Theme.colDark : Theme.colSubtext
                        font.family: Theme.uiFont
                        font.pixelSize: 22
                    }
                    MouseArea {
                        id: closeNotifArea
                        anchors.fill: parent
                        anchors.margins: -4
                        onClicked: notifsRoot.closeRequested()
                    }
                }
            }

            Flickable {
                Layout.fillWidth: true
                Layout.fillHeight: true
                contentWidth: width
                contentHeight: notifListCol.implicitHeight
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                interactive: contentHeight > height

                Column {
                    id: notifListCol
                    width: parent.width
                    spacing: 12

                    Repeater {
                        model: hub.notifItems
                        delegate: Rectangle {
                            required property var modelData
                            width: parent.width
                            implicitHeight: notifCardCol.implicitHeight + 32
                            radius: 18
                            color: notifTapArea.pressed ? Theme.colSurface1 : Theme.colSurface
                            border.color: Theme.colSurface1
                            border.width: 1

                            MouseArea {
                                id: notifTapArea
                                anchors.fill: parent
                                onClicked: hub.openNotificationApp(String(modelData.pkg || ""))
                            }

                            Column {
                                id: notifCardCol
                                anchors.fill: parent
                                anchors.leftMargin: 20
                                anchors.rightMargin: 20
                                anchors.topMargin: 16
                                anchors.bottomMargin: 16
                                spacing: 6

                                RowLayout {
                                    width: parent.width
                                    spacing: 10
                                    Text {
                                        text: String(modelData.app || "Android")
                                        color: Theme.colBlue
                                        font.family: Theme.uiFont
                                        font.pixelSize: 16
                                        font.bold: true
                                    }
                                    Text {
                                        visible: String(modelData.time || "").length > 0
                                        text: "· " + String(modelData.time || "")
                                        color: Theme.colSubtext
                                        font.family: Theme.uiFont
                                        font.pixelSize: 15
                                    }
                                    Item { Layout.fillWidth: true }
                                    Rectangle {
                                        visible: String(modelData.key || "").length > 0
                                        width: 36
                                        height: 36
                                        radius: 14
                                        color: snoozeArea.pressed ? Theme.colBlue : Theme.colPopupBase
                                        border.color: Theme.colSurface1
                                        border.width: 1
                                        Text {
                                            anchors.centerIn: parent
                                            text: "󰅖"
                                            color: snoozeArea.pressed ? Theme.colDark : Theme.colSubtext
                                            font.family: Theme.uiFont
                                            font.pixelSize: 18
                                        }
                                        MouseArea {
                                            id: snoozeArea
                                            anchors.fill: parent
                                            anchors.margins: -5
                                            onClicked: hub.snoozeNotification(String(modelData.key || ""))
                                        }
                                    }
                                }

                                Text {
                                    width: parent.width
                                    elide: Text.ElideRight
                                    text: String(modelData.title || "")
                                    color: Theme.colText
                                    font.family: Theme.uiFont
                                    font.pixelSize: 20
                                    font.bold: true
                                }

                                Text {
                                    visible: String(modelData.body || "").length > 0
                                    width: parent.width
                                    wrapMode: Text.WordWrap
                                    maximumLineCount: 3
                                    elide: Text.ElideRight
                                    text: String(modelData.body || "")
                                    color: Theme.colSubtext
                                    font.family: Theme.uiFont
                                    font.pixelSize: 17
                                }
                            }
                        }
                    }

                    Rectangle {
                        visible: hub.notifItems.length === 0
                        width: parent.width
                        height: 96
                        radius: 18
                        color: Theme.colSurface
                        border.color: Theme.colSurface1
                        border.width: 1
                        Text {
                            anchors.centerIn: parent
                            text: hub.notifProbing ? "Loading notifications..." : "No active notifications"
                            color: Theme.colSubtext
                            font.family: Theme.uiFont
                            font.pixelSize: 20
                        }
                    }
                }
            }
        }
    }
}
