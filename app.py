from flask import Flask, render_template, request, jsonify
import os

app = Flask(__name__)

@app.route('/')
def landing():
    return render_template('landing.html')

@app.route('/dictionary')
def dictionary_page():
    return render_template('index.html')

@app.route('/search')
def search():
    query = request.args.get('q', '').strip()
    # Pagination params
    try:
        limit = max(1, min(int(request.args.get('limit', 40)), 200))
    except ValueError:
        limit = 40
    try:
        offset = max(0, int(request.args.get('offset', 0)))
    except ValueError:
        offset = 0
    if not query:
        return jsonify({'results': [], 'count': 0, 'total_count': 0, 'offset': offset, 'limit': limit, 'query': query})
    conn = get_db()
    c = conn.cursor()
    # Total count first
    c.execute('''
        SELECT COUNT(*) AS cnt FROM entries_fts
        WHERE entries_fts MATCH ?
    ''', (query + '*',))
    total = c.fetchone()['cnt']
    # Page of results (FTS5 rank ordering)
    c.execute('''
        SELECT word, definition FROM entries_fts
        WHERE entries_fts MATCH ?
        ORDER BY rank
        LIMIT ? OFFSET ?;
    ''', (query + '*', limit, offset))
    results = [(row['word'], row['definition']) for row in c.fetchall()]
    conn.close()
    return jsonify({'results': results, 'count': len(results), 'total_count': total, 'offset': offset, 'limit': limit, 'query': query})

import sqlite3

@app.route('/suggest')
def suggest():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({'suggestions': []})
    conn = get_db()
    c = conn.cursor()
    # Suggest words by prefix match (fast autocomplete)
    c.execute('''
        SELECT word FROM entries_fts
        WHERE word MATCH ?
        ORDER BY rank
        LIMIT 8;
    ''', (query + '*',))
    suggestions = [row['word'] for row in c.fetchall()]
    conn.close()
    return jsonify({'suggestions': suggestions})

def get_db():
    conn = sqlite3.connect('dictionary.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/index')
def index_letters():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT DISTINCT UPPER(SUBSTR(word, 1, 1)) AS letter FROM entries ORDER BY letter ASC;")
    letters = [row['letter'] for row in c.fetchall()]
    conn.close()
    return jsonify({'letters': letters})

@app.route('/words_by_letter')
def words_by_letter():
    letter = request.args.get('letter', '').strip().upper()
    try:
        limit = max(1, min(int(request.args.get('limit', 40)), 200))
    except ValueError:
        limit = 40
    try:
        offset = max(0, int(request.args.get('offset', 0)))
    except ValueError:
        offset = 0
    if not letter or len(letter) != 1:
        return jsonify({'results': [], 'count': 0, 'total_count': 0, 'offset': offset, 'limit': limit, 'letter': letter})
    conn = get_db()
    c = conn.cursor()
    # Total count by letter
    c.execute("SELECT COUNT(*) AS cnt FROM entries WHERE UPPER(SUBSTR(word, 1, 1)) = ?;", (letter,))
    total = c.fetchone()['cnt']
    c.execute("SELECT word, definition FROM entries WHERE UPPER(SUBSTR(word, 1, 1)) = ? ORDER BY word ASC LIMIT ? OFFSET ?;", (letter, limit, offset))
    results = [(row['word'], row['definition']) for row in c.fetchall()]
    conn.close()
    return jsonify({'results': results, 'count': len(results), 'total_count': total, 'offset': offset, 'limit': limit, 'letter': letter})

@app.route('/all_words')
def all_words():
    # Return words in alphabetical order with pagination from entries table
    try:
        limit = max(1, min(int(request.args.get('limit', 40)), 200))
    except ValueError:
        limit = 40
    try:
        offset = max(0, int(request.args.get('offset', 0)))
    except ValueError:
        offset = 0
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) AS cnt FROM entries;")
    total = c.fetchone()['cnt']
    c.execute("SELECT word, definition FROM entries ORDER BY word ASC LIMIT ? OFFSET ?;", (limit, offset))
    results = [(row['word'], row['definition']) for row in c.fetchall()]
    conn.close()
    return jsonify({
        'results': results,
        'count': len(results),
        'total_count': total,
        'offset': offset,
        'limit': limit
    })

# New endpoint: fetch a single entry (with refs)
@app.route('/entry')
def entry_by_word():
    word = request.args.get('word', '').strip()
    if not word:
        return jsonify({'ok': False, 'error': 'missing word'}), 400
    conn = get_db()
    c = conn.cursor()
    # Try exact match first
    c.execute("SELECT id, word, pos, definition, page, column FROM entries WHERE word = ? LIMIT 1;", (word,))
    row = c.fetchone()
    if not row:
        # Fallback: LIKE or FTS prefix
        c.execute("SELECT id, word, pos, definition, page, column FROM entries WHERE word LIKE ? ORDER BY word LIMIT 1;", (word + '%',))
        row = c.fetchone()
        if not row:
            # FTS fallback
            c.execute("SELECT rowid AS id, word, '' as pos, definition FROM entries_fts WHERE entries_fts MATCH ? ORDER BY rank LIMIT 1;", (word + '*',))
            row = c.fetchone()
            if not row:
                conn.close()
                return jsonify({'ok': False, 'error': 'not found'}), 404
    eid = row['id']
    result = {
        'id': eid,
        'word': row['word'],
        'pos': row['pos'] if 'pos' in row.keys() else '',
        'definition': row['definition'],
        'page': row['page'] if 'page' in row.keys() else None,
        'column': row['column'] if 'column' in row.keys() else None,
        'crossRefs': [],
        'seeAlso': [],
        'referredBy': [],
        'similar': []
    }
    # Load refs
    c.execute("SELECT type, target_word FROM refs WHERE source_id = ? ORDER BY id ASC;", (eid,))
    for r in c.fetchall():
        if r['type'] == 'see':
            result['crossRefs'].append(r['target_word'])
        else:
            result['seeAlso'].append(r['target_word'])
    # Incoming refs (reverse links)
    c.execute("""
        SELECT e.word AS source_word
        FROM refs r
        JOIN entries e ON e.id = r.source_id
        WHERE r.target_id = ? OR r.target_word = ?
        ORDER BY e.word ASC
    """, (eid, result['word']))
    result['referredBy'] = [r['source_word'] for r in c.fetchall()]
    # Similar words by prefix (3 letters), exclude self
    try:
        base = result['word'] or ''
        prefix = base[:3]
        if prefix:
            c.execute("""
                SELECT DISTINCT word FROM entries
                WHERE word LIKE ? AND word <> ?
                ORDER BY word ASC
                LIMIT 12;
            """, (prefix + '%', base))
            result['similar'] = [r['word'] for r in c.fetchall()]
    except Exception:
        pass
    conn.close()
    return jsonify({'ok': True, 'entry': result})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', '5002'))
    app.run(debug=True, host='0.0.0.0', port=port)
