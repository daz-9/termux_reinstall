import QtQuick

Rectangle {
    id: btn
    property string iconText: ""
    property string subText: ""
    property color iconColor: Theme.colText
    property color baseColor: Theme.colSurface
    property color activeColor: Theme.colSurface1
    property bool active: false
    property int iconSize: 28
    property int buttonHeight: 60
    signal clicked()

    implicitWidth: 92
    implicitHeight: btn.buttonHeight
    radius: 18
    color: area.pressed ? Theme.colBlue : (btn.active ? btn.activeColor : btn.baseColor)

    Behavior on color { ColorAnimation { duration: 80 } }

    Column {
        anchors.centerIn: parent
        spacing: 1
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: btn.iconText
            color: area.pressed ? Theme.colDark : btn.iconColor
            font.family: Theme.uiFont
            font.pixelSize: btn.iconSize
            lineHeight: 1.0
        }
        Text {
            visible: btn.subText.length > 0
            anchors.horizontalCenter: parent.horizontalCenter
            text: btn.subText
            color: area.pressed ? Theme.colDark : Theme.colSubtext
            font.family: Theme.uiFont
            font.pixelSize: 13
            font.bold: true
        }
    }

    MouseArea {
        id: area
        anchors.fill: parent
        anchors.leftMargin: -16
        anchors.rightMargin: -12
        anchors.topMargin: -4
        anchors.bottomMargin: -4
        onClicked: btn.clicked()
    }
}
