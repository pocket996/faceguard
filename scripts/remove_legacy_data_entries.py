"""Remove only verified legacy links; preserve all canonical files and frozen manifests."""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from faceguard.data_locations import DATA_ROOT


def main():
    store = DATA_ROOT.resolve()
    catalog_path = store / 'DATA_CATALOG.json'
    catalog = json.loads(catalog_path.read_text(encoding='utf-8'))
    report_dir = ROOT / 'outputs/data-cleanup-20261031'
    report_dir.mkdir(exist_ok=True)
    targets = []
    allowed = (ROOT / 'data', ROOT / 'reference_run/data', ROOT / 'outputs', Path('D:/datasets'), Path('D:/qq_files'))
    # Validate the complete removal list before unlinking anything.
    for entry in catalog['entries']:
        old, canonical = Path(entry['legacy_entry']), Path(entry['directory'])
        if not canonical.resolve().is_relative_to(store) or not canonical.exists():
            raise ValueError('Canonical target is missing or outside the data store')
        if old.is_relative_to(store) or not any(old.is_relative_to(parent) for parent in allowed):
            raise ValueError('Legacy entry is outside the specifically intended old locations')
        if not os.path.lexists(old):
            targets.append((entry, old, canonical, 'already_absent'))
            continue
        if not os.path.samefile(old, canonical):
            raise ValueError('Old entry is not the same data; preserved: ' + str(old))
        if canonical.is_dir():
            if not old.lstat().st_file_attributes & 0x400:
                raise ValueError('Refuse to remove a real data directory: ' + str(old))
            kind = 'junction'
        else:
            if old.stat().st_nlink < 2:
                raise ValueError('Refuse to remove an unverified file copy: ' + str(old))
            kind = 'hardlink'
        targets.append((entry, old, canonical, kind))
    events = []
    for entry, old, canonical, kind in targets:
        # These are nonrecursive operations on the literal OLD entry, never on resolve().
        if kind == 'junction':
            os.rmdir(old)
        elif kind == 'hardlink':
            os.unlink(old)
        if os.path.lexists(old) or not canonical.exists():
            raise ValueError('Legacy unlink verification failed')
        entry['legacy_status'] = 'removed'
        events.append(dict(old=str(old), canonical=str(canonical), action=kind))
        (report_dir / 'removed-entries.json').write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding='utf-8')

    removed_empty = []
    def remove_empty(path, approved_root):
        if not path.exists():
            return
        if not path.resolve().is_relative_to(approved_root) or path.lstat().st_file_attributes & 0x400:
            raise ValueError('Refuse to traverse a link or unexpected old container: ' + str(path))
        for item in path.iterdir():
            if item.is_dir() and not item.lstat().st_file_attributes & 0x400:
                remove_empty(item, approved_root)
        if not any(path.iterdir()):
            path.rmdir()
            removed_empty.append(str(path))
    for old_root in (ROOT / 'data', ROOT / 'reference_run/data',
                     Path('D:/qq_files/ai_generated.zip'), Path('D:/qq_files/real.zip')):
        remove_empty(old_root, old_root)

    # Same-volume identities and metadata prove unlinking did not touch the physical data.
    provenance = store / '05_provenance/consolidation-20261031'
    plan = json.loads((provenance / 'plan.json').read_text(encoding='utf-8'))['operations']
    count = 0
    with (provenance / 'files-before.jsonl').open(encoding='utf-8') as file:
        for line in file:
            record = json.loads(line)
            target = Path(plan[record['group']]['destination'])
            path = target if record['relative'] == '.' else target / record['relative']
            stat = path.stat()
            if (stat.st_size, stat.st_mtime_ns, stat.st_ino, stat.st_dev) != (record['size'], record['mtime_ns'], record['file_id'], record['device']):
                raise ValueError('Canonical file changed: ' + str(path))
            count += 1
    catalog['legacy_policy'] = 'Filesystem aliases removed; original path text is translated by faceguard.data_locations.resolve_data_path'
    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding='utf-8')
    import csv
    with (store / 'DATA_CATALOG.csv').open('w', encoding='utf-8-sig', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=list(catalog['entries'][0])); writer.writeheader(); writer.writerows(catalog['entries'])
    summary = dict(state='complete', date_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),
                   legacy_entries_removed=len(events), empty_containers_removed=removed_empty,
                   canonical_files_unchanged=count, recursive_delete_used=False,
                   project_data_directory_removed=not (ROOT/'data').exists(),
                   reference_data_directory_removed=not (ROOT/'reference_run/data').exists())
    (report_dir / 'unlink-verification.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=True, indent=2))


if __name__ == '__main__':
    main()
