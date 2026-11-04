import QtQuick
import QtQuick.Controls

ComboBox {
    id: control
    implicitHeight: 46
    font.family: "Microsoft YaHei UI"; font.pixelSize: 13
    leftPadding: 14; rightPadding: 36
    contentItem: Text { text: control.displayText; font: control.font; color: control.enabled ? "#355349" : "#8a9889"; verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight }
    background: Rectangle { radius: 12; color: control.enabled ? "#fcfbf7" : "#f0f1e9"; border.color: control.activeFocus ? "#aa925a" : control.hovered ? "#8fa68d" : "#cfd9c8" }
    indicator: Text { x: control.width - 28; y: (control.height - height) / 2; text: "⌄"; font.pixelSize: 20; color: "#55705f" }
    delegate: ItemDelegate {
        required property var modelData
        required property int index
        width: control.width - 12; height: 48
        highlighted: control.highlightedIndex === index
        contentItem: Text { text: modelData.label; font: control.font; color: "#355349"; verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight }
        background: Rectangle { radius: 9; color: parent.highlighted ? "#e4ecdf" : "transparent" }
    }
    popup: Popup {
        objectName: "modelChoicesPopup"
        y: control.height + 6; width: control.width; padding: 6
        implicitHeight: Math.min(contentItem.implicitHeight + 12, 270)
        contentItem: ListView { clip: true; implicitHeight: contentHeight; model: control.popup.visible ? control.delegateModel : null; currentIndex: control.highlightedIndex; ScrollIndicator.vertical: ScrollIndicator { } }
        background: Rectangle { radius: 15; color: "#fcfbf7"; border.color: "#cbd7c6" }
    }
}
