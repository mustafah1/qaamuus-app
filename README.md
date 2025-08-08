# Qaamuus – Somali Dictionary Web App

Modern, Somali‑first dictionary web app. The UI is fully localized in Somali and inspired by authentic linguistic content from the source dictionary PDF. Includes fast search, infinite scroll, dark mode, and an elegant entry modal with cross‑references and similar words.

## Features

- 📚 **PDF Corpus**: Text extracted from the source PDF for research/AI use (`data/qaam_corpus.json`, `data/qaam_corpus.txt`).
- 🔎 **Search & Browse**: Query words, browse by letter, client + server pagination with infinite scroll.
- 🗂️ **Card UI**: Modern, responsive, and consistent card layout across landing and dictionary pages.
- 🌗 **Dark Mode**: Theme toggle with persisted preference.
- 🌐 **Somali Localization**: All UI text in Somali with culturally accurate phrasing.
- ♿ **Accessibility**: Keyboard‑navigable modals, focus management, aria labels.
- 🧭 **Entry Modal**: Beautiful, sectioned modal showing POS, source (page/column), definition, outgoing refs (eeg/ld), incoming refs, and “Erayo la mid ah”. Empty sections auto‑hide for a clean look.

## Quick Start

1) Install dependencies
```bash
pip install -r requirements.txt
```

2) Run the app
```bash
python app.py
```

3) Open in browser
```
http://localhost:5000
```

## How It Works

- On startup, the backend loads entries from an **SQLite DB** (`dictionary.db`) populated from the PDF. A lightweight cache file (`dictionary_cache.json`) may also be used during development.
- Frontend renders results with client‑side pagination; server endpoints support offset/limit for efficient loading.
- The full PDF text (72 pages) has been extracted for future AI/RAG workflows:
  - JSON (page‑by‑page): `data/qaam_corpus.json`
  - TXT (concatenated): `data/qaam_corpus.txt`

## Scripts

- `scripts/extract_entries_pymupdf.py` – Structured extractor using PyMuPDF; produces normalized entries, POS, refs, and debug overlays.
- `scripts/migrate_extracted_to_db.py` – Loads extracted entries into `dictionary.db` (SQLite schema) with cross‑refs.
- `scripts/extract_pdf_text.py` – Basic text extraction from `qaam-cama_removed.pdf` into `data/`.

Run any script, for example:
```bash
python scripts/migrate_extracted_to_db.py
```

## Key Routes

- `/` – Landing page (Somali content + educational sections)
- `/dictionary` – Dictionary UI (search, browse, infinite scroll)
- `/search` – Search endpoint (query params include `q`, optional pagination)
- `/all_words` – Paginated list of all entries (offset/limit)
- `/words_by_letter/<letter>` – Paginated list for an initial letter
- `/entry` – Fetch a single entry with refs and similar words: `GET /entry?word=<headword>`

## Project Structure (selected)

```
Qaamuus App/
├── app.py
├── requirements.txt
├── static/
│   └── main.css
├── templates/
│   ├── base.html
│   ├── landing.html
│   ├── index.html
│   └── partials/
│       ├── header.html
│       ├── footer.html
│       ├── dictionary_search.html
│       └── entry_modal.html
├── data/
│   ├── qaam_corpus.json
│   └── qaam_corpus.txt
└── scripts/
    └── extract_pdf_text.py
```

## Notes

- If you update the source PDF (`qaam.pdf`), rebuild `dictionary.db` by re‑running the extractor + migrator. Delete `dictionary_cache.json` if present.
- For deploying, ensure static assets are cache‑busted if needed (e.g., `?v=3`).

## Dictionary Entry Format

Entries start with a headword possibly with homograph markers (¹ ² ³) and apostrophes: e.g., a, aa', aa¹, aa², aa³.
Immediately after headword: POS tokens with dotted morphology codes: m.dh, f.g1, f.mg1, u.j, m.l/dh, etc.
Senses are numbered (1., 2.) or unnumbered continuation text.
A lot of cross-references (eeg WORD) and “ld” markers (likely “la mid”/“see also”/“same as” style).
Continuation lines are indented; new entries align to a left baseline. Hyphenation, parentheses with inflection forms appear after POS.

## License

MIT (or your preferred license). Update this section as needed.
