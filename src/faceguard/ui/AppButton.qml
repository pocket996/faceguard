import QtQuick
import QtQuick.Controls

Button {
    id: button
    property bool primary: false
    property bool quiet: false
    implicitHeight: 44
    implicitWidth: Math.max(90, contentItem.implicitWidth + 34)
    hoverEnabled: true
    font.family: "Microsoft YaHei UI"
    font.pixelSize: 13
    padding: 12
    contentItem: Text {
        text: button.text
        font: button.font
        color: !button.enabled ? "#a6aca3" : button.primary ? "#fcfbf7" : "#355349"
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }
    background: Rectangle {
        radius: 12
        color: !button.enabled ? "#e8e7e0" : button.primary ? (button.down ? "#29443b" : button.hovered ? "#45685a" : "#355349") : (button.hovered ? "#e5eadf" : button.quiet ? "transparent" : "#fcfbf7")
        border.width: button.primary || button.quiet ? 0 : 1
        border.color: button.activeFocus ? "#9c8758" : "#d9ddd1"
    }
    HoverHandler { cursorShape: button.enabled ? Qt.PointingHandCursor : Qt.ArrowCursor }
}
