import QtQuick
import QtQuick3D

import QtQuick.Timeline

Node {
    id: node

    // FaceGuard clip controller: one skeletal timeline at a time.
    property string clipName: ""
    property real clipTime: 0
    readonly property real clipDuration: clipName === "Respond" ? 1434 : (clipName === "Listen" ? 3234 : 4834)
    property bool ready: false
    property var bindTransforms: []
    function resetAndSelect(name) {
        clipName = ""
        for (var i = 0; i < skin.joints.length; ++i) {
            var joint = skin.joints[i]
            joint.position = bindTransforms[i].position
            joint.rotation = bindTransforms[i].rotation
            joint.scale = bindTransforms[i].scale
        }
        clipTime = 0
        clipName = name
    }
    Component.onCompleted: {
        for (var i = 0; i < skin.joints.length; ++i) {
            var joint = skin.joints[i]
            bindTransforms.push({position: joint.position, rotation: joint.rotation, scale: joint.scale})
        }
        ready = true
    }

    // Resources
    property url textureData: "maps/textureData.png"
    Texture {
        id: _0_texture
        generateMipmaps: true
        mipFilter: Texture.Linear
        source: node.textureData
    }
    PrincipledMaterial {
        id: diting_multiview_painted_surface_material
        objectName: "Diting multiview painted surface"
        baseColorMap: _0_texture
        roughness: 0.4300000071525574
        cullMode: PrincipledMaterial.NoCulling
        alphaMode: PrincipledMaterial.Opaque
        clearcoatAmount: 0.11999999731779099
    }
    Skin {
        id: skin
        joints: [
            root,
            pelvis,
            chest,
            neck,
            head,
            earUpright,
            earFolded,
            tailBase,
            tailMid,
            tailTip,
            pawFrontL,
            pawFrontR,
            pawRearL,
            pawRearR
        ]
        inverseBindPoses: [
            Qt.matrix4x4(1, 0, 0, 0, 0, 1, 0, -0.1, 0, 0, 1, 0, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.1, 0, 1, 0, -0.55, 0, 0, 1, 0.2, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.25, 0, 1, 0, -1.45, 0, 0, 1, -0.25, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.3, 0, 1, 0, -2.22, 0, 0, 1, -0.55, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.35, 0, 1, 0, -2.6, 0, 0, 1, -0.65, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.25, 0, 1, 0, -3.22, 0, 0, 1, -0.65, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -1, 0, 1, 0, -3.03, 0, 0, 1, -0.55, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.7, 0, 1, 0, -0.45, 0, 0, 1, 0.65, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 1.05, 0, 1, 0, -1.03, 0, 0, 1, 1.2, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 1.04, 0, 1, 0, -1.6, 0, 0, 1, 1.15, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.25, 0, 1, 0, -0.1, 0, 0, 1, -1.2, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.95, 0, 1, 0, -0.1, 0, 0, 1, -1.2, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.55, 0, 1, 0, -0.1, 0, 0, 1, 0.7, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.85, 0, 1, 0, -0.1, 0, 0, 1, 0.7, 0, 0, 0, 1)
        ]
    }

    // Nodes:
    Node {
        id: ditingRig
        objectName: "DitingRig"
        Model {
            id: diting_reconstructed_real_surface__unrigged_
            objectName: "Diting reconstructed real surface (unrigged)"
            source: "meshes/diting_reconstructed_mesh.mesh"
            skin: skin
            materials: [
                diting_multiview_painted_surface_material
            ]
        }
        Node {
            id: root
            objectName: "Root"
            position: Qt.vector3d(0, 0.1, 0)
            Node {
                id: pelvis
                objectName: "Pelvis"
                position: Qt.vector3d(0.1, 0.45, -0.2)
                scale: Qt.vector3d(1, 1, 1)
                Node {
                    id: chest
                    objectName: "Chest"
                    position: Qt.vector3d(0.15, 0.9, 0.45)
                    Node {
                        id: neck
                        objectName: "Neck"
                        position: Qt.vector3d(0.05, 0.77, 0.3)
                        scale: Qt.vector3d(1, 1, 1)
                        Node {
                            id: head
                            objectName: "Head"
                            position: Qt.vector3d(0.05, 0.38, 0.1)
                            Node {
                                id: earUpright
                                objectName: "EarUpright"
                                position: Qt.vector3d(-0.6, 0.62, 0)
                            }
                            Node {
                                id: earFolded
                                objectName: "EarFolded"
                                position: Qt.vector3d(0.65, 0.43, -0.1)
                                scale: Qt.vector3d(1, 1, 1)
                            }
                        }
                    }
                }
                Node {
                    id: tailBase
                    objectName: "TailBase"
                    position: Qt.vector3d(-0.8, -0.1, -0.45)
                    Node {
                        id: tailMid
                        objectName: "TailMid"
                        position: Qt.vector3d(-0.35, 0.58, -0.55)
                        Node {
                            id: tailTip
                            objectName: "TailTip"
                            position: Qt.vector3d(0.00999999, 0.57, 0.0500001)
                        }
                    }
                }
            }
            Node {
                id: pawFrontL
                objectName: "PawFrontL"
                position: Qt.vector3d(-0.25, 0, 1.2)
            }
            Node {
                id: pawFrontR
                objectName: "PawFrontR"
                position: Qt.vector3d(0.95, 0, 1.2)
            }
            Node {
                id: pawRearL
                objectName: "PawRearL"
                position: Qt.vector3d(-0.55, 0, -0.7)
            }
            Node {
                id: pawRearR
                objectName: "PawRearR"
                position: Qt.vector3d(0.85, 0, -0.7)
            }
        }
    }

    // Animations:
    Timeline {
        id: idle_timeline
        objectName: "Idle"
        property real framesPerSecond: 1000
        startFrame: 0
        endFrame: 4834
        currentFrame: node.clipTime
        enabled: node.clipName === "Idle"
        KeyframeGroup {
            target: earUpright
            property: "rotation"
            keyframeSource: "animations/earUpright_rotation_0.qad"
        }
        KeyframeGroup {
            target: chest
            property: "scale"
            keyframeSource: "animations/chest_scale_0.qad"
        }
        KeyframeGroup {
            target: neck
            property: "rotation"
            keyframeSource: "animations/neck_rotation_0.qad"
        }
        KeyframeGroup {
            target: head
            property: "rotation"
            keyframeSource: "animations/head_rotation_0.qad"
        }
        KeyframeGroup {
            target: tailBase
            property: "rotation"
            keyframeSource: "animations/tailBase_rotation_0.qad"
        }
        KeyframeGroup {
            target: tailMid
            property: "rotation"
            keyframeSource: "animations/tailMid_rotation_0.qad"
        }
        KeyframeGroup {
            target: tailTip
            property: "rotation"
            keyframeSource: "animations/tailTip_rotation_0.qad"
        }
    }
    Timeline {
        id: listen_timeline
        objectName: "Listen"
        property real framesPerSecond: 1000
        startFrame: 0
        endFrame: 3234
        currentFrame: node.clipTime
        enabled: node.clipName === "Listen"
        KeyframeGroup {
            target: earUpright
            property: "rotation"
            keyframeSource: "animations/earUpright_rotation_1.qad"
        }
        KeyframeGroup {
            target: neck
            property: "rotation"
            keyframeSource: "animations/neck_rotation_1.qad"
        }
        KeyframeGroup {
            target: head
            property: "rotation"
            keyframeSource: "animations/head_rotation_1.qad"
        }
        KeyframeGroup {
            target: earFolded
            property: "rotation"
            keyframeSource: "animations/earFolded_rotation_1.qad"
        }
    }
    Timeline {
        id: respond_timeline
        objectName: "Respond"
        property real framesPerSecond: 1000
        startFrame: 0
        endFrame: 1434
        currentFrame: node.clipTime
        enabled: node.clipName === "Respond"
        KeyframeGroup {
            target: earUpright
            property: "rotation"
            keyframeSource: "animations/earUpright_rotation_2.qad"
        }
        KeyframeGroup {
            target: neck
            property: "rotation"
            keyframeSource: "animations/neck_rotation_2.qad"
        }
        KeyframeGroup {
            target: head
            property: "rotation"
            keyframeSource: "animations/head_rotation_2.qad"
        }
    }
}
