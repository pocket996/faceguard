"""Copy named datasets locally and verify every file; never delete the source."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import shutil
import time


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    source, destination = args.source.resolve(), args.destination.resolve()
    if destination == source or destination.is_relative_to(source) or source.is_relative_to(destination):
        raise ValueError('Source and destination must be separate directories')
    paths = []
    for name in ('dff', 'gan140k', 'SOURCE.md'):
        entry = source / name
        if not entry.exists():
            raise FileNotFoundError(entry)
        paths.extend([entry] if entry.is_file() else sorted(p for p in entry.rglob('*') if p.is_file()))
    if any(p.is_symlink() for p in paths):
        raise ValueError('Dataset files must not be links')
    total_bytes = sum(p.stat().st_size for p in paths)
    destination.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(destination).free < total_bytes + 5 * 1024**3:
        raise RuntimeError('Insufficient space: reserve 5 GiB in addition to dataset size')
    args.receipt.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    print(f'Copying and verifying {len(paths)} files / {total_bytes:,} bytes', flush=True)

    def copy_file(path):
        relative = path.relative_to(source)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        before = path.stat()
        if target.exists():
            source_hash = sha256(path)
            if target.stat().st_size != before.st_size or sha256(target) != source_hash:
                raise RuntimeError(f'Existing destination differs; preserved: {target}')
            action = 'already_verified'
        else:
            temp = target.with_name(target.name + '.copying')
            digest = hashlib.sha256()
            with path.open('rb') as reader, temp.open('wb') as writer:
                for block in iter(lambda: reader.read(1024 * 1024), b''):
                    writer.write(block)
                    digest.update(block)
            source_hash = digest.hexdigest()
            if temp.stat().st_size != before.st_size or sha256(temp) != source_hash:
                raise RuntimeError(f'Copy verification failed: {target}')
            shutil.copystat(path, temp)
            # No other copy job writes this relative path.
            if target.exists():
                raise RuntimeError(f'Destination appeared during copy: {target}')
            temp.rename(target)
            action = 'copied_verified'
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise RuntimeError(f'Source changed during copy: {path}')
        return dict(path=relative.as_posix(), size=before.st_size, sha256=source_hash, action=action)

    count = 0
    try:
        with (args.receipt / 'files.jsonl').open('w', encoding='utf-8') as receipt:
            with ThreadPoolExecutor(max_workers=4) as executor:
                for record in executor.map(copy_file, paths):
                    receipt.write(json.dumps(record, ensure_ascii=False) + '\n')
                    count += 1
                    if count % 2000 == 0:
                        receipt.flush()
                        print(f'Verified {count}/{len(paths)} files; {time.monotonic()-start:.1f}s', flush=True)
        state = 'complete'
    except Exception:
        state = 'incomplete'
        raise
    finally:
        summary = dict(state=state, date_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),
                       source=str(source), destination=str(destination), expected_files=len(paths),
                       verified_files=count, total_bytes=total_bytes, seconds=time.monotonic()-start,
                       source_deleted=False, verification='SHA256 source bytes compared with every local file')
        (args.receipt / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
