import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: page
    objectName: "historyPage"
    signal backRequested()
    signal fileOpened()
    property string query: ""
    property string kindFilter: "all"
    property var rows: {
        var needle = query.toLowerCase()
        return controller.historyRecords.filter(function(row) {
            return (!needle || row.file_name.toLowerCase().indexOf(needle) >= 0)
                && (kindFilter === "all" || row.kind === kindFilter)
        })
    }
    ColumnLayout {
        anchors.fill: parent; spacing: 20
        RowLayout {
            Layout.fillWidth: true
            Column { spacing: 7
                Text { text: "历史记录"; color: "#355349"; font.family: "SimSun"; font.pixelSize: 28 }
                Text { text: "本机工作记录，重新打开文件即可继续。"; color: "#7c8778"; font.pixelSize: 12 }
            }
            Item { Layout.fillWidth: true }
            AppButton { objectName: "clearHistory"; text: "清空历史"; enabled: controller.historyCount > 0; onClicked: clearDialog.open() }
            AppButton { text: "返回工作台 ↗"; primary: true; onClicked: page.backRequested() }
        }
        RowLayout {
            Layout.fillWidth: true; spacing: 10
            TextField {
                objectName: "historySearch"
                Layout.preferredWidth: 300; implicitHeight: 42
                placeholderText: "搜索文件名称"; text: page.query
                onTextEdited: page.query = text
                background: Rectangle { color: "#fcfbf7"; radius: 12; border.color: "#d9ddd1" }
            }
            Repeater { model: [{label:"全部", value:"all"},{label:"照片", value:"image"},{label:"视频", value:"video"}]
                AppButton { required property var modelData; text: modelData.label; primary: page.kindFilter === modelData.value; implicitWidth: 72; onClicked: page.kindFilter = modelData.value }
            }
            Item { Layout.fillWidth: true }
            Text { text: page.rows.length + " 条记录"; color: "#7c8778"; font.pixelSize: 12 }
        }
        Rectangle {
            Layout.fillWidth: true; Layout.fillHeight: true
            color: "#fcfbf7"; radius: 18; border.color: "#e1dfd3"
            ColumnLayout {
                anchors.fill: parent; anchors.margins: 18; spacing: 0
                RowLayout { Layout.fillWidth: true; Layout.preferredHeight: 38
                    Text { text: "文件 / 媒体类型"; Layout.fillWidth: true; color: "#7c8778"; font.pixelSize: 11 }
                    Text { text: "导入时间 · 北京时间"; Layout.preferredWidth: 165; color: "#7c8778"; font.pixelSize: 11 }
                    Text { text: "检测状态"; Layout.preferredWidth: 92; color: "#7c8778"; font.pixelSize: 11 }
                    Text { text: "操作"; Layout.preferredWidth: 166; color: "#7c8778"; font.pixelSize: 11 }
                }
                Rectangle { Layout.fillWidth: true; height: 1; color: "#e5e2d6" }
                ListView {
                    id: list
                    objectName: "historyList"
                    Layout.fillWidth: true; Layout.fillHeight: true; clip: true
                    model: page.rows; spacing: 0
                    ScrollBar.vertical: ScrollBar { }
                    delegate: Item {
                        required property var modelData
                        width: list.width; height: 84
                        RowLayout {
                            anchors.fill: parent; spacing: 12
                            Rectangle { width: 38; height: 40; radius: 10; color: "#e5ecdf"
                                Text { anchors.centerIn: parent; text: modelData.kind === "image" ? "图" : "影"; color: "#557565"; font.family: "SimSun"; font.pixelSize: 18 }
                            }
                            ColumnLayout { Layout.fillWidth: true; spacing: 5
                                Text { text: modelData.file_name; Layout.fillWidth: true; elide: Text.ElideMiddle; color: "#355349"; font.pixelSize: 13; font.bold: true }
                                Text { text: (modelData.kind === "image" ? "照片" : "视频") + " · " + modelData.metadata; Layout.fillWidth: true; elide: Text.ElideRight; color: "#7c8778"; font.pixelSize: 10 }
                            }
                            Text { text: modelData.display_time; Layout.preferredWidth: 165; color: "#7c8778"; font.pixelSize: 11 }
                            Text { text: ({pending:"待检测",running:"检测中",completed:"已检测",partial:"部分完成",failed:"未完成",cancelled:"已取消"})[modelData.status] || "未完成"; Layout.preferredWidth: 92; color: "#a0834d"; font.pixelSize: 12 }
                            AppButton { text: "重新打开"; implicitWidth: 100; implicitHeight: 36; onClicked: { if (controller.reopenRecord(modelData.id)) page.fileOpened() } }
                            AppButton { text: "删除"; quiet: true; implicitWidth: 54; implicitHeight: 36; onClicked: controller.deleteRecord(modelData.id) }
                        }
                        Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: "#efeee6" }
                    }
                    Column { anchors.centerIn: parent; spacing: 15; visible: page.rows.length === 0
                        Text { text: controller.historyCount ? "没有匹配的记录" : "还没有工作记录"; color: "#355349"; font.family: "SimSun"; font.pixelSize: 23; anchors.horizontalCenter: parent.horizontalCenter }
                        Text { text: controller.historyCount ? "换个文件名或筛选条件试试。" : "选择照片或视频后，导入信息会保存在这里。"; color: "#7c8778"; font.pixelSize: 12; anchors.horizontalCenter: parent.horizontalCenter }
                    }
                }
            }
        }
        Text { text: "本机保存文件路径、导入信息与检测结果；原媒体不会复制到历史库。重新打开可查看记录，原文件改变后需重新检测。"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: "#7c8778"; font.pixelSize: 11 }
        Text { text: controller.errorText; visible: !!controller.errorText; Layout.fillWidth: true; wrapMode: Text.Wrap; color: "#9c6335"; font.pixelSize: 12 }
    }
    AppDialog {
        id: clearDialog
        objectName: "clearHistoryDialog"
        parent: Overlay.overlay; anchors.centerIn: parent; width: 420; modal: true
        title: "清空全部历史记录？"
        eyebrow: "历史管理 / HISTORY"; confirmText: "清空记录"
        standardButtons: Dialog.Cancel | Dialog.Ok
        onAccepted: controller.clearHistory()
        contentItem: Text { text: "仅清除本机历史信息，原始照片和视频不受影响。"; wrapMode: Text.Wrap; color: "#355349"; font.pixelSize: 13 }
    }
}
