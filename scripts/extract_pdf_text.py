import json
import os
from pathlib import Path
from PyPDF2 import PdfReader

BASE_DIR = Path(__file__).resolve().parents[1]
PDF_PATH = BASE_DIR / "qaam-cama_removed.pdf"
OUT_DIR = BASE_DIR / "data"
TXT_OUT = OUT_DIR / "qaam_corpus.txt"
JSON_OUT = OUT_DIR / "qaam_corpus.json"


def extract_text(pdf_path: Path):
    reader = PdfReader(str(pdf_path))
    pages = []
    for i, page in enumerate(reader.pages):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        # Normalize whitespace a bit
        text = "\n".join([ln.rstrip() for ln in text.splitlines()])
        pages.append({"page": i + 1, "text": text})
    return pages


def main():
    if not PDF_PATH.exists():
        raise FileNotFoundError(f"PDF not found: {PDF_PATH}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    pages = extract_text(PDF_PATH)

    # Write JSON (page-by-page)
    with JSON_OUT.open("w", encoding="utf-8") as f:
        json.dump({"source": str(PDF_PATH.name), "num_pages": len(pages), "pages": pages}, f, ensure_ascii=False, indent=2)

    # Write TXT (full concatenated)
    with TXT_OUT.open("w", encoding="utf-8") as f:
        for p in pages:
            f.write(f"\n\n===== BOGGA {p['page']} =====\n\n")
            f.write(p["text"])  # already utf-8 safe

    print(f"Extracted {len(pages)} pages from {PDF_PATH.name}")
    print(f"JSON: {JSON_OUT}")
    print(f"TXT:  {TXT_OUT}")


if __name__ == "__main__":
    main()
