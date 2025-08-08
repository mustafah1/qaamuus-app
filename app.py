from flask import Flask, render_template, request, jsonify
import PyPDF2
import re
import json
import os

app = Flask(__name__)

class SomaliDictionary:
    def __init__(self):
        self.words = {}
        self.load_dictionary()
    
    def extract_from_pdf(self, pdf_path):
        """Extract words and definitions from the PDF file using word-pattern + abbreviation detection."""
        words_dict = {}
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text = ""
                for page in pdf_reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                lines = text.split('\n')
                # Regex: Somali word (letters, primes, numbers, etc.), abbreviation, then definition
                entry_pattern = re.compile(r"^([a-zA-Z’ʼʻ0-9()¹²³'′]+)\s+([mf]\.[a-z]+\d{0,2})\s+(.*)")
                current_word = None
                current_definition = ""
                for line in lines:
                    stripped = line.strip()
                    if not stripped:
                        continue
                    match = entry_pattern.match(stripped)
                    if match:
                        # Save previous word/definition
                        if current_word and current_definition:
                            words_dict[current_word.lower()] = current_definition.strip()
                        word = match.group(1)
                        # Clean up word (remove trailing punctuation, numbers, parens)
                        word = re.sub(r'^[\(\d]+|[\)\d]+$', '', word)
                        current_word = word
                        # Start new definition with everything after abbreviation
                        current_definition = match.group(2) + ' ' + match.group(3)
                    else:
                        # Continuation of previous definition
                        if current_word:
                            current_definition += ' ' + stripped
                if current_word and current_definition:
                    words_dict[current_word.lower()] = current_definition.strip()
                print(f"Extracted {len(words_dict)} words from PDF (pattern-based)")
                return words_dict
        except Exception as e:
            print(f"Error extracting from PDF: {e}")
            return {}
    
    def load_dictionary(self):
        """Load dictionary from cache or extract from PDF"""
        cache_file = 'dictionary_cache.json'
        
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    self.words = json.load(f)
                print(f"Loaded {len(self.words)} words from cache")
                return
            except Exception as e:
                print(f"Error loading cache: {e}")
        
        # Extract from PDF if cache doesn't exist
        pdf_path = 'qaam.pdf'
        if os.path.exists(pdf_path):
            self.words = self.extract_from_pdf(pdf_path)
            
            # Save to cache
            try:
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(self.words, f, ensure_ascii=False, indent=2)
                print("Dictionary cached successfully")
            except Exception as e:
                print(f"Error saving cache: {e}")
        else:
            print("PDF file not found!")
    
    def search(self, query):
        """Search for words matching the query"""
        if not query:
            return list(self.words.items())[:50]  # Return first 50 words if no query
        
        query = query.lower().strip()
        results = []
        
        # Exact match first
        if query in self.words:
            results.append((query, self.words[query]))
        
        # Partial matches
        for word, definition in self.words.items():
            if query in word and (word, definition) not in results:
                results.append((word, definition))
            elif len(results) >= 100:  # Limit results
                break
        
        return results

# Initialize dictionary
dictionary = SomaliDictionary()

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
