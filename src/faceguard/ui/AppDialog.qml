import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Dialog {
    id: dialog
    property string eyebrow: "谛听 · FACEGUARD"
    property string subtitle: ""
    property string confirmText: "完成"
    property string footerNote: ""
    parent: Overlay.overlay
    anchors.centerIn: parent
    modal: true; focus: true
    padding: 24; topPadding: 8; bottomPadding: 4
    standardButtons: Dialog.Ok
    height: Math.min(parent ? parent.height - 60 : 660, implicitHeight)
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    font.family: "Microsoft YaHei UI"
    background: Rectangle {
        radius: 24; color: "#fcfbf7"; border.color: "#cbd7ca"
        Rectangle { z: -1; x: -5; y: 7; width: parent.width + 10; height: parent.height + 3; radius: 28; color: "#160e2e24" }
        Rectangle { x: 26; y: 0; width: 52; height: 3; radius: 2; color: "#b59b65" }
    }
    Overlay.modal: Rectangle { color: "#730e2720" }
    header: Item {
        implicitHeight: dialog.subtitle ? 126 : 102
        RowLayout {
            anchors.left: parent.left; anchors.right: parent.right
            anchors.top: parent.top; anchors.margins: 24; spacing: 14
            Rectangle {
                width: 48; height: 48; radius: 15; color: "#e8ede4"
                Image { anchors.centerIn: parent; width: 38; height: 38; source: "brand.svg" }
            }
            ColumnLayout {
                Layout.fillWidth: true; spacing: 5
                Text { text: dialog.eyebrow; font.pixelSize: 10; font.letterSpacing: 1.5; color: "#8b784e" }
                Text { Layout.fillWidth: true; text: dialog.title; elide: Text.ElideRight; font.pixelSize: 23; font.family: "SimSun"; font.bold: true; color: "#294d40" }
            }
            AppButton { objectName: "dialogClose"; text: "×"; quiet: true; implicitWidth: 34; implicitHeight: 34; font.pixelSize: 22; Accessible.name: "关闭弹窗"; onClicked: dialog.reject() }
        }
        Text { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; anchors.leftMargin: 24; anchors.rightMargin: 24; anchors.bottomMargin: 15; visible: !!dialog.subtitle; text: dialog.subtitle; color: "#647b6d"; font.pixelSize: 13; wrapMode: Text.Wrap }
    }
    footer: Item {
        implicitHeight: 78
        Rectangle { x: 24; width: parent.width - 48; height: 1; color: "#e3e7dc" }
        RowLayout {
            anchors.fill: parent; anchors.leftMargin: 24; anchors.rightMargin: 24; spacing: 10
            Text { Layout.fillWidth: true; text: dialog.footerNote; color: "#6b8172"; font.pixelSize: 12; wrapMode: Text.Wrap }
            AppButton { objectName: "dialogCancel"; visible: !!(dialog.standardButtons & Dialog.Cancel); text: "取消"; onClicked: dialog.reject() }
            AppButton { objectName: "dialogConfirm"; text: dialog.confirmText; primary: true; implicitWidth: 104; onClicked: dialog.accept() }
        }
    }
    enter: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: controller.reducedMotion ? 0 : 140 } }
    exit: Transition { NumberAnimation { property: "opacity"; from: 1; to: 0; duration: controller.reducedMotion ? 0 : 100 } }
}
