"""Convert the animated GLB with Qt Balsam and expose exclusive clip controls.

Generated QML, mesh, embedded texture and binary tracks live in one directory.
The controlled component selects exactly one timeline and resets bind transforms
before switching; unmodified Balsam output enables all imported clips at once.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--asset',type=Path,required=True)
    p.add_argument('--balsam',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    result=subprocess.run([str(args.balsam.resolve()),str(args.asset.resolve()),'-o',str(out),'--useBinaryKeyframes'],
                          capture_output=True,text=True,errors='replace',
                          creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    (out/'import.log').write_text(result.stdout+'\n'+result.stderr,encoding='utf-8')
    result.check_returncode()
    qml=out/(args.asset.stem+'.qml')
    source=qml.read_text(encoding='utf-8')
    durations={name:int(end) for name,end in re.findall(r'objectName: "(Idle|Respond|Listen)"\s+property real framesPerSecond: 1000\s+startFrame: 0\s+endFrame: (\d+)',source)}
    assert set(durations)=={'Idle','Respond','Listen'},durations
    interface='''
    // FaceGuard clip controller: one skeletal timeline at a time.
    property string clipName: ""
    property real clipTime: 0
    readonly property real clipDuration: clipName === "Respond" ? %d : (clipName === "Listen" ? %d : %d)
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
    Component.onCompleted: {
        for (var i = 0; i < skin.joints.length; ++i) {
            var joint = skin.joints[i]
            bindTransforms.push(snapshot(joint))
        }
        ready = true
    }
'''%(durations['Respond'],durations['Listen'],durations['Idle'])
    source=source.replace('    id: node\n','    id: node\n'+interface,1)
    for name in durations:
        pattern=r'(id: '+name.lower()+r'_timeline\s+objectName: "'+name+r'"[\s\S]*?endFrame: \d+)\s+currentFrame: 0\s+enabled: true\s+animations: TimelineAnimation \{[\s\S]*?\n        \}'
        source,count=re.subn(pattern,lambda m:m.group(1)+'\n        currentFrame: node.clipTime\n        enabled: node.clipName === "'+name+'"',source,count=1)
        assert count==1,'Could not control '+name
    assert 'running: true' not in source
    qml.write_text(source,encoding='utf-8')
    report={'source_glb':str(args.asset.resolve()),'source_sha256':hashlib.sha256(args.asset.read_bytes()).hexdigest(),
            'clip_durations_ms':durations,'exclusive_timeline_control':True,'bind_pose_reset_on_switch':True,
            'files':[str(x.relative_to(out)) for x in out.rglob('*') if x.is_file()]}
    (out/'import-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
