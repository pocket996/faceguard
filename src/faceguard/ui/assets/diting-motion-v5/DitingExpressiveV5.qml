import QtQuick
import QtQuick3D

import QtQuick.Timeline

Node {
    id: node

    // FaceGuard clip controller: one skeletal timeline at a time.
    property string clipName: ""
    property real clipTime: 0
    readonly property real clipDuration: clipName === "Respond" ? 2434 : (clipName === "Listen" ? 4034 : 6034)
    property bool ready: false
    property var bindTransforms: []
    property var transitionFrom: []
    function snapshot(joint) {
        var p=joint.position, q=joint.rotation, s=joint.scale
        return {position: Qt.vector3d(p.x,p.y,p.z), rotation: Qt.quaternion(q.scalar,q.x,q.y,q.z), scale: Qt.vector3d(s.x,s.y,s.z)}
    }
    function prepareTransition() {
        transitionFrom = []
        var changed = false
        for (var i = 0; i < skin.joints.length; ++i) {
            var joint = skin.joints[i]
            transitionFrom.push(snapshot(joint))
            var rest = bindTransforms[i]
            if (joint.position.minus(rest.position).length() > 0.00001 ||
                joint.scale.minus(rest.scale).length() > 0.00001 ||
                Math.abs(joint.rotation.scalar - rest.rotation.scalar) +
                Math.abs(joint.rotation.x - rest.rotation.x) +
                Math.abs(joint.rotation.y - rest.rotation.y) +
                Math.abs(joint.rotation.z - rest.rotation.z) > 0.00001) changed = true
        }
        clipName = ""
        blendToBind(0)
        return changed
    }
    function blendToBind(t) {
        for (var i = 0; i < transitionFrom.length; ++i) {
            var from = transitionFrom[i], to = bindTransforms[i], joint = skin.joints[i]
            joint.position = from.position.times(1-t).plus(to.position.times(t))
            joint.scale = from.scale.times(1-t).plus(to.scale.times(t))
            var a = from.rotation, b = to.rotation
            var sign = a.scalar*b.scalar+a.x*b.x+a.y*b.y+a.z*b.z < 0 ? -1 : 1
            var w=a.scalar*(1-t)+b.scalar*t*sign, x=a.x*(1-t)+b.x*t*sign
            var y=a.y*(1-t)+b.y*t*sign, z=a.z*(1-t)+b.z*t*sign
            var length=Math.sqrt(w*w+x*x+y*y+z*z)
            joint.rotation = Qt.quaternion(w/length,x/length,y/length,z/length)
        }
    }
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
            bindTransforms.push(snapshot(joint))
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
    PrincipledMaterial {
        id: ivory_jade_eyelid_material
        objectName: "Ivory jade eyelid"
        baseColor: "#ffc7b38c"
        roughness: 0.3799999952316284
        cullMode: PrincipledMaterial.NoCulling
        alphaMode: PrincipledMaterial.Opaque
        clearcoatAmount: 0.20000000298023224
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
            eyeNear,
            lidNear,
            lidDepthNear,
            eyeFar,
            lidFar,
            lidDepthFar,
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
            Qt.matrix4x4(0.908174, 0, 0.418593, -0.527648, 0, 1, 0, -3.02686, -0.418593, 0, 0.908174, -1.0726, 0, 0, 0, 1),
            Qt.matrix4x4(0.908174, 0, 0.418593, -0.527648, 0, 1, 0, -3.02686, -0.418593, 0, 0.908174, -1.0726, 0, 0, 0, 1),
            Qt.matrix4x4(0.908174, 0, 0.418593, -0.527648, 0, 1, 0, -3.02686, -0.418593, 0, 0.908174, -1.0726, 0, 0, 0, 1),
            Qt.matrix4x4(0.993591, 0, -0.113037, -0.712348, 0, 1, 0, -2.90262, 0.113037, 0, 0.993591, -0.919123, 0, 0, 0, 1),
            Qt.matrix4x4(0.993591, 0, -0.113037, -0.712348, 0, 1, 0, -2.90262, 0.113037, 0, 0.993591, -0.919123, 0, 0, 0, 1),
            Qt.matrix4x4(0.993591, 0, -0.113037, -0.712348, 0, 1, 0, -2.90262, 0.113037, 0, 0.993591, -0.919123, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.7, 0, 1, 0, -0.45, 0, 0, 1, 0.65, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 1.05, 0, 1, 0, -1.03, 0, 0, 1, 1.2, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 1.04, 0, 1, 0, -1.6, 0, 0, 1, 1.15, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.25, 0, 1, 0, -0.1, 0, 0, 1, -1.2, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.95, 0, 1, 0, -0.1, 0, 0, 1, -1.2, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.55, 0, 1, 0, -0.1, 0, 0, 1, 0.7, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.85, 0, 1, 0, -0.1, 0, 0, 1, 0.7, 0, 0, 0, 1)
        ]
    }
    PrincipledMaterial {
        id: amber_iris_and_pupil_material
        objectName: "Amber iris and pupil"
        roughness: 0.23000000417232513
        cullMode: PrincipledMaterial.NoCulling
        alphaMode: PrincipledMaterial.Opaque
        clearcoatAmount: 0.6499999761581421
    }
    Skin {
        id: skin12
        joints: [
            root,
            pelvis,
            chest,
            neck,
            head,
            earUpright,
            earFolded,
            eyeNear,
            lidNear,
            lidDepthNear,
            eyeFar,
            lidFar,
            lidDepthFar,
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
            Qt.matrix4x4(0.908174, 0, 0.418593, -0.527648, 0, 1, 0, -3.02686, -0.418593, 0, 0.908174, -1.0726, 0, 0, 0, 1),
            Qt.matrix4x4(0.908174, 0, 0.418593, -0.527648, 0, 1, 0, -3.02686, -0.418593, 0, 0.908174, -1.0726, 0, 0, 0, 1),
            Qt.matrix4x4(0.908174, 0, 0.418593, -0.527648, 0, 1, 0, -3.02686, -0.418593, 0, 0.908174, -1.0726, 0, 0, 0, 1),
            Qt.matrix4x4(0.993591, 0, -0.113037, -0.712348, 0, 1, 0, -2.90262, 0.113037, 0, 0.993591, -0.919123, 0, 0, 0, 1),
            Qt.matrix4x4(0.993591, 0, -0.113037, -0.712348, 0, 1, 0, -2.90262, 0.113037, 0, 0.993591, -0.919123, 0, 0, 0, 1),
            Qt.matrix4x4(0.993591, 0, -0.113037, -0.712348, 0, 1, 0, -2.90262, 0.113037, 0, 0.993591, -0.919123, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.7, 0, 1, 0, -0.45, 0, 0, 1, 0.65, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 1.05, 0, 1, 0, -1.03, 0, 0, 1, 1.2, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 1.04, 0, 1, 0, -1.6, 0, 0, 1, 1.15, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.25, 0, 1, 0, -0.1, 0, 0, 1, -1.2, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.95, 0, 1, 0, -0.1, 0, 0, 1, -1.2, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.55, 0, 1, 0, -0.1, 0, 0, 1, 0.7, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.85, 0, 1, 0, -0.1, 0, 0, 1, 0.7, 0, 0, 0, 1)
        ]
    }
    Skin {
        id: skin15
        joints: [
            root,
            pelvis,
            chest,
            neck,
            head,
            earUpright,
            earFolded,
            eyeNear,
            lidNear,
            lidDepthNear,
            eyeFar,
            lidFar,
            lidDepthFar,
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
            Qt.matrix4x4(0.908174, 0, 0.418593, -0.527648, 0, 1, 0, -3.02686, -0.418593, 0, 0.908174, -1.0726, 0, 0, 0, 1),
            Qt.matrix4x4(0.908174, 0, 0.418593, -0.527648, 0, 1, 0, -3.02686, -0.418593, 0, 0.908174, -1.0726, 0, 0, 0, 1),
            Qt.matrix4x4(0.908174, 0, 0.418593, -0.527648, 0, 1, 0, -3.02686, -0.418593, 0, 0.908174, -1.0726, 0, 0, 0, 1),
            Qt.matrix4x4(0.993591, 0, -0.113037, -0.712348, 0, 1, 0, -2.90262, 0.113037, 0, 0.993591, -0.919123, 0, 0, 0, 1),
            Qt.matrix4x4(0.993591, 0, -0.113037, -0.712348, 0, 1, 0, -2.90262, 0.113037, 0, 0.993591, -0.919123, 0, 0, 0, 1),
            Qt.matrix4x4(0.993591, 0, -0.113037, -0.712348, 0, 1, 0, -2.90262, 0.113037, 0, 0.993591, -0.919123, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.7, 0, 1, 0, -0.45, 0, 0, 1, 0.65, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 1.05, 0, 1, 0, -1.03, 0, 0, 1, 1.2, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 1.04, 0, 1, 0, -1.6, 0, 0, 1, 1.15, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.25, 0, 1, 0, -0.1, 0, 0, 1, -1.2, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.95, 0, 1, 0, -0.1, 0, 0, 1, -1.2, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.55, 0, 1, 0, -0.1, 0, 0, 1, 0.7, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.85, 0, 1, 0, -0.1, 0, 0, 1, 0.7, 0, 0, 0, 1)
        ]
    }
    Skin {
        id: skin18
        joints: [
            root,
            pelvis,
            chest,
            neck,
            head,
            earUpright,
            earFolded,
            eyeNear,
            lidNear,
            lidDepthNear,
            eyeFar,
            lidFar,
            lidDepthFar,
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
            Qt.matrix4x4(0.908174, 0, 0.418593, -0.527648, 0, 1, 0, -3.02686, -0.418593, 0, 0.908174, -1.0726, 0, 0, 0, 1),
            Qt.matrix4x4(0.908174, 0, 0.418593, -0.527648, 0, 1, 0, -3.02686, -0.418593, 0, 0.908174, -1.0726, 0, 0, 0, 1),
            Qt.matrix4x4(0.908174, 0, 0.418593, -0.527648, 0, 1, 0, -3.02686, -0.418593, 0, 0.908174, -1.0726, 0, 0, 0, 1),
            Qt.matrix4x4(0.993591, 0, -0.113037, -0.712348, 0, 1, 0, -2.90262, 0.113037, 0, 0.993591, -0.919123, 0, 0, 0, 1),
            Qt.matrix4x4(0.993591, 0, -0.113037, -0.712348, 0, 1, 0, -2.90262, 0.113037, 0, 0.993591, -0.919123, 0, 0, 0, 1),
            Qt.matrix4x4(0.993591, 0, -0.113037, -0.712348, 0, 1, 0, -2.90262, 0.113037, 0, 0.993591, -0.919123, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.7, 0, 1, 0, -0.45, 0, 0, 1, 0.65, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 1.05, 0, 1, 0, -1.03, 0, 0, 1, 1.2, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 1.04, 0, 1, 0, -1.6, 0, 0, 1, 1.15, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.25, 0, 1, 0, -0.1, 0, 0, 1, -1.2, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.95, 0, 1, 0, -0.1, 0, 0, 1, -1.2, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.55, 0, 1, 0, -0.1, 0, 0, 1, 0.7, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.85, 0, 1, 0, -0.1, 0, 0, 1, 0.7, 0, 0, 0, 1)
        ]
    }
    Skin {
        id: skin21
        joints: [
            root,
            pelvis,
            chest,
            neck,
            head,
            earUpright,
            earFolded,
            eyeNear,
            lidNear,
            lidDepthNear,
            eyeFar,
            lidFar,
            lidDepthFar,
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
            Qt.matrix4x4(0.908174, 0, 0.418593, -0.527648, 0, 1, 0, -3.02686, -0.418593, 0, 0.908174, -1.0726, 0, 0, 0, 1),
            Qt.matrix4x4(0.908174, 0, 0.418593, -0.527648, 0, 1, 0, -3.02686, -0.418593, 0, 0.908174, -1.0726, 0, 0, 0, 1),
            Qt.matrix4x4(0.908174, 0, 0.418593, -0.527648, 0, 1, 0, -3.02686, -0.418593, 0, 0.908174, -1.0726, 0, 0, 0, 1),
            Qt.matrix4x4(0.993591, 0, -0.113037, -0.712348, 0, 1, 0, -2.90262, 0.113037, 0, 0.993591, -0.919123, 0, 0, 0, 1),
            Qt.matrix4x4(0.993591, 0, -0.113037, -0.712348, 0, 1, 0, -2.90262, 0.113037, 0, 0.993591, -0.919123, 0, 0, 0, 1),
            Qt.matrix4x4(0.993591, 0, -0.113037, -0.712348, 0, 1, 0, -2.90262, 0.113037, 0, 0.993591, -0.919123, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.7, 0, 1, 0, -0.45, 0, 0, 1, 0.65, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 1.05, 0, 1, 0, -1.03, 0, 0, 1, 1.2, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 1.04, 0, 1, 0, -1.6, 0, 0, 1, 1.15, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.25, 0, 1, 0, -0.1, 0, 0, 1, -1.2, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.95, 0, 1, 0, -0.1, 0, 0, 1, -1.2, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.55, 0, 1, 0, -0.1, 0, 0, 1, 0.7, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.85, 0, 1, 0, -0.1, 0, 0, 1, 0.7, 0, 0, 0, 1)
        ]
    }
    Skin {
        id: skin24
        joints: [
            root,
            pelvis,
            chest,
            neck,
            head,
            earUpright,
            earFolded,
            eyeNear,
            lidNear,
            lidDepthNear,
            eyeFar,
            lidFar,
            lidDepthFar,
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
            Qt.matrix4x4(0.908174, 0, 0.418593, -0.527648, 0, 1, 0, -3.02686, -0.418593, 0, 0.908174, -1.0726, 0, 0, 0, 1),
            Qt.matrix4x4(0.908174, 0, 0.418593, -0.527648, 0, 1, 0, -3.02686, -0.418593, 0, 0.908174, -1.0726, 0, 0, 0, 1),
            Qt.matrix4x4(0.908174, 0, 0.418593, -0.527648, 0, 1, 0, -3.02686, -0.418593, 0, 0.908174, -1.0726, 0, 0, 0, 1),
            Qt.matrix4x4(0.993591, 0, -0.113037, -0.712348, 0, 1, 0, -2.90262, 0.113037, 0, 0.993591, -0.919123, 0, 0, 0, 1),
            Qt.matrix4x4(0.993591, 0, -0.113037, -0.712348, 0, 1, 0, -2.90262, 0.113037, 0, 0.993591, -0.919123, 0, 0, 0, 1),
            Qt.matrix4x4(0.993591, 0, -0.113037, -0.712348, 0, 1, 0, -2.90262, 0.113037, 0, 0.993591, -0.919123, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.7, 0, 1, 0, -0.45, 0, 0, 1, 0.65, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 1.05, 0, 1, 0, -1.03, 0, 0, 1, 1.2, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 1.04, 0, 1, 0, -1.6, 0, 0, 1, 1.15, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.25, 0, 1, 0, -0.1, 0, 0, 1, -1.2, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.95, 0, 1, 0, -0.1, 0, 0, 1, -1.2, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.55, 0, 1, 0, -0.1, 0, 0, 1, 0.7, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.85, 0, 1, 0, -0.1, 0, 0, 1, 0.7, 0, 0, 0, 1)
        ]
    }
    Skin {
        id: skin27
        joints: [
            root,
            pelvis,
            chest,
            neck,
            head,
            earUpright,
            earFolded,
            eyeNear,
            lidNear,
            lidDepthNear,
            eyeFar,
            lidFar,
            lidDepthFar,
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
            Qt.matrix4x4(0.908174, 0, 0.418593, -0.527648, 0, 1, 0, -3.02686, -0.418593, 0, 0.908174, -1.0726, 0, 0, 0, 1),
            Qt.matrix4x4(0.908174, 0, 0.418593, -0.527648, 0, 1, 0, -3.02686, -0.418593, 0, 0.908174, -1.0726, 0, 0, 0, 1),
            Qt.matrix4x4(0.908174, 0, 0.418593, -0.527648, 0, 1, 0, -3.02686, -0.418593, 0, 0.908174, -1.0726, 0, 0, 0, 1),
            Qt.matrix4x4(0.993591, 0, -0.113037, -0.712348, 0, 1, 0, -2.90262, 0.113037, 0, 0.993591, -0.919123, 0, 0, 0, 1),
            Qt.matrix4x4(0.993591, 0, -0.113037, -0.712348, 0, 1, 0, -2.90262, 0.113037, 0, 0.993591, -0.919123, 0, 0, 0, 1),
            Qt.matrix4x4(0.993591, 0, -0.113037, -0.712348, 0, 1, 0, -2.90262, 0.113037, 0, 0.993591, -0.919123, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.7, 0, 1, 0, -0.45, 0, 0, 1, 0.65, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 1.05, 0, 1, 0, -1.03, 0, 0, 1, 1.2, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 1.04, 0, 1, 0, -1.6, 0, 0, 1, 1.15, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.25, 0, 1, 0, -0.1, 0, 0, 1, -1.2, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.95, 0, 1, 0, -0.1, 0, 0, 1, -1.2, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.55, 0, 1, 0, -0.1, 0, 0, 1, 0.7, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.85, 0, 1, 0, -0.1, 0, 0, 1, 0.7, 0, 0, 0, 1)
        ]
    }
    Skin {
        id: skin30
        joints: [
            root,
            pelvis,
            chest,
            neck,
            head,
            earUpright,
            earFolded,
            eyeNear,
            lidNear,
            lidDepthNear,
            eyeFar,
            lidFar,
            lidDepthFar,
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
            Qt.matrix4x4(0.908174, 0, 0.418593, -0.527648, 0, 1, 0, -3.02686, -0.418593, 0, 0.908174, -1.0726, 0, 0, 0, 1),
            Qt.matrix4x4(0.908174, 0, 0.418593, -0.527648, 0, 1, 0, -3.02686, -0.418593, 0, 0.908174, -1.0726, 0, 0, 0, 1),
            Qt.matrix4x4(0.908174, 0, 0.418593, -0.527648, 0, 1, 0, -3.02686, -0.418593, 0, 0.908174, -1.0726, 0, 0, 0, 1),
            Qt.matrix4x4(0.993591, 0, -0.113037, -0.712348, 0, 1, 0, -2.90262, 0.113037, 0, 0.993591, -0.919123, 0, 0, 0, 1),
            Qt.matrix4x4(0.993591, 0, -0.113037, -0.712348, 0, 1, 0, -2.90262, 0.113037, 0, 0.993591, -0.919123, 0, 0, 0, 1),
            Qt.matrix4x4(0.993591, 0, -0.113037, -0.712348, 0, 1, 0, -2.90262, 0.113037, 0, 0.993591, -0.919123, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.7, 0, 1, 0, -0.45, 0, 0, 1, 0.65, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 1.05, 0, 1, 0, -1.03, 0, 0, 1, 1.2, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 1.04, 0, 1, 0, -1.6, 0, 0, 1, 1.15, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.25, 0, 1, 0, -0.1, 0, 0, 1, -1.2, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.95, 0, 1, 0, -0.1, 0, 0, 1, -1.2, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.55, 0, 1, 0, -0.1, 0, 0, 1, 0.7, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.85, 0, 1, 0, -0.1, 0, 0, 1, 0.7, 0, 0, 0, 1)
        ]
    }
    Skin {
        id: skin33
        joints: [
            root,
            pelvis,
            chest,
            neck,
            head,
            earUpright,
            earFolded,
            eyeNear,
            lidNear,
            lidDepthNear,
            eyeFar,
            lidFar,
            lidDepthFar,
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
            Qt.matrix4x4(0.908174, 0, 0.418593, -0.527648, 0, 1, 0, -3.02686, -0.418593, 0, 0.908174, -1.0726, 0, 0, 0, 1),
            Qt.matrix4x4(0.908174, 0, 0.418593, -0.527648, 0, 1, 0, -3.02686, -0.418593, 0, 0.908174, -1.0726, 0, 0, 0, 1),
            Qt.matrix4x4(0.908174, 0, 0.418593, -0.527648, 0, 1, 0, -3.02686, -0.418593, 0, 0.908174, -1.0726, 0, 0, 0, 1),
            Qt.matrix4x4(0.993591, 0, -0.113037, -0.712348, 0, 1, 0, -2.90262, 0.113037, 0, 0.993591, -0.919123, 0, 0, 0, 1),
            Qt.matrix4x4(0.993591, 0, -0.113037, -0.712348, 0, 1, 0, -2.90262, 0.113037, 0, 0.993591, -0.919123, 0, 0, 0, 1),
            Qt.matrix4x4(0.993591, 0, -0.113037, -0.712348, 0, 1, 0, -2.90262, 0.113037, 0, 0.993591, -0.919123, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.7, 0, 1, 0, -0.45, 0, 0, 1, 0.65, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 1.05, 0, 1, 0, -1.03, 0, 0, 1, 1.2, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 1.04, 0, 1, 0, -1.6, 0, 0, 1, 1.15, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.25, 0, 1, 0, -0.1, 0, 0, 1, -1.2, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.95, 0, 1, 0, -0.1, 0, 0, 1, -1.2, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.55, 0, 1, 0, -0.1, 0, 0, 1, 0.7, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.85, 0, 1, 0, -0.1, 0, 0, 1, 0.7, 0, 0, 0, 1)
        ]
    }
    PrincipledMaterial {
        id: continuous_facial_skin_material
        objectName: "Continuous facial skin"
        roughness: 0.4300000071525574
        cullMode: PrincipledMaterial.NoCulling
        alphaMode: PrincipledMaterial.Opaque
        clearcoatAmount: 0.11999999731779099
    }
    Skin {
        id: skin37
        joints: [
            root,
            pelvis,
            chest,
            neck,
            head,
            earUpright,
            earFolded,
            eyeNear,
            lidNear,
            lidDepthNear,
            eyeFar,
            lidFar,
            lidDepthFar,
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
            Qt.matrix4x4(0.908174, 0, 0.418593, -0.527648, 0, 1, 0, -3.02686, -0.418593, 0, 0.908174, -1.0726, 0, 0, 0, 1),
            Qt.matrix4x4(0.908174, 0, 0.418593, -0.527648, 0, 1, 0, -3.02686, -0.418593, 0, 0.908174, -1.0726, 0, 0, 0, 1),
            Qt.matrix4x4(0.908174, 0, 0.418593, -0.527648, 0, 1, 0, -3.02686, -0.418593, 0, 0.908174, -1.0726, 0, 0, 0, 1),
            Qt.matrix4x4(0.993591, 0, -0.113037, -0.712348, 0, 1, 0, -2.90262, 0.113037, 0, 0.993591, -0.919123, 0, 0, 0, 1),
            Qt.matrix4x4(0.993591, 0, -0.113037, -0.712348, 0, 1, 0, -2.90262, 0.113037, 0, 0.993591, -0.919123, 0, 0, 0, 1),
            Qt.matrix4x4(0.993591, 0, -0.113037, -0.712348, 0, 1, 0, -2.90262, 0.113037, 0, 0.993591, -0.919123, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.7, 0, 1, 0, -0.45, 0, 0, 1, 0.65, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 1.05, 0, 1, 0, -1.03, 0, 0, 1, 1.2, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 1.04, 0, 1, 0, -1.6, 0, 0, 1, 1.15, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.25, 0, 1, 0, -0.1, 0, 0, 1, -1.2, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.95, 0, 1, 0, -0.1, 0, 0, 1, -1.2, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.55, 0, 1, 0, -0.1, 0, 0, 1, 0.7, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.85, 0, 1, 0, -0.1, 0, 0, 1, 0.7, 0, 0, 0, 1)
        ]
    }
    Skin {
        id: skin40
        joints: [
            root,
            pelvis,
            chest,
            neck,
            head,
            earUpright,
            earFolded,
            eyeNear,
            lidNear,
            lidDepthNear,
            eyeFar,
            lidFar,
            lidDepthFar,
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
            Qt.matrix4x4(0.908174, 0, 0.418593, -0.527648, 0, 1, 0, -3.02686, -0.418593, 0, 0.908174, -1.0726, 0, 0, 0, 1),
            Qt.matrix4x4(0.908174, 0, 0.418593, -0.527648, 0, 1, 0, -3.02686, -0.418593, 0, 0.908174, -1.0726, 0, 0, 0, 1),
            Qt.matrix4x4(0.908174, 0, 0.418593, -0.527648, 0, 1, 0, -3.02686, -0.418593, 0, 0.908174, -1.0726, 0, 0, 0, 1),
            Qt.matrix4x4(0.993591, 0, -0.113037, -0.712348, 0, 1, 0, -2.90262, 0.113037, 0, 0.993591, -0.919123, 0, 0, 0, 1),
            Qt.matrix4x4(0.993591, 0, -0.113037, -0.712348, 0, 1, 0, -2.90262, 0.113037, 0, 0.993591, -0.919123, 0, 0, 0, 1),
            Qt.matrix4x4(0.993591, 0, -0.113037, -0.712348, 0, 1, 0, -2.90262, 0.113037, 0, 0.993591, -0.919123, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.7, 0, 1, 0, -0.45, 0, 0, 1, 0.65, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 1.05, 0, 1, 0, -1.03, 0, 0, 1, 1.2, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 1.04, 0, 1, 0, -1.6, 0, 0, 1, 1.15, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.25, 0, 1, 0, -0.1, 0, 0, 1, -1.2, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.95, 0, 1, 0, -0.1, 0, 0, 1, -1.2, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.55, 0, 1, 0, -0.1, 0, 0, 1, 0.7, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.85, 0, 1, 0, -0.1, 0, 0, 1, 0.7, 0, 0, 0, 1)
        ]
    }
    PrincipledMaterial {
        id: dark_brown_lid_margin_material
        objectName: "Dark brown lid margin"
        baseColor: "#ff070302"
        roughness: 0.3799999952316284
        cullMode: PrincipledMaterial.NoCulling
        alphaMode: PrincipledMaterial.Opaque
        clearcoatAmount: 0.10000000149011612
    }
    Skin {
        id: skin44
        joints: [
            root,
            pelvis,
            chest,
            neck,
            head,
            earUpright,
            earFolded,
            eyeNear,
            lidNear,
            lidDepthNear,
            eyeFar,
            lidFar,
            lidDepthFar,
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
            Qt.matrix4x4(0.908174, 0, 0.418593, -0.527648, 0, 1, 0, -3.02686, -0.418593, 0, 0.908174, -1.0726, 0, 0, 0, 1),
            Qt.matrix4x4(0.908174, 0, 0.418593, -0.527648, 0, 1, 0, -3.02686, -0.418593, 0, 0.908174, -1.0726, 0, 0, 0, 1),
            Qt.matrix4x4(0.908174, 0, 0.418593, -0.527648, 0, 1, 0, -3.02686, -0.418593, 0, 0.908174, -1.0726, 0, 0, 0, 1),
            Qt.matrix4x4(0.993591, 0, -0.113037, -0.712348, 0, 1, 0, -2.90262, 0.113037, 0, 0.993591, -0.919123, 0, 0, 0, 1),
            Qt.matrix4x4(0.993591, 0, -0.113037, -0.712348, 0, 1, 0, -2.90262, 0.113037, 0, 0.993591, -0.919123, 0, 0, 0, 1),
            Qt.matrix4x4(0.993591, 0, -0.113037, -0.712348, 0, 1, 0, -2.90262, 0.113037, 0, 0.993591, -0.919123, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.7, 0, 1, 0, -0.45, 0, 0, 1, 0.65, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 1.05, 0, 1, 0, -1.03, 0, 0, 1, 1.2, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 1.04, 0, 1, 0, -1.6, 0, 0, 1, 1.15, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.25, 0, 1, 0, -0.1, 0, 0, 1, -1.2, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.95, 0, 1, 0, -0.1, 0, 0, 1, -1.2, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.55, 0, 1, 0, -0.1, 0, 0, 1, 0.7, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.85, 0, 1, 0, -0.1, 0, 0, 1, 0.7, 0, 0, 0, 1)
        ]
    }
    Skin {
        id: skin47
        joints: [
            root,
            pelvis,
            chest,
            neck,
            head,
            earUpright,
            earFolded,
            eyeNear,
            lidNear,
            lidDepthNear,
            eyeFar,
            lidFar,
            lidDepthFar,
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
            Qt.matrix4x4(0.908174, 0, 0.418593, -0.527648, 0, 1, 0, -3.02686, -0.418593, 0, 0.908174, -1.0726, 0, 0, 0, 1),
            Qt.matrix4x4(0.908174, 0, 0.418593, -0.527648, 0, 1, 0, -3.02686, -0.418593, 0, 0.908174, -1.0726, 0, 0, 0, 1),
            Qt.matrix4x4(0.908174, 0, 0.418593, -0.527648, 0, 1, 0, -3.02686, -0.418593, 0, 0.908174, -1.0726, 0, 0, 0, 1),
            Qt.matrix4x4(0.993591, 0, -0.113037, -0.712348, 0, 1, 0, -2.90262, 0.113037, 0, 0.993591, -0.919123, 0, 0, 0, 1),
            Qt.matrix4x4(0.993591, 0, -0.113037, -0.712348, 0, 1, 0, -2.90262, 0.113037, 0, 0.993591, -0.919123, 0, 0, 0, 1),
            Qt.matrix4x4(0.993591, 0, -0.113037, -0.712348, 0, 1, 0, -2.90262, 0.113037, 0, 0.993591, -0.919123, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.7, 0, 1, 0, -0.45, 0, 0, 1, 0.65, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 1.05, 0, 1, 0, -1.03, 0, 0, 1, 1.2, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 1.04, 0, 1, 0, -1.6, 0, 0, 1, 1.15, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.25, 0, 1, 0, -0.1, 0, 0, 1, -1.2, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.95, 0, 1, 0, -0.1, 0, 0, 1, -1.2, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.55, 0, 1, 0, -0.1, 0, 0, 1, 0.7, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.85, 0, 1, 0, -0.1, 0, 0, 1, 0.7, 0, 0, 0, 1)
        ]
    }
    Skin {
        id: skin50
        joints: [
            root,
            pelvis,
            chest,
            neck,
            head,
            earUpright,
            earFolded,
            eyeNear,
            lidNear,
            lidDepthNear,
            eyeFar,
            lidFar,
            lidDepthFar,
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
            Qt.matrix4x4(0.908174, 0, 0.418593, -0.527648, 0, 1, 0, -3.02686, -0.418593, 0, 0.908174, -1.0726, 0, 0, 0, 1),
            Qt.matrix4x4(0.908174, 0, 0.418593, -0.527648, 0, 1, 0, -3.02686, -0.418593, 0, 0.908174, -1.0726, 0, 0, 0, 1),
            Qt.matrix4x4(0.908174, 0, 0.418593, -0.527648, 0, 1, 0, -3.02686, -0.418593, 0, 0.908174, -1.0726, 0, 0, 0, 1),
            Qt.matrix4x4(0.993591, 0, -0.113037, -0.712348, 0, 1, 0, -2.90262, 0.113037, 0, 0.993591, -0.919123, 0, 0, 0, 1),
            Qt.matrix4x4(0.993591, 0, -0.113037, -0.712348, 0, 1, 0, -2.90262, 0.113037, 0, 0.993591, -0.919123, 0, 0, 0, 1),
            Qt.matrix4x4(0.993591, 0, -0.113037, -0.712348, 0, 1, 0, -2.90262, 0.113037, 0, 0.993591, -0.919123, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.7, 0, 1, 0, -0.45, 0, 0, 1, 0.65, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 1.05, 0, 1, 0, -1.03, 0, 0, 1, 1.2, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 1.04, 0, 1, 0, -1.6, 0, 0, 1, 1.15, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.25, 0, 1, 0, -0.1, 0, 0, 1, -1.2, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.95, 0, 1, 0, -0.1, 0, 0, 1, -1.2, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.55, 0, 1, 0, -0.1, 0, 0, 1, 0.7, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.85, 0, 1, 0, -0.1, 0, 0, 1, 0.7, 0, 0, 0, 1)
        ]
    }
    Skin {
        id: skin53
        joints: [
            root,
            pelvis,
            chest,
            neck,
            head,
            earUpright,
            earFolded,
            eyeNear,
            lidNear,
            lidDepthNear,
            eyeFar,
            lidFar,
            lidDepthFar,
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
            Qt.matrix4x4(0.908174, 0, 0.418593, -0.527648, 0, 1, 0, -3.02686, -0.418593, 0, 0.908174, -1.0726, 0, 0, 0, 1),
            Qt.matrix4x4(0.908174, 0, 0.418593, -0.527648, 0, 1, 0, -3.02686, -0.418593, 0, 0.908174, -1.0726, 0, 0, 0, 1),
            Qt.matrix4x4(0.908174, 0, 0.418593, -0.527648, 0, 1, 0, -3.02686, -0.418593, 0, 0.908174, -1.0726, 0, 0, 0, 1),
            Qt.matrix4x4(0.993591, 0, -0.113037, -0.712348, 0, 1, 0, -2.90262, 0.113037, 0, 0.993591, -0.919123, 0, 0, 0, 1),
            Qt.matrix4x4(0.993591, 0, -0.113037, -0.712348, 0, 1, 0, -2.90262, 0.113037, 0, 0.993591, -0.919123, 0, 0, 0, 1),
            Qt.matrix4x4(0.993591, 0, -0.113037, -0.712348, 0, 1, 0, -2.90262, 0.113037, 0, 0.993591, -0.919123, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.7, 0, 1, 0, -0.45, 0, 0, 1, 0.65, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 1.05, 0, 1, 0, -1.03, 0, 0, 1, 1.2, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 1.04, 0, 1, 0, -1.6, 0, 0, 1, 1.15, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.25, 0, 1, 0, -0.1, 0, 0, 1, -1.2, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.95, 0, 1, 0, -0.1, 0, 0, 1, -1.2, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.55, 0, 1, 0, -0.1, 0, 0, 1, 0.7, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.85, 0, 1, 0, -0.1, 0, 0, 1, 0.7, 0, 0, 0, 1)
        ]
    }
    Skin {
        id: skin56
        joints: [
            root,
            pelvis,
            chest,
            neck,
            head,
            earUpright,
            earFolded,
            eyeNear,
            lidNear,
            lidDepthNear,
            eyeFar,
            lidFar,
            lidDepthFar,
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
            Qt.matrix4x4(0.908174, 0, 0.418593, -0.527648, 0, 1, 0, -3.02686, -0.418593, 0, 0.908174, -1.0726, 0, 0, 0, 1),
            Qt.matrix4x4(0.908174, 0, 0.418593, -0.527648, 0, 1, 0, -3.02686, -0.418593, 0, 0.908174, -1.0726, 0, 0, 0, 1),
            Qt.matrix4x4(0.908174, 0, 0.418593, -0.527648, 0, 1, 0, -3.02686, -0.418593, 0, 0.908174, -1.0726, 0, 0, 0, 1),
            Qt.matrix4x4(0.993591, 0, -0.113037, -0.712348, 0, 1, 0, -2.90262, 0.113037, 0, 0.993591, -0.919123, 0, 0, 0, 1),
            Qt.matrix4x4(0.993591, 0, -0.113037, -0.712348, 0, 1, 0, -2.90262, 0.113037, 0, 0.993591, -0.919123, 0, 0, 0, 1),
            Qt.matrix4x4(0.993591, 0, -0.113037, -0.712348, 0, 1, 0, -2.90262, 0.113037, 0, 0.993591, -0.919123, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.7, 0, 1, 0, -0.45, 0, 0, 1, 0.65, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 1.05, 0, 1, 0, -1.03, 0, 0, 1, 1.2, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 1.04, 0, 1, 0, -1.6, 0, 0, 1, 1.15, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.25, 0, 1, 0, -0.1, 0, 0, 1, -1.2, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.95, 0, 1, 0, -0.1, 0, 0, 1, -1.2, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.55, 0, 1, 0, -0.1, 0, 0, 1, 0.7, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.85, 0, 1, 0, -0.1, 0, 0, 1, 0.7, 0, 0, 0, 1)
        ]
    }
    Skin {
        id: skin59
        joints: [
            root,
            pelvis,
            chest,
            neck,
            head,
            earUpright,
            earFolded,
            eyeNear,
            lidNear,
            lidDepthNear,
            eyeFar,
            lidFar,
            lidDepthFar,
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
            Qt.matrix4x4(0.908174, 0, 0.418593, -0.527648, 0, 1, 0, -3.02686, -0.418593, 0, 0.908174, -1.0726, 0, 0, 0, 1),
            Qt.matrix4x4(0.908174, 0, 0.418593, -0.527648, 0, 1, 0, -3.02686, -0.418593, 0, 0.908174, -1.0726, 0, 0, 0, 1),
            Qt.matrix4x4(0.908174, 0, 0.418593, -0.527648, 0, 1, 0, -3.02686, -0.418593, 0, 0.908174, -1.0726, 0, 0, 0, 1),
            Qt.matrix4x4(0.993591, 0, -0.113037, -0.712348, 0, 1, 0, -2.90262, 0.113037, 0, 0.993591, -0.919123, 0, 0, 0, 1),
            Qt.matrix4x4(0.993591, 0, -0.113037, -0.712348, 0, 1, 0, -2.90262, 0.113037, 0, 0.993591, -0.919123, 0, 0, 0, 1),
            Qt.matrix4x4(0.993591, 0, -0.113037, -0.712348, 0, 1, 0, -2.90262, 0.113037, 0, 0.993591, -0.919123, 0, 0, 0, 1),
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
            source: "meshes/diting_reconstructed_real_surface__unrigged__mesh.mesh"
            skin: skin
            materials: [
                diting_multiview_painted_surface_material,
                ivory_jade_eyelid_material
            ]
        }
        Model {
            id: eyeSurfaceFar
            objectName: "EyeSurfaceFar"
            source: "meshes/eyeSurfaceFar_mesh.mesh"
            skin: skin12
            materials: [
                amber_iris_and_pupil_material
            ]
        }
        Model {
            id: eyeSurfaceNear
            objectName: "EyeSurfaceNear"
            source: "meshes/eyeSurfaceNear_mesh.mesh"
            skin: skin15
            materials: [
                amber_iris_and_pupil_material
            ]
        }
        Model {
            id: fineWhisker
            objectName: "FineWhisker"
            source: "meshes/fine_whisker_mesh.mesh"
            skin: skin18
            materials: [
                ivory_jade_eyelid_material
            ]
        }
        Model {
            id: fineWhisker_001
            objectName: "FineWhisker.001"
            source: "meshes/fine_whisker_001_mesh.mesh"
            skin: skin21
            materials: [
                ivory_jade_eyelid_material
            ]
        }
        Model {
            id: fineWhisker_002
            objectName: "FineWhisker.002"
            source: "meshes/fine_whisker_002_mesh.mesh"
            skin: skin24
            materials: [
                ivory_jade_eyelid_material
            ]
        }
        Model {
            id: fineWhisker_003
            objectName: "FineWhisker.003"
            source: "meshes/fine_whisker_003_mesh.mesh"
            skin: skin27
            materials: [
                ivory_jade_eyelid_material
            ]
        }
        Model {
            id: fineWhisker_004
            objectName: "FineWhisker.004"
            source: "meshes/fine_whisker_004_mesh.mesh"
            skin: skin30
            materials: [
                ivory_jade_eyelid_material
            ]
        }
        Model {
            id: fineWhisker_005
            objectName: "FineWhisker.005"
            source: "meshes/fine_whisker_005_mesh.mesh"
            skin: skin33
            materials: [
                ivory_jade_eyelid_material
            ]
        }
        Model {
            id: lowerLidFar
            objectName: "LowerLidFar"
            source: "meshes/lowerLidFar_mesh.mesh"
            skin: skin37
            materials: [
                continuous_facial_skin_material
            ]
        }
        Model {
            id: lowerLidNear
            objectName: "LowerLidNear"
            source: "meshes/lowerLidNear_mesh.mesh"
            skin: skin40
            materials: [
                continuous_facial_skin_material
            ]
        }
        Model {
            id: lowerLinerFar
            objectName: "LowerLinerFar"
            source: "meshes/lowerLinerFar_mesh.mesh"
            skin: skin44
            materials: [
                dark_brown_lid_margin_material
            ]
        }
        Model {
            id: lowerLinerNear
            objectName: "LowerLinerNear"
            source: "meshes/lowerLinerNear_mesh.mesh"
            skin: skin47
            materials: [
                dark_brown_lid_margin_material
            ]
        }
        Model {
            id: upperLidFar
            objectName: "UpperLidFar"
            source: "meshes/upperLidFar_mesh.mesh"
            skin: skin50
            materials: [
                continuous_facial_skin_material
            ]
        }
        Model {
            id: upperLidNear
            objectName: "UpperLidNear"
            source: "meshes/upperLidNear_mesh.mesh"
            skin: skin53
            materials: [
                continuous_facial_skin_material
            ]
        }
        Model {
            id: upperLinerFar
            objectName: "UpperLinerFar"
            source: "meshes/upperLinerFar_mesh.mesh"
            skin: skin56
            materials: [
                dark_brown_lid_margin_material
            ]
        }
        Model {
            id: upperLinerNear
            objectName: "UpperLinerNear"
            source: "meshes/upperLinerNear_mesh.mesh"
            skin: skin59
            materials: [
                dark_brown_lid_margin_material
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
                            Node {
                                id: eyeNear
                                objectName: "EyeNear"
                                position: Qt.vector3d(-0.319787, 0.426855, 0.544978)
                                rotation: Qt.quaternion(0.976774, 0, -0.214274, 0)
                            }
                            Node {
                                id: lidNear
                                objectName: "LidNear"
                                position: Qt.vector3d(-0.319787, 0.426855, 0.544978)
                                rotation: Qt.quaternion(0.976774, 0, -0.214274, 0)
                            }
                            Node {
                                id: lidDepthNear
                                objectName: "LidDepthNear"
                                position: Qt.vector3d(-0.319787, 0.426855, 0.544978)
                                rotation: Qt.quaternion(0.976774, 0, -0.214274, 0)
                            }
                            Node {
                                id: eyeFar
                                objectName: "EyeFar"
                                position: Qt.vector3d(0.461678, 0.302622, 0.18271)
                                rotation: Qt.quaternion(0.998396, 0, 0.0566094, 0)
                            }
                            Node {
                                id: lidFar
                                objectName: "LidFar"
                                position: Qt.vector3d(0.461678, 0.302622, 0.18271)
                                rotation: Qt.quaternion(0.998396, 0, 0.0566094, 0)
                            }
                            Node {
                                id: lidDepthFar
                                objectName: "LidDepthFar"
                                position: Qt.vector3d(0.461678, 0.302622, 0.18271)
                                rotation: Qt.quaternion(0.998396, 0, 0.0566094, 0)
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
        endFrame: 6034
        currentFrame: node.clipTime
        enabled: node.clipName === "Idle"
        KeyframeGroup {
            target: eyeNear
            property: "rotation"
            keyframeSource: "animations/eyeNear_rotation_0.qad"
        }
        KeyframeGroup {
            target: chest
            property: "scale"
            keyframeSource: "animations/chest_scale_0.qad"
        }
        KeyframeGroup {
            target: earFolded
            property: "rotation"
            keyframeSource: "animations/earFolded_rotation_0.qad"
        }
        KeyframeGroup {
            target: neck
            property: "rotation"
            keyframeSource: "animations/neck_rotation_0.qad"
        }
        KeyframeGroup {
            target: neck
            property: "scale"
            keyframeSource: "animations/neck_scale_0.qad"
        }
        KeyframeGroup {
            target: earUpright
            property: "rotation"
            keyframeSource: "animations/earUpright_rotation_0.qad"
        }
        KeyframeGroup {
            target: head
            property: "rotation"
            keyframeSource: "animations/head_rotation_0.qad"
        }
        KeyframeGroup {
            target: lidNear
            property: "position"
            keyframeSource: "animations/lidNear_position_0.qad"
        }
        KeyframeGroup {
            target: lidNear
            property: "rotation"
            keyframeSource: "animations/lidNear_rotation_0.qad"
        }
        KeyframeGroup {
            target: lidDepthNear
            property: "position"
            keyframeSource: "animations/lidDepthNear_position_0.qad"
        }
        KeyframeGroup {
            target: lidDepthNear
            property: "rotation"
            keyframeSource: "animations/lidDepthNear_rotation_0.qad"
        }
        KeyframeGroup {
            target: eyeFar
            property: "rotation"
            keyframeSource: "animations/eyeFar_rotation_0.qad"
        }
        KeyframeGroup {
            target: lidFar
            property: "position"
            keyframeSource: "animations/lidFar_position_0.qad"
        }
        KeyframeGroup {
            target: lidDepthFar
            property: "position"
            keyframeSource: "animations/lidDepthFar_position_0.qad"
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
        endFrame: 4034
        currentFrame: node.clipTime
        enabled: node.clipName === "Listen"
        KeyframeGroup {
            target: eyeNear
            property: "rotation"
            keyframeSource: "animations/eyeNear_rotation_1.qad"
        }
        KeyframeGroup {
            target: chest
            property: "rotation"
            keyframeSource: "animations/chest_rotation_1.qad"
        }
        KeyframeGroup {
            target: earFolded
            property: "rotation"
            keyframeSource: "animations/earFolded_rotation_1.qad"
        }
        KeyframeGroup {
            target: neck
            property: "rotation"
            keyframeSource: "animations/neck_rotation_1.qad"
        }
        KeyframeGroup {
            target: earUpright
            property: "rotation"
            keyframeSource: "animations/earUpright_rotation_1.qad"
        }
        KeyframeGroup {
            target: head
            property: "rotation"
            keyframeSource: "animations/head_rotation_1.qad"
        }
        KeyframeGroup {
            target: lidNear
            property: "position"
            keyframeSource: "animations/lidNear_position_1.qad"
        }
        KeyframeGroup {
            target: lidDepthNear
            property: "position"
            keyframeSource: "animations/lidDepthNear_position_1.qad"
        }
        KeyframeGroup {
            target: eyeFar
            property: "rotation"
            keyframeSource: "animations/eyeFar_rotation_1.qad"
        }
        KeyframeGroup {
            target: lidFar
            property: "position"
            keyframeSource: "animations/lidFar_position_1.qad"
        }
        KeyframeGroup {
            target: lidDepthFar
            property: "position"
            keyframeSource: "animations/lidDepthFar_position_1.qad"
        }
        KeyframeGroup {
            target: tailMid
            property: "rotation"
            keyframeSource: "animations/tailMid_rotation_1.qad"
        }
        KeyframeGroup {
            target: tailTip
            property: "rotation"
            keyframeSource: "animations/tailTip_rotation_1.qad"
        }
    }
    Timeline {
        id: respond_timeline
        objectName: "Respond"
        property real framesPerSecond: 1000
        startFrame: 0
        endFrame: 2434
        currentFrame: node.clipTime
        enabled: node.clipName === "Respond"
        KeyframeGroup {
            target: eyeNear
            property: "rotation"
            keyframeSource: "animations/eyeNear_rotation_2.qad"
        }
        KeyframeGroup {
            target: chest
            property: "position"
            keyframeSource: "animations/chest_position_2.qad"
        }
        KeyframeGroup {
            target: chest
            property: "rotation"
            keyframeSource: "animations/chest_rotation_2.qad"
        }
        KeyframeGroup {
            target: earFolded
            property: "rotation"
            keyframeSource: "animations/earFolded_rotation_2.qad"
        }
        KeyframeGroup {
            target: neck
            property: "rotation"
            keyframeSource: "animations/neck_rotation_2.qad"
        }
        KeyframeGroup {
            target: earUpright
            property: "rotation"
            keyframeSource: "animations/earUpright_rotation_2.qad"
        }
        KeyframeGroup {
            target: head
            property: "rotation"
            keyframeSource: "animations/head_rotation_2.qad"
        }
        KeyframeGroup {
            target: lidNear
            property: "position"
            keyframeSource: "animations/lidNear_position_2.qad"
        }
        KeyframeGroup {
            target: lidDepthNear
            property: "position"
            keyframeSource: "animations/lidDepthNear_position_2.qad"
        }
        KeyframeGroup {
            target: eyeFar
            property: "rotation"
            keyframeSource: "animations/eyeFar_rotation_2.qad"
        }
        KeyframeGroup {
            target: lidFar
            property: "position"
            keyframeSource: "animations/lidFar_position_2.qad"
        }
        KeyframeGroup {
            target: lidDepthFar
            property: "position"
            keyframeSource: "animations/lidDepthFar_position_2.qad"
        }
        KeyframeGroup {
            target: tailBase
            property: "rotation"
            keyframeSource: "animations/tailBase_rotation_2.qad"
        }
        KeyframeGroup {
            target: tailMid
            property: "rotation"
            keyframeSource: "animations/tailMid_rotation_2.qad"
        }
        KeyframeGroup {
            target: tailTip
            property: "rotation"
            keyframeSource: "animations/tailTip_rotation_2.qad"
        }
    }
}
