"""Serial GUI/cancellation/inference integration checks; source data and stable models stay unchanged."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

from project_io import HERE,save_json


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session',type=Path,required=True)
    args=parser.parse_args();base=args.session.resolve()
    gen=json.loads((base/'generation-selection.json').read_text())['selected']['checkpoint']
    photo=json.loads((base/'photo-selection.json').read_text())['selected']['checkpoint']
    results=[]
    commands=[
        ('unit_tests',['-m','unittest','discover','-s',str(HERE.parent/'tests'),'-v']),
        ('stable_two_faces',[str(HERE/'gui.py'),'--self-test','--self-test-task','auto','--test-input',str(base/'two-face-fixture.png'),
            '--expected-decision','separate_results','--test-output',str(base/'ui-final-stable.json'),'--device','cpu']),
        ('candidate_two_faces',[str(HERE/'gui.py'),'--self-test','--self-test-task','auto','--test-input',str(base/'two-face-fixture.png'),
            '--expected-decision','separate_results','--test-output',str(base/'ui-final-candidate.json'),'--device','cpu',
            '--generation-checkpoint',gen,'--photo-checkpoint',photo]),
        ('cancel_detection',[str(HERE/'gui.py'),'--self-test','--self-test-task','auto','--test-input',str(base/'two-face-fixture.png'),
            '--cancel-after-ms','10','--test-output',str(base/'ui-final-cancel.json'),'--device','cpu']),
        ('adaptive_video',[str(HERE/'gui.py'),'--self-test','--self-test-task','manipulation','--expected-decision','video_results',
            '--test-output',str(base/'ui-final-video.json'),'--device','cpu'])]
    for key,arguments in commands:
        print('Integration:',key,flush=True)
        subprocess.run([sys.executable]+arguments,cwd=HERE.parent,check=True)
        results.append(dict(check=key,status='passed'))
        save_json(base/'integration.json',results)


if __name__=='__main__':main()
