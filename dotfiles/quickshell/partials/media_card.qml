                        // Android MediaSession Control Card (via rish)
                        Rectangle {
                            Layout.fillWidth: true
                            implicitHeight: spotifyCol.implicitHeight + 44
                            radius: 20
                            color: root.colSurface
                            border.color: root.colSurface1
                            border.width: 1

                            Column {
                                id: spotifyCol
                                anchors.fill: parent
                                anchors.leftMargin: 24
                                anchors.rightMargin: 24
                                anchors.topMargin: 22
                                anchors.bottomMargin: 22
                                spacing: 18

                                Row {
                                    width: parent.width
                                    spacing: 20
                                    Rectangle {
                                        width: 112
                                        height: 112
                                        radius: 18
                                        color: root.colSurface1
                                        Text {
                                            anchors.centerIn: parent
                                            text: root.mediaPackage.indexOf("spotify") >= 0 ? "󰓇" : "󰎄"
                                            color: root.mediaPackage.indexOf("spotify") >= 0 ? root.colGreen : (root.mediaPlaying ? root.colBlue : root.colSubtext)
                                            font.family: root.uiFont
                                            font.pixelSize: 54
                                        }
                                        MouseArea {
                                            anchors.fill: parent
                                            onClicked: root.refreshMedia()
                                        }
                                    }
                                    Column {
                                        width: parent.width - 132
                                        anchors.verticalCenter: parent.verticalCenter
                                        spacing: 6
                                        Text {
                                            width: parent.width
                                            elide: Text.ElideRight
                                            text: root.mediaApp.toUpperCase() + " · " + root.mediaState
                                            color: root.mediaPlaying ? root.colGreen : (root.mediaAvailable ? root.colBlue : root.colPeach)
                                            font.family: root.uiFont
                                            font.pixelSize: 16
                                            font.bold: true
                                        }
                                        Text {
                                            width: parent.width
                                            elide: Text.ElideRight
                                            text: root.mediaTitle
                                            color: root.colText
                                            font.family: root.uiFont
                                            font.pixelSize: 27
                                            font.bold: true
                                        }
                                        Text {
                                            width: parent.width
                                            elide: Text.ElideRight
                                            text: root.mediaArtist + (root.mediaAlbum.length > 0 ? " · " + root.mediaAlbum : "")
                                            color: root.colSubtext
                                            font.family: root.uiFont
                                            font.pixelSize: 22
                                        }
                                    }
                                }

                                Column {
                                    width: parent.width
                                    spacing: 8
                                    Rectangle {
                                        width: parent.width
                                        height: 10
                                        radius: 5
                                        color: root.colSurface1
                                        Rectangle {
                                            width: root.mediaPlaying
                                                ? parent.width * Math.min(1.0, Math.max(0.08, (root.mediaPosSec % 240) / 240.0))
                                                : (root.mediaPosSec > 0 ? parent.width * Math.min(1.0, Math.max(0.08, (root.mediaPosSec % 240) / 240.0)) : 0)
                                            height: parent.height
                                            radius: 5
                                            color: root.mediaPlaying ? root.colGreen : root.colBlue
                                            Behavior on width { NumberAnimation { duration: 250 } }
                                        }
                                    }
                                    RowLayout {
                                        width: parent.width
                                        Text {
                                            text: root.mediaPosText
                                            color: root.colSubtext
                                            font.family: root.uiFont
                                            font.pixelSize: 19
                                            font.bold: true
                                        }
                                        Item { Layout.fillWidth: true }
                                        Text {
                                            text: root.mediaPlaying ? "Playing" : (root.mediaState === "PAUSED" ? "Paused" : root.mediaApp)
                                            color: root.colSubtext
                                            font.family: root.uiFont
                                            font.pixelSize: 19
                                            font.bold: true
                                        }
                                    }
                                }

                                Row {
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    spacing: 28
                                    Rectangle {
                                        anchors.verticalCenter: parent.verticalCenter
                                        width: 56
                                        height: 56
                                        radius: 16
                                        color: prevArea.pressed ? root.colSurface1 : "transparent"
                                        Text {
                                            anchors.centerIn: parent
                                            text: "󰒮"
                                            color: prevArea.pressed ? root.colText : root.colSubtext
                                            font.family: root.uiFont
                                            font.pixelSize: 32
                                        }
                                        MouseArea {
                                            id: prevArea
                                            anchors.fill: parent
                                            onClicked: root.sendMediaAction("previous")
                                        }
                                    }
                                    Rectangle {
                                        width: 62
                                        height: 62
                                        radius: 31
                                        color: playArea.pressed ? root.colBlue : (root.mediaPlaying ? root.colGreen : root.colBlue)
                                        scale: playArea.pressed ? 0.92 : 1.0
                                        Behavior on scale { NumberAnimation { duration: 80 } }
                                        Text {
                                            anchors.centerIn: parent
                                            text: root.mediaPlaying ? "󰏤" : "󰐊"
                                            color: root.colDark
                                            font.family: root.uiFont
                                            font.pixelSize: 30
                                        }
                                        MouseArea {
                                            id: playArea
                                            anchors.fill: parent
                                            onClicked: root.sendMediaAction("play-pause")
                                        }
                                    }
                                    Rectangle {
                                        anchors.verticalCenter: parent.verticalCenter
                                        width: 56
                                        height: 56
                                        radius: 16
                                        color: nextArea.pressed ? root.colSurface1 : "transparent"
                                        Text {
                                            anchors.centerIn: parent
                                            text: "󰒭"
                                            color: nextArea.pressed ? root.colText : root.colSubtext
                                            font.family: root.uiFont
                                            font.pixelSize: 32
                                        }
                                        MouseArea {
                                            id: nextArea
                                            anchors.fill: parent
                                            onClicked: root.sendMediaAction("next")
                                        }
                                    }
                                }
                            }
                        }
