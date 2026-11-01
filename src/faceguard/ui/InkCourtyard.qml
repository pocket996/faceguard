import QtQuick
import QtQuick3D

Item {
    id: courtyard
    objectName: "inkCourtyard"
    property bool reducedMotion: false
    property real gaze: 0
    readonly property real parallax: reducedMotion ? 0 : gaze
    readonly property bool assetReady: garden.status === Image.Ready
    readonly property string representation: "Ink landscape backplate with actual Qt Quick 3D textured stone terrace"
    clip: true

    Image {
        id: garden
        objectName: "courtyardLandscape"
        x: -8 - courtyard.parallax * 4; y: -3
        width: parent.width + 16; height: parent.height + 8
        source: "assets/ink-courtyard-v1.png"
        asynchronous: true; fillMode: Image.PreserveAspectCrop
        sourceSize.width: 1600
    }

    View3D {
        id: terraceView
        objectName: "courtyardTerrace3D"
        x: 0; y: parent.height * 0.48
        width: parent.width; height: parent.height * 0.52
        camera: terraceCamera
        environment: SceneEnvironment {
            backgroundMode: SceneEnvironment.Transparent
            antialiasingMode: SceneEnvironment.MSAA
            antialiasingQuality: SceneEnvironment.Medium
        }
        Node { id: terraceAim; position: Qt.vector3d(0, 0, 0) }
        OrthographicCamera {
            id: terraceCamera
            objectName: "courtyardCamera"
            position: Qt.vector3d(courtyard.parallax * 22, 420, 850)
            lookAtNode: terraceAim
            clipNear: 1; clipFar: 2200
            horizontalMagnification: Math.max(0.01, Math.min(terraceView.width / 650, terraceView.height / 230))
            verticalMagnification: horizontalMagnification
        }
        DirectionalLight {
            eulerRotation: Qt.vector3d(-55, -28, 0)
            brightness: 0.7; color: "#fffdfa"; ambientColor: "#d8d8d5"
            castsShadow: true; shadowFactor: 24
        }
        DirectionalLight { eulerRotation: Qt.vector3d(-25, 135, 0); brightness: 0.25; color: "#dce8de" }

        DefaultMaterial {
            id: stone
            diffuseColor: "#ffffff"; specularAmount: 0
            diffuseMap: Texture { source: "assets/ink-courtyard-stone-v1.png"; scaleU: 1; scaleV: 1 }
        }
        DefaultMaterial { id: stoneSide; diffuseColor: "#a6a69e"; diffuseMap: stone.diffuseMap; specularAmount: 0 }
        DefaultMaterial { id: stoneRim; diffuseColor: "#d2d1c7"; diffuseMap: stone.diffuseMap; specularAmount: 0 }

        Model { objectName: "courtyardLowerStep"; source: "#Cylinder"; position: Qt.vector3d(0, -19, 0); scale: Qt.vector3d(3.8, 0.12, 2.8); materials: stoneSide }
        Model { source: "#Cylinder"; position: Qt.vector3d(0, -12, 0); scale: Qt.vector3d(3.7, 0.04, 2.7); materials: stoneRim }
        Model { source: "#Cylinder"; position: Qt.vector3d(0, -6, 0); scale: Qt.vector3d(3.55, 0.08, 2.55); materials: stoneSide }
        Model { objectName: "courtyardStonePlatform"; source: "#Cylinder"; position: Qt.vector3d(0, 0, 0); scale: Qt.vector3d(3.5, 0.04, 2.5); materials: stone }
    }

    // Feather the painting into the app paper without a rectangular picture frame.
    Rectangle {
        width: Math.min(45, parent.width * 0.07); height: parent.height
        gradient: Gradient { orientation: Gradient.Horizontal; GradientStop { position: 0; color: "#f3f1e8" } GradientStop { position: 1; color: "#00f3f1e8" } }
    }
    Rectangle {
        anchors.right: parent.right; width: Math.min(45, parent.width * 0.07); height: parent.height
        gradient: Gradient { orientation: Gradient.Horizontal; GradientStop { position: 0; color: "#00f3f1e8" } GradientStop { position: 1; color: "#f3f1e8" } }
    }
    Rectangle {
        width: parent.width; height: 24
        gradient: Gradient { GradientStop { position: 0; color: "#f3f1e8" } GradientStop { position: 1; color: "#00f3f1e8" } }
    }
    Rectangle {
        anchors.bottom: parent.bottom; width: parent.width; height: 24
        gradient: Gradient { GradientStop { position: 0; color: "#00f3f1e8" } GradientStop { position: 1; color: "#f3f1e8" } }
    }
}
