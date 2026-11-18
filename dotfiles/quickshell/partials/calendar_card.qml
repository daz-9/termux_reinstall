                        // Interactive Month Calendar
                        Rectangle {
                            Layout.fillWidth: true
                            implicitHeight: calCol.implicitHeight + 44
                            radius: 20
                            color: root.colSurface
                            border.color: root.colSurface1
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
                                            text: "\U000f00ed"
                                            color: root.colBlue
                                            font.family: root.uiFont
                                            font.pixelSize: 28
                                        }
                                        Text {
                                            anchors.verticalCenter: parent.verticalCenter
                                            text: root.calMonthTitle
                                            color: titleArea.pressed ? root.colBlue : root.colText
                                            font.family: root.uiFont
                                            font.pixelSize: 24
                                            font.bold: true
                                            MouseArea {
                                                id: titleArea
                                                anchors.fill: parent
                                                onClicked: root.resetCalendarToday()
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
                                            color: prevMonthArea.pressed ? root.colBlue : root.colPopupBase
                                            border.color: root.colSurface1
                                            border.width: 1
                                            Text {
                                                anchors.centerIn: parent
                                                text: "\U000f0141"
                                                color: prevMonthArea.pressed ? root.colDark : root.colSubtext
                                                font.family: root.uiFont
                                                font.pixelSize: 22
                                            }
                                            MouseArea {
                                                id: prevMonthArea
                                                anchors.fill: parent
                                                onClicked: root.stepCalendarMonth(-1)
                                            }
                                        }
                                        Rectangle {
                                            width: 42
                                            height: 42
                                            radius: 12
                                            color: nextMonthArea.pressed ? root.colBlue : root.colPopupBase
                                            border.color: root.colSurface1
                                            border.width: 1
                                            Text {
                                                anchors.centerIn: parent
                                                text: "\U000f0142"
                                                color: nextMonthArea.pressed ? root.colDark : root.colSubtext
                                                font.family: root.uiFont
                                                font.pixelSize: 22
                                            }
                                            MouseArea {
                                                id: nextMonthArea
                                                anchors.fill: parent
                                                onClicked: root.stepCalendarMonth(1)
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
                                        model: root.calendarHeaders
                                        delegate: Item {
                                            required property string modelData
                                            Layout.fillWidth: true
                                            implicitHeight: 42
                                            Text {
                                                anchors.centerIn: parent
                                                text: modelData
                                                color: root.colSubtext
                                                font.family: root.uiFont
                                                font.pixelSize: 21
                                                font.bold: true
                                            }
                                        }
                                    }

                                    Repeater {
                                        model: root.calGridCells
                                        delegate: Rectangle {
                                            required property var modelData
                                            readonly property bool selected: root.calSelectedDateKey.length > 0 && root.calSelectedDateKey === modelData.key
                                            Layout.fillWidth: true
                                            implicitHeight: 48
                                            radius: 14
                                            color: modelData.cls === "today"
                                                ? root.colBlue
                                                : (selected ? root.colSurface1 : (dayArea.pressed && modelData.cls !== "muted" ? root.colPopupBase : "transparent"))
                                            border.color: selected && modelData.cls !== "today" ? root.colBlue : "transparent"
                                            border.width: selected && modelData.cls !== "today" ? 2 : 0

                                            Column {
                                                anchors.centerIn: parent
                                                spacing: 2
                                                Text {
                                                    anchors.horizontalCenter: parent.horizontalCenter
                                                    text: modelData.d
                                                    color: modelData.cls === "today"
                                                        ? root.colDark
                                                        : (modelData.cls === "muted"
                                                            ? root.colSurface1
                                                            : (modelData.cls === "wknd" ? root.colSubtext : root.colText))
                                                    font.family: root.uiFont
                                                    font.pixelSize: 22
                                                    font.bold: modelData.cls === "today" || selected
                                                }
                                                Rectangle {
                                                    visible: modelData.hasEvent
                                                    anchors.horizontalCenter: parent.horizontalCenter
                                                    width: 6
                                                    height: 6
                                                    radius: 3
                                                    color: modelData.cls === "today" ? root.colDark : root.colMauve
                                                }
                                            }

                                            MouseArea {
                                                id: dayArea
                                                anchors.fill: parent
                                                onClicked: root.toggleCalendarDay(modelData)
                                            }
                                        }
                                    }
                                }
                            }
                        }
