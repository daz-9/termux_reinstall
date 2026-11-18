                            Rectangle {
                                Layout.fillWidth: true
                                implicitHeight: weatherCol.implicitHeight + 40
                                radius: 20
                                color: weatherCardArea.pressed ? root.colSurface1 : root.colSurface
                                border.color: root.colSurface1
                                border.width: 1

                                Column {
                                    id: weatherCol
                                    anchors.fill: parent
                                    anchors.margins: 20
                                    spacing: 8
                                    RowLayout {
                                        width: parent.width
                                        Row {
                                            spacing: 12
                                            Text {
                                                anchors.verticalCenter: parent.verticalCenter
                                                text: root.weatherIcon
                                                color: root.weatherColor(root.weatherTone)
                                                font.family: root.uiFont
                                                font.pixelSize: 38
                                            }
                                            Text {
                                                anchors.verticalCenter: parent.verticalCenter
                                                text: root.weatherTemp
                                                color: root.colText
                                                font.family: root.uiFont
                                                font.pixelSize: 32
                                                font.bold: true
                                            }
                                        }
                                        Item { Layout.fillWidth: true }
                                        Text {
                                            text: root.weatherLocation
                                            color: root.colBlue
                                            font.family: root.uiFont
                                            font.pixelSize: 16
                                            font.bold: true
                                        }
                                    }
                                    Text {
                                        width: parent.width
                                        elide: Text.ElideRight
                                        text: root.weatherDetail
                                        color: root.colSubtext
                                        font.family: root.uiFont
                                        font.pixelSize: 20
                                    }
                                }

                                MouseArea {
                                    id: weatherCardArea
                                    anchors.fill: parent
                                    onClicked: root.refreshWeather()
                                }
                            }
