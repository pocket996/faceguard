import QtQuick
import QtQuick3D
import "assets/diting-motion-v7" as Character

Item {
    id: volume
    objectName: "ditingVolumePreview"
    property real angle: 0
    property bool reducedMotion: false
    property bool userPaused: false
    property string pendingMotion: ""
    property real blendProgress: 0
    readonly property bool assetReady: character.ready
    readonly property bool loadFailed: false
    readonly property string motionName: transition.running ? pendingMotion : character.clipName
    readonly property real motionTime: character.clipTime
    readonly property bool playing: (playback.running && !playback.paused) || (transition.running && !transition.paused)
    readonly property bool transitioning: transition.running
    function turn(degrees) { angle = (angle + degrees) % 360 }
    function resetOrientation() { angle = 0 }
    function playMotion(name) {
        if (!character.ready || reducedMotion || ["Idle", "Respond", "Listen"].indexOf(name) < 0) return
        playback.stop()
        transition.stop()
        userPaused = false
        pendingMotion = name
        if (character.prepareTransition()) {
            blendProgress = 0
            transition.start()
            syncPause()
        } else startPlayback(name)
    }
    function startPlayback(name) {
        character.resetAndSelect(name)
        playback.from = 0
        playback.to = character.clipDuration
        playback.duration = character.clipDuration
        playback.loops = name === "Idle" ? Animation.Infinite : 1
        playback.start()
        syncPause()
    }
    function syncPause() {
        if (playback.running) playback.paused = userPaused || !visible
        if (transition.running) transition.paused = userPaused || !visible
    }
    function togglePause() { if (!reducedMotion) { userPaused = !userPaused; syncPause() } }
    function seekPose(name, milliseconds) {
        playback.stop()
        transition.stop()
        userPaused = true
        character.resetAndSelect(name)
        character.clipTime = Math.max(0, Math.min(character.clipDuration, milliseconds))
    }
    onVisibleChanged: syncPause()
    onReducedMotionChanged: {
        if (!character.ready) return
        if (reducedMotion) { playback.stop(); transition.stop(); character.resetAndSelect(""); userPaused = false }
        else playMotion("Idle")
    }
    Component.onCompleted: if (character.ready && !reducedMotion) playMotion("Idle")
    onBlendProgressChanged: if (character.ready) character.blendToBind(blendProgress)
    NumberAnimation {
        id: transition
        target: volume; property: "blendProgress"; from: 0; to: 1; duration: 220
        easing.type: Easing.InOutQuad
        onFinished: volume.startPlayback(volume.pendingMotion)
    }
    NumberAnimation {
        id: playback
        target: character; property: "clipTime"
        easing.type: Easing.Linear
        onFinished: if (!volume.reducedMotion && character.clipName !== "Idle") volume.playMotion("Idle")
    }

    View3D {
        id: view
        anchors.fill: parent
        camera: camera
        environment: SceneEnvironment {
            backgroundMode: SceneEnvironment.Transparent
            antialiasingMode: SceneEnvironment.MSAA
            antialiasingQuality: SceneEnvironment.High
        }
        Node { id: aim; objectName: "ditingPreviewAim"; position: Qt.vector3d(0, 1.9, 0) }
        OrthographicCamera {
            id: camera
            objectName: "ditingPreviewCamera"
            position: Qt.vector3d(-5, 2.6, 8)
            lookAtNode: aim
            clipNear: 0.05; clipFar: 40
            horizontalMagnification: Math.max(1, Math.min(view.width / 4.1, view.height / 4.45))
            verticalMagnification: horizontalMagnification
        }
        DirectionalLight {
            eulerRotation: Qt.vector3d(-40, -35, 0)
            brightness: 0.35
            color: "#ffffff"
            ambientColor: "#dfdfd7"
        }
        DirectionalLight { eulerRotation: Qt.vector3d(-15, 145, 0); brightness: 0.25; color: "#f7faf5" }
        Node {
            position: Qt.vector3d(0, 1.9, 0)
            eulerRotation.y: volume.angle
            Character.DitingEyesV7 {
                id: character
                objectName: "ditingRuntimeModel"
                position: Qt.vector3d(0, -1.9, 0)
            }
        }
    }
    MouseArea {
        anchors.fill: parent
        property real lastX: 0
        cursorShape: pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor
        onPressed: function(mouse) { lastX = mouse.x }
        onPositionChanged: function(mouse) {
            if (pressed) { volume.turn((mouse.x - lastX) * 0.5); lastX = mouse.x }
        }
        onWheel: function(wheel) { volume.turn(wheel.angleDelta.y / 8); wheel.accepted = true }
    }
}
