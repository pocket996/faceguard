"""Local history metadata. Imported media are never marked as detected."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import json
from uuid import uuid4


class HistoryStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as database:
            database.execute('''CREATE TABLE IF NOT EXISTS records (
                id TEXT PRIMARY KEY, file_path TEXT NOT NULL, file_name TEXT NOT NULL,
                kind TEXT NOT NULL, metadata TEXT NOT NULL, created_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending'
            )''')
            columns = {row['name'] for row in database.execute('PRAGMA table_info(records)')}
            if 'result_json' not in columns:
                database.execute('ALTER TABLE records ADD COLUMN result_json TEXT')

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def add(self, path, kind, metadata):
        path = Path(path).resolve()
        identifier = uuid4().hex
        created = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='microseconds')
        with self.connect() as database:
            database.execute('INSERT INTO records (id, file_path, file_name, kind, metadata, created_at, status) VALUES (?, ?, ?, ?, ?, ?, ?)',
                             (identifier, str(path), path.name, kind, metadata, created, 'pending'))
        return identifier

    def list(self):
        with self.connect() as database:
            records = [dict(row) for row in database.execute('SELECT id,file_path,file_name,kind,metadata,created_at,status FROM records ORDER BY created_at DESC, id DESC')]
        for record in records:
            record['display_time'] = datetime.fromisoformat(record['created_at']).strftime('%Y-%m-%d %H:%M:%S')
        return records

    def get(self, identifier):
        with self.connect() as database:
            row = database.execute('SELECT * FROM records WHERE id = ?', (identifier,)).fetchone()
        return dict(row) if row else None

    def set_result(self, identifier, result=None, status='completed'):
        payload = json.dumps(result, ensure_ascii=False, allow_nan=False) if result is not None else None
        with self.connect() as database:
            database.execute('UPDATE records SET result_json=?, status=? WHERE id=?', (payload, status, identifier))

    def delete(self, identifier):
        with self.connect() as database:
            database.execute('DELETE FROM records WHERE id = ?', (identifier,))

    def clear(self):
        with self.connect() as database:
            database.execute('DELETE FROM records')
