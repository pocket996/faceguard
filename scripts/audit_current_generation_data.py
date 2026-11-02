"""Reconcile existing local source evidence, rejected faces and frozen split availability."""
from collections import Counter,defaultdict
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from faceguard.data_locations import data_location,resolve_data_path


def read_csv(path):
    with path.open(encoding='utf-8-sig',newline='') as file:return list(csv.DictReader(file))


def sha(path):
    with Path(path).open('rb') as file:return hashlib.file_digest(file,'sha256').hexdigest()


def build_pools():
    from PIL import Image
    source=data_location('generation_joint_manifests')/'manifest.csv'
    source_protocol=json.loads((source.parent/'protocol.json').read_text(encoding='utf-8'))
    if sha(source)!=source_protocol['manifest_sha256']:raise ValueError('Frozen source manifest changed')
    out=data_location('current_generation_pools');out.mkdir(parents=True,exist_ok=True)
    if (out/'pool-protocol.json').exists():raise FileExistsError('Reuse pools already frozen')
    real=defaultdict(list);development=[];external=[]
    with source.open(encoding='utf-8-sig',newline='') as file:
        for row in csv.DictReader(file):
            if row['split']=='train' and row['label']=='0':real[row['source']].append(row)
            if row['label']=='1' and row['method'].startswith('gpt-'):
                (development if row['split'] in ('train','val') else external).append(row)
    def order(row):return hashlib.sha256(('real-reuse-v1:'+row['sample_id']).encode()).hexdigest()
    selected=[];groups=set();pixels=set();ids=set()
    def accept(row):
        if row['group'] in groups or row['pixel_sha256'] in pixels:return False
        selected.append(row);groups.add(row['group']);pixels.add(row['pixel_sha256']);ids.add(row['sample_id']);return True
    for name,target in [('OpenFake:pexels',150),('OpenFake:laion',150),('LFW',700),('FFHQ-256-mirror',1000),('DFF',1000)]:
        count=0
        for row in sorted(real[name],key=order):
            if count>=target:break
            count+=int(accept(row))
    for row in sorted((r for values in real.values() for r in values if r['sample_id'] not in ids),key=order):
        if len(selected)>=3000:break
        accept(row)
    if len(selected)!=3000:raise ValueError('Insufficient independent existing real groups for reuse target')
    names={'real-training-pool.csv':selected,'gpt-development.csv':development,'gpt-external-regression.csv':external}
    for name,rows in names.items():
        for row in rows:
            with Image.open(resolve_data_path(row['path'])) as image:
                if hashlib.sha256(image.convert('RGB').tobytes()).hexdigest()!=row['pixel_sha256']:
                    raise ValueError('Reuse pool pixels changed')
        with (out/name).open('w',encoding='utf-8',newline='') as file:
            fields=sorted(set().union(*(r.keys() for r in rows)));writer=csv.DictWriter(file,fieldnames=fields);writer.writeheader();writer.writerows(rows)
    report=dict(state='complete',version='current-data-low-fpr-20261031',source_manifest_sha256=sha(source),
        real_training_rows=len(selected),real_training_sources=dict(Counter(r['source'] for r in selected)),
        real_unique_groups=len(groups),real_unique_pixels=len(pixels),
        gpt_development_roles=dict(Counter(r['split'] for r in development)),gpt_external_regression_rows=len(external),
        files={name:dict(rows=len(rows),sha256=sha(out/name)) for name,rows in names.items()},
        policy='Only existing train real rows selected; all original group/split/labels retained; one real row per component group and pixel; GPT external rows stay outside fitting',
        limitations=['Reuse subsets, not newly collected independent images','Publisher source labels retained, no exhaustive manual truth or biometric audit',
            'No complete age/camera/beauty/screenshot annotations; counts do not prove scene diversity'])
    (out/'pool-protocol.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True),flush=True)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--pools-only',action='store_true')
    args=parser.parse_args()
    if args.pools_only:build_pools();return
    from PIL import Image,ImageOps
    start=time.monotonic();out=data_location('current_data_audit');out.mkdir(parents=True,exist_ok=True)
    if (out/'report.json').exists():raise FileExistsError('Audit result already exists')
    raw=data_location('openfake');processed=data_location('openfake_faces')
    receipts=json.loads((raw/'receipts.json').read_text(encoding='utf-8'))
    metadata=json.loads((raw/'selected_metadata.json').read_text(encoding='utf-8'))
    protocol=json.loads((raw/'PROTOCOL.json').read_text(encoding='utf-8'))
    meta={r['row_id']:r for r in metadata}
    if len(meta)!=len(metadata) or len({r['row_id'] for r in receipts})!=len(receipts):raise ValueError('Duplicate metadata ID')
    crops=read_csv(processed/'new_manifest.csv')+read_csv(processed/'quarantined.csv')
    crop_map={r['sample_id']:r for r in crops}
    old_quarantine={r['sample_id'] for r in read_csv(processed/'quarantined.csv')}
    rejected={r['row_id']:r for r in json.loads((processed/'rejected.json').read_text(encoding='utf-8'))}
    joint_folder=data_location('generation_joint_manifests')
    joint_quarantine={r['sample_id'] for r in read_csv(joint_folder/'quarantined.csv')}
    allocation={};counts=Counter();group_roles=defaultdict(set);pixels=defaultdict(set)
    manifest=joint_folder/'manifest.csv'
    joint_protocol=json.loads((joint_folder/'protocol.json').read_text(encoding='utf-8'))
    if sha(manifest)!=joint_protocol['manifest_sha256']:raise ValueError('Frozen manifest changed')
    with manifest.open(encoding='utf-8',newline='') as file:
        for row in csv.DictReader(file):
            counts[row['split']+'|'+row['source']+'|'+row['method']+'|'+row['label']]+=1
            group_roles[row['group']].add(row['split']);pixels[row['pixel_sha256']].add(row['split'])
            if row['source'].startswith('OpenFake:'):allocation[row['sample_id']]=row['split']
    if any(len(v)>1 for mapping in (group_roles,pixels) for v in mapping.values()):raise ValueError('Frozen split leakage')
    del group_roles,pixels
    result=[];verified_crops=set()
    for index,item in enumerate(receipts,1):
        identifier=item['row_id'];source=meta[identifier]
        if any(item[k]!=source[k] for k in ('label','model','dataset_split','image_sha256','use')):
            raise ValueError('Source receipt disagreement')
        if '/--/'+protocol['revision']+'/--/' not in source['image']['src']:
            raise ValueError('Viewer revision differs from pinned local evidence')
        path=resolve_data_path(item['path'])
        if path.stat().st_size!=item['bytes'] or sha(path)!=item['downloaded_sha256']:
            raise ValueError('Raw download changed: '+identifier)
        with Image.open(path) as image:
            format_name=image.format;image=ImageOps.exif_transpose(image);image.load();width,height=image.size
        if identifier in allocation:status='frozen_'+allocation[identifier]
        elif identifier in joint_quarantine:status='joint_similarity_quarantine'
        elif identifier in old_quarantine:status='original_similarity_quarantine'
        elif identifier in rejected:status='rejected_'+rejected[identifier]['reason']
        else:raise ValueError('Unaccounted downloaded row: '+identifier)
        if identifier in crop_map:
            crop=crop_map[identifier];crop_path=resolve_data_path(crop['path'])
            with Image.open(crop_path) as image:
                if image.size!=(128,128):raise ValueError('Unexpected canonical crop size')
                if hashlib.sha256(image.convert('RGB').tobytes()).hexdigest()!=crop['pixel_sha256']:
                    raise ValueError('Canonical crop pixels changed')
            verified_crops.add(identifier)
        result.append(dict(row_id=identifier,model=item['model'],label=item['label'],publisher_split=item['dataset_split'],
            frozen_status=status,raw_path=str(path),width=width,height=height,decoded_format=format_name,
            downloaded_sha256=item['downloaded_sha256'],publisher_sha256=item['image_sha256'],
            download_matches_publisher_hash=item['downloaded_sha256']==item['image_sha256'],
            label_basis='Pinned publisher image-level metadata, not independent per-face truth verification'))
        if index%300==0:print(json.dumps(dict(stage='source-audit',done=index,total=len(receipts))),flush=True)
    with (out/'openfake-row-audit.csv').open('w',encoding='utf-8-sig',newline='') as file:
        writer=csv.DictWriter(file,fieldnames=list(result[0]));writer.writeheader();writer.writerows(result)
    cache_counts=Counter();cache_rows=Counter()
    for path in raw.glob('scan-*.json'):
        split='train' if path.name.startswith('scan-train-') else 'test'
        body=json.loads(path.read_text(encoding='utf-8'))
        for record in body['rows']:cache_counts[split+'|'+record['row']['model']]+=1;cache_rows[split]+=1
    raw_counts=Counter(r['dataset_split']+'|'+r['model'] for r in receipts)
    available=Counter(r['model']+'|'+r['frozen_status'] for r in result)
    targets=[]
    import pyarrow.parquet as pq
    ffhq_receipt=json.loads((data_location('ffhq256')/'receipts.json').read_text(encoding='utf-8'))
    for record in ffhq_receipt['files']:
        path=data_location('ffhq256')/record['file']
        if sha(path)!=record['sha256']:raise ValueError('FFHQ source shard changed')
        targets.append(dict(source='FFHQ-256 mirror',file=str(path),rows=pq.ParquetFile(path).metadata.num_rows,
            source_sha256=record['sha256'],use='Existing source; no extra unexported rows beyond 8,750 total'))
    gan=data_location('gan140k')/'validation-00000.parquet';parquet=pq.ParquetFile(gan)
    gan_counts=Counter()
    for batch in parquet.iter_batches(batch_size=512,columns=['label','generator']):
        for row in batch.to_pylist():gan_counts[str(row['label'])+'|'+str(row['generator'])]+=1
    import_count=sum(raw_counts[k] for k in raw_counts if k.endswith('|gpt-image-1'))
    report=dict(state='complete',seconds=time.monotonic()-start,source_revision=protocol['revision'],
        raw_openfake_receipts_verified=len(receipts),canonical_crops_pixel_verified=len(verified_crops),
        raw_container_format_counts=dict(Counter(r['decoded_format'] for r in result)),
        publisher_hash_matches=sum(r['download_matches_publisher_hash'] for r in result),
        representation_note='Viewer downloads may be re-encoded; downloaded SHA verified against original receipt, publisher hash mismatch is recorded, not silently treated as original bytes',
        metadata_rows=len(metadata),missing_download_ids=sorted(set(meta)-{r['row_id'] for r in receipts}),
        raw_counts=dict(raw_counts),availability=dict(available),cached_scan_rows=dict(cache_rows),cached_source_counts=dict(cache_counts),
        current_manifest_sha256=sha(manifest),current_split_source_label_counts=dict(counts),group_and_pixel_cross_split=False,
        ffhq_shards=targets,gan_validation_rows=parquet.metadata.num_rows,gan_label_generator_counts=dict(gan_counts),
        gan_policy='Original validation remains outside fitting; fixed 200 already observed, remaining rows not promoted to training',
        gpt1_raw_local=import_count,gpt1_train=available['gpt-image-1|frozen_train'],gpt1_val=available['gpt-image-1|frozen_val'],
        gpt_development_faces=available['gpt-image-1|frozen_train']+available['gpt-image-1|frozen_val'],
        gpt_external_regression_faces=sum(v for k,v in available.items() if k.startswith('gpt-') and k.endswith('|frozen_external_test')),
        gpt_total_retained_faces=sum(v for k,v in available.items() if k.startswith('gpt-') and k.rsplit('|',1)[-1] in ('frozen_train','frozen_val','frozen_external_test')),
        gpt_development_gap_to_1000=max(0,1000-available['gpt-image-1|frozen_train']-available['gpt-image-1|frozen_val']),
        actions_completed=['Source/receipt reconciliation','Decoded raw inputs and verified accepted/quarantined crop pixels','Frozen role and cross-split hash/group audit','Cached metadata inventory without network requests','Raw FFHQ shard hash/count check','GAN label-only shard inventory; no image fitting'],
        limitations=['No new images downloaded or synthesized; repeated encoding and augmentations are not independent samples',
            'GPT generation version and labels rely on pinned publisher metadata; user GPT exact version remains unknown',
            'Real-photo volume exceeds 3,000 but age/camera/platform diversity has no complete annotations; volume alone is not coverage',
            'No exhaustive manual label or biometric identity audit; unverified archives remain excluded'])
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ['state','raw_openfake_receipts_verified','canonical_crops_pixel_verified','gpt1_raw_local','gpt1_train','gpt1_val','gpt_development_gap_to_1000','gan_validation_rows']},ensure_ascii=True),flush=True)


if __name__=='__main__':main()
