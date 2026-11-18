                            Rectangle {
                                Layout.fillWidth: true
                                implicitHeight: focusCol.implicitHeight + 40
                                radius: 20
                                color: focusArea.pressed ? root.colSurface1 : root.colSurface
                                border.color: root.focusDnd ? root.colMauve : root.colSurface1
                                border.width: 1

                                Column {
                                    id: focusCol
                                    anchors.fill: parent
                                    anchors.margins: 20
                                    spacing: 8
                                    RowLayout {
                                        width: parent.width
                                        Row {
                                            spacing: 12
                                            Text {
                                                anchors.verticalCenter: parent.verticalCenter
                                                text: root.focusDnd ? "󰂛" : "󰂚"
                                                color: root.focusDnd ? root.colMauve : (root.focusAvailable ? root.colTeal : root.colPeach)
                                                font.family: root.uiFont
                                                font.pixelSize: 38
                                            }
                                            Text {
                                                anchors.verticalCenter: parent.verticalCenter
                                                text: "Focus"
                                                color: root.colText
                                                font.family: root.uiFont
                                                font.pixelSize: 32
                                                font.bold: true
                                            }
                                        }
                                        Item { Layout.fillWidth: true }
                                        Text {
                                            text: root.focusDnd ? "DND ON" : (root.focusAvailable ? (root.focusNotifCount + " notifs") : "Offline")
                                            color: root.focusDnd ? root.colMauve : root.colSubtext
                                            font.family: root.uiFont
                                            font.pixelSize: 16
                                            font.bold: true
                                        }
                                    }
                                    Text {
                                        width: parent.width
                                        elide: Text.ElideRight
                                        text: root.focusAvailable
                                            ? (root.focusDnd ? (root.focusLabel + " · Tap off") : "DND Off · Tap for Priority")
                                            : root.focusLabel
                                        color: root.colSubtext
                                        font.family: root.uiFont
                                        font.pixelSize: 20
                                    }
                                }

                                MouseArea {
                                    id: focusArea
                                    anchors.fill: parent
                                    onClicked: root.toggleFocusDnd()
                                }
                            }
