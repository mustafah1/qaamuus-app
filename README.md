# Qaamuus – Somali Dictionary Web App

Modern, Somali‑first dictionary web app. The UI is fully localized in Somali and inspired by authentic linguistic content from the provided dictionary PDF. Includes fast search, infinite scroll, dark mode, and accessible modals.

## Features

- 📚 **PDF Corpus**: Text extracted from the source PDF for research/AI use (`data/qaam_corpus.json`, `data/qaam_corpus.txt`).
- 🔎 **Search & Browse**: Query words, browse by letter, client + server pagination with infinite scroll.
- 🗂️ **Card UI**: Modern, responsive, and consistent card layout across landing and dictionary pages.
- 🌗 **Dark Mode**: Theme toggle with persisted preference.
- 🌐 **Somali Localization**: All UI text in Somali with culturally accurate phrasing.
- ♿ **Accessibility**: Keyboard‑navigable modals, focus management, aria labels.

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

- On startup, the backend loads a cached dictionary (`dictionary_cache.json`) or extracts entries from `qaam.pdf` using a pattern‑based parser.
- Frontend renders results with client‑side pagination; server endpoints support offset/limit for efficient loading.
- The full PDF text (72 pages) has been extracted for future AI/RAG workflows:
  - JSON (page‑by‑page): `data/qaam_corpus.json`
  - TXT (concatenated): `data/qaam_corpus.txt`

## Scripts

- `scripts/extract_pdf_text.py` – Extracts page text from `qaam-cama_removed.pdf` into the `data/` folder.

Run it manually if needed:
```bash
python scripts/extract_pdf_text.py
```

## Key Routes

- `/` – Landing page (Somali content + educational sections)
- `/dictionary` – Dictionary UI (search, browse, infinite scroll)
- `/search` – Search endpoint (query params include `q`, optional pagination)

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

- If you update the source PDF (`qaam.pdf`), delete `dictionary_cache.json` to force re‑extraction on next run.
- For deploying, ensure static assets are cache‑busted if needed (e.g., `?v=3`).

## License

MIT (or your preferred license). Update this section as needed.
