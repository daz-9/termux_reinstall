                        // Live Android Calendar Agenda
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            implicitHeight: agendaCol.implicitHeight + 44
                            radius: 20
                            color: root.colSurface
                            border.color: root.colSurface1
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
                                            text: "\U000f039a"
                                            color: root.colMauve
                                            font.family: root.uiFont
                                            font.pixelSize: 28
                                        }
                                        Text {
                                            anchors.verticalCenter: parent.verticalCenter
                                            text: root.calSelectedDateKey.length > 0 ? "Day Events" : "Agenda"
                                            color: root.colText
                                            font.family: root.uiFont
                                            font.pixelSize: 24
                                            font.bold: true
                                        }
                                    }
                                    Item { Layout.fillWidth: true }
                                    Rectangle {
                                        implicitWidth: agendaActionLbl.implicitWidth + 24
                                        height: 36
                                        radius: 10
                                        color: agendaActionArea.pressed ? root.colBlue : root.colPopupBase
                                        border.color: root.colSurface1
                                        border.width: 1
                                        Text {
                                            id: agendaActionLbl
                                            anchors.centerIn: parent
                                            text: root.calSelectedDateKey.length > 0 ? "Show Upcoming" : "Refresh"
                                            color: agendaActionArea.pressed ? root.colDark : root.colSubtext
                                            font.family: root.uiFont
                                            font.pixelSize: 17
                                            font.bold: true
                                        }
                                        MouseArea {
                                            id: agendaActionArea
                                            anchors.fill: parent
                                            onClicked: {
                                                if (root.calSelectedDateKey.length > 0) {
                                                    root.calSelectedDateKey = "";
                                                } else {
                                                    root.queryCalendarMonth(root.calViewYear, root.calViewMonth);
                                                }
                                            }
                                        }
                                    }
                                }

                                Repeater {
                                    model: root.filteredAgendaEvents()
                                    delegate: Rectangle {
                                        required property var modelData
                                        width: parent.width
                                        height: 54
                                        radius: 14
                                        color: root.colPopupBase
                                        border.color: root.colSurface1
                                        border.width: 1
                                        RowLayout {
                                            anchors.fill: parent
                                            anchors.leftMargin: 16
                                            anchors.rightMargin: 16
                                            spacing: 14
                                            Text {
                                                text: root.formatEventWhen(modelData)
                                                color: root.eventColor(modelData)
                                                font.family: root.uiFont
                                                font.pixelSize: 19
                                                font.bold: true
                                            }
                                            Text {
                                                Layout.fillWidth: true
                                                elide: Text.ElideRight
                                                text: String(modelData.title || "")
                                                color: root.colText
                                                font.family: root.uiFont
                                                font.pixelSize: 20
                                            }
                                        }
                                    }
                                }

                                Rectangle {
                                    visible: root.filteredAgendaEvents().length === 0
                                    width: parent.width
                                    height: 54
                                    radius: 14
                                    color: root.colPopupBase
                                    border.color: root.colSurface1
                                    border.width: 1
                                    Text {
                                        anchors.centerIn: parent
                                        text: root.calendarOk
                                            ? (root.calSelectedDateKey.length > 0 ? "No events on selected day" : "No upcoming events")
                                            : "Start Shizuku to sync Android Calendar"
                                        color: root.colSubtext
                                        font.family: root.uiFont
                                        font.pixelSize: 19
                                    }
                                }
                            }
                        }
