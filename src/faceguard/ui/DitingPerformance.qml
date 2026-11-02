import QtQuick
import QtQuick3D
import "assets/diting-motion-v6" as Character

Node {
    id: actor
    property bool reducedMotion: false
    property bool active: true
    property bool detecting: false
    property real blendProgress: 0
    property real listenPhase: 0
    property string pendingMotion: "Idle"
    readonly property bool ready: character.ready
    readonly property string motionName: blend.running ? pendingMotion : character.clipName
    readonly property real motionTime: character.clipTime
    readonly property bool transitioning: blend.running
    readonly property bool holdingListen: hold.running
    readonly property bool playing: (playback.running || blend.running || hold.running) && active && !reducedMotion

    function stop() { playback.stop(); blend.stop(); hold.stop() }
    function respond() { if (!detecting && !reducedMotion) select("Respond") }
    function select(name) {
        if (!ready) return
        stop()
        if (reducedMotion) { character.resetAndSelect(""); return }
        pendingMotion = name
        character.prepareTransition(name, 0)
        blendProgress = 0
        blend.start()
        syncPause()
    }
    function startClip() {
        character.resetAndSelect(pendingMotion)
        playback.from = 0
        playback.to = pendingMotion === "Listen" && detecting ? 1650 : character.clipDuration
        playback.duration = playback.to
        playback.loops = pendingMotion === "Idle" ? Animation.Infinite : 1
        playback.start()
        syncPause()
    }
    function syncPause() {
        if (playback.running) playback.paused = !active
        if (blend.running) blend.paused = !active
        if (hold.running) hold.paused = !active
    }
    function seekPose(name, milliseconds) {
        stop()
        character.resetAndSelect(name)
        character.clipTime = Math.max(0, Math.min(character.clipDuration, milliseconds))
    }
    onDetectingChanged: select(detecting ? "Listen" : "Idle")
    onReducedMotionChanged: select(detecting ? "Listen" : "Idle")
    onActiveChanged: syncPause()
    onBlendProgressChanged: if (ready) character.blendToBind(blendProgress)
    onListenPhaseChanged: if (hold.running) {
        character.clipTime = 1650 + 270 * Math.sin(listenPhase)
        character.breathe(listenPhase)
    }
    Component.onCompleted: if (ready) select(detecting ? "Listen" : "Idle")
    NumberAnimation {
        id: blend
        target: actor; property: "blendProgress"; from: 0; to: 1
        duration: 340; easing.type: Easing.InOutSine
        onFinished: actor.startClip()
    }
    NumberAnimation {
        id: playback
        target: character; property: "clipTime"; easing.type: Easing.Linear
        onFinished: {
            if (actor.detecting && character.clipName === "Listen") {
                actor.listenPhase = 0
                hold.start()
                actor.syncPause()
            } else actor.select(actor.detecting ? "Listen" : "Idle")
        }
    }
    NumberAnimation {
        id: hold
        target: actor; property: "listenPhase"; from: 0; to: Math.PI * 2
        duration: 5200; loops: Animation.Infinite
    }
    Character.DitingActingV6 { id: character; objectName: "ditingWorkspaceSkin" }
}
