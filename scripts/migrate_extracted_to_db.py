import sqlite3
import json
import os
import sys
from typing import List, Dict, Any

DB_FILE = os.environ.get('QAAM_DB', 'dictionary.db')

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS entries (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  word TEXT NOT NULL,
  pos TEXT,
  definition TEXT NOT NULL,
  page INTEGER,
  column INTEGER
);
CREATE INDEX IF NOT EXISTS idx_entries_word ON entries(word);

CREATE TABLE IF NOT EXISTS refs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_id INTEGER NOT NULL,
  type TEXT NOT NULL,           -- 'see' | 'seealso'
  target_word TEXT NOT NULL,    -- normalized token
  target_id INTEGER,            -- resolved entry id if available
  FOREIGN KEY(source_id) REFERENCES entries(id) ON DELETE CASCADE,
  FOREIGN KEY(target_id) REFERENCES entries(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_refs_source ON refs(source_id);
CREATE INDEX IF NOT EXISTS idx_refs_target_word ON refs(target_word);
CREATE INDEX IF NOT EXISTS idx_refs_target_id ON refs(target_id);

-- FTS for fast search
CREATE VIRTUAL TABLE IF NOT EXISTS entries_fts USING fts5(
  word, definition, content='entries', content_rowid='id'
);
"""


def load_json(path: str) -> Dict[str, Any]:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def recreate(conn: sqlite3.Connection):
    c = conn.cursor()
    # Clear existing data
    c.execute('DELETE FROM refs;')
    c.execute('DELETE FROM entries;')
    c.execute('DELETE FROM entries_fts;')
    conn.commit()


def migrate(json_path: str, db_path: str = DB_FILE):
    data = load_json(json_path)
    entries: List[Dict[str, Any]] = data.get('entries', [])
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    # Ensure schema exists
    for stmt in SCHEMA_SQL.strip().split(';'):
        s = stmt.strip()
        if s:
            c.execute(s + ';')
    recreate(conn)

    # Insert entries
    word_to_ids: Dict[str, List[int]] = {}
    for e in entries:
        word = e.get('word') or ''
        pos = e.get('pos') or ''
        definition = e.get('definition') or ''
        page = int(e.get('page') or 0)
        col = int(e.get('column') or 0)
        c.execute('INSERT INTO entries(word,pos,definition,page,column) VALUES(?,?,?,?,?)',
                  (word, pos, definition, page, col))
        eid = c.lastrowid
        word_to_ids.setdefault(word, []).append(eid)
    # Populate FTS
    c.execute('INSERT INTO entries_fts(rowid, word, definition) SELECT id, word, definition FROM entries;')

    # Resolve a simple word->id mapping preferring first occurrence
    def resolve_word(w: str):
        lst = word_to_ids.get(w)
        return lst[0] if lst else None

    # Insert refs
    for e in entries:
        source_ids = word_to_ids.get(e.get('word') or '') or []
        if not source_ids:
            continue
        source_id = source_ids[0]
        # crossRefs
        for token, tgt in zip(e.get('crossRefs', []) or [], e.get('crossRefTargets', []) or []):
            target_id = resolve_word(tgt)
            c.execute('INSERT INTO refs(source_id,type,target_word,target_id) VALUES(?,?,?,?)',
                      (source_id, 'see', token, target_id))
        # seeAlso
        for token, tgt in zip(e.get('seeAlso', []) or [], e.get('seeAlsoTargets', []) or []):
            target_id = resolve_word(tgt)
            c.execute('INSERT INTO refs(source_id,type,target_word,target_id) VALUES(?,?,?,?)',
                      (source_id, 'seealso', token, target_id))

    conn.commit()
    conn.close()
    print(f"Migrated {len(entries)} entries and refs into {db_path}")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python scripts/migrate_extracted_to_db.py data/full_entries.json')
        sys.exit(1)
    migrate(sys.argv[1], DB_FILE)
