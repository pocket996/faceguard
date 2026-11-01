"""Consolidate known local data with full hash verification and legacy path links."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from faceguard.data_locations import DATA_ROOT, data_location

SESSION = ROOT / 'outputs/autonomous-20261026/started-1248'


def plan(data_root):
    def group(key, source, name, notes='', destination=None):
        return dict(key=key, source=str(source), destination=str(destination or data_location(key, data_root)),
                    name=name, notes=notes)
    return [
        group('dff', Path('D:/datasets/dff'), 'DFF 真图与 SD1.5 生成图', '原始 ZIP 与解包内部结构保留；30,000 对同源家族；未完成正式分组'),
        group('gan140k', Path('D:/datasets/gan140k'), 'GAN140k validation 子集', 'Parquet 原图与限量重编码导出均保留；不可重复计样；不是完整 140k'),
        group('fairfacegen', ROOT / 'data/raw/fairfacegen', 'FairFaceGen FLUX / SD3.5 种子包'),
        group('ffpp', ROOT / 'data/raw/ffpp', 'FF++ c23 视频', '5,000 段；原官方划分不变'),
        group('lfw', ROOT / 'reference_run/data/raw/lfw', 'LFW 真实照片', '原包、照片、下载说明共同保留'),
        group('ffhq256', ROOT / 'reference_run/data/raw/ffhq256', 'FFHQ-256 镜像子集', '两个 Parquet 分片与导出图；不可重复计样'),
        group('ffpp_faces', ROOT / 'data/processed/ffpp', 'FF++ 裁脸与处理缓存', '含历史预览配置；不同配置不可当独立来源相加'),
        group('generation_faces', ROOT / 'reference_run/data/processed/generation128', '原生成任务 128px 裁脸'),
        group('ffpp_manifests', ROOT / 'data/manifests', 'FF++ 清单、下载收据及旧第三方索引', '第三方索引文件名标为 unverified，不代表已审核数据'),
        group('generation_manifest', ROOT / 'reference_run/data/generation_manifest.csv', '原生成任务清单', '原 CSV 字节与哈希保留，旧文件入口使用硬链接'),
        group('examples', ROOT / 'reference_run/data/examples', '参考生成检测演示素材'),
        group('openfake', SESSION / 'openfake-subset', 'OpenFake 原图及下载元数据', '发布者标签；历史开发 / 外部检查材料'),
        group('openfake_faces', SESSION / 'openfake-prepared', 'OpenFake 裁脸与组合清单', '沿用已有分组、隔离与拒绝记录'),
        group('photo_supervision', SESSION / 'photo-supervision-data', '照片监督实验裁脸', '实验用途，不等于真实精确篡改标注'),
        group('sparse_video', SESSION / 'sparse-video', '短暂替换练习视频与记录', '构造回归素材；保留原有 .part 文件，不算已完成视频'),
        group('clean_generation', SESSION / 'clean-generation', '保守去重后的生成清单'),
        group('fairface_evaluation', SESSION / 'fairface-exam', 'FairFace 历史评测包', '将原 Parquet、裁脸、清单和协议作为一套保留；已观察，不能当新盲测'),
        group('locked_evaluation', SESSION / 'locked-exam', '10 月 26 日冻结评测包', '历史已评测；原协议与素材一起保留'),
        group('new_data_evaluation', ROOT / 'outputs/new-data-20261031', '10 月 31 日新数据开发检查', '400 张开发抽查及原 Parquet 字节副本，不是训练划分'),
        group('source_record', Path('D:/datasets/SOURCE.md'), 'U 盘来源原始说明', '原样保留，不把其中历史推测当新审核结论'),
        group('import_receipts', ROOT / 'outputs/data-archive-20261031', 'U 盘全文件复制凭据'),
        group('unverified_inspection', ROOT / 'outputs/local-data-inspection.json', '第三方归档检查原记录'),
        group('unverified_previews', ROOT / 'outputs/local-data-preview', '未核验第三方内容预览', '不用于正式训练'),
        *[group('third_party_' + str(index), Path(source), title,
                '来源、许可与真假依据未确认；仅归档，不进入正式训练或评测',
                data_location('unverified_archives', data_root) / filename)
          for index, (source, filename, title) in enumerate([
              ('D:/qq_files/ai_generated.zip/ai_generated.zip', 'ai_generated-main.zip', '第三方生成标签主包（未核验）'),
              ('D:/qq_files/real.zip/real.zip', 'real-main.zip', '第三方真实标签主包（未核验）'),
              ('D:/qq_files/real.zip/real (1).zip', 'real-secondary.zip', '第三方真实标签另一包（未核验）'),
              ('D:/qq_files/ai_generated (1).zip', 'ai_generated-secondary.zip', '第三方生成标签另一包（未核验）'),
          ])],
    ]


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


def files_in(path):
    if path.is_file():
        yield path, Path('.')
        return
    stack = [path]
    while stack:
        folder = stack.pop()
        with os.scandir(folder) as entries:
            for entry in entries:
                item = Path(entry.path)
                if entry.stat(follow_symlinks=False).st_file_attributes & 0x400:
                    raise ValueError(f'Nested link in source data is not supported: {item}')
                if entry.is_dir(follow_symlinks=False):
                    stack.append(item)
                elif entry.is_file(follow_symlinks=False):
                    yield item, item.relative_to(path)


def sha256(path):
    with path.open('rb') as file:
        return hashlib.file_digest(file, 'sha256').hexdigest()


def catalog_status(key, layer):
    if layer == '90_quarantine':
        return '待核验，不进入正式训练'
    if layer == '04_evaluation':
        return '历史已观察的开发 / 评测材料'
    if layer == '05_provenance':
        return '来源与完整性凭据'
    if key == 'dff':
        return '待去重、人物分组与正式划分'
    if key == 'gan140k':
        return '仅 validation 子集，已用于开发'
    if layer == '03_manifests':
        return '保留历史清单与划分'
    return '既有研究材料，适用范围见说明'


def check_plan(groups, data_root):
    if os.name != 'nt':
        raise ValueError('This local migration uses Windows directory junctions')
    data_root = data_root.resolve()
    if data_root == Path(data_root.anchor) or len(data_root.parts) < 3:
        raise ValueError('Choose a dedicated data directory, never a volume root')
    allowed = [ROOT / 'data', ROOT / 'reference_run/data', ROOT / 'outputs', Path('D:/datasets'), Path('D:/qq_files')]
    destinations = []
    sources = []
    for group in groups:
        source, destination = Path(group['source']), Path(group['destination'])
        resolved_source, resolved_destination = source.resolve(), destination.resolve()
        if not any(resolved_source.is_relative_to(parent.resolve()) for parent in allowed):
            raise ValueError(f'Source outside the specifically intended directories: {source}')
        if not resolved_destination.is_relative_to(data_root) or resolved_destination == data_root:
            raise ValueError(f'Destination escapes intended data root: {destination}')
        if source.drive.lower() != data_root.drive.lower():
            raise ValueError('Require same-volume atomic rename; no implicit copy/delete fallback')
        if not source.exists():
            raise FileNotFoundError(source)
        if destination.exists():
            raise FileExistsError(f'Destination already exists; preserved: {destination}')
        if resolved_destination.is_relative_to(resolved_source) or resolved_source.is_relative_to(resolved_destination):
            raise ValueError('Source/destination are nested')
        sources.append(resolved_source); destinations.append(resolved_destination)
    for collection in (sources, destinations):
        for index, first in enumerate(collection):
            if any(first.is_relative_to(other) or other.is_relative_to(first) for other in collection[index+1:]):
                raise ValueError('Overlapping operations in migration plan')


def create_legacy_link(source, destination, directory):
    if directory:
        def quote(value):
            return "'" + str(value).replace("'", "''") + "'"
        # This shell only creates the junction; all validated moves are native atomic renames above.
        command = "$ErrorActionPreference='Stop'; New-Item -ItemType Junction -Path " + quote(source) + ' -Target ' + quote(destination) + ' | Out-Null'
        subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', command],
                       check=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
    else:
        os.link(destination, source)
    if not os.path.samefile(source, destination):
        raise ValueError(f'Legacy link does not refer to the same data: {source}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=DATA_ROOT)
    parser.add_argument('--apply', action='store_true', help='Execute the reviewed built-in layout and verify content')
    args = parser.parse_args()
    data_root = args.root.resolve()
    groups = plan(data_root)
    check_plan(groups, data_root)
    receipt = data_root / '05_provenance/consolidation-20261031'
    save_json(ROOT / 'outputs/data-consolidation-20261031/plan.json', dict(root=str(data_root), operations=groups))
    if not args.apply:
        print(json.dumps(dict(root=str(data_root), operations=groups), ensure_ascii=True, indent=2))
        return
    receipt.mkdir(parents=True, exist_ok=True)
    save_json(receipt / 'plan.json', dict(root=str(data_root), operations=groups))
    start = time.monotonic()
    entries = []
    for index, group in enumerate(groups):
        source = Path(group['source'])
        group['directory'] = source.is_dir()
        for path, relative in files_in(source):
            stat = path.stat()
            entries.append(dict(group=index, source=str(path), relative=relative.as_posix(),
                                size=stat.st_size, mtime_ns=stat.st_mtime_ns, file_id=stat.st_ino, device=stat.st_dev))
    print(f'Hashing {len(entries)} files / {sum(x["size"] for x in entries):,} bytes before migration', flush=True)
    def hash_before(entry):
        entry['sha256'] = sha256(Path(entry['source']))
        return entry
    with ThreadPoolExecutor(max_workers=4) as pool, (receipt / 'files-before.jsonl').open('w', encoding='utf-8') as output:
        for count, entry in enumerate(pool.map(hash_before, entries), 1):
            output.write(json.dumps(entry, ensure_ascii=False) + '\n')
            if count % 10000 == 0:
                output.flush(); print(f'Before hashes {count}/{len(entries)}; {time.monotonic()-start:.1f}s', flush=True)
    # Snapshot fully persisted before any move. A recovery journal records each primitive.
    journal = (receipt / 'operations.jsonl').open('a', encoding='utf-8')
    def record(event):
        journal.write(json.dumps(event, ensure_ascii=False) + '\n'); journal.flush()
    for index, group in enumerate(groups):
        source, destination = Path(group['source']), Path(group['destination'])
        destination.parent.mkdir(parents=True, exist_ok=True)
        # Recheck final absolute target and the source file identities immediately before moving.
        if not destination.resolve().is_relative_to(data_root) or destination.exists():
            raise ValueError(f'Unsafe or conflicting final target: {destination}')
        for entry in (row for row in entries if row['group'] == index):
            stat = Path(entry['source']).stat()
            if (stat.st_size, stat.st_mtime_ns, stat.st_ino, stat.st_dev) != (entry['size'], entry['mtime_ns'], entry['file_id'], entry['device']):
                raise ValueError('Source changed since snapshot: ' + entry['source'])
        record(dict(action='rename_planned', source=str(source), destination=str(destination)))
        os.rename(source, destination)
        record(dict(action='renamed', source=str(source), destination=str(destination)))
        create_legacy_link(source, destination, group['directory'])
        record(dict(action='legacy_link_created', source=str(source), destination=str(destination),
                    kind='junction' if group['directory'] else 'hardlink'))
        print(f'Moved {index+1}/{len(groups)}: {group["key"]}', flush=True)
    journal.close()
    print('Verifying every canonical file hash, file identity, and every legacy entry', flush=True)
    def verify(entry):
        group = groups[entry['group']]
        destination = Path(group['destination'])
        path = destination / entry['relative'] if group['directory'] else destination
        stat = path.stat()
        if (stat.st_size, stat.st_mtime_ns, stat.st_ino, stat.st_dev) != (entry['size'], entry['mtime_ns'], entry['file_id'], entry['device']):
            raise ValueError('File identity/metadata changed: ' + str(path))
        if sha256(path) != entry['sha256']:
            raise ValueError('SHA256 mismatch: ' + str(path))
        if not os.path.samefile(path, entry['source']):
            raise ValueError('Legacy file path is not the same file: ' + entry['source'])
        return True
    with ThreadPoolExecutor(max_workers=4) as pool:
        for count, _ in enumerate(pool.map(verify, entries), 1):
            if count % 10000 == 0:
                print(f'After verification {count}/{len(entries)}; {time.monotonic()-start:.1f}s', flush=True)
    catalog = []
    for index, group in enumerate(groups):
        members = [entry for entry in entries if entry['group'] == index]
        extensions = Counter(Path(entry['source']).suffix.lower() for entry in members)
        catalog.append(dict(dataset_id=group['key'], name=group['name'],
                            layer=Path(group['destination']).relative_to(data_root).parts[0],
                            status=catalog_status(group['key'], Path(group['destination']).relative_to(data_root).parts[0]),
                            directory=group['destination'], legacy_entry=group['source'],
                            files=len(members), bytes=sum(entry['size'] for entry in members),
                            image_files=sum(extensions[x] for x in ('.jpg', '.jpeg', '.png', '.webp', '.bmp')),
                            video_files=sum(extensions[x] for x in ('.mp4', '.avi', '.mov', '.mkv')),
                            parquet_files=extensions['.parquet'], notes=group['notes']))
    save_json(data_root / 'DATA_CATALOG.json', dict(root=str(data_root), entries=catalog,
              count_scope='Physical organized files, including archives and derived/configuration versions; not unique training samples'))
    with (data_root / 'DATA_CATALOG.csv').open('w', encoding='utf-8-sig', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=list(catalog[0])); writer.writeheader(); writer.writerows(catalog)
    readme = '''# FaceGuard 统一数据入口

所有已整理数据的实体文件集中在这里。先看 DATA_CATALOG.csv / DATA_CATALOG.json 查来源、用途、数量、实际位置与旧入口。

```text
01_raw/          原始视频、图片、压缩包、Parquet；按生成 / 篡改 / 真实 / 混合来源分组
02_processed/    裁脸、派生练习、演示素材；按用途和实验版本分组
03_manifests/    旧训练清单、官方划分、保守去重清单；原内容与哈希保留
04_evaluation/   历史评测包与新数据开发检查；已观察的不能再当新盲测
05_provenance/   来源说明、导入凭据、此次迁移全文件校验与旧入口映射
90_quarantine/   来源与标签未核验的第三方包及预览；不进入正式训练
```

原始数据集内部目录保留发布时的结构，便于对应 ZIP / 分片与逐图来源。原图、归档、导出和不同裁脸配置不等于互不重复的样本数。

旧 data、reference_run/data、实验目录与 D:\\datasets 下的旧入口使用目录联接或文件硬链接；它们指向相同实体，不占第二份数据空间。不要用递归删除清理旧兼容入口。新代码优先使用项目 faceguard.data_locations；完整维护说明见仓库 docs/data-setup.md。
'''
    (data_root / 'README.md').write_text(readme, encoding='utf-8')
    summary = dict(state='complete', date_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),
                   root=str(data_root), groups=len(groups), files=len(entries), bytes=sum(x['size'] for x in entries),
                   sha256_before_after_equal=True, same_volume_file_identities_preserved=True,
                   legacy_paths_verified=True, duplicates_deleted=False, sample_labels_or_splits_changed=False,
                   seconds=time.monotonic()-start)
    save_json(receipt / 'verification.json', summary)
    save_json(ROOT / 'outputs/data-consolidation-20261031/completion.json', summary)
    print(json.dumps(summary, ensure_ascii=True, indent=2), flush=True)


if __name__ == '__main__':
    main()
