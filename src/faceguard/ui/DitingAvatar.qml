import QtQuick
import QtQuick3D

Item {
    id: avatar
    property bool reducedMotion: false
    property real listening: 0
    property string motion: "idle"
    property real gaze: 0
    property bool waterSurface: true
    readonly property bool assetReady: actor.ready
    readonly property string representation: "23-joint skinned 3D character with continuous skeletal performance"
    readonly property real footLine: height * 0.885
    readonly property alias performance: actor
    Behavior on listening { enabled: !avatar.reducedMotion; NumberAnimation { duration: 650; easing.type: Easing.InOutSine } }
    Behavior on gaze { enabled: !avatar.reducedMotion; NumberAnimation { duration: 400; easing.type: Easing.InOutSine } }
    function respond() { actor.respond() }
    // Reuse the actual rendered pose so the reflection has no separate clock.
    ShaderEffectSource {
        id: reflectionSource
        sourceItem: view
        visible: false
        live: avatar.waterSurface && avatar.visible
        textureSize: Qt.size(Math.max(1, view.width), Math.max(1, view.height))
    }
    ShaderEffect {
        objectName: "ditingWaterReflection"
        visible: avatar.waterSurface
        x: 0; y: avatar.footLine - 1
        width: parent.width; height: parent.height * 0.25
        property variant source: reflectionSource
        property real footRatio: 0.885
        property real phase: water.phase
        fragmentShader: "shaders/water-reflection.frag.qsb"
        blending: true
    }
    Canvas {
        id: water
        objectName: "ditingWaterContact"
        visible: avatar.waterSurface
        anchors.fill: parent
        property real phase: 0
        NumberAnimation on phase {
            from: 0; to: Math.PI * 2; duration: 5200; loops: Animation.Infinite
            running: avatar.visible && avatar.waterSurface && !avatar.reducedMotion
        }
        onPhaseChanged: requestPaint()
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        onPaint: {
            var ctx = getContext("2d"); ctx.reset()
            var cx = width * 0.51, cy = avatar.footLine
            ctx.save(); ctx.translate(cx, cy); ctx.scale(width * 0.30, height * 0.029)
            var shade = ctx.createRadialGradient(0, 0, 0, 0, 0, 1)
            shade.addColorStop(0, "rgba(42,71,65,0.26)"); shade.addColorStop(1, "rgba(42,71,65,0)")
            ctx.fillStyle = shade; ctx.fillRect(-1, -1, 2, 2); ctx.restore()
            for (var paw = 0; paw < 3; ++paw) {
                var px = width * (0.40 + paw * 0.105)
                var py = cy + (paw === 1 ? 2 : -1)
                for (var i = 0; i < 2; ++i) {
                    var p = (phase / (Math.PI * 2) + i / 2 + paw * .13) % 1
                    var rx = width * (.035 + p * (.045 + avatar.listening * .025))
                    var ry = height * (.005 + p * .015)
                    ctx.strokeStyle = "rgba(79,119,108," + (1-p) * (.17 + avatar.listening * .12) + ")"
                    ctx.lineWidth = 1
                    ctx.beginPath(); ctx.ellipse(px-rx, py-ry, rx*2, ry*2); ctx.stroke()
                }
            }
        }
    }
    View3D {
        id: view
        objectName: "ditingWorkspaceView"
        anchors.fill: parent
        camera: camera
        environment: SceneEnvironment {
            backgroundMode: SceneEnvironment.Transparent
            antialiasingMode: SceneEnvironment.MSAA
            antialiasingQuality: SceneEnvironment.High
        }
        Node { id: aim; position: Qt.vector3d(0, 1.9, 0) }
        OrthographicCamera {
            id: camera
            position: Qt.vector3d(-5, 2.6, 8)
            lookAtNode: aim
            clipNear: 0.05; clipFar: 40
            horizontalMagnification: Math.max(1, Math.min(view.width / 3.9, view.height / 4.45))
            verticalMagnification: horizontalMagnification
        }
        DirectionalLight { eulerRotation: Qt.vector3d(-40, -35, 0); brightness: .32; color: "#fffaf0"; ambientColor: "#d1dad3" }
        DirectionalLight { eulerRotation: Qt.vector3d(-15, 145, 0); brightness: .22; color: "#dcece6" }
        DitingPerformance {
            id: actor
            objectName: "ditingPerformance"
            reducedMotion: avatar.reducedMotion
            active: avatar.visible
            detecting: avatar.motion === "listening"
        }
    }
}
