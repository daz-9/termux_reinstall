import QtQuick

Rectangle {
    id: btn
    signal clicked()

    implicitWidth: collapseRow.implicitWidth + 24
    height: 44
    radius: 16
    color: btnArea.pressed ? Theme.colBlue : Theme.colPopupBase
    border.color: Theme.colSurface1
    border.width: 1

    Row {
        id: collapseRow
        anchors.centerIn: parent
        spacing: 6
        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: "󰊓"
            color: btnArea.pressed ? Theme.colDark : Theme.colBlue
            font.family: Theme.uiFont
            font.pixelSize: 18
        }
        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: "Collapse"
            color: btnArea.pressed ? Theme.colDark : Theme.colSubtext
            font.family: Theme.uiFont
            font.pixelSize: 16
            font.bold: true
        }
    }

    MouseArea {
        id: btnArea
        anchors.fill: parent
        anchors.margins: -6
        onClicked: btn.clicked()
    }
}
