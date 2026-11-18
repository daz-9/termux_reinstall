                        // Termux:API & Shizuku Status Card
                        Rectangle {
                            Layout.fillWidth: true
                            implicitHeight: androidStatusCol.implicitHeight + 40
                            radius: 20
                            color: root.colSurface
                            border.color: root.colSurface1
                            border.width: 1

                            Column {
                                id: androidStatusCol
                                anchors.fill: parent
                                anchors.leftMargin: 24
                                anchors.rightMargin: 24
                                anchors.topMargin: 20
                                anchors.bottomMargin: 20
                                spacing: 14

                                RowLayout {
                                    width: parent.width
                                    Row {
                                        spacing: 12
                                        Text {
                                            anchors.verticalCenter: parent.verticalCenter
                                            text: ""
                                            color: (root.termuxApiOk && root.shizukuOk) ? root.colGreen : ((root.termuxApiOk || root.shizukuOk) ? root.colPeach : root.colRed)
                                            font.family: root.uiFont
                                            font.pixelSize: 28
                                        }
                                        Text {
                                            anchors.verticalCenter: parent.verticalCenter
                                            text: "Termux:API & Shizuku"
                                            color: root.colText
                                            font.family: root.uiFont
                                            font.pixelSize: 24
                                            font.bold: true
                                        }
                                    }
                                    Item { Layout.fillWidth: true }
                                    Rectangle {
                                        implicitWidth: refreshRow.implicitWidth + 24
                                        height: 40
                                        radius: 12
                                        color: refreshBtnArea.pressed ? root.colBlue : root.colPopupBase
                                        border.color: root.colSurface1
                                        border.width: 1
                                        Row {
                                            id: refreshRow
                                            anchors.centerIn: parent
                                            spacing: 8
                                            Text {
                                                anchors.verticalCenter: parent.verticalCenter
                                                text: ""
                                                color: refreshBtnArea.pressed ? root.colDark : root.colBlue
                                                font.family: root.uiFont
                                                font.pixelSize: 18
                                            }
                                            Text {
                                                anchors.verticalCenter: parent.verticalCenter
                                                text: root.androidProbing ? "Checking" : "Refresh"
                                                color: refreshBtnArea.pressed ? root.colDark : root.colSubtext
                                                font.family: root.uiFont
                                                font.pixelSize: 18
                                                font.bold: true
                                            }
                                        }
                                        MouseArea {
                                            id: refreshBtnArea
                                            anchors.fill: parent
                                            onClicked: root.refreshAndroidStatus()
                                        }
                                    }
                                }

                                RowLayout {
                                    width: parent.width
                                    spacing: 14

                                    // Termux:API Tile
                                    Rectangle {
                                        Layout.fillWidth: true
                                        implicitHeight: apiTileCol.implicitHeight + 32
                                        radius: 16
                                        color: apiTileArea.pressed ? root.colSurface1 : root.colPopupBase
                                        border.color: root.termuxApiOk ? root.colGreen : root.colSurface1
                                        border.width: 1

                                        Column {
                                            id: apiTileCol
                                            anchors.fill: parent
                                            anchors.margins: 16
                                            spacing: 6

                                            RowLayout {
                                                width: parent.width
                                                Row {
                                                    spacing: 10
                                                    Rectangle {
                                                        anchors.verticalCenter: parent.verticalCenter
                                                        width: 12
                                                        height: 12
                                                        radius: 6
                                                        color: root.termuxApiOk ? root.colGreen : (root.termuxApiState === "Missing" ? root.colRed : root.colPeach)
                                                    }
                                                    Text {
                                                        anchors.verticalCenter: parent.verticalCenter
                                                        text: "Termux:API"
                                                        color: root.colText
                                                        font.family: root.uiFont
                                                        font.pixelSize: 21
                                                        font.bold: true
                                                    }
                                                }
                                                Item { Layout.fillWidth: true }
                                                Text {
                                                    visible: root.termuxApiVer.length > 0
                                                    text: "v" + root.termuxApiVer
                                                    color: root.colSubtext
                                                    font.family: root.uiFont
                                                    font.pixelSize: 17
                                                }
                                            }

                                            Text {
                                                width: parent.width
                                                elide: Text.ElideRight
                                                text: root.termuxApiState
                                                color: root.termuxApiOk ? root.colGreen : (root.termuxApiState === "Missing" ? root.colRed : root.colPeach)
                                                font.family: root.uiFont
                                                font.pixelSize: 23
                                                font.bold: true
                                            }

                                            Text {
                                                width: parent.width
                                                elide: Text.ElideRight
                                                text: root.termuxApiDetail
                                                color: root.colSubtext
                                                font.family: root.uiFont
                                                font.pixelSize: 18
                                            }
                                        }

                                        MouseArea {
                                            id: apiTileArea
                                            anchors.fill: parent
                                            onClicked: {
                                                root.runCmd(["sh", "-c", "termux-api-start >/dev/null 2>&1"]);
                                                androidDelayTimer.restart();
                                            }
                                        }
                                    }

                                    // Shizuku Tile
                                    Rectangle {
                                        Layout.fillWidth: true
                                        implicitHeight: shzTileCol.implicitHeight + 32
                                        radius: 16
                                        color: shzTileArea.pressed ? root.colSurface1 : root.colPopupBase
                                        border.color: root.shizukuOk ? root.colGreen : root.colSurface1
                                        border.width: 1

                                        Column {
                                            id: shzTileCol
                                            anchors.fill: parent
                                            anchors.margins: 16
                                            spacing: 6

                                            RowLayout {
                                                width: parent.width
                                                Row {
                                                    spacing: 10
                                                    Rectangle {
                                                        anchors.verticalCenter: parent.verticalCenter
                                                        width: 12
                                                        height: 12
                                                        radius: 6
                                                        color: root.shizukuOk ? root.colGreen : (root.shizukuState === "No rish" ? root.colRed : root.colPeach)
                                                    }
                                                    Text {
                                                        anchors.verticalCenter: parent.verticalCenter
                                                        text: "Shizuku"
                                                        color: root.colText
                                                        font.family: root.uiFont
                                                        font.pixelSize: 21
                                                        font.bold: true
                                                    }
                                                }
                                                Item { Layout.fillWidth: true }
                                                Text {
                                                    visible: root.shizukuVer.length > 0
                                                    text: "v" + root.shizukuVer
                                                    color: root.colSubtext
                                                    font.family: root.uiFont
                                                    font.pixelSize: 17
                                                }
                                            }

                                            Text {
                                                width: parent.width
                                                elide: Text.ElideRight
                                                text: root.shizukuState
                                                color: root.shizukuOk ? root.colGreen : (root.shizukuState === "No rish" ? root.colRed : root.colPeach)
                                                font.family: root.uiFont
                                                font.pixelSize: 23
                                                font.bold: true
                                            }

                                            Text {
                                                width: parent.width
                                                elide: Text.ElideRight
                                                text: root.shizukuDetail
                                                color: root.colSubtext
                                                font.family: root.uiFont
                                                font.pixelSize: 18
                                            }
                                        }

                                        MouseArea {
                                            id: shzTileArea
                                            anchors.fill: parent
                                            onClicked: root.refreshAndroidStatus()
                                        }
                                    }
                                }
                            }
                        }
