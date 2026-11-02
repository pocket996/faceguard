import QtQuick
import QtQuick.Layouts

Rectangle {
    id: card
    property string title: ""
    property string summary: ""
    property string state: "idle"
    readonly property bool attention: state === "attention"
    readonly property color accent: attention ? "#a04a32" : state === "clear" ? "#2d6047" : "#68786b"
    implicitHeight: 104
    radius: 14; color: attention ? "#fcf0e6" : state === "clear" ? "#edf3e8" : "#f3f3ec"
    border.color: attention ? "#e1bd9b" : "#dbe4d4"
    Rectangle { width: 3; height: parent.height - 30; x: 0; y: 15; radius: 2; color: card.accent }
    ColumnLayout {
        anchors.fill: parent; anchors.margins: 15; spacing: 9
        RowLayout {
            Layout.fillWidth: true
            Text { text: card.title; color: "#526c5a"; font.pixelSize: 13; Layout.fillWidth: true }
            Rectangle {
                implicitWidth: statusLabel.implicitWidth + 14; implicitHeight: 22; radius: 7
                color: card.attention ? "#f1d7bd" : "#e0e8d9"
                Text { id: statusLabel; anchors.centerIn: parent; text: card.attention ? "需关注" : card.state === "clear" ? "未检出" : card.state === "working" ? "检测中" : card.state === "idle" ? "待检测" : "请复核"; font.pixelSize: 10; font.bold: true; color: card.accent }
            }
        }
        Text {
            objectName: "overviewVerdict"
            Layout.fillWidth: true; Layout.fillHeight: true
            text: card.state === "working" ? "正在检测，请稍候" : card.summary; color: card.accent; font.pixelSize: 18; font.bold: true
            wrapMode: Text.Wrap; verticalAlignment: Text.AlignVCenter
        }
    }
}
