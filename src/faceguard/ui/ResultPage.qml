import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: page
    objectName: "resultPage"
    signal backRequested()
    property int viewMode: 0
    property real overlayOpacity: 0.6
    property url heatmapSource: ""
    readonly property bool heatmapReady: heatmapProbe.status === Image.Ready
    property bool hasPhoto: !!controller.fileName && controller.mediaKind === "image"
    property url displayedSource: page.hasPhoto ? controller.previewUrl : controller.selectedFrameUrl
    readonly property bool hasImage: page.hasPhoto || !!controller.selectedFrameUrl.toString()
    readonly property bool compact: page.height < 620
    property real zoom: 1
    property real panX: 0.5
    property real panY: 0.5
    onZoomChanged: { panX = 0.5; panY = 0.5 }
    function fitImage() { zoom = 1; panX = 0.5; panY = 0.5 }
    Image { id: heatmapProbe; source: page.heatmapSource; visible: false; asynchronous: true }

    ColumnLayout {
        anchors.fill: parent; spacing: 16
        RowLayout {
            Layout.fillWidth: true
            Column { spacing: 7
                Text { text: "检测结果与热力图"; color: "#355349"; font.family: "SimSun"; font.pixelSize: 28 }
                Text { text: controller.fileName || "先导入媒体，再查看分析结果"; color: "#7c8778"; font.pixelSize: 12 }
            }
            Item { Layout.fillWidth: true }
            AppButton { objectName: "saveReport"; text: "保存检测报告"; enabled: controller.hasResult && !controller.busy; onClicked: controller.saveReport() }
            AppButton { text: "返回工作台 ↗"; primary: true; onClicked: page.backRequested() }
        }
        RowLayout {
            Layout.fillWidth: true; spacing: 18
            Rectangle {
                Layout.fillWidth: true; Layout.fillHeight: true
                radius: 18; color: "#fcfbf7"; border.color: "#e1dfd3"
                ColumnLayout {
                    anchors.fill: parent; anchors.margins: 18; spacing: 14
                    RowLayout {
                        Layout.fillWidth: true; spacing: 7
                        Repeater { model: ["原图", "热力图叠加", "并排对比"]
                            AppButton { required property string modelData; required property int index; text: modelData; primary: page.viewMode === index; implicitWidth: index === 0 ? 66 : 110; onClicked: page.viewMode = index }
                        }
                        Item { Layout.fillWidth: true }
                        AppButton { text: "适应"; implicitWidth: 52; enabled: page.hasImage; onClicked: page.fitImage() }
                        AppButton { text: "－"; implicitWidth: 34; enabled: page.hasImage && page.zoom > 1; onClicked: page.zoom = Math.max(1, page.zoom - 0.25) }
                        Text { text: Math.round(page.zoom * 100) + "%"; color: "#7c8778"; font.pixelSize: 11 }
                        AppButton { text: "＋"; implicitWidth: 34; enabled: page.hasImage && page.zoom < 3; onClicked: page.zoom = Math.min(3, page.zoom + 0.25) }
                    }
                    RowLayout {
                        Layout.fillWidth: true; Layout.fillHeight: true; spacing: 12
                        Repeater {
                            model: page.viewMode === 2 ? 2 : 1
                            Rectangle {
                                required property int index
                                readonly property bool showOverlay: page.viewMode === 1 || (page.viewMode === 2 && index === 1)
                                Layout.fillWidth: true; Layout.fillHeight: true; radius: 12; color: "#efefe5"; clip: true
                                Text { x: 12; y: 10; z: 3; text: showOverlay ? "模型关注区域" : controller.mediaKind === "video" ? "视频采样帧" : "原始图像"; color: "#355349"; font.pixelSize: 11 }
                                Flickable {
                                    id: viewport
                                    objectName: "resultViewport"
                                    property bool synchronizing: false
                                    anchors.fill: parent; anchors.margins: 30
                                    contentWidth: width * page.zoom; contentHeight: height * page.zoom; clip: true
                                    boundsBehavior: Flickable.StopAtBounds
                                    function alignViews() {
                                        synchronizing = true
                                        contentX = Math.max(0, contentWidth - width) * page.panX
                                        contentY = Math.max(0, contentHeight - height) * page.panY
                                        synchronizing = false
                                    }
                                    onContentWidthChanged: alignViews()
                                    onContentHeightChanged: alignViews()
                                    onContentXChanged: if (!synchronizing && contentWidth > width && Math.abs(contentX / (contentWidth - width) - page.panX) > 0.0001) page.panX = Math.max(0, Math.min(1, contentX / (contentWidth - width)))
                                    onContentYChanged: if (!synchronizing && contentHeight > height && Math.abs(contentY / (contentHeight - height) - page.panY) > 0.0001) page.panY = Math.max(0, Math.min(1, contentY / (contentHeight - height)))
                                    Connections {
                                        target: page
                                        function onPanXChanged() { viewport.alignViews() }
                                        function onPanYChanged() { viewport.alignViews() }
                                    }
                                    Image { objectName: "resultOriginal"; width: viewport.contentWidth; height: viewport.contentHeight; source: page.displayedSource; autoTransform: true; fillMode: Image.PreserveAspectFit; sourceSize.width: 2400 }
                                    Image { objectName: "heatmapOverlay"; width: viewport.contentWidth; height: viewport.contentHeight; source: page.heatmapSource; visible: showOverlay && page.heatmapReady; opacity: page.overlayOpacity; fillMode: Image.PreserveAspectFit }
                                }
                                Rectangle {
                                    visible: showOverlay && !page.heatmapReady
                                    anchors.centerIn: parent; width: Math.min(parent.width - 24, 295); height: 110
                                    radius: 14; color: "#f6f5ed"; border.color: "#daddce"; opacity: 0.97
                                    Column { anchors.centerIn: parent; width: parent.width - 24; spacing: 10
                                        Text { anchors.horizontalCenter: parent.horizontalCenter; text: heatmapProbe.status === Image.Error ? "热力图无法读取" : "等待热力图结果"; font.family: "SimSun"; font.pixelSize: 20; color: "#355349" }
                                        Text { width: parent.width; text: heatmapProbe.status === Image.Error ? "结果文件可能已移动或损坏" : "热力图计算尚待实现\n当前可查看真实检测分数与人脸"; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap; color: "#7c8778"; font.pixelSize: 11; lineHeight: 1.5 }
                                    }
                                }
                                Text { anchors.centerIn: parent; visible: !page.hasImage && !showOverlay; width: parent.width - 30; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap; text: controller.mediaKind === "video" && controller.fileName ? (controller.hasResult ? "选择右侧人脸，查看对应视频采样帧" : "完成视频检测后，可选择采样帧查看") : "导入照片后，在此查看原图"; color: "#7c8778"; font.pixelSize: 13 }
                            }
                        }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        Text { text: "叠加强度"; color: "#7c8778"; font.pixelSize: 11 }
                        Slider {
                            id: strength; Layout.fillWidth: true; from: 0; to: 1; value: page.overlayOpacity
                            enabled: page.heatmapReady; onMoved: page.overlayOpacity = value
                            background: Rectangle {
                                x: strength.leftPadding; y: strength.topPadding + strength.availableHeight / 2 - height / 2
                                implicitHeight: 4; width: strength.availableWidth; height: 4; radius: 2; color: "#e2e6da"
                                Rectangle { width: strength.visualPosition * parent.width; height: parent.height; radius: 2; color: strength.enabled ? "#668977" : "#becbbd" }
                            }
                            handle: Rectangle {
                                x: strength.leftPadding + strength.visualPosition * (strength.availableWidth - width)
                                y: strength.topPadding + strength.availableHeight / 2 - height / 2
                                implicitWidth: 18; implicitHeight: 18; radius: 9; color: "#fcfbf7"
                                border.color: strength.enabled ? "#668977" : "#becbbd"
                            }
                        }
                        Text { text: Math.round(page.overlayOpacity * 100) + "%"; color: "#7c8778"; font.pixelSize: 11 }
                    }
                    Text { Layout.fillWidth: true; wrapMode: Text.Wrap; text: "热力图用于解释模型关注区域，不代表已经验证的精确篡改边界。"; color: "#7c8778"; font.pixelSize: 10 }
                }
            }
            Rectangle {
                Layout.preferredWidth: page.width < 1150 ? 310 : 340; Layout.fillHeight: true
                radius: 18; color: "#fcfbf7"; border.color: "#e1dfd3"
                ScrollView {
                    objectName: "resultSummaryScroll"
                    anchors.fill: parent; anchors.margins: 18; clip: true
                    contentWidth: availableWidth
                    ScrollBar.vertical.policy: ScrollBar.AsNeeded
                    ScrollBar.vertical.active: true
                    ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                    ColumnLayout {
                        width: parent.width; spacing: page.compact ? 10 : 12
                        Text { text: "分析摘要"; font.family: "SimSun"; font.pixelSize: 21; color: "#355349" }
                        Text { text: "AI 整脸生成"; color: "#355349"; font.pixelSize: 15; font.bold: true }
                        Text { Layout.fillWidth: true; wrapMode: Text.Wrap; text: controller.generationSummary; color: "#55705f"; font.pixelSize: 14; lineHeight: 1.3 }
                        Rectangle { Layout.fillWidth: true; height: 1; color: "#e5e2d6" }
                        Text { text: "换脸 / 面部篡改"; color: "#355349"; font.pixelSize: 15; font.bold: true }
                        Text { Layout.fillWidth: true; wrapMode: Text.Wrap; text: controller.manipulationSummary; color: "#55705f"; font.pixelSize: 14; lineHeight: 1.3 }
                        Rectangle { Layout.fillWidth: true; height: 1; color: "#e5e2d6" }
                        Text { text: "人脸与采样帧"; color: "#355349"; font.pixelSize: 15; font.bold: true }
                        ListView {
                            objectName: "faceResultList"
                            Layout.fillWidth: true; Layout.preferredHeight: page.compact ? 75 : 110; clip: true
                            model: controller.resultDetails; spacing: 4
                            ScrollBar.vertical: ScrollBar { }
                            delegate: AppButton {
                                required property var modelData
                                required property int index
                                width: ListView.view.width; implicitHeight: 34
                                text: modelData.title
                                onClicked: controller.selectDetail(index)
                            }
                        }
                        Image { objectName: "selectedFacePreview"; Layout.fillWidth: true; Layout.preferredHeight: controller.detailPreviewUrl.toString() ? (page.compact ? 70 : 100) : 0; source: controller.detailPreviewUrl; fillMode: Image.PreserveAspectFit }
                        Text { Layout.fillWidth: true; text: controller.selectedDetailText; visible: !!text; wrapMode: Text.Wrap; color: "#355349"; font.pixelSize: 14; lineHeight: 1.35 }
                        TextArea {
                            objectName: "detectionResultText"; Layout.fillWidth: true
                            text: controller.resultText; readOnly: true; selectByMouse: true
                            wrapMode: TextEdit.Wrap; font.pixelSize: 15; color: "#355349"
                            padding: 12
                            background: Rectangle { color: "#e9ecdf"; radius: 10 }
                        }
                    }
                }
            }
        }
    }
}
