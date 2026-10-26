"""Create a new manifest by conservatively quarantining cross-split similarity groups."""
import argparse
from collections import Counter, defaultdict
import csv
from pathlib import Path

from project_io import digest,save_json


def quarantine(rows, pairs):
    by_id = {r['sample_id']: r for r in rows}
    parent = {r['group']: r['group'] for r in rows}
    def find(group):
        while parent[group] != group:
            parent[group] = parent[parent[group]]
            group = parent[group]
        return group
    for pair in pairs:
        a, b = by_id[pair['left_id']]['group'], by_id[pair['right_id']]['group']
        parent[find(a)] = find(b)
    components = defaultdict(list)
    for row in rows:
        components[find(row['group'])].append(row)
    priority = {'train': 0, 'val': 1, 'test': 2}
    kept, removed = [], []
    for component in components.values():
        highest = max(priority[r['split']] for r in component)
        for row in component:
            (kept if priority[row['split']] == highest else removed).append(row)
    return kept, removed


def write(path, rows, fields):
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--candidates', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    with args.manifest.open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    with args.candidates.open(encoding='utf-8-sig', newline='') as stream:
        pairs = list(csv.DictReader(stream))
    kept, removed = quarantine(rows, pairs)
    args.output.mkdir(parents=True, exist_ok=True)
    write(args.output / 'manifest.csv', kept, list(rows[0]))
    write(args.output / 'quarantined.csv', removed, list(rows[0]))
    save_json(args.output / 'protocol.json', dict(original_manifest_sha256=digest(args.manifest),
        candidate_sha256=digest(args.candidates), original_images=len(rows), kept=len(kept), removed=len(removed),
        removed_by_split=dict(Counter(r['split'] for r in removed)),
        removed_by_source=dict(Counter(r['source'] for r in removed)),
        policy='Union original groups connected by all pHash candidates <=6; keep highest-priority split test > val > train, quarantine whole lower-priority groups',
        note='Conservative similarity quarantine, not verified identity grouping. Existing model trained before this audit is NOT retroactively repaired. Original files and splits untouched.'))
    print(f'Kept {len(kept)}, quarantined {len(removed)}. New manifest only; no source files changed.')


if __name__ == '__main__':
    main()
