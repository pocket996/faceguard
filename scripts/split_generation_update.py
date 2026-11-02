"""Freeze DFF + cleaned legacy splits, linking names, source families and duplicate crops."""
from collections import Counter,defaultdict
from concurrent.futures import ThreadPoolExecutor
import csv
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'reference_run'))
from faceguard.data_locations import DATA_ROOT,data_location,resolve_data_path
from faceguard.model_registry import digest,checked_resource
from faceguard.training_protocol import person_key,group_split,UnionFind,component_split
from audit_near_duplicates import near_pairs
from prepare_generation_update import VERSION,save_json


def read(path):
    with path.open(encoding='utf-8-sig',newline='') as file:return list(csv.DictReader(file))


def write(path,rows):
    fields=sorted(set().union(*(row.keys() for row in rows)))
    with path.open('w',encoding='utf-8',newline='') as file:
        writer=csv.DictWriter(file,fieldnames=fields);writer.writeheader();writer.writerows(rows)


def main():
    import cv2
    import numpy as np
    from PIL import Image
    from scipy.io import loadmat
    cv2.setNumThreads(1)
    start=time.monotonic()
    receipt=data_location('dff_update_provenance')
    folder=data_location('generation_update_manifests')
    folder.mkdir(parents=True,exist_ok=True)
    manifest=folder/'manifest.csv'
    if manifest.exists():
        raise FileExistsError('Frozen manifest already exists; use the existing verified manifest, do not silently resplit')
    crop_report=json.loads((receipt/'crop-report.json').read_text(encoding='utf-8'))
    if crop_report['raw']!=60000 or crop_report['stage']!='crop_complete':raise ValueError('DFF preparation incomplete')
    original_path=ROOT/'reference_run/artifacts/generation/joint/manifest.csv'
    old=read(original_path)
    clean_path=data_location('clean_generation')/'manifest.csv'
    clean=read(clean_path)
    old_by_id={row['sample_id']:row for row in old}
    metadata_path=data_location('wiki_identity_metadata')/'wiki.mat'
    metadata=loadmat(metadata_path,simplify_cells=True)['wiki']
    identities={str(path):str(name) for path,name in zip(metadata['full_path'],metadata['name'])}
    anchors=defaultdict(set)
    def identity_group(row):
        if row['source']=='LFW':return 'person:'+person_key(row['group'][4:])
        return row['group']
    for row in old:
        if row['source']=='LFW':anchors[person_key(row['group'][4:])].add(row['split'])
    baseline=data_location('new_data_evaluation')/'development-baseline/selection.csv'
    observed={row['original_image_path'] for row in read(baseline) if row['source']=='DFF'}
    observed_people={person_key(identities[name]) for name in observed if name in identities}
    rows=[]
    clean_ids={row['sample_id'] for row in clean}
    # Ghost entries participate in leakage screening because the initial checkpoint
    # saw some old train rows subsequently excluded by the historical similarity audit.
    for item in old:
        row=dict(item,path=str(resolve_data_path(item['path'],ROOT/'reference_run')),
                 group=identity_group(item),original_group=item['group'],
                 pretrained_train=item['split']=='train',ghost=item['sample_id'] not in clean_ids,
                 origin='legacy',preexclude='')
        rows.append(row)
    overlap_names=set();unknown_names=0
    for item in read(receipt/'cropped.csv'):
        name=identities.get(item['relative_path'],'')
        name_key=person_key(name)
        if not name_key:unknown_names+=1
        group='person:'+name_key if name_key else item['family']
        known=anchors.get(name_key,set())
        role=next(iter(known)) if len(known)==1 else group_split(group)
        reason=''
        if known:overlap_names.add(name_key)
        was_observed=item['relative_path'] in observed or bool(name_key and name_key in observed_people)
        if was_observed and role=='test':
            if known:reason='previously_observed_DFF_conflicts_with_legacy_test_identity'
            else:role='val'
        if len(known)>1:reason='ambiguous_legacy_name_split'
        rows.append(dict(item,group=group,original_group=item['family'],split=role,
                         pretrained_train=False,ghost=False,origin='DFF',preexclude=reason,
                         identity_name=name,identity_basis='official WIKI name matched to file; normalized-name grouping, not biometrics' if name_key else 'source family only',
                         previously_observed=was_observed))
    print(json.dumps(dict(stage='audit_pixels',rows=len(rows),metadata_names_matched=len(identities),lfw_overlap_names=len(overlap_names))),flush=True)
    def fingerprint(row):
        with Image.open(row['path']) as file:
            image=file.convert('RGB');pixels=image.tobytes()
            gray=np.asarray(image.convert('L'))
        actual=hashlib.sha256(pixels).hexdigest()
        if actual!=row['pixel_sha256']:raise ValueError('Canonical pixel checksum changed: '+row['sample_id'])
        low=cv2.dct(cv2.resize(gray,(32,32),interpolation=cv2.INTER_AREA).astype(np.float32))[:8,:8].flatten()
        bits=low>np.median(low[1:]);bits[0]=False
        row['phash']=sum(int(bit)<<i for i,bit in enumerate(bits))
        return row
    with ThreadPoolExecutor(max_workers=2) as pool:
        for index,_ in enumerate(pool.map(fingerprint,rows),1):
            if index%10000==0:print(json.dumps(dict(stage='pixels',done=index,total=len(rows))),flush=True)
    groups=UnionFind(row['group'] for row in rows)
    pixel_rows=defaultdict(list)
    for index,row in enumerate(rows):pixel_rows[row['pixel_sha256']].append(index)
    conflicting_pixels=set()
    for pixel,indices in pixel_rows.items():
        if len({rows[i]['label'] for i in indices})>1:conflicting_pixels.add(pixel)
        for index in indices[1:]:groups.union(rows[indices[0]]['group'],rows[index]['group'])
    pairs_path=receipt/'near-pairs.csv';pair_count=0
    with pairs_path.open('w',encoding='utf-8',newline='') as file:
        writer=csv.DictWriter(file,fieldnames=['left_id','right_id','distance','left_split','right_split']);writer.writeheader()
        for left,right,distance in near_pairs([row['phash'] for row in rows],6):
            a,b=rows[left],rows[right];groups.union(a['group'],b['group']);pair_count+=1
            writer.writerow(dict(left_id=a['sample_id'],right_id=b['sample_id'],distance=distance,left_split=a['split'],right_split=b['split']))
        file.flush()
    print(json.dumps(dict(stage='group_components',similar_pairs=pair_count)),flush=True)
    components=defaultdict(list)
    for row in rows:components[groups.find(row['group'])].append(row)
    accepted,rejected=[],[]
    for component in components.values():
        role=component_split(component)
        global_group='component:'+hashlib.sha256('|'.join(sorted({r['group'] for r in component})).encode()).hexdigest()[:24]
        conflict=any(row['pixel_sha256'] in conflicting_pixels for row in component)
        seen=set()
        for row in sorted(component,key=lambda r:(r['origin']!='legacy',r['sample_id'])):
            reason=row['preexclude'] or ('conflicting_exact_pixel_labels' if conflict else '')
            if not reason and row['split']!=role:
                reason='connected_to_checkpoint_training_exposure' if role=='train' and any(r['pretrained_train'] for r in component) else 'cross_split_identity_or_similarity_component'
            if not reason and row['pixel_sha256'] in seen:reason='exact_duplicate_within_retained_split'
            if row['ghost']:continue
            if reason:
                rejected.append(dict(row,quarantine_reason=reason));continue
            seen.add(row['pixel_sha256'])
            accepted.append(dict(row,group=global_group,split=role))
    accepted.sort(key=lambda r:(r['split'],r['source'],r['sample_id']))
    for role in ('train','val','test'):
        if {r['label'] for r in accepted if r['split']==role}!={'0','1'}:raise ValueError('Missing class in '+role)
    by_group=defaultdict(set);by_pixel=defaultdict(set)
    for row in accepted:by_group[row['group']].add(row['split']);by_pixel[row['pixel_sha256']].add(row['split'])
    assert all(len(v)==1 for mapping in (by_group,by_pixel) for v in mapping.values())
    write(manifest,accepted);write(folder/'quarantined.csv',rejected)
    train_val=[row for row in accepted if row['split'] in ('train','val')]
    write(folder/'train-val.csv',train_val)
    write(folder/'locked-test.csv',[row for row in accepted if row['split']=='test'])
    report=dict(version=VERSION,stage='split_complete',seed=20261031,
                manifest=str(manifest),manifest_sha256=digest(manifest),raw_crop_report_sha256=digest(receipt/'crop-report.json'),
                original_joint_manifest_sha256=digest(original_path),old_clean_manifest_sha256=digest(clean_path),wiki_metadata_sha256=digest(metadata_path),
                init_checkpoint_sha256=digest(checked_resource('generation.pt')),
                accepted=len(accepted),quarantined=len(rejected),near_hash_pairs=pair_count,identity_name_overlap_with_lfw=len(overlap_names),unknown_name_rows=unknown_names,
                split_counts=dict(Counter(r['split'] for r in accepted)),
                split_source_label_counts=dict(Counter(r['split']+'|'+r['source']+'|'+r['method']+'|'+r['label'] for r in accepted)),
                quarantine_reasons=dict(Counter(r['quarantine_reason'] for r in rejected)),
                group_leakage=False,exact_pixel_leakage=False,test_used_for_model_selection=False,
                policy='DFF named identity/family hash 70/15/15, anchor matching LFW names to existing roles; all pHash<=6 components kept in one role; checkpoint train exposure forces quarantine of connected held-out rows',
                gan_policy='Existing GAN validation remains external development only; no GAN images enter train/val selection',
                limitations=['Normalized publisher names are not biometric identity verification; ambiguous or unannotated faces may remain',
                             'pHash is conservative similarity screening, not proof of identity; difficult edits may evade it',
                             'Old test sources are historical regression, not a fresh never-observed blind benchmark',
                             'Previously observed DFF families/known names cannot enter new DFF final test'],seconds=time.monotonic()-start)
    save_json(folder/'protocol.json',report);save_json(receipt/'split-report.json',report)
    print(json.dumps(report,ensure_ascii=True,indent=2),flush=True)


if __name__=='__main__':main()
