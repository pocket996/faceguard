import QtQuick
import QtQuick.Controls

Switch {
    id: control
    implicitHeight: 42
    implicitWidth: contentItem.implicitWidth + 60
    hoverEnabled: true
    indicator: Rectangle {
        x: 0; y: (control.height - height) / 2
        width: 42; height: 24; radius: 12
        color: control.checked ? "#416b56" : "#d4ddcf"
        border.color: control.activeFocus ? "#ad955f" : "transparent"
        Rectangle {
            x: control.checked ? 21 : 3; y: 3; width: 18; height: 18; radius: 9; color: "#fcfbf7"
            Behavior on x { NumberAnimation { duration: controller.reducedMotion ? 0 : 140 } }
        }
    }
    contentItem: Text {
        text: control.text; leftPadding: 55; verticalAlignment: Text.AlignVCenter
        font.family: "Microsoft YaHei UI"; font.pixelSize: 14; color: "#355349"
    }
    HoverHandler { cursorShape: Qt.PointingHandCursor }
}
