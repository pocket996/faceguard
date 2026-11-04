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
    property var transitionTo: []
    function snapshot(joint) {
        var p=joint.position, q=joint.rotation, s=joint.scale
        return {position: Qt.vector3d(p.x,p.y,p.z), rotation: Qt.quaternion(q.scalar,q.x,q.y,q.z), scale: Qt.vector3d(s.x,s.y,s.z)}
    }
    function prepareTransition(targetName, targetTime) {
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
        if (targetName !== undefined) {
            resetAndSelect(targetName)
            clipTime = targetTime || 0
            transitionTo = []
            for (var j = 0; j < skin.joints.length; ++j) transitionTo.push(snapshot(skin.joints[j]))
        } else transitionTo = bindTransforms
        clipName = ""
        blendToBind(0)
        return changed
    }
    function blendToBind(t) {
        for (var i = 0; i < transitionFrom.length; ++i) {
            var from = transitionFrom[i], to = transitionTo[i], joint = skin.joints[i]
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
    function breathe(phase) {
        for (var i = 0; i < skin.joints.length; ++i) {
            if (skin.joints[i].objectName !== "Chest") continue
            var rest = bindTransforms[i].scale, wave = Math.sin(phase)
            skin.joints[i].scale = Qt.vector3d(rest.x*(1+.009*wave), rest.y*(1+.006*wave), rest.z*(1+.012*wave))
        }
    }
    function flutterEars(phase) {
        // A small local pinna adjustment over the freshly sampled clip pose.
        // Both additive curves begin/end at zero and differ in timing.
        for (var i = 0; i < skin.joints.length; ++i) {
            var joint = skin.joints[i], angle = 0
            if (joint.objectName === "EarUpright") angle = 4*(Math.sin(2*phase)+.30*Math.sin(5*phase))
            else if (joint.objectName === "EarFolded") angle = 3*(Math.sin(2*phase-.7)+Math.sin(.7)*Math.cos(phase))
            else continue
            var half = angle*Math.PI/360, c = Math.cos(half), s = Math.sin(half), q = joint.rotation
            joint.rotation = Qt.quaternion(q.scalar*c-q.z*s,q.x*c+q.y*s,q.y*c-q.x*s,q.z*c+q.scalar*s)
        }
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
            chin,
            browNear,
            browFar,
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
            Qt.matrix4x4(1, 0, 0, -0.34, 0, 1, 0, -2.65, 0, 0, 1, -1.23, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.0302128, 0, 1, 0, -3.21686, 0, 0, 1, -1.19498, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.811678, 0, 1, 0, -3.09262, 0, 0, 1, -0.83271, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.7, 0, 1, 0, -0.45, 0, 0, 1, 0.65, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 1.05, 0, 1, 0, -1.03, 0, 0, 1, 1.2, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 1.04, 0, 1, 0, -1.6, 0, 0, 1, 1.15, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.25, 0, 1, 0, -0.1, 0, 0, 1, -1.2, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.95, 0, 1, 0, -0.1, 0, 0, 1, -1.2, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.55, 0, 1, 0, -0.1, 0, 0, 1, 0.7, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.85, 0, 1, 0, -0.1, 0, 0, 1, 0.7, 0, 0, 0, 1)
        ]
    }
    CustomMaterial {
        id: transparent_convex_cornea_Far_material
        objectName: "Transparent convex cornea Far"
        property real highlightStrength: 1.0
        shadingMode: CustomMaterial.Shaded
        cullMode: Material.BackFaceCulling
        sourceBlend: CustomMaterial.SrcAlpha
        destinationBlend: CustomMaterial.OneMinusSrcAlpha
        sourceAlphaBlend: CustomMaterial.One
        destinationAlphaBlend: CustomMaterial.OneMinusSrcAlpha
        fragmentShader: "cornea.frag"
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
            chin,
            browNear,
            browFar,
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
            Qt.matrix4x4(1, 0, 0, -0.34, 0, 1, 0, -2.65, 0, 0, 1, -1.23, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.0302128, 0, 1, 0, -3.21686, 0, 0, 1, -1.19498, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.811678, 0, 1, 0, -3.09262, 0, 0, 1, -0.83271, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.7, 0, 1, 0, -0.45, 0, 0, 1, 0.65, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 1.05, 0, 1, 0, -1.03, 0, 0, 1, 1.2, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 1.04, 0, 1, 0, -1.6, 0, 0, 1, 1.15, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.25, 0, 1, 0, -0.1, 0, 0, 1, -1.2, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.95, 0, 1, 0, -0.1, 0, 0, 1, -1.2, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, 0.55, 0, 1, 0, -0.1, 0, 0, 1, 0.7, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.85, 0, 1, 0, -0.1, 0, 0, 1, 0.7, 0, 0, 0, 1)
        ]
    }
    CustomMaterial {
        id: transparent_convex_cornea_Near_material
        objectName: "Transparent convex cornea Near"
        property real highlightStrength: 1.0
        shadingMode: CustomMaterial.Shaded
        cullMode: Material.BackFaceCulling
        sourceBlend: CustomMaterial.SrcAlpha
        destinationBlend: CustomMaterial.OneMinusSrcAlpha
        sourceAlphaBlend: CustomMaterial.One
        destinationAlphaBlend: CustomMaterial.OneMinusSrcAlpha
        fragmentShader: "cornea.frag"
    }
    Skin {
        id: skin16
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
            chin,
            browNear,
            browFar,
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
            Qt.matrix4x4(1, 0, 0, -0.34, 0, 1, 0, -2.65, 0, 0, 1, -1.23, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.0302128, 0, 1, 0, -3.21686, 0, 0, 1, -1.19498, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.811678, 0, 1, 0, -3.09262, 0, 0, 1, -0.83271, 0, 0, 0, 1),
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
        id: radial_amber_iris_Far_material
        objectName: "Radial amber iris Far"
        roughness: 0.3799999952316284
        cullMode: PrincipledMaterial.NoCulling
        alphaMode: PrincipledMaterial.Opaque
        clearcoatAmount: 0.10000000149011612
    }
    Skin {
        id: skin20
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
            chin,
            browNear,
            browFar,
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
            Qt.matrix4x4(1, 0, 0, -0.34, 0, 1, 0, -2.65, 0, 0, 1, -1.23, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.0302128, 0, 1, 0, -3.21686, 0, 0, 1, -1.19498, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.811678, 0, 1, 0, -3.09262, 0, 0, 1, -0.83271, 0, 0, 0, 1),
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
        id: radial_amber_iris_Near_material
        objectName: "Radial amber iris Near"
        roughness: 0.3799999952316284
        cullMode: PrincipledMaterial.NoCulling
        alphaMode: PrincipledMaterial.Opaque
        clearcoatAmount: 0.10000000149011612
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
            chin,
            browNear,
            browFar,
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
            Qt.matrix4x4(1, 0, 0, -0.34, 0, 1, 0, -2.65, 0, 0, 1, -1.23, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.0302128, 0, 1, 0, -3.21686, 0, 0, 1, -1.19498, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.811678, 0, 1, 0, -3.09262, 0, 0, 1, -0.83271, 0, 0, 0, 1),
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
        id: recessed_pupil_Far_material
        objectName: "Recessed pupil Far"
        baseColor: "#ff000000"
        roughness: 0.27000001072883606
        cullMode: PrincipledMaterial.NoCulling
        alphaMode: PrincipledMaterial.Opaque
        clearcoatAmount: 0.05000000074505806
    }
    Skin {
        id: skin28
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
            chin,
            browNear,
            browFar,
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
            Qt.matrix4x4(1, 0, 0, -0.34, 0, 1, 0, -2.65, 0, 0, 1, -1.23, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.0302128, 0, 1, 0, -3.21686, 0, 0, 1, -1.19498, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.811678, 0, 1, 0, -3.09262, 0, 0, 1, -0.83271, 0, 0, 0, 1),
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
        id: recessed_pupil_Near_material
        objectName: "Recessed pupil Near"
        baseColor: "#ff000000"
        roughness: 0.27000001072883606
        cullMode: PrincipledMaterial.NoCulling
        alphaMode: PrincipledMaterial.Opaque
        clearcoatAmount: 0.05000000074505806
    }
    Skin {
        id: skin32
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
            chin,
            browNear,
            browFar,
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
            Qt.matrix4x4(1, 0, 0, -0.34, 0, 1, 0, -2.65, 0, 0, 1, -1.23, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.0302128, 0, 1, 0, -3.21686, 0, 0, 1, -1.19498, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.811678, 0, 1, 0, -3.09262, 0, 0, 1, -0.83271, 0, 0, 0, 1),
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
        id: warm_recessed_sclera_Far_material
        objectName: "Warm recessed sclera Far"
        baseColor: "#ff635236"
        roughness: 0.30000001192092896
        cullMode: PrincipledMaterial.NoCulling
        alphaMode: PrincipledMaterial.Opaque
        clearcoatAmount: 0.18000000715255737
    }
    Skin {
        id: skin36
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
            chin,
            browNear,
            browFar,
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
            Qt.matrix4x4(1, 0, 0, -0.34, 0, 1, 0, -2.65, 0, 0, 1, -1.23, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.0302128, 0, 1, 0, -3.21686, 0, 0, 1, -1.19498, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.811678, 0, 1, 0, -3.09262, 0, 0, 1, -0.83271, 0, 0, 0, 1),
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
        id: warm_recessed_sclera_Near_material
        objectName: "Warm recessed sclera Near"
        baseColor: "#ff635236"
        roughness: 0.30000001192092896
        cullMode: PrincipledMaterial.NoCulling
        alphaMode: PrincipledMaterial.Opaque
        clearcoatAmount: 0.18000000715255737
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
            chin,
            browNear,
            browFar,
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
            Qt.matrix4x4(1, 0, 0, -0.34, 0, 1, 0, -2.65, 0, 0, 1, -1.23, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.0302128, 0, 1, 0, -3.21686, 0, 0, 1, -1.19498, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.811678, 0, 1, 0, -3.09262, 0, 0, 1, -0.83271, 0, 0, 0, 1),
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
        id: skin43
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
            chin,
            browNear,
            browFar,
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
            Qt.matrix4x4(1, 0, 0, -0.34, 0, 1, 0, -2.65, 0, 0, 1, -1.23, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.0302128, 0, 1, 0, -3.21686, 0, 0, 1, -1.19498, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.811678, 0, 1, 0, -3.09262, 0, 0, 1, -0.83271, 0, 0, 0, 1),
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
        id: skin46
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
            chin,
            browNear,
            browFar,
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
            Qt.matrix4x4(1, 0, 0, -0.34, 0, 1, 0, -2.65, 0, 0, 1, -1.23, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.0302128, 0, 1, 0, -3.21686, 0, 0, 1, -1.19498, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.811678, 0, 1, 0, -3.09262, 0, 0, 1, -0.83271, 0, 0, 0, 1),
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
        id: skin49
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
            chin,
            browNear,
            browFar,
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
            Qt.matrix4x4(1, 0, 0, -0.34, 0, 1, 0, -2.65, 0, 0, 1, -1.23, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.0302128, 0, 1, 0, -3.21686, 0, 0, 1, -1.19498, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.811678, 0, 1, 0, -3.09262, 0, 0, 1, -0.83271, 0, 0, 0, 1),
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
        id: skin52
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
            chin,
            browNear,
            browFar,
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
            Qt.matrix4x4(1, 0, 0, -0.34, 0, 1, 0, -2.65, 0, 0, 1, -1.23, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.0302128, 0, 1, 0, -3.21686, 0, 0, 1, -1.19498, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.811678, 0, 1, 0, -3.09262, 0, 0, 1, -0.83271, 0, 0, 0, 1),
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
        id: skin55
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
            chin,
            browNear,
            browFar,
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
            Qt.matrix4x4(1, 0, 0, -0.34, 0, 1, 0, -2.65, 0, 0, 1, -1.23, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.0302128, 0, 1, 0, -3.21686, 0, 0, 1, -1.19498, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.811678, 0, 1, 0, -3.09262, 0, 0, 1, -0.83271, 0, 0, 0, 1),
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
        id: skin58
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
            chin,
            browNear,
            browFar,
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
            Qt.matrix4x4(1, 0, 0, -0.34, 0, 1, 0, -2.65, 0, 0, 1, -1.23, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.0302128, 0, 1, 0, -3.21686, 0, 0, 1, -1.19498, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.811678, 0, 1, 0, -3.09262, 0, 0, 1, -0.83271, 0, 0, 0, 1),
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
        id: skin62
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
            chin,
            browNear,
            browFar,
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
            Qt.matrix4x4(1, 0, 0, -0.34, 0, 1, 0, -2.65, 0, 0, 1, -1.23, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.0302128, 0, 1, 0, -3.21686, 0, 0, 1, -1.19498, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.811678, 0, 1, 0, -3.09262, 0, 0, 1, -0.83271, 0, 0, 0, 1),
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
        id: skin65
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
            chin,
            browNear,
            browFar,
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
            Qt.matrix4x4(1, 0, 0, -0.34, 0, 1, 0, -2.65, 0, 0, 1, -1.23, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.0302128, 0, 1, 0, -3.21686, 0, 0, 1, -1.19498, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.811678, 0, 1, 0, -3.09262, 0, 0, 1, -0.83271, 0, 0, 0, 1),
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
        id: skin69
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
            chin,
            browNear,
            browFar,
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
            Qt.matrix4x4(1, 0, 0, -0.34, 0, 1, 0, -2.65, 0, 0, 1, -1.23, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.0302128, 0, 1, 0, -3.21686, 0, 0, 1, -1.19498, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.811678, 0, 1, 0, -3.09262, 0, 0, 1, -0.83271, 0, 0, 0, 1),
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
        id: skin72
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
            chin,
            browNear,
            browFar,
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
            Qt.matrix4x4(1, 0, 0, -0.34, 0, 1, 0, -2.65, 0, 0, 1, -1.23, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.0302128, 0, 1, 0, -3.21686, 0, 0, 1, -1.19498, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.811678, 0, 1, 0, -3.09262, 0, 0, 1, -0.83271, 0, 0, 0, 1),
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
        id: skin75
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
            chin,
            browNear,
            browFar,
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
            Qt.matrix4x4(1, 0, 0, -0.34, 0, 1, 0, -2.65, 0, 0, 1, -1.23, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.0302128, 0, 1, 0, -3.21686, 0, 0, 1, -1.19498, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.811678, 0, 1, 0, -3.09262, 0, 0, 1, -0.83271, 0, 0, 0, 1),
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
        id: skin78
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
            chin,
            browNear,
            browFar,
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
            Qt.matrix4x4(1, 0, 0, -0.34, 0, 1, 0, -2.65, 0, 0, 1, -1.23, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.0302128, 0, 1, 0, -3.21686, 0, 0, 1, -1.19498, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.811678, 0, 1, 0, -3.09262, 0, 0, 1, -0.83271, 0, 0, 0, 1),
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
        id: skin81
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
            chin,
            browNear,
            browFar,
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
            Qt.matrix4x4(1, 0, 0, -0.34, 0, 1, 0, -2.65, 0, 0, 1, -1.23, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.0302128, 0, 1, 0, -3.21686, 0, 0, 1, -1.19498, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.811678, 0, 1, 0, -3.09262, 0, 0, 1, -0.83271, 0, 0, 0, 1),
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
        id: skin84
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
            chin,
            browNear,
            browFar,
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
            Qt.matrix4x4(1, 0, 0, -0.34, 0, 1, 0, -2.65, 0, 0, 1, -1.23, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.0302128, 0, 1, 0, -3.21686, 0, 0, 1, -1.19498, 0, 0, 0, 1),
            Qt.matrix4x4(1, 0, 0, -0.811678, 0, 1, 0, -3.09262, 0, 0, 1, -0.83271, 0, 0, 0, 1),
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
            id: eyeCorneaFar
            objectName: "EyeCorneaFar"
            source: "meshes/eyeCorneaFar_mesh.mesh"
            skin: skin12
            materials: [
                transparent_convex_cornea_Far_material
            ]
        }
        Model {
            id: eyeCorneaNear
            objectName: "EyeCorneaNear"
            source: "meshes/eyeCorneaNear_mesh.mesh"
            skin: skin16
            materials: [
                transparent_convex_cornea_Near_material
            ]
        }
        Model {
            id: eyeIrisFar
            objectName: "EyeIrisFar"
            source: "meshes/eyeIrisFar_mesh.mesh"
            skin: skin20
            materials: [
                radial_amber_iris_Far_material
            ]
        }
        Model {
            id: eyeIrisNear
            objectName: "EyeIrisNear"
            source: "meshes/eyeIrisNear_mesh.mesh"
            skin: skin24
            materials: [
                radial_amber_iris_Near_material
            ]
        }
        Model {
            id: eyePupilFar
            objectName: "EyePupilFar"
            source: "meshes/eyePupilFar_mesh.mesh"
            skin: skin28
            materials: [
                recessed_pupil_Far_material
            ]
        }
        Model {
            id: eyePupilNear
            objectName: "EyePupilNear"
            source: "meshes/eyePupilNear_mesh.mesh"
            skin: skin32
            materials: [
                recessed_pupil_Near_material
            ]
        }
        Model {
            id: eyeScleraFar
            objectName: "EyeScleraFar"
            source: "meshes/eyeScleraFar_mesh.mesh"
            skin: skin36
            materials: [
                warm_recessed_sclera_Far_material
            ]
        }
        Model {
            id: eyeScleraNear
            objectName: "EyeScleraNear"
            source: "meshes/eyeScleraNear_mesh.mesh"
            skin: skin40
            materials: [
                warm_recessed_sclera_Near_material
            ]
        }
        Model {
            id: fineWhisker
            objectName: "FineWhisker"
            source: "meshes/fine_whisker_mesh.mesh"
            skin: skin43
            materials: [
                ivory_jade_eyelid_material
            ]
        }
        Model {
            id: fineWhisker_001
            objectName: "FineWhisker.001"
            source: "meshes/fine_whisker_001_mesh.mesh"
            skin: skin46
            materials: [
                ivory_jade_eyelid_material
            ]
        }
        Model {
            id: fineWhisker_002
            objectName: "FineWhisker.002"
            source: "meshes/fine_whisker_002_mesh.mesh"
            skin: skin49
            materials: [
                ivory_jade_eyelid_material
            ]
        }
        Model {
            id: fineWhisker_003
            objectName: "FineWhisker.003"
            source: "meshes/fine_whisker_003_mesh.mesh"
            skin: skin52
            materials: [
                ivory_jade_eyelid_material
            ]
        }
        Model {
            id: fineWhisker_004
            objectName: "FineWhisker.004"
            source: "meshes/fine_whisker_004_mesh.mesh"
            skin: skin55
            materials: [
                ivory_jade_eyelid_material
            ]
        }
        Model {
            id: fineWhisker_005
            objectName: "FineWhisker.005"
            source: "meshes/fine_whisker_005_mesh.mesh"
            skin: skin58
            materials: [
                ivory_jade_eyelid_material
            ]
        }
        Model {
            id: lowerLidFar
            objectName: "LowerLidFar"
            source: "meshes/lowerLidFar_mesh.mesh"
            skin: skin62
            materials: [
                continuous_facial_skin_material
            ]
        }
        Model {
            id: lowerLidNear
            objectName: "LowerLidNear"
            source: "meshes/lowerLidNear_mesh.mesh"
            skin: skin65
            materials: [
                continuous_facial_skin_material
            ]
        }
        Model {
            id: lowerLinerFar
            objectName: "LowerLinerFar"
            source: "meshes/lowerLinerFar_mesh.mesh"
            skin: skin69
            materials: [
                dark_brown_lid_margin_material
            ]
        }
        Model {
            id: lowerLinerNear
            objectName: "LowerLinerNear"
            source: "meshes/lowerLinerNear_mesh.mesh"
            skin: skin72
            materials: [
                dark_brown_lid_margin_material
            ]
        }
        Model {
            id: upperLidFar
            objectName: "UpperLidFar"
            source: "meshes/upperLidFar_mesh.mesh"
            skin: skin75
            materials: [
                continuous_facial_skin_material
            ]
        }
        Model {
            id: upperLidNear
            objectName: "UpperLidNear"
            source: "meshes/upperLidNear_mesh.mesh"
            skin: skin78
            materials: [
                continuous_facial_skin_material
            ]
        }
        Model {
            id: upperLinerFar
            objectName: "UpperLinerFar"
            source: "meshes/upperLinerFar_mesh.mesh"
            skin: skin81
            materials: [
                dark_brown_lid_margin_material
            ]
        }
        Model {
            id: upperLinerNear
            objectName: "UpperLinerNear"
            source: "meshes/upperLinerNear_mesh.mesh"
            skin: skin84
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
                            Node {
                                id: chin
                                objectName: "Chin"
                                position: Qt.vector3d(-0.00999999, 0.0500002, 0.58)
                                scale: Qt.vector3d(1, 1, 1)
                            }
                            Node {
                                id: browNear
                                objectName: "BrowNear"
                                position: Qt.vector3d(-0.319787, 0.616855, 0.544978)
                                scale: Qt.vector3d(1, 1, 1)
                            }
                            Node {
                                id: browFar
                                objectName: "BrowFar"
                                position: Qt.vector3d(0.461678, 0.492622, 0.18271)
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
        endFrame: 6034
        currentFrame: node.clipTime
        enabled: node.clipName === "Idle"
        KeyframeGroup {
            target: earFolded
            property: "rotation"
            keyframeSource: "animations/earFolded_rotation_0.qad"
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
            target: neck
            property: "scale"
            keyframeSource: "animations/neck_scale_0.qad"
        }
        KeyframeGroup {
            target: head
            property: "rotation"
            keyframeSource: "animations/head_rotation_0.qad"
        }
        KeyframeGroup {
            target: earUpright
            property: "rotation"
            keyframeSource: "animations/earUpright_rotation_0.qad"
        }
        KeyframeGroup {
            target: eyeNear
            property: "rotation"
            keyframeSource: "animations/eyeNear_rotation_0.qad"
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
            target: chin
            property: "rotation"
            keyframeSource: "animations/chin_rotation_0.qad"
        }
        KeyframeGroup {
            target: browNear
            property: "position"
            keyframeSource: "animations/browNear_position_0.qad"
        }
        KeyframeGroup {
            target: browNear
            property: "rotation"
            keyframeSource: "animations/browNear_rotation_0.qad"
        }
        KeyframeGroup {
            target: browFar
            property: "position"
            keyframeSource: "animations/browFar_position_0.qad"
        }
        KeyframeGroup {
            target: browFar
            property: "rotation"
            keyframeSource: "animations/browFar_rotation_0.qad"
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
            target: earFolded
            property: "rotation"
            keyframeSource: "animations/earFolded_rotation_1.qad"
        }
        KeyframeGroup {
            target: chest
            property: "rotation"
            keyframeSource: "animations/chest_rotation_1.qad"
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
            target: earUpright
            property: "rotation"
            keyframeSource: "animations/earUpright_rotation_1.qad"
        }
        KeyframeGroup {
            target: eyeNear
            property: "rotation"
            keyframeSource: "animations/eyeNear_rotation_1.qad"
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
            target: chin
            property: "rotation"
            keyframeSource: "animations/chin_rotation_1.qad"
        }
        KeyframeGroup {
            target: browNear
            property: "position"
            keyframeSource: "animations/browNear_position_1.qad"
        }
        KeyframeGroup {
            target: browFar
            property: "position"
            keyframeSource: "animations/browFar_position_1.qad"
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
            target: earFolded
            property: "rotation"
            keyframeSource: "animations/earFolded_rotation_2.qad"
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
            target: neck
            property: "rotation"
            keyframeSource: "animations/neck_rotation_2.qad"
        }
        KeyframeGroup {
            target: head
            property: "rotation"
            keyframeSource: "animations/head_rotation_2.qad"
        }
        KeyframeGroup {
            target: earUpright
            property: "rotation"
            keyframeSource: "animations/earUpright_rotation_2.qad"
        }
        KeyframeGroup {
            target: eyeNear
            property: "rotation"
            keyframeSource: "animations/eyeNear_rotation_2.qad"
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
            target: chin
            property: "rotation"
            keyframeSource: "animations/chin_rotation_2.qad"
        }
        KeyframeGroup {
            target: browNear
            property: "position"
            keyframeSource: "animations/browNear_position_2.qad"
        }
        KeyframeGroup {
            target: browFar
            property: "position"
            keyframeSource: "animations/browFar_position_2.qad"
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
