import sqlite3
import json
import os

DB_FILE = 'dictionary.db'
JSON_FILE = 'dictionary_cache.json'

def create_schema(conn):
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS dictionary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT NOT NULL,
            definition TEXT NOT NULL
        );
    ''')
    c.execute('CREATE INDEX IF NOT EXISTS idx_word ON dictionary(word);')
    # Create FTS5 table for full-text search (industry standard)
    c.execute('''
        CREATE VIRTUAL TABLE IF NOT EXISTS dictionary_fts USING fts5(
            word, definition, content='dictionary', content_rowid='id'
        );
    ''')
    conn.commit()

def migrate_json_to_db(json_file, db_file):
    if not os.path.exists(json_file):
        print(f"JSON file not found: {json_file}")
        return
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    conn = sqlite3.connect(db_file)
    create_schema(conn)
    c = conn.cursor()
    c.execute('DELETE FROM dictionary;')
    c.execute('DELETE FROM dictionary_fts;')
    for word, definition in data.items():
        c.execute('INSERT INTO dictionary (word, definition) VALUES (?, ?)', (word, definition))
    # Populate FTS5 table from dictionary
    c.execute('INSERT INTO dictionary_fts(rowid, word, definition) SELECT id, word, definition FROM dictionary;')
    conn.commit()
    conn.close()
    print(f"Migrated {len(data)} entries to {db_file} and FTS5 full-text index")

if __name__ == '__main__':
    migrate_json_to_db(JSON_FILE, DB_FILE)
