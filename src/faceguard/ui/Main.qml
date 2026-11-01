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
    property bool motionPreview: false
    property real petOffset: 0
    property bool reduced: controller.reducedMotion
    property string activePage: "workspace"
    readonly property bool mediaImageReady: photo.status === Image.Ready
    readonly property bool videoIsPlaying: player.playbackState === MediaPlayer.PlayingState
    readonly property int videoPosition: player.position
    property string stageText: controller.busy ? "正在辨析，请稍候" : motionPreview ? "动作预览 · 非检测" : controller.hasResult ? "辨析已毕，请查阅结果" : controller.fileName ? "文件已就绪，静候辨析" : "以静听万象，以慧辨真伪"

    onPetChanged: {
        if (motionPreview) motionSequence.stop()
        motionPreview = false
        creature.listening = 0
        creature.walking = 0
        petOffset = 0
    }
    onReducedChanged: {
        if (reduced) {
            motionSequence.stop(); motionPreview = false
            creature.listening = 0; creature.walking = 0; petOffset = 0
        }
    }
    function startMotion() {
        if (reduced) { detailsDialog.open(); return }
        motionSequence.restart()
    }
    function showPage(page) {
        player.pause()
        if (motionPreview) {
            motionSequence.stop(); motionPreview = false
            creature.listening = 0; creature.walking = 0; petOffset = 0
        }
        activePage = page
    }
    Shortcut { sequence: "Ctrl+O"; onActivated: controller.chooseFile("image") }
    Shortcut { sequence: "Ctrl+Shift+O"; onActivated: controller.chooseFile("video") }
    Shortcut { sequence: "Ctrl+H"; enabled: !window.pet; onActivated: window.showPage("history") }
    Shortcut { sequence: "Ctrl+R"; enabled: !window.pet; onActivated: window.showPage("results") }
    Shortcut { sequence: "F1"; enabled: !window.pet; onActivated: guideDialog.open() }
    Shortcut { sequence: "Escape"; enabled: window.motionPreview; onActivated: { motionSequence.stop(); window.motionPreview = false; creature.listening = 0; creature.walking = 0; window.petOffset = 0 } }
    Connections {
        target: controller
        function onMediaOpened() {
            resultsPage.heatmapSource = ""
            resultsPage.zoom = 1
            window.showPage("workspace")
        }
        function onDetectionFinished() { window.showPage("results") }
    }

    Rectangle {
        id: surface
        anchors.fill: parent
        visible: !window.pet
        color: "#f3f1e8"; radius: 23
        border.color: "#e1dfd3"; border.width: 1
        // Deliberately quiet celadon horizon, beneath the three working areas.
        Rectangle {
            width: parent.width * 0.7; height: 250
            anchors.horizontalCenter: parent.horizontalCenter; y: parent.height * 0.41
            radius: height / 2; opacity: 0.45
            gradient: Gradient { GradientStop { position: 0; color: "#f3f1e8" } GradientStop { position: 0.65; color: "#e1e7d9" } GradientStop { position: 1; color: "#f3f1e8" } }
        }
    }

    Rectangle {
        id: header
        visible: !window.pet
        x: 1; y: 1; width: parent.width - 2; height: 78
        radius: 23; color: "#fcfbf7"
        Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 24; color: parent.color }
        MouseArea { anchors.fill: parent; onPressed: window.startSystemMove(); onDoubleClicked: window.visibility === Window.Maximized ? window.showNormal() : window.showMaximized() }
        Row {
            x: 30; anchors.verticalCenter: parent.verticalCenter; spacing: 12
            Image { source: "brand.svg"; width: 36; height: 36; anchors.verticalCenter: parent.verticalCenter }
            Text { text: "谛听"; font.family: "SimSun"; font.pixelSize: 27; font.bold: true; color: window.ink; anchors.verticalCenter: parent.verticalCenter }
            Rectangle { width: 1; height: 24; color: "#d8c9a8"; anchors.verticalCenter: parent.verticalCenter }
            Column { spacing: 3; anchors.verticalCenter: parent.verticalCenter
                Text { text: "青玉守真"; font.family: "SimSun"; font.pixelSize: 17; font.letterSpacing: 3; color: window.ink }
                Text { text: "FACEGUARD · 慧眼辨伪"; font.pixelSize: 9; font.letterSpacing: 1; color: window.muted }
            }
        }
        Row { anchors.right: parent.right; anchors.rightMargin: 20; anchors.verticalCenter: parent.verticalCenter; spacing: 6
            Text { text: "◉  本机处理"; font.pixelSize: 12; color: window.muted; anchors.verticalCenter: parent.verticalCenter; rightPadding: 16 }
            AppButton { text: "使用说明"; quiet: true; implicitWidth: 80; onClicked: guideDialog.open() }
            AppButton { objectName: "historyEntry"; text: "历史"; primary: window.activePage === "history"; quiet: window.activePage !== "history"; implicitWidth: 58; onClicked: window.showPage("history") }
            AppButton { text: "设置"; quiet: true; implicitWidth: 58; onClicked: settingsDialog.open() }
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
                        audioOutput: AudioOutput { muted: true }
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
                    Rectangle {
                        required property string modelData
                        required property int index
                        Layout.fillWidth: true
                        Layout.preferredHeight: window.height < 800 ? 78 : 105
                        Layout.minimumHeight: window.height < 800 ? 78 : 105
                        Layout.maximumHeight: window.height < 800 ? 78 : 105
                        radius: 13; color: "#faf9f3"; border.color: "#e5e5da"
                        Row { anchors.left: parent.left; anchors.leftMargin: 13; anchors.verticalCenter: parent.verticalCenter; spacing: 12
                            Rectangle { width: 39; height: 39; radius: 20; color: "#e1e9de"; Text { anchors.centerIn: parent; text: index === 0 ? "◎" : "⌘"; font.pixelSize: 23; color: "#678d79" } }
                            Column { spacing: 10; width: 160
                                Text { text: modelData; font.family: "SimSun"; font.pixelSize: 16; color: window.ink }
                                Text { width: parent.width; wrapMode: Text.Wrap; text: index === 0 ? controller.generationSummary : controller.manipulationSummary; color: window.muted; font.pixelSize: 11 }
                            }
                        }
                    }
                }
                Text { text: controller.hasResult ? "两项结果分别查看；未检出不等于保证真实。" : "未完成检测，不生成结论或分数。"; color: window.muted; font.pixelSize: 11; Layout.fillWidth: true; wrapMode: Text.Wrap }
                Item { Layout.fillHeight: true }
                AppButton { objectName: "resultsEntry"; text: "查看结果与热力图  ↗"; primary: true; Layout.fillWidth: true; implicitHeight: window.height < 800 ? 36 : 44; onClicked: window.showPage("results") }
                AppButton { objectName: "technicalDetails"; text: "技术详情  ↗"; quiet: true; Layout.fillWidth: true; implicitHeight: window.height < 800 ? 34 : 44; onClicked: detailsDialog.open() }
            }
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
                AppButton { text: window.motionPreview ? "停止预览" : "预览倾听动作"; implicitWidth: 142; onClicked: { if (window.motionPreview) { motionSequence.stop(); window.motionPreview = false; creature.listening = 0; creature.walking = 0; window.petOffset = 0 } else window.startMotion() } }
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

    // A single source artwork and mesh are retained across workspace/pet modes.
    Item {
        id: characterStage
        objectName: "characterStage"
        visible: window.pet || window.activePage === "workspace"
        x: window.pet ? 0 : 330
        y: window.pet ? 38 : 173
        width: window.pet ? window.width : window.width - 660
        height: window.pet ? window.height - 90 : window.height - 482
        Canvas {
            anchors.horizontalCenter: parent.horizontalCenter; y: parent.height * 0.78
            width: parent.width * 0.68; height: parent.height * 0.2
            onWidthChanged: requestPaint()
            onHeightChanged: requestPaint()
            onPaint: {
                var ctx = getContext("2d"); ctx.reset()
                ctx.scale(width / 2, height / 2); ctx.translate(1, 1)
                var shade = ctx.createRadialGradient(0, 0, 0, 0, 0, 1)
                shade.addColorStop(0, "rgba(69,91,61,0.16)"); shade.addColorStop(1, "rgba(69,91,61,0)")
                ctx.fillStyle = shade; ctx.fillRect(-1, -1, 2, 2)
            }
        }
        Canvas {
            id: ripples; anchors.fill: parent; opacity: creature.listening * 0.8
            property real phase: 0
            NumberAnimation on phase { from: 0; to: 1; duration: 2400; loops: Animation.Infinite; running: window.motionPreview && !window.reduced }
            onPhaseChanged: requestPaint()
            onWidthChanged: requestPaint()
            onHeightChanged: requestPaint()
            onPaint: {
                var ctx = getContext("2d"); ctx.reset()
                for (var i = 0; i < 3; i++) {
                    var p = (phase + i / 3) % 1
                    ctx.strokeStyle = "rgba(104,150,125," + (1 - p) * 0.4 + ")"
                    ctx.lineWidth = 2
                    ctx.beginPath(); ctx.ellipse(width * 0.13 - p * 35, height * 0.72 - p * 16, 80 + p * 80, 22 + p * 34); ctx.stroke()
                }
            }
        }
        DitingAvatar {
            id: creature
            objectName: "ditingCharacter"
            anchors.fill: parent
            reducedMotion: controller.reducedMotion
            transform: Translate { x: window.petOffset }
            motion: controller.fileName ? "ready" : "idle"
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
                creature.gaze = Math.max(-1, Math.min(1, (mouse.x / width - 0.5) * 2))
                if (window.pet && pressed && !dragged && Math.abs(mouse.x - pressX) + Math.abs(mouse.y - pressY) > 10) {
                    dragged = true; window.startSystemMove()
                }
            }
            onExited: creature.gaze = 0
            onClicked: function(mouse) { if (mouse.button === Qt.LeftButton && !dragged) creature.respond() }
            onDoubleClicked: if (!controller.petTransitioning) controller.togglePet()
            ToolTip.visible: containsMouse && !pressed && !window.motionPreview
            ToolTip.delay: 1100
            ToolTip.text: window.pet ? "拖动可停靠，双击展开；右键查看更多" : "点击回应，双击收为桌宠"
        }
        DropArea { anchors.fill: parent; onDropped: function(drop) { if (drop.urls.length === 1) controller.dropFile(drop.urls[0]); else controller.showError("每次请选择一个文件。"); } }
    }

    Column {
        visible: window.pet
        anchors.horizontalCenter: parent.horizontalCenter; y: 6; spacing: 4
        Rectangle { width: 230; height: 37; color: "#fcfbf7"; radius: 18; border.color: "#dfe1d4"
            Text { anchors.centerIn: parent; text: "要辨析时，叫我一声。"; font.family: "SimSun"; font.pixelSize: 15; color: window.ink }
        }
    }
    Row {
        visible: window.pet
        anchors.horizontalCenter: parent.horizontalCenter; anchors.bottom: parent.bottom; anchors.bottomMargin: 10; spacing: 5
        AppButton { text: "照片"; implicitWidth: 66; onClicked: controller.chooseFile("image") }
        AppButton { text: "视频"; implicitWidth: 66; onClicked: controller.chooseFile("video") }
        AppButton { text: "展开 ↗"; implicitWidth: 79; enabled: !controller.petTransitioning; onClicked: controller.togglePet() }
    }
    Menu {
        id: petMenu
        MenuItem { text: "打开工作台"; onTriggered: controller.showWorkbench() }
        MenuItem { text: "选择照片"; onTriggered: controller.chooseFile("image") }
        MenuItem { text: "选择视频"; onTriggered: controller.chooseFile("video") }
        MenuSeparator { }
        MenuItem { text: "减少动态效果"; checkable: true; checked: controller.reducedMotion; onTriggered: controller.toggleReducedMotion() }
        MenuItem { text: "始终置顶"; checkable: true; checked: controller.topmost; onTriggered: controller.toggleTopmost() }
        MenuItem { text: "暂时隐藏（从托盘恢复）"; onTriggered: controller.hideWindow() }
        MenuItem { text: "退出"; onTriggered: Qt.quit() }
    }
    SequentialAnimation {
        id: motionSequence
        ScriptAction { script: { window.motionPreview = true; creature.walking = 1 } }
        NumberAnimation { target: window; property: "petOffset"; to: -20; duration: 600; easing.type: Easing.InOutSine }
        NumberAnimation { target: window; property: "petOffset"; to: 0; duration: 600; easing.type: Easing.InOutSine }
        ScriptAction { script: { creature.walking = 0; creature.listening = 1 } }
        PauseAnimation { duration: 4200 }
        ScriptAction { script: creature.listening = 0 }
        PauseAnimation { duration: 1100 }
        ScriptAction { script: { creature.respond(); window.motionPreview = false } }
    }

    Dialog {
        id: guideDialog
        parent: Overlay.overlay
        anchors.centerIn: parent; width: 660; modal: true
        title: "谛听 · 使用说明"; standardButtons: Dialog.Ok
        background: Rectangle { color: "#fcfbf7"; radius: 18; border.color: "#dddcca" }
        ColumnLayout { width: parent.width; spacing: 18
            Text { Layout.fillWidth: true; text: "01  选择媒体\n选择或拖入一张照片、一段视频。文件只在本机读取。照片可放大预览，视频可静音播放。"; wrapMode: Text.Wrap; color: window.ink; font.pixelSize: 14; lineHeight: 1.6 }
            Text { Layout.fillWidth: true; text: "02  中央谛听\n角色沿用原效果图的形象，以同一张透明资产做连续网格形变，支持轻呼吸、尾摆、点头与侧倾。动作预览不会进行检测；工作台当前为 2.5D 展示；设置中可查看带眨眼与大幅回应动作的 3D 版本。"; wrapMode: Text.Wrap; color: window.ink; font.pixelSize: 13; lineHeight: 1.5 }
            Text { Layout.fillWidth: true; text: "03  桌宠模式\n点击“收为桌宠”缩小为透明窗口，拖动角色可调整位置。双击或点击“展开”返回工作台，右键可设置、隐藏或退出。隐藏后可从系统托盘恢复。"; wrapMode: Text.Wrap; color: window.ink; font.pixelSize: 14; lineHeight: 1.6 }
            Text { Layout.fillWidth: true; text: "04  检测与历史\n选择媒体后点击“开始检测”；照片分别检查整脸生成和面部篡改，视频检查面部篡改并采样复核。可取消、逐脸查看并保存 JSON / 文本报告；历史记录可重新打开结果。热力图算法尚待实现，导入不等于检测完成。"; wrapMode: Text.Wrap; color: "#967849"; font.pixelSize: 12; lineHeight: 1.5 }
        }
    }
    Dialog {
        id: settingsDialog
        objectName: "settingsDialog"
        parent: Overlay.overlay; anchors.centerIn: parent; width: 470; modal: true
        title: "工作空间设置"; standardButtons: Dialog.Ok
        background: Rectangle { color: "#fcfbf7"; radius: 18; border.color: "#dddcca" }
        ColumnLayout { width: parent.width; spacing: 14
            Text { text: "整脸生成模型"; color: window.ink; font.pixelSize: 13 }
            ComboBox {
                objectName: "generationModelSelector"
                Layout.fillWidth: true; enabled: !controller.busy
                model: controller.generationModels; textRole: "label"
                currentIndex: controller.generationModelIndex
                onActivated: function(index) { controller.setGenerationModel(index) }
            }
            Text { Layout.fillWidth: true; text: controller.generationModelNotice + " 切换后需重新检测；未检出不代表照片真实。"; font.pixelSize: 12; wrapMode: Text.Wrap; color: window.muted }
            CheckBox { text: "减少动态效果"; checked: controller.reducedMotion; onClicked: controller.toggleReducedMotion() }
            CheckBox { text: "窗口始终置顶"; checked: controller.topmost; onClicked: controller.toggleTopmost() }
            AppButton { text: "查看角色立体预览"; implicitWidth: 182; onClicked: { settingsDialog.close(); volumeDialog.open() } }
            Text { Layout.fillWidth: true; text: "桌宠位置和以上偏好保存在本机。历史库保存文件路径、名称、大小与时间，不复制媒体内容，也不上传文件。可在右上角“历史”删除记录或清空。"; font.pixelSize: 12; wrapMode: Text.Wrap; color: window.muted; lineHeight: 1.6 }
        }
    }
    Dialog {
        id: volumeDialog
        objectName: "volumePreviewDialog"
        parent: Overlay.overlay; anchors.centerIn: parent
        width: Math.min(720, window.width - 80); height: Math.min(720, window.height - 50)
        title: "谛听 · 立体预览"; modal: true; standardButtons: Dialog.Close
        background: Rectangle { color: "#f7f5ec"; radius: 18; border.color: "#dddcca" }
        ColumnLayout {
            anchors.fill: parent; spacing: 8
            Item {
                Layout.fillWidth: true; Layout.fillHeight: true
                Loader {
                    id: volumeLoader; objectName: "volumePreviewLoader"
                    anchors.fill: parent; active: volumeDialog.visible
                    asynchronous: true; source: "DitingVolume.qml"
                    onLoaded: item.reducedMotion = Qt.binding(function() { return controller.reducedMotion })
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
                enabled: !controller.reducedMotion && volumeLoader.item && volumeLoader.item.assetReady
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
            Text { Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter; text: controller.reducedMotion ? "已开启减少动态效果，角色保持静止 · 可拖动或滚轮旋转" : "拖动或滚轮旋转 · 眨眼、大幅点头、转头倾听"; color: window.muted; font.pixelSize: 12 }
        }
    }
    Dialog {
        id: detailsDialog
        parent: Overlay.overlay; anchors.centerIn: parent; width: 520; modal: true
        title: "正式项目 · 技术详情"; standardButtons: Dialog.Ok
        background: Rectangle { color: "#fcfbf7"; radius: 18; border.color: "#dddcca" }
        Text { width: parent.width; text: "展示层：PySide6 / Qt Quick\n工作台与桌宠：同源资产 + 2.5D 连续网格形变\n立体预览：20 骨骼蒙皮，眨眼 / 回应 / 倾听\n完整面部表演与四足行走：待完善\n媒体：本机读取，不上传\n历史：本机 SQLite，保存检测结果\n模型：FLUX / SD3.5 生成联合版 + FF++ 篡改基线\n视频：整段16帧基线与有上限的局部复核，可能漏过短事件\n照片篡改：视频帧模型，普通照片误报尚需评测\n报告：JSON / 文本；分数不是真假概率\n热力图：算法尚待实现\n\n正式应用使用独立推理模块和本地资源目录，不依赖 reference_run 运行。"; wrapMode: Text.Wrap; color: window.ink; font.pixelSize: 13; lineHeight: 1.7 }
    }
    Dialog {
        id: previewDialog
        parent: Overlay.overlay; anchors.centerIn: parent
        width: window.width - 100; height: window.height - 90; modal: true
        title: controller.fileName; standardButtons: Dialog.Close
        background: Rectangle { color: "#fcfbf7"; radius: 18; border.color: "#dddcca" }
        Image { anchors.fill: parent; source: previewDialog.visible ? controller.previewUrl : ""; autoTransform: true; fillMode: Image.PreserveAspectFit; sourceSize.width: 2400 }
    }
    MouseArea { visible: !window.pet; width: 18; height: 18; anchors.right: parent.right; anchors.bottom: parent.bottom; cursorShape: Qt.SizeFDiagCursor; onPressed: window.startSystemResize(Qt.RightEdge | Qt.BottomEdge) }
}
