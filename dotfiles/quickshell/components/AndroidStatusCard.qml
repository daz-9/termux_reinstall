import QtQuick
import QtQuick.Layouts

Rectangle {
    required property var hub

    Layout.fillWidth: true
    implicitHeight: androidStatusCol.implicitHeight + 40
    radius: 20
    color: Theme.colSurface
    border.color: Theme.colSurface1
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
                    color: (hub.termuxApiOk && hub.shizukuOk) ? Theme.colGreen : ((hub.termuxApiOk || hub.shizukuOk) ? Theme.colPeach : Theme.colRed)
                    font.family: Theme.uiFont
                    font.pixelSize: 28
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: "Termux:API & Shizuku"
                    color: Theme.colText
                    font.family: Theme.uiFont
                    font.pixelSize: 24
                    font.bold: true
                }
            }
            Item { Layout.fillWidth: true }
            Rectangle {
                implicitWidth: refreshRow.implicitWidth + 24
                height: 40
                radius: 12
                color: refreshBtnArea.pressed ? Theme.colBlue : Theme.colPopupBase
                border.color: Theme.colSurface1
                border.width: 1
                Row {
                    id: refreshRow
                    anchors.centerIn: parent
                    spacing: 8
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: ""
                        color: refreshBtnArea.pressed ? Theme.colDark : Theme.colBlue
                        font.family: Theme.uiFont
                        font.pixelSize: 18
                    }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: hub.androidProbing ? "Checking" : "Refresh"
                        color: refreshBtnArea.pressed ? Theme.colDark : Theme.colSubtext
                        font.family: Theme.uiFont
                        font.pixelSize: 18
                        font.bold: true
                    }
                }
                MouseArea {
                    id: refreshBtnArea
                    anchors.fill: parent
                    onClicked: hub.refreshAndroidStatus()
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
                color: apiTileArea.pressed ? Theme.colSurface1 : Theme.colPopupBase
                border.color: hub.termuxApiOk ? Theme.colGreen : Theme.colSurface1
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
                                color: hub.termuxApiOk ? Theme.colGreen : (hub.termuxApiState === "Missing" ? Theme.colRed : Theme.colPeach)
                            }
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                text: "Termux:API"
                                color: Theme.colText
                                font.family: Theme.uiFont
                                font.pixelSize: 21
                                font.bold: true
                            }
                        }
                        Item { Layout.fillWidth: true }
                        Text {
                            visible: hub.termuxApiVer.length > 0
                            text: "v" + hub.termuxApiVer
                            color: Theme.colSubtext
                            font.family: Theme.uiFont
                            font.pixelSize: 17
                        }
                    }

                    Text {
                        width: parent.width
                        elide: Text.ElideRight
                        text: hub.termuxApiState
                        color: hub.termuxApiOk ? Theme.colGreen : (hub.termuxApiState === "Missing" ? Theme.colRed : Theme.colPeach)
                        font.family: Theme.uiFont
                        font.pixelSize: 23
                        font.bold: true
                    }

                    Text {
                        width: parent.width
                        elide: Text.ElideRight
                        text: hub.termuxApiDetail
                        color: Theme.colSubtext
                        font.family: Theme.uiFont
                        font.pixelSize: 18
                    }
                }

                MouseArea {
                    id: apiTileArea
                    anchors.fill: parent
                    onClicked: hub.startTermuxApi()
                }
            }

            // Shizuku Tile
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: shzTileCol.implicitHeight + 32
                radius: 16
                color: shzTileArea.pressed ? Theme.colSurface1 : Theme.colPopupBase
                border.color: hub.shizukuOk ? Theme.colGreen : Theme.colSurface1
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
                                color: hub.shizukuOk ? Theme.colGreen : (hub.shizukuState === "No rish" ? Theme.colRed : Theme.colPeach)
                            }
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                text: "Shizuku"
                                color: Theme.colText
                                font.family: Theme.uiFont
                                font.pixelSize: 21
                                font.bold: true
                            }
                        }
                        Item { Layout.fillWidth: true }
                        Text {
                            visible: hub.shizukuVer.length > 0
                            text: "v" + hub.shizukuVer
                            color: Theme.colSubtext
                            font.family: Theme.uiFont
                            font.pixelSize: 17
                        }
                    }

                    Text {
                        width: parent.width
                        elide: Text.ElideRight
                        text: hub.shizukuState
                        color: hub.shizukuOk ? Theme.colGreen : (hub.shizukuState === "No rish" ? Theme.colRed : Theme.colPeach)
                        font.family: Theme.uiFont
                        font.pixelSize: 23
                        font.bold: true
                    }

                    Text {
                        width: parent.width
                        elide: Text.ElideRight
                        text: hub.shizukuDetail
                        color: Theme.colSubtext
                        font.family: Theme.uiFont
                        font.pixelSize: 18
                    }
                }

                MouseArea {
                    id: shzTileArea
                    anchors.fill: parent
                    onClicked: hub.refreshAndroidStatus()
                }
            }
        }
    }
}
