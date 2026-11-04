import QtQuick
import QtQuick.Layouts

Rectangle {
    id: card
    property string marker: ""
    property string title: ""
    property string body: ""
    implicitHeight: contents.implicitHeight + 32
    radius: 16; color: "#f1f3eb"; border.color: "#e0e6d8"
    RowLayout {
        id: contents
        x: 16; y: 16; width: parent.width - 32; spacing: 14
        Rectangle {
            visible: !!card.marker; Layout.alignment: Qt.AlignTop
            width: 33; height: 33; radius: 11; color: "#dfe9dd"
            Text { anchors.centerIn: parent; text: card.marker; color: "#466c55"; font.pixelSize: 13; font.bold: true }
        }
        ColumnLayout {
            Layout.fillWidth: true; spacing: 7
            Text { Layout.fillWidth: true; text: card.title; wrapMode: Text.Wrap; color: "#294d40"; font.pixelSize: 15; font.bold: true }
            Text { Layout.fillWidth: true; text: card.body; wrapMode: Text.Wrap; color: "#5b7363"; font.pixelSize: 14; lineHeight: 1.45 }
        }
    }
}
