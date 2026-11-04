import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import QtMultimedia

Window {
    id: window
    objectName: "mainWindow"
    visible: true
    width: 1380; height: 860
    minimumWidth: 1080; minimumHeight: 720
    title: "谛听 · 青玉守真 — FaceGuard"
    color: "transparent"
    flags: Qt.Window | Qt.FramelessWindowHint
    property color ink: "#355349"
    property color muted: "#7c8778"
    property color gold: "#b59b65"
    property bool pet: controller.petMode
    // Preference changes fan out into timelines and render resources. Apply
    // the Python notification after its signal stack unwinds to avoid reentry.
    property bool reduced: false
    function refreshMotionPreference() { reduced = controller.reducedMotion }
    Component.onCompleted: refreshMotionPreference()
    property string activePage: "workspace"
    readonly property bool mediaImageReady: photo.status === Image.Ready
    readonly property bool videoIsPlaying: player.playbackState === MediaPlayer.PlayingState
    readonly property int videoPosition: player.position
    property string stageText: controller.busy ? "正在辨析，请稍候" : controller.hasResult ? "辨析已毕，请查阅结果" : controller.fileName ? "文件已就绪，静候辨析" : "以静听万象，以慧辨真伪"

    function showPage(page) {
        player.pause()
        activePage = page
        if (page === "results") controller.ensureDetail()
    }
    Shortcut { sequence: "Ctrl+O"; onActivated: controller.chooseFile("image") }
    Shortcut { sequence: "Ctrl+Shift+O"; onActivated: controller.chooseFile("video") }
    Shortcut { sequence: "Ctrl+H"; enabled: !window.pet; onActivated: window.showPage("history") }
    Shortcut { sequence: "Ctrl+R"; enabled: !window.pet; onActivated: window.showPage("results") }
    Shortcut { sequence: "F1"; enabled: !window.pet; onActivated: guideDialog.open() }
    Connections {
        target: controller
        function onSettingsChanged() { Qt.callLater(window.refreshMotionPreference) }
        function onChanged() { if (controller.busy) player.pause() }
        function onMediaOpened() {
            resultsPage.zoom = 1
            window.showPage("workspace")
        }
    }

    Rectangle {
        id: surface
        anchors.fill: parent
        visible: !window.pet
        color: "#f3f1e8"; radius: 23
        border.color: "#e1dfd3"; border.width: 1
    }

    Loader {
        id: courtyardLoader
        objectName: "courtyardLoader"
        x: 1; y: 1; width: parent.width - 2; height: parent.height - 2
        active: !window.pet && window.activePage === "workspace"
        source: "InkCourtyard.qml"
        onLoaded: {
            item.reducedMotion = Qt.binding(function() { return window.reduced })
            item.gaze = Qt.binding(function() { return creature.gaze })
        }
    }

    Rectangle {
        id: header
        visible: !window.pet
        x: 1; y: 1; width: parent.width - 2; height: 78
        radius: 23; color: window.activePage === "workspace" ? "#d9fcfbf7" : "#fcfbf7"
        Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 24; color: parent.color }
        MouseArea { anchors.fill: parent; onPressed: window.startSystemMove(); onDoubleClicked: window.visibility === Window.Maximized ? window.showNormal() : window.showMaximized() }
        Row {
            x: 30; anchors.verticalCenter: parent.verticalCenter; spacing: 12
            Image { objectName: "brandMark"; readonly property bool assetReady: status === Image.Ready; source: "brand.png"; sourceSize: Qt.size(84, 84); mipmap: true; width: 42; height: 42; anchors.verticalCenter: parent.verticalCenter }
            Text { text: "谛听"; font.family: "SimSun"; font.pixelSize: 27; font.bold: true; color: window.ink; anchors.verticalCenter: parent.verticalCenter }
            Rectangle { width: 1; height: 24; color: "#d8c9a8"; anchors.verticalCenter: parent.verticalCenter }
            Column { spacing: 3; anchors.verticalCenter: parent.verticalCenter
                Text { text: "青玉守真"; font.family: "SimSun"; font.pixelSize: 17; font.letterSpacing: 3; color: window.ink }
                Text { text: "FACEGUARD · 慧眼辨伪"; font.pixelSize: 9; font.letterSpacing: 1; color: window.muted }
            }
        }
        Row { anchors.right: parent.right; anchors.rightMargin: 20; anchors.verticalCenter: parent.verticalCenter; spacing: 6
            Text { text: "◉  本机处理"; font.pixelSize: 12; color: window.muted; anchors.verticalCenter: parent.verticalCenter; rightPadding: 16 }
            AppButton { objectName: "guideEntry"; text: "使用说明"; quiet: true; implicitWidth: 80; onClicked: guideDialog.open() }
            AppButton { objectName: "historyEntry"; text: "历史"; primary: window.activePage === "history"; quiet: window.activePage !== "history"; implicitWidth: 58; onClicked: window.showPage("history") }
            AppButton { objectName: "settingsEntry"; text: "设置"; quiet: true; implicitWidth: 58; onClicked: settingsDialog.open() }
            AppButton { text: "收为桌宠 ↘"; quiet: true; implicitWidth: 110; enabled: !controller.petTransitioning; onClicked: controller.togglePet() }
            AppButton { text: "—"; quiet: true; implicitWidth: 36; onClicked: window.showMinimized(); Accessible.name: "最小化" }
            AppButton { text: "×"; quiet: true; implicitWidth: 36; onClicked: Qt.quit(); Accessible.name: "退出应用" }
        }
    }

    Item {
        id: workbench
        visible: !window.pet && window.activePage === "workspace"
        anchors.fill: parent
        Text { x: 36; y: 104; text: "万象有声，真伪有迹。"; font.family: "SimSun"; font.pixelSize: 25; font.letterSpacing: 2; color: window.ink }
        Text { x: 37; y: 144; text: "选择一份媒体，让辨析从这里开始。"; font.family: "Microsoft YaHei UI"; font.pixelSize: 12; color: window.muted }
        Rectangle { x: parent.width - 217; y: 119; width: 180; height: 30; radius: 15; color: "#e6eade"
            Text { anchors.centerIn: parent; text: "正式项目  /  本机双项检测"; color: window.ink; font.pixelSize: 11 }
        }

        Rectangle {
            id: mediaCard
            x: 36; y: 191; width: 286; height: parent.height - 310
            radius: 20; color: "#fcfbf7"; border.color: dropArea.containsDrag ? "#729786" : "#e4e2d7"; border.width: dropArea.containsDrag ? 2 : 1
            ColumnLayout {
                anchors.fill: parent; anchors.margins: 18; spacing: 15
                RowLayout { Layout.fillWidth: true
                    Text { text: "待检测文件"; font.family: "SimSun"; font.pixelSize: 20; font.bold: true; color: window.ink }
                    Item { Layout.fillWidth: true }
                    AppButton { text: "清除"; quiet: true; implicitWidth: 48; implicitHeight: 32; enabled: !!controller.fileName && !controller.busy; onClicked: controller.clearFile() }
                }
                RowLayout { Layout.fillWidth: true; spacing: 8
                    AppButton { objectName: "choosePhoto"; text: "＋ 选择照片"; enabled: !controller.busy; Layout.fillWidth: true; primary: controller.mediaKind === "image"; onClicked: controller.chooseFile("image") }
                    AppButton { objectName: "chooseVideo"; text: "▷ 选择视频"; enabled: !controller.busy; Layout.fillWidth: true; primary: controller.mediaKind === "video"; onClicked: controller.chooseFile("video") }
                }
                ColumnLayout { visible: !!controller.fileName; Layout.fillWidth: true; spacing: 5
                    Text { text: controller.fileName; color: window.ink; font.pixelSize: 13; font.bold: true; elide: Text.ElideMiddle; Layout.fillWidth: true }
                    Text { text: controller.metadata; color: window.muted; font.pixelSize: 10; wrapMode: Text.Wrap; Layout.fillWidth: true }
                }
                Rectangle {
                    id: previewArea
                    Layout.fillWidth: true; Layout.fillHeight: true; Layout.minimumHeight: 155
                    radius: 14; color: "#efefe5"; border.color: "#e1e5d9"; clip: true
                    Column { anchors.centerIn: parent; spacing: 14; visible: !controller.fileName; width: parent.width - 26
                        Text { anchors.horizontalCenter: parent.horizontalCenter; text: "＋"; font.pixelSize: 46; color: "#8da997" }
                        Text { anchors.horizontalCenter: parent.horizontalCenter; text: "拖入照片或视频"; font.family: "SimSun"; font.pixelSize: 17; color: window.ink }
                        Text { anchors.horizontalCenter: parent.horizontalCenter; text: "或使用上方按钮选择文件"; font.pixelSize: 11; color: window.muted }
                    }
                    Image { id: photo; objectName: "mediaImage"; anchors.fill: parent; anchors.margins: 5; source: controller.mediaKind === "image" ? controller.previewUrl : ""; visible: controller.mediaKind === "image" && !!controller.fileName; fillMode: Image.PreserveAspectFit; autoTransform: true; sourceSize.width: 1000; asynchronous: true
                        onStatusChanged: if (status === Image.Error) controller.showError("照片预览失败，请尝试其他文件。")
                    }
                    MediaPlayer {
                        id: player
                        objectName: "mediaPlayer"
                        source: controller.mediaKind === "video" ? controller.previewUrl : ""
                        videoOutput: videoOutput
                        // Preview is silent: disable decoding, rather than mute an
                        // audio sink that still creates an FFmpeg resampler.
                        activeAudioTrack: -1
                        onTracksChanged: activeAudioTrack = -1
                        onErrorOccurred: function(error, errorString) { controller.showError("视频预览失败：" + errorString) }
                    }
                    VideoOutput { id: videoOutput; anchors.fill: parent; visible: controller.mediaKind === "video" && !!controller.fileName; fillMode: VideoOutput.PreserveAspectFit }
                    AppButton { anchors.centerIn: parent; visible: controller.mediaKind === "video" && !!controller.fileName; text: player.playbackState === MediaPlayer.PlayingState ? "Ⅱ 暂停预览" : "▷ 播放预览"; onClicked: player.playbackState === MediaPlayer.PlayingState ? player.pause() : player.play() }
                }
                RowLayout { Layout.fillWidth: true
                    Text { text: controller.hasResult ? "原始媒体 · 已有检测记录" : controller.fileName ? "原始媒体 · 尚未完成检测" : "JPG / PNG / WEBP / MP4 等"; font.pixelSize: 10; color: window.muted; Layout.fillWidth: true; wrapMode: Text.Wrap }
                    AppButton { text: "放大 ↗"; implicitWidth: 64; implicitHeight: 32; quiet: true; enabled: !!controller.fileName && controller.mediaKind === "image"; onClicked: previewDialog.open() }
                }
            }
            DropArea { id: dropArea; anchors.fill: parent; onDropped: function(drop) { if (drop.urls.length === 1) controller.dropFile(drop.urls[0]); else controller.showError("每次请选择一个照片或视频文件。"); } }
        }

        Rectangle {
            id: resultsCard
            x: parent.width - width - 36; y: 191; width: 286; height: parent.height - 310
            radius: 20; color: "#fcfbf7"; border.color: "#e4e2d7"
            ColumnLayout {
                anchors.fill: parent; anchors.margins: window.height < 800 ? 18 : 22; spacing: window.height < 800 ? 9 : 18
                RowLayout { Layout.fillWidth: true
                    Text { text: "Ⅱ"; color: window.gold; font.pixelSize: 22 }
                    Text { text: "结果概览"; color: window.ink; font.family: "SimSun"; font.pixelSize: 21; font.bold: true }
                    Item { Layout.fillWidth: true }
                    Text { text: "☁"; color: "#d5c5a4"; font.pixelSize: 24 }
                }
                Rectangle { Layout.fillWidth: true; height: 1; color: "#e5e2d6" }
                Repeater {
                    model: ["AI 整脸生成", "换脸 / 面部篡改"]
                    ResultSummaryCard {
                        required property string modelData
                        required property int index
                        Layout.fillWidth: true; Layout.preferredHeight: 104
                        title: modelData
                        summary: index === 0 ? controller.generationSummary : controller.manipulationSummary
                        state: index === 0 ? controller.generationState : controller.manipulationState
                    }
                }

                Text { text: controller.busy ? "正在辨析，结果会显示在这里。" : controller.hasResult ? "两项结果分别查看；未检出不等于保证真实。" : "完成检测后，在此查看结果。"; color: window.muted; font.pixelSize: 12; Layout.fillWidth: true; wrapMode: Text.Wrap }
                Item { Layout.fillHeight: true }
                AppButton { objectName: "resultsEntry"; text: "查看结果与热力图  ↗"; primary: true; Layout.fillWidth: true; implicitHeight: window.height < 800 ? 36 : 44; onClicked: window.showPage("results") }
            }
        }

        Rectangle {
            x: mediaCard.x + mediaCard.width + 12; y: parent.height - 312
            width: resultsCard.x - x - 12; height: 232
            radius: 24; color: "#b8f8f6ee"
        }
        Column {
            x: mediaCard.x + mediaCard.width + 16; y: parent.height - 297
            width: resultsCard.x - x - 16; spacing: 15
            Text { width: parent.width; horizontalAlignment: Text.AlignHCenter; text: window.stageText; font.family: "SimSun"; font.pixelSize: window.width < 1200 ? 22 : 29; font.letterSpacing: 1; color: window.ink }
            Row { anchors.horizontalCenter: parent.horizontalCenter; spacing: 12
                Repeater { model: ["读取文件", "检测人脸", "分析特征"]
                    Row { required property string modelData; required property int index; spacing: 12
                        Text { text: (index + 1).toString().padStart(2, "0") + "  " + modelData; font.pixelSize: 11; color: controller.fileName && index === 0 ? window.ink : "#929a8c" }
                        Rectangle { visible: index < 2; width: window.width < 1200 ? 10 : 22; height: 1; color: "#c8cdbb"; anchors.verticalCenter: parent.verticalCenter }
                    }
                }
            }
            Row { anchors.horizontalCenter: parent.horizontalCenter; spacing: 10
                AppButton { objectName: "startDetection"; text: controller.busy ? (controller.cancelling ? "正在取消" : "取消检测") : "开始检测"; primary: true; enabled: controller.busy ? !controller.cancelling : !!controller.fileName && controller.engineReady; implicitWidth: 135; onClicked: controller.busy ? controller.cancelDetection() : controller.startDetection() }
            }
            Text { text: (controller.progressText || controller.engineStatus) + "\n生成模型：" + controller.generationModelLabel; width: parent.width; wrapMode: Text.Wrap; horizontalAlignment: Text.AlignHCenter; color: window.muted; font.pixelSize: 10 }
        }
        Text { x: 37; y: parent.height - 86; width: parent.width - 74; text: controller.errorText; color: "#9c6335"; font.pixelSize: 12; wrapMode: Text.Wrap }
        Rectangle { x: 36; y: parent.height - 57; width: parent.width - 72; height: 1; color: "#dfded0" }
        Text { x: 37; y: parent.height - 38; text: "ⓘ  分数为模型倾向，不是真假概率。"; color: window.muted; font.pixelSize: 11 }
        Text { anchors.right: parent.right; anchors.rightMargin: 37; y: parent.height - 38; text: "本机读取 · 媒体不上传"; color: window.muted; font.pixelSize: 11 }
    }

    HistoryPage {
        visible: !window.pet && window.activePage === "history"
        x: 32; y: 108; width: window.width - 64; height: window.height - 145
        onBackRequested: window.showPage("workspace")
        onFileOpened: window.showPage("workspace")
    }
    ResultPage {
        id: resultsPage
        visible: !window.pet && window.activePage === "results"
        x: 32; y: 108; width: window.width - 64; height: window.height - 145
        onBackRequested: window.showPage("workspace")
    }

    // The same skinned character and motion state are retained across workspace/pet modes.
    Item {
        id: characterStage
        objectName: "characterStage"
        visible: window.pet || window.activePage === "workspace"
        x: window.pet ? 0 : 330
        y: window.pet ? 38 : 173
        width: window.pet ? window.width : window.width - 660
        height: window.pet ? window.height - 90 : window.height - 482
        DitingAvatar {
            id: creature
            objectName: "ditingCharacter"
            anchors.fill: parent
            waterSurface: !window.pet
            reducedMotion: window.reduced
            listening: controller.busy && !window.reduced ? 1 : 0
            motion: controller.busy ? "listening" : controller.fileName ? "ready" : "idle"
        }
        MouseArea {
            id: characterMouse
            anchors.fill: parent; acceptedButtons: Qt.LeftButton | Qt.RightButton
            hoverEnabled: true
            property real pressX: 0
            property real pressY: 0
            property bool dragged: false
            cursorShape: window.pet ? Qt.SizeAllCursor : Qt.PointingHandCursor
            onPressed: function(mouse) {
                pressX = mouse.x; pressY = mouse.y; dragged = false
                if (mouse.button === Qt.RightButton) petMenu.popup()
            }
            onPositionChanged: function(mouse) {
                creature.gaze = controller.busy ? 0 : Math.max(-1, Math.min(1, (mouse.x / width - 0.5) * 2))
                if (window.pet && pressed && !dragged && Math.abs(mouse.x - pressX) + Math.abs(mouse.y - pressY) > 10) {
                    dragged = true; window.startSystemMove()
                }
            }
            onExited: creature.gaze = 0
            onClicked: function(mouse) { if (mouse.button === Qt.LeftButton && !dragged && !controller.busy) creature.respond() }
            onDoubleClicked: if (!controller.petTransitioning) controller.togglePet()
            ToolTip.visible: containsMouse && !pressed && !controller.busy
            ToolTip.delay: 1100
            ToolTip.text: window.pet ? "拖动可停靠，双击展开；右键查看更多" : "点击回应，双击收为桌宠"
        }
        DropArea { anchors.fill: parent; onDropped: function(drop) { if (drop.urls.length === 1) controller.dropFile(drop.urls[0]); else controller.showError("每次请选择一个文件。"); } }
    }

    Item {
        anchors.fill: parent
        visible: window.pet
        // Observe the whole pet area without taking clicks or dragging away
        // from the character. Keep hover while moving onto either toolbar.
        HoverHandler { id: petHover }
        Column {
            objectName: "petHint"
            visible: petHover.hovered
            anchors.horizontalCenter: parent.horizontalCenter; y: 6; spacing: 4
            Rectangle { width: 230; height: 37; color: "#fcfbf7"; radius: 18; border.color: "#dfe1d4"
                Text { anchors.centerIn: parent; text: "要辨析时，叫我一声。"; font.family: "SimSun"; font.pixelSize: 15; color: window.ink }
            }
        }
        Row {
            objectName: "petActions"
            visible: petHover.hovered
            anchors.horizontalCenter: parent.horizontalCenter; anchors.bottom: parent.bottom; anchors.bottomMargin: 10; spacing: 5
            AppButton { objectName: "petPhoto"; text: "照片"; implicitWidth: 66; onClicked: controller.chooseFile("image") }
            AppButton { objectName: "petVideo"; text: "视频"; implicitWidth: 66; onClicked: controller.chooseFile("video") }
            AppButton { objectName: "petExpand"; text: "展开 ↗"; implicitWidth: 79; enabled: !controller.petTransitioning; onClicked: controller.togglePet() }
        }
    }
    Menu {
        id: petMenu
        padding: 8
        background: Rectangle { color: "#fcfbf7"; radius: 16; border.color: "#cbd7ca" }
        MenuItem { text: "打开工作台"; onTriggered: controller.showWorkbench() }
        MenuItem { text: "选择照片"; onTriggered: controller.chooseFile("image") }
        MenuItem { text: "选择视频"; onTriggered: controller.chooseFile("video") }
        MenuSeparator { }
        MenuItem { text: "减少动态效果"; checkable: true; checked: window.reduced; onTriggered: controller.toggleReducedMotion() }
        MenuItem { text: "始终置顶"; checkable: true; checked: controller.topmost; onTriggered: controller.toggleTopmost() }
        MenuItem { text: "暂时隐藏（从托盘恢复）"; onTriggered: controller.hideWindow() }
        MenuItem { text: "退出"; onTriggered: Qt.quit() }
    }
    AppDialog {
        id: guideDialog; objectName: "guideDialog"
        width: 660; title: "使用说明"
        eyebrow: "使用说明 / GET STARTED"
        subtitle: "三个步骤，查看照片与视频中的可疑线索。"
        confirmText: "开始使用"; footerNote: "本机处理 · 媒体不上传"
        contentItem: ScrollView {
            implicitHeight: guideContent.implicitHeight
            contentWidth: availableWidth; clip: true
            ScrollBar.vertical.active: true
            ColumnLayout {
                id: guideContent; width: parent.width; spacing: 12
                InfoCard { Layout.fillWidth: true; marker: "01"; title: "选一张照片，或一段视频"; body: "点击选择文件，也可以直接拖入工作台。照片支持放大，视频可静音预览。" }
                InfoCard { Layout.fillWidth: true; marker: "02"; title: "点击检测，谛听俯耳倾听"; body: "辨析与倾听动作同时开始，结束后回到待机。右侧先显示结果概览，点击查看按钮再进入详细结果。" }
                InfoCard { Layout.fillWidth: true; marker: "03"; title: "细看线索，保存报告"; body: "逐脸查看生成与篡改结果，视频可查看采样帧。报告默认 PDF，也可选 TXT；历史记录可重新打开。" }
                Text { Layout.fillWidth: true; text: "未检出不代表真实，分数不是真假概率。选择人脸可查看对应检测项目的关注热力图；颜色不代表精确篡改边界。"; wrapMode: Text.Wrap; font.pixelSize: 13; lineHeight: 1.5; color: "#8c744c" }
            }
        }
    }
    AppDialog {
        id: settingsDialog; objectName: "settingsDialog"
        width: 600; title: "工作空间设置"
        eyebrow: "工作空间设置 / PREFERENCES"
        subtitle: "显示、角色与检测偏好，集中管理。"
        footerNote: "偏好自动保存在本机"; confirmText: "完成设置"
        contentItem: ScrollView {
            implicitHeight: settingsContent.implicitHeight
            contentWidth: availableWidth; clip: true
            ScrollBar.vertical.active: true
            ColumnLayout {
                id: settingsContent; width: parent.width; spacing: 14
                InfoCard { Layout.fillWidth: true; marker: "◎"; title: "当前模型 · " + controller.generationModelLabel; body: controller.generationModelNotice }
                Rectangle {
                    Layout.fillWidth: true; implicitHeight: preferences.implicitHeight + 24
                    radius: 16; color: "#f1f3eb"; border.color: "#e0e6d8"
                    ColumnLayout {
                        id: preferences; x: 16; y: 12; width: parent.width - 32; spacing: 6
                        AppSwitch { objectName: "reducedMotionSwitch"; text: "减少动态效果"; checked: window.reduced; onClicked: controller.toggleReducedMotion() }
                        Rectangle { Layout.fillWidth: true; height: 1; color: "#dfe5d7" }
                        AppSwitch { objectName: "topmostSwitch"; text: "窗口始终置顶"; checked: controller.topmost; onClicked: controller.toggleTopmost() }
                    }
                }
                RowLayout {
                    Layout.fillWidth: true; spacing: 10
                    AppButton { objectName: "volumePreviewEntry"; text: "角色立体预览  ↗"; Layout.fillWidth: true; onClicked: { settingsDialog.close(); volumeDialog.open() } }
                    AppButton { objectName: "technicalDetails"; text: "技术详情  ↗"; Layout.fillWidth: true; onClicked: { settingsDialog.close(); detailsDialog.open() } }
                }
                AppButton {
                    id: advancedToggle; objectName: "advancedModelOptions"; Layout.fillWidth: true
                    property bool expanded: false
                    text: expanded ? "收起高级选项  ▴" : "高级选项 · 实验模型  ▾"
                    quiet: true; onClicked: expanded = !expanded
                }
                ColumnLayout {
                    visible: advancedToggle.expanded; Layout.fillWidth: true; spacing: 10
                    Text { Layout.fillWidth: true; text: "实验模型用于对照评测，日常无需切换。不同候选在检出率与误报之间各有取舍。"; font.pixelSize: 13; wrapMode: Text.Wrap; color: window.muted }
                    AppComboBox {
                        objectName: "generationModelSelector"
                        Layout.fillWidth: true; enabled: !controller.busy
                        model: controller.generationModels; textRole: "label"
                        currentIndex: controller.generationModelIndex
                        onActivated: function(index) { controller.setGenerationModel(index) }
                    }
                    Text { Layout.fillWidth: true; text: "切换后需重新检测，历史结果保留。"; font.pixelSize: 13; wrapMode: Text.Wrap; color: window.muted }
                }
                Text { Layout.fillWidth: true; text: "历史只保存文件路径与检测记录，不复制媒体，可从“历史”中删除。"; font.pixelSize: 12; wrapMode: Text.Wrap; color: "#758674"; lineHeight: 1.5 }
            }
        }
    }
    AppDialog {
        id: volumeDialog
        objectName: "volumePreviewDialog"
        parent: Overlay.overlay; anchors.centerIn: parent
        width: Math.min(720, window.width - 80); height: Math.min(720, window.height - 50)
        title: "谛听 · 立体预览"; eyebrow: "角色空间 / DITING"; confirmText: "收起预览"
        ColumnLayout {
            anchors.fill: parent; spacing: 8
            Item {
                Layout.fillWidth: true; Layout.fillHeight: true
                Loader {
                    id: volumeLoader; objectName: "volumePreviewLoader"
                    anchors.fill: parent; active: volumeDialog.visible
                    asynchronous: true; source: "DitingVolume.qml"
                    onLoaded: item.reducedMotion = Qt.binding(function() { return window.reduced })
                }
                BusyIndicator { anchors.centerIn: parent; running: volumeLoader.status === Loader.Loading }
                Text {
                    anchors.centerIn: parent; color: window.muted
                    visible: volumeLoader.status === Loader.Error || (volumeLoader.item && volumeLoader.item.loadFailed)
                    text: "暂时无法加载立体角色。"; font.pixelSize: 14
                }
            }
            RowLayout {
                Layout.alignment: Qt.AlignHCenter; spacing: 10
                enabled: !window.reduced && volumeLoader.item && volumeLoader.item.assetReady
                AppButton { text: "待机呼吸"; quiet: true; onClicked: volumeLoader.item.playMotion("Idle") }
                AppButton { text: "点头回应"; quiet: true; onClicked: volumeLoader.item.playMotion("Respond") }
                AppButton { text: "侧耳倾听"; quiet: true; onClicked: volumeLoader.item.playMotion("Listen") }
                AppButton { text: volumeLoader.item && volumeLoader.item.userPaused ? "继续" : "暂停"; quiet: true; onClicked: volumeLoader.item.togglePause() }
            }
            RowLayout {
                Layout.alignment: Qt.AlignHCenter; spacing: 12
                AppButton { text: "向左转"; quiet: true; onClicked: if (volumeLoader.item) volumeLoader.item.turn(-25) }
                AppButton { text: "恢复朝向"; quiet: true; onClicked: if (volumeLoader.item) volumeLoader.item.resetOrientation() }
                AppButton { text: "向右转"; quiet: true; onClicked: if (volumeLoader.item) volumeLoader.item.turn(25) }
            }
            Text { Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter; text: window.reduced ? "已开启减少动态效果，角色保持静止 · 可拖动或滚轮旋转" : "拖动或滚轮旋转 · 眨眼、大幅点头、转头倾听"; color: window.muted; font.pixelSize: 12 }
        }
    }
    AppDialog {
        id: detailsDialog; objectName: "technicalDetailsDialog"
        width: 660; title: "技术与能力说明"
        eyebrow: "技术详情 / ABOUT"; confirmText: "了解了"
        contentItem: ScrollView {
            implicitHeight: technicalContent.implicitHeight
            contentWidth: availableWidth; clip: true
            ScrollBar.vertical.active: true
            ColumnLayout {
                id: technicalContent; width: parent.width; spacing: 12
                InfoCard { Layout.fillWidth: true; marker: "◎"; title: "模型与媒体"; body: "当前生成模型：" + controller.generationModelLabel + "\n视频同时检查生成与篡改：生成项使用照片模型分析采样人脸，尚未标定整段视频结论；篡改项保留 FF++ 的 16 帧基线与局部复核。采样间隙仍可能漏检，普通照片篡改结果仅作复核线索。" }
                InfoCard { Layout.fillWidth: true; marker: "◇"; title: "能力与边界"; body: "工作台、桌宠与立体预览均为 23 骨骼坐姿角色，支持眨眼、回应和检测倾听。热力图展示所选人脸的模型关注区域。张嘴表演与四足行走尚待完善。分数是模型倾向，不是真假概率。" }
                Text { Layout.fillWidth: true; text: "FaceGuard " + controller.appVersion + "\nPySide6 / Qt Quick · 本机 SQLite 历史 · PDF / TXT 报告\n独立推理模块与本地资源，不依赖参考项目运行。"; wrapMode: Text.Wrap; color: "#6c806e"; font.pixelSize: 12; lineHeight: 1.5 }
            }
        }
    }
    AppDialog {
        id: previewDialog
        objectName: "mediaPreviewDialog"
        parent: Overlay.overlay; anchors.centerIn: parent
        width: window.width - 100; height: window.height - 90; modal: true
        title: controller.fileName; eyebrow: "媒体预览 / PREVIEW"; confirmText: "关闭预览"
        Image { anchors.fill: parent; source: previewDialog.visible ? controller.previewUrl : ""; autoTransform: true; fillMode: Image.PreserveAspectFit; sourceSize.width: 2400 }
    }
    MouseArea { visible: !window.pet; width: 18; height: 18; anchors.right: parent.right; anchors.bottom: parent.bottom; cursorShape: Qt.SizeFDiagCursor; onPressed: window.startSystemResize(Qt.RightEdge | Qt.BottomEdge) }
}
