import QtQuick

Item {
    id: avatar
    property bool reducedMotion: false
    property real listening: 0
    property real walking: 0
    property real clock: 0
    property real acknowledgement: 0
    property string motion: "idle"
    property real gaze: 0
    readonly property bool assetReady: artwork.status === Image.Ready
    readonly property real artworkAspect: artwork.implicitWidth / Math.max(1, artwork.implicitHeight)
    readonly property string representation: "2.5D textured mesh; not a rigged 3D model"

    Behavior on listening { NumberAnimation { duration: avatar.reducedMotion ? 0 : 950; easing.type: Easing.InOutSine } }
    Behavior on gaze { NumberAnimation { duration: avatar.reducedMotion ? 0 : 400; easing.type: Easing.InOutSine } }
    onReducedMotionChanged: if (reducedMotion) { nod.stop(); acknowledgement = 0 }
    NumberAnimation on clock { from: 0; to: 6283.185; duration: 1000000; loops: Animation.Infinite; running: true; paused: avatar.reducedMotion || !avatar.visible }
    function respond() { if (!reducedMotion) nod.restart() }
    SequentialAnimation {
        id: nod
        NumberAnimation { target: avatar; property: "acknowledgement"; to: 1; duration: 260; easing.type: Easing.InOutSine }
        NumberAnimation { target: avatar; property: "acknowledgement"; to: 0; duration: 440; easing.type: Easing.InOutSine }
    }
    Image {
        id: artwork
        source: "assets/diting-v2.png"
        visible: false
        asynchronous: true
        sourceSize.width: 1400
    }
    ShaderEffect {
        width: Math.min(parent.width * 0.94, parent.height * 0.92 * avatar.artworkAspect)
        height: width / Math.max(0.01, avatar.artworkAspect)
        anchors.centerIn: parent
        property variant source: artwork
        property real phase: avatar.clock
        property real listen: avatar.listening
        property real acknowledge: avatar.acknowledgement
        property real still: avatar.reducedMotion ? 1 : 0
        property real gaze: avatar.reducedMotion ? 0 : avatar.gaze
        property size itemSize: Qt.size(width, height)
        mesh: GridMesh { resolution: Qt.size(48, 56) }
        vertexShader: "shaders/diting.vert.qsb"
        fragmentShader: "shaders/diting.frag.qsb"
        blending: true
    }
}
