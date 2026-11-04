import QtQuick

Item {
    id: courtyard
    objectName: "inkCourtyard"
    property bool reducedMotion: false
    property real gaze: 0
    readonly property real parallax: reducedMotion ? 0 : gaze
    readonly property bool assetReady: garden.status === Image.Ready
    readonly property string representation: "Full-window ink landscape and continuous lake, with live 3D character reflection"
    clip: true
    Image {
        id: garden
        objectName: "courtyardLandscape"
        x: -10 - courtyard.parallax * 5; y: -5
        width: parent.width + 20; height: parent.height + 10
        source: "assets/ink-lake-lotus-v3.png"
        asynchronous: true; fillMode: Image.PreserveAspectCrop
        sourceSize.width: 2200
    }
    // Gentle paper veils preserve text readability over the full-window lake.
    Rectangle {
        width: parent.width; height: parent.height * .25
        gradient: Gradient { GradientStop { position: 0; color: "#dcf3f1e8" } GradientStop { position: .65; color: "#b8f3f1e8" } GradientStop { position: 1; color: "#00f3f1e8" } }
    }
    Rectangle {
        anchors.bottom: parent.bottom; width: parent.width; height: parent.height * .40
        gradient: Gradient { GradientStop { position: 0; color: "#00f3f1e8" } GradientStop { position: 1; color: "#e6f3f1e8" } }
    }
}
