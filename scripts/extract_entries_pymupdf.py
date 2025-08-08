from __future__ import annotations

def detect_divider_x(page: fitz.Page, lines_data: List[Dict[str, Any]]) -> float:
    """Try to detect the vertical column divider x-coordinate.
    1) Prefer a long vertical drawing near the middle
    2) Fallback to histogram gap between two x0 clusters
    Returns divider x in page coordinates, or None if unknown.
    """
    try:
        dw = page.get_drawings()
        page_w = float(page.rect.width)
        page_h = float(page.rect.height)
        best = None
        for d in dw:
            for p in d.get('items', []):
                # items are pen paths; look for straight vertical segments
                if not isinstance(p, dict):
                    continue
                if p.get('type') != 'line':
                    continue
                x0, y0, x1, y1 = p.get('rect', p.get('bbox', (0, 0, 0, 0)))
                # Some builds store line coords as 'points'
                if 'points' in p:
                    pts = p['points']
                    if len(pts) >= 2:
                        x0, y0 = pts[0]
                        x1, y1 = pts[-1]
                if abs(x0 - x1) < 1.0:
                    length = abs(y1 - y0)
                    # Long vertical line near middle third of the page width
                    if length > page_h * 0.6 and page_w * 0.3 < x0 < page_w * 0.7:
                        best = x0
                        break
            if best is not None:
                break
        if best is not None:
            return float(best)
    except Exception:
        pass
    # Fallback: histogram of line lefts
    xs = [ld['bbox'][0] for ld in lines_data]
    if not xs:
        return None
    xs = sorted(xs)
    # Use simple two-cluster midpoint using 1D k-means-like split by median
    mid = xs[len(xs)//2]
    left_mean = sum(v for v in xs if v <= mid) / max(1, len([v for v in xs if v <= mid]))
    right_mean = sum(v for v in xs if v > mid) / max(1, len([v for v in xs if v > mid]))
    divider = (left_mean + right_mean) / 2.0
    return divider
import os
import re
import argparse
import json
from dataclasses import dataclass, asdict, field
from typing import List, Tuple, Dict, Any

import fitz  # PyMuPDF

# ---- Normalization helpers ----
APOSTROPHE_MAP = {
    "\u2019": "'",  # ’
    "\u2032": "'",  # ′
    "\u02bc": "'",  # ʼ
    "\u02bb": "'",  # ʻ
}

def normalize_text(s: str) -> str:
    if not s:
        return s
    for k, v in APOSTROPHE_MAP.items():
        s = s.replace(k, v)
    # Collapse multiple spaces
    s = re.sub(r"\s+", " ", s).strip()
    return s

# ---- Data model ----
@dataclass
class Sense:
    text: str

@dataclass
class Entry:
    word: str
    pos: str = ""
    senses: List[Sense] = field(default_factory=list)
    seeAlso: List[str] = field(default_factory=list)
    crossRefs: List[str] = field(default_factory=list)
    crossRefTargets: List[str] = field(default_factory=list)  # resolved word_ids
    seeAlsoTargets: List[str] = field(default_factory=list)   # resolved word_ids
    page: int = -1
    column: int = 0
    bbox: Tuple[float, float, float, float] = (0, 0, 0, 0)

# ---- Heuristics ----
POS_TOKENS = {
    'm.', 'f.', 'g.', 'l.',
    'm.dh', 'f.dh', 'm.l', 'f.l', 'g.1', 'g.2', 'g.3', 'f.g1', 'f.g2', 'f.g3',
    'f.mg1', 'f.mg2', 'f.mg3', 'f.mg4', 'm.f.dh', 'm.g', 'f.g', 'm.mg', 'f.mg'
}

# Expanded POS/morph pattern: handles tokens like m., f., g., l., u.j, e.d, qr.dd, f.mg1, m.f.dh, m.l/dh, etc.
POS_PATTERN = re.compile(
    r"^(?:"
    r"(?:[a-z]{1,3}\.[a-z]{1,3}(?:\.[a-z]{1,3})?)|"  # composites first: e.d, qr.dd, m.f.dh
    r"u\.j|e\.d|qr\.dd|m\.l/dh|"                 # explicit specials
    r"(?:[mfgleu]\.[a-z]{1,3}(?:\d)?)|"            # m.g1 f.mg3 etc
    r"[mfgleu]\."                                   # single-letter POS last
    r")\b",
    re.IGNORECASE
)
# Headline: starts with a headword token, then the rest of the line
HEADLINE_PATTERN = re.compile(r"^(?P<word>[A-Za-z\u2019\u2032\u02bc\u02bb'¹²³()\-]+)\s+(?P<rest>.+)$")
# Cross-reference phrases: capture content after cue words, up to a terminator; we will split by separators later
CROSS_REF_PHRASE = re.compile(r"\(?(?:\b(?:eeg|→)\s+)([^)\.;:]+)[)\.;:]*", flags=re.IGNORECASE)
SEE_ALSO_PHRASE = re.compile(r"\b(?:ld|eeg\s+sidoo\s+kale)\s+([^)\.;:]+)", flags=re.IGNORECASE)
# Single-token fallback (legacy)
CROSS_REF_TOKEN = re.compile(r"\beeg\s+([A-Za-z\u2019\u2032\u02bc\u02bb'¹²³\-]+)", flags=re.IGNORECASE)
SEE_ALSO_TOKEN = re.compile(r"\bld\s+([A-Za-z\u2019\u2032\u02bc\u02bb'¹²³\-]+)", flags=re.IGNORECASE)

WORD_PATTERN = re.compile(r"^[A-Za-z\u2019\u2032\u02bc\u02bb'¹²³()\-]+\d?\b")
WORD_INLINE_CANDIDATE = re.compile(r"\b([A-Za-z\u2019\u2032\u02bc\u02bb'¹²³()\-]{1,40})\s+")

# ---- Columnization ----

def detect_columns(words: List[Dict[str, Any]], min_gap: float = 20.0) -> List[Tuple[float, float]]:
    """Return list of (x0, x1) column bands based on word x positions."""
    if not words:
        return []
    xs = sorted([(w['x0'], w['x1']) for w in words], key=lambda t: t[0])
    # Simple clustering: split where large gaps between consecutive x0s
    bands: List[Tuple[float, float]] = []
    current = [xs[0][0], xs[0][1]]
    for x0, x1 in xs[1:]:
        if x0 - current[1] > min_gap:
            bands.append(tuple(current))
            current = [x0, x1]
        else:
            current[0] = min(current[0], x0)
            current[1] = max(current[1], x1)
    bands.append(tuple(current))
    # Merge if too many tiny bands; aim for 1–3 columns
    if len(bands) > 3:
        # Coalesce adjacent bands greedily
        merged = [bands[0]]
        for b in bands[1:]:
            last = merged[-1]
            if b[0] - last[1] < min_gap * 2:
                merged[-1] = (min(last[0], b[0]), max(last[1], b[1]))
            else:
                merged.append(b)
        bands = merged
    return bands

# ---- Page parsing ----

def extract_page_entries(page: fitz.Page, page_num: int, debug: bool = False, debug_dir: str = None) -> List[Entry]:
    """Extract entries from a page using spans with font/size and geometry."""
    text_dict = page.get_text("dict")
    blocks = text_dict.get('blocks', [])

    # Collect words (approx) and lines with spans
    words: List[Dict[str, Any]] = []
    lines_data: List[Dict[str, Any]] = []

    page_h = float(page.rect.height)
    top_band = page_h * 0.06
    bot_band = page_h * 0.06

    for b in blocks:
        for l in b.get('lines', []):
            spans = l.get('spans', [])
            if not spans:
                continue
            # Build a line record
            line_text = "".join(s.get('text', '') for s in spans)
            line_bbox = l.get('bbox')
            # Skip header/footer bands
            if line_bbox[1] < top_band or (page_h - line_bbox[3]) < bot_band:
                continue
            # Collect word positions from spans roughly (span bbox per chunk)
            for s in spans:
                t = s.get('text', '').strip()
                if not t:
                    continue
                bbox = s.get('bbox')
                words.append({
                    'x0': bbox[0], 'y0': bbox[1], 'x1': bbox[2], 'y1': bbox[3],
                    'size': s.get('size', 0), 'font': s.get('font', ''), 'text': t
                })
            lines_data.append({
                'bbox': line_bbox,
                'spans': spans,
                'text': line_text
            })

    # Detect columns bands
    divider_x = detect_divider_x(page, lines_data)
    if divider_x is not None:
        # add divider guide spanning usable content area for debug (do not reset debug_guides)
        try:
            page_h = float(page.rect.height)
            top_band = page_h * 0.06
            bot_band = page_h * 0.06
            debug_guides.append(("DIVIDER", float(divider_x), top_band, page_h - bot_band))
        except Exception:
            pass
    # Prefer divider-based columns when available
    col_bands: List[Tuple[float, float]]
    if divider_x is not None:
        w = float(page.rect.width)
        epsilon = 1.0
        col_bands = [(0.0, max(0.0, float(divider_x) - epsilon)), (min(w, float(divider_x) + epsilon), w)]
    else:
        col_bands = detect_columns(words)
        if not col_bands:
            col_bands = [(0, page.rect.width)]
    # Ensure left-to-right order
    col_bands = sorted(col_bands, key=lambda b: b[0])

    # Assign lines to columns
    columns: List[List[Dict[str, Any]]] = [[] for _ in col_bands]
    for ld in lines_data:
        x0, y0, x1, y1 = ld['bbox']
        cx = (x0 + x1) / 2.0
        # find nearest column band containing center x
        best_idx = 0
        best_dist = float('inf')
        for i, (bx0, bx1) in enumerate(col_bands):
            if bx0 <= cx <= bx1:
                best_idx = i
                best_dist = 0
                break
            # distance to band
            d = min(abs(cx - bx0), abs(cx - bx1))
            if d < best_dist:
                best_dist = d
                best_idx = i
        columns[best_idx].append(ld)

    # Sort each column by y (top->bottom)
    for col in columns:
        col.sort(key=lambda ld: ld['bbox'][1])

    entries: List[Entry] = []
    debug_lines: List[Tuple[str, Tuple[float, float, float, float]]] = []  # (label, bbox)
    debug_guides: List[Tuple[str, float, float, float]] = []  # (label, x, y0, y1)

    # FSM per column, with carry-over from previous column when crossing divider
    carry_from_prev_col: Entry = None
    for col_idx, col in enumerate(columns):
        current: Entry = None
        last_y = None
        last_left = None
        local_sizes = []
        # Estimate a headword baseline (left x) for this column from lines that look like headline
        headword_lefts = []
        for ld in col:
            spans = ld['spans']
            text = normalize_text("".join(s.get('text', '') for s in spans))
            hl_m = HEADLINE_PATTERN.match(text)
            if hl_m and POS_PATTERN.match(normalize_text(hl_m.group('rest'))):
                headword_lefts.append(ld['bbox'][0])
        head_left = None
        if headword_lefts:
            srt = sorted(headword_lefts)
            k = int(len(srt) * 0.15)
            srt = srt[k: len(srt)-k] if len(srt) - 2*k > 0 else srt
            head_left = srt[len(srt)//2]
        else:
            # Fallback: infer baseline from word-like starts and size cues
            candidates = []
            size_pool = []
            for ld in col:
                spans = ld['spans']
                if not spans:
                    continue
                ft = normalize_text(spans[0].get('text', ''))
                if not WORD_PATTERN.match(ft):
                    continue
                sizes = [s.get('size', 0) for s in spans if s.get('text','').strip()]
                if sizes:
                    size_pool.extend(sizes)
                max_size = max(sizes) if sizes else 0
                candidates.append((ld['bbox'][0], max_size))
            if candidates:
                # Prefer those with larger size than local median
                med = 0
                if size_pool:
                    ss = sorted(size_pool)
                    med = ss[len(ss)//2]
                xs = [x for (x, ms) in candidates if ms >= med]
                if not xs:
                    xs = [x for (x, _) in candidates]
                xs.sort()
                k = int(len(xs) * 0.15)
                xs = xs[k: len(xs)-k] if len(xs) - 2*k > 0 else xs
                if xs:
                    head_left = xs[len(xs)//2]
        indent_delta = 20.0
        # Adaptive indent estimation based on observed offsets
        if head_left is not None:
            diffs = []
            y_min, y_max = None, None
            for ld in col:
                x0c, y0c, _, y1c = ld['bbox']
                if y_min is None or y0c < y_min:
                    y_min = y0c
                if y_max is None or y1c > y_max:
                    y_max = y1c
                d = x0c - head_left
                if 8.0 < d < 40.0:
                    diffs.append(d)
            if diffs:
                diffs.sort()
                k2 = int(len(diffs) * 0.15)
                diffs = diffs[k2: len(diffs)-k2] if len(diffs) - 2*k2 > 0 else diffs
                if diffs:
                    indent_delta = float(diffs[len(diffs)//2])
            # record guides for debug
            if y_min is not None and y_max is not None:
                debug_guides.append(("BASE", head_left, y_min, y_max))
                debug_guides.append(("INDENT", head_left + indent_delta, y_min, y_max))
        else:
            # Final fallback: histogram over x0 to propose baseline and indent
            if col:
                # Build histogram of left x positions (rounded to 2px)
                hist = {}
                y_min, y_max = None, None
                for ld in col:
                    x0c, y0c, _, y1c = ld['bbox']
                    y_min = y0c if y_min is None or y0c < y_min else y_min
                    y_max = y1c if y_max is None or y1c > y_max else y_max
                    key = round(x0c / 2.0) * 2.0
                    hist[key] = hist.get(key, 0) + 1
                if hist:
                    # most frequent left -> baseline
                    head_left = max(hist.items(), key=lambda kv: kv[1])[0]
                    # second band near +[14..40] px -> indent
                    indent_candidates = {x: c for x, c in hist.items() if 14.0 <= (x - head_left) <= 40.0}
                    if indent_candidates:
                        indent_x = max(indent_candidates.items(), key=lambda kv: kv[1])[0]
                        indent_delta = float(indent_x - head_left)
                    else:
                        indent_delta = 22.0
                    if y_min is not None and y_max is not None:
                        debug_guides.append(("BASE", head_left, y_min, y_max))
                        debug_guides.append(("INDENT", head_left + indent_delta, y_min, y_max))

        head_tol = 8.0
        cont_tol = 2.0
        for ld in col:
            y0 = ld['bbox'][1]
            x0 = ld['bbox'][0]
            spans = ld['spans']
            text = normalize_text("".join(s.get('text', '') for s in spans))
            if not text:
                continue
            # Estimate local typical font size
            sizes = [s.get('size', 0) for s in spans if s.get('text', '').strip()]
            if sizes:
                local_sizes.extend(sizes)
            avg_size = (sum(sizes) / len(sizes)) if sizes else 0
            max_size = max(sizes) if sizes else 0

            # Heuristic: headword if first span is noticeably larger or has Bold in font name
            first = spans[0]
            first_text = normalize_text(first.get('text', ''))
            first_font = (first.get('font', '') or '').lower()
            first_size = first.get('size', 0)
            is_boldy = ('bold' in first_font) or ('black' in first_font) or ('semibold' in first_font)
            # compare size with median of recent sizes
            size_thresh = 0
            if local_sizes:
                sorted_sizes = sorted(local_sizes[-30:])
                mid = sorted_sizes[len(sorted_sizes)//2]
                size_thresh = mid + 0.4  # tweakable
            looks_like_word = bool(WORD_PATTERN.match(first_text))
            looks_like_headword = looks_like_word and (is_boldy or (first_size >= size_thresh) or (max_size >= size_thresh + 0.2))

            # Additional heuristic: if the line begins with a word and the rest starts with a POS token
            hl_m = HEADLINE_PATTERN.match(text)
            rest_after_word = None
            if hl_m:
                rest_after_word = normalize_text(hl_m.group('rest'))
            pos_in_line = False
            if rest_after_word:
                tmp = rest_after_word
                while tmp.startswith('(') and ')' in tmp:
                    close = tmp.find(')')
                    tmp = tmp[close+1:].lstrip()
                pos_in_line = bool(POS_PATTERN.match(tmp))

            # Gap heuristics
            gap_ok = True
            if last_y is not None:
                vgap = y0 - last_y
                gap_ok = vgap > 2  # very small overlaps are same para

            # Before anything else, if we have a carry-over entry from previous column and nothing started yet,
            # allow continuation only if this line aligns to this column's indent (purple) and is not a clear headword.
            if current is None and carry_from_prev_col is not None and head_left is not None:
                # recompute head/pos alignment for this line
                is_head_aligned_tmp = abs(x0 - head_left) <= head_tol
                is_pos_near_start_tmp = False
                hl_m_tmp = HEADLINE_PATTERN.match(text)
                if hl_m_tmp:
                    rest_tmp = normalize_text(hl_m_tmp.group('rest'))
                    ttmp = rest_tmp
                    while ttmp.startswith('(') and ')' in ttmp:
                        c3 = ttmp.find(')')
                        ttmp = ttmp[c3+1:].lstrip()
                    is_pos_near_start_tmp = bool(POS_PATTERN.match(ttmp))
                # if indented (purple) and not a head-aligned+POS line, treat as continuation of carry
                if (x0 >= head_left + indent_delta - cont_tol) and not (is_head_aligned_tmp and is_pos_near_start_tmp):
                    current = carry_from_prev_col
                    # append text to current definition stream
                    debug_lines.append(('CONT', ld['bbox']))
                    # fall through to normal continuation handling below

            # Determine if this line is likely a continuation by indent, if we already have an entry
            is_continuation_by_indent = False
            if head_left is not None and current is not None:
                same_col = True
                if divider_x is not None:
                    try:
                        curr_x0 = float(current.bbox[0])
                        same_col = (curr_x0 < divider_x and x0 < divider_x) or (curr_x0 >= divider_x and x0 >= divider_x)
                    except Exception:
                        same_col = True
                # Continuations must align to the indent (purple) within tolerance
                if same_col and (x0 >= head_left + indent_delta - cont_tol):
                    is_continuation_by_indent = True

            # Decide start of new entry
            # Only start a new entry if a POS is present after optional alias parentheses
            # and the line is aligned closely to the headword baseline (prevents indented continuations)
            is_head_aligned = True
            if head_left is not None:
                # Headword must align close to baseline (red)
                is_head_aligned = abs(x0 - head_left) <= head_tol
            # If strongly looks like a headword (aligned+POS), don't require a vertical gap
            # Also allow starting a new entry if this line is not more indented than the current entry start
            aligned_vs_current = True
            if current is not None and isinstance(current.bbox, tuple):
                try:
                    curr_x = float(current.bbox[0])
                    aligned_vs_current = x0 <= curr_x + 2.0
                except Exception:
                    aligned_vs_current = True
            if pos_in_line and is_head_aligned:
                # Push previous entry if exists
                if current is not None:
                    if not current.senses and current.word:
                        # whatever collected text as one sense
                        pass
                    entries.append(current)
                # Determine headword from headline regex if available; otherwise fall back to first span
                hw = first_text
                if hl_m:
                    hw = normalize_text(hl_m.group('word'))
                current = Entry(word=hw, page=page_num, column=col_idx, bbox=tuple(ld['bbox']))
                # Try to capture POS from the rest of the line
                rest = rest_after_word if hl_m else normalize_text(text[len(first.get('text', '').strip()):].lstrip())
                # capture POS and optional immediate inflection parens
                # consume alias parentheses again for actual POS capture
                tmp = rest
                while tmp.startswith('(') and ')' in tmp:
                    c = tmp.find(')')
                    tmp = tmp[c+1:].lstrip()
                m = POS_PATTERN.match(tmp)
                if m:
                    current.pos = m.group(0)
                    rest = tmp[m.end():].strip()
                    # inflection in parentheses immediately after POS
                    if rest.startswith('('):
                        # capture up to first closing paren
                        close = rest.find(')')
                        if close != -1:
                            infl = rest[0:close+1]
                            # store as crossRef-like meta for now (could add field)
                            # remove from rest
                            rest = rest[close+1:].lstrip()
                if rest:
                    # initialize first sense
                    # If line begins with numbered sense, split
                    if re.match(r"^\d+\.", rest):
                        current.senses.append(Sense(text=rest))
                    else:
                        current.senses.append(Sense(text=rest))
                debug_lines.append(("HEADWORD", tuple(ld['bbox'])))
            else:
                # Continuation line (definition wrap or new sense)
                if current is None:
                    # Not started yet; skip noise lines (headers/footers heuristics could be added)
                    continue
                # Guard: if this continuation actually looks like a new headword line (head-aligned + POS soon), start a new entry
                promote_to_head = False
                if head_left is not None:
                    if abs(x0 - head_left) <= 10.0:
                        tmp2 = text
                        hl2 = HEADLINE_PATTERN.match(tmp2)
                        if hl2:
                            rest2 = normalize_text(hl2.group('rest'))
                            # consume alias parens
                            while rest2.startswith('(') and ')' in rest2:
                                c2 = rest2.find(')')
                                rest2 = rest2[c2+1:].lstrip()
                            m2 = POS_PATTERN.match(rest2)
                            if m2 and m2.start() == 0:
                                promote_to_head = True
                if promote_to_head:
                    # finalize current and start a new entry
                    entries.append(current)
                    hw = normalize_text(hl2.group('word')) if hl2 else first_text
                    current = Entry(word=hw, page=page_num, column=col_idx, bbox=tuple(ld['bbox']))
                    rest = rest2[m2.end():].lstrip() if (hl2 and m2) else ''
                    if rest.startswith('('):
                        close = rest.find(')')
                        if close != -1:
                            rest = rest[close+1:].lstrip()
                    if rest:
                        current.senses.append(Sense(text=rest))
                    debug_lines.append(("HEADWORD", tuple(ld['bbox'])))
                    last_y = y0
                    last_left = x0
                    continue
                # If this line begins with a digit+dot, treat as a new sense
                if re.match(r"^\d+\.", text):
                    current.senses.append(Sense(text=text))
                else:
                    # Before appending, check for inline headword break (e.g., previous join glued next entry)
                    split_idx, new_hw, new_rest = find_inline_headword_break(text)
                    if split_idx != -1 and (head_left is None or abs(x0 - head_left) <= 12.0):
                        # Append left part to current sense
                        left_part = text[:split_idx].rstrip()
                        if left_part:
                            if current.senses:
                                current.senses[-1].text = normalize_text(current.senses[-1].text + " " + left_part)
                            else:
                                current.senses.append(Sense(text=left_part))
                        # Finalize current and start new entry inline
                        entries.append(current)
                        current = Entry(word=new_hw, page=page_num, column=col_idx, bbox=tuple(ld['bbox']))
                        if new_rest:
                            # remove leading inflection
                            if new_rest.startswith('('):
                                c3 = new_rest.find(')')
                                if c3 != -1:
                                    new_rest = new_rest[c3+1:].lstrip()
                            current.senses.append(Sense(text=new_rest))
                        debug_lines.append(("HEADWORD", tuple(ld['bbox'])))
                    else:
                        # append to last sense or create one
                        if current.senses:
                            current.senses[-1].text = normalize_text(current.senses[-1].text + " " + text)
                        else:
                            current.senses.append(Sense(text=text))
                debug_lines.append(("CONT", tuple(ld['bbox'])))

            last_y = y0
            last_left = x0

        # flush at column end
        if current:
            entries.append(current)

    # Post-process: join hyphenated wraps, extract cross-refs, trim
    for e in entries:
        e.word = normalize_text(e.word)
        if e.pos:
            e.pos = normalize_text(e.pos)
        merged: List[Sense] = []
        for s in e.senses:
            t = s.text.strip()
            # Hyphenation: '...-' + next line already merged by concat; ensure no stray ' - '
            t = re.sub(r"\s+-\s+", "-", t)
            # Extract cross-ref phrases, then split into individual refs
            def _split_refs(chunk: str) -> List[str]:
                parts = []
                for p in re.split(r"[;,،]", chunk):
                    p = normalize_text(p.strip())
                    if not p:
                        continue
                    # drop leading cue words if remained
                    p = re.sub(r"^(eeg\s+|ld\s+)", "", p)
                    parts.append(p)
                return parts
            for m in CROSS_REF_PHRASE.finditer(t):
                for cr in _split_refs(m.group(1)):
                    if cr and cr not in e.crossRefs:
                        e.crossRefs.append(cr)
            for m in SEE_ALSO_PHRASE.finditer(t):
                for sa in _split_refs(m.group(1)):
                    if sa and sa not in e.seeAlso:
                        e.seeAlso.append(sa)
            # Fallback single-token capture
            for cr in CROSS_REF_TOKEN.findall(t):
                crn = normalize_text(cr)
                if crn and crn not in e.crossRefs:
                    e.crossRefs.append(crn)
            for sa in SEE_ALSO_TOKEN.findall(t):
                san = normalize_text(sa)
                if san and san not in e.seeAlso:
                    e.seeAlso.append(san)
            merged.append(Sense(text=t))
        e.senses = merged
    # Optional debug overlay
    if debug and debug_dir:
        try:
            os.makedirs(debug_dir, exist_ok=True)
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            from PIL import Image, ImageDraw
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            draw = ImageDraw.Draw(img)
            # scale bboxes to matrix
            scale = 2
            for label, bb in debug_lines:
                x0, y0, x1, y1 = [v * scale for v in bb]
                color = (0, 200, 0) if label == 'HEADWORD' else (50, 120, 255)
                draw.rectangle([x0, y0, x1, y1], outline=color, width=2)
            # draw guides
            for glabel, gx, gy0, gy1 in debug_guides:
                x = gx * scale
                y0 = gy0 * scale
                y1 = gy1 * scale
                if glabel == 'BASE':
                    color = (255, 0, 0)  # red
                elif glabel == 'INDENT':
                    color = (160, 32, 240)  # purple
                else:  # DIVIDER
                    color = (0, 0, 0)
                draw.line([x, y0, x, y1], fill=color, width=2)
                # Add very small labels near top for clarity
                try:
                    label = glabel
                    # map to L/R by comparing to divider if available
                    if divider_x is not None and glabel in ('BASE', 'INDENT'):
                        lr = 'L' if gx < divider_x else 'R'
                        label = f"{lr}-{glabel}"
                    draw.text((x+4, max(0, int(y0)+4)), label, fill=color)
                except Exception:
                    pass
            out_path = os.path.join(debug_dir, f"page_{page_num:03d}.png")
            img.save(out_path)
        except Exception as _:
            pass
    return entries


def entries_to_simple(entries: List[Entry]) -> List[Dict[str, Any]]:
    out = []
    for e in entries:
        out.append({
            'word': e.word,
            'pos': e.pos,
            'definition': " ".join(s.text for s in e.senses).strip(),
            'crossRefs': e.crossRefs,
            'seeAlso': e.seeAlso,
            'crossRefTargets': e.crossRefTargets,
            'seeAlsoTargets': e.seeAlsoTargets,
            'page': e.page,
            'column': e.column,
        })
    return out


def find_inline_headword_break(text: str) -> Tuple[int, str, str]:
    """Return (split_index, headword, rest_after_pos) if a new headword+POS appears in text; else (-1, '', '').
    We search for a candidate headword token followed shortly by a POS token.
    """
    if not text:
        return -1, '', ''
    for m in WORD_INLINE_CANDIDATE.finditer(text):
        hw = normalize_text(m.group(1))
        # Ignore very short like single letters unless exactly 'a'
        if len(hw) == 1 and hw != 'a':
            continue
        rest = text[m.end():].lstrip()
        # consume alias parentheses if any
        tmp = rest
        if tmp.startswith('(') and ')' in tmp:
            c = tmp.find(')')
            tmp = tmp[c+1:].lstrip()
        pm = POS_PATTERN.match(tmp)
        if pm and pm.start() == 0:
            # position to split is before the headword token
            return m.start(), hw, tmp[pm.end():].lstrip()
    return -1, '', ''


def parse_pages(pdf_path: str, pages: List[int], debug: bool = False, debug_dir: str = None) -> List[Entry]:
    doc = fitz.open(pdf_path)
    n = doc.page_count
    entries: List[Entry] = []
    for p in pages:
        if p < 1 or p > n:
            continue
        page = doc.load_page(p - 1)
        entries.extend(extract_page_entries(page, p, debug=debug, debug_dir=debug_dir))
    # Resolve cross-refs against the collected entries (within these pages)
    index_norm: Dict[str, List[Entry]] = {}
    index_base: Dict[str, List[Entry]] = {}
    def norm_key(s: str) -> str:
        return normalize_text(s)
    def strip_superscripts(s: str) -> str:
        return re.sub(r"[¹²³]", "", s)
    def word_id(e: Entry) -> str:
        # include superscripts if present in word
        return e.word
    for e in entries:
        nk = norm_key(e.word)
        index_norm.setdefault(nk, []).append(e)
        index_base.setdefault(strip_superscripts(nk), []).append(e)
    def resolve_list(items: List[str]) -> List[str]:
        targets: List[str] = []
        for token in items:
            nk = norm_key(token)
            base = strip_superscripts(nk)
            cand = index_norm.get(nk) or []
            if len(cand) == 1:
                targets.append(word_id(cand[0]))
                continue
            # fallback by base (no superscript)
            cand2 = index_base.get(base) or []
            if len(cand2) >= 1:
                # prefer first by page proximity (same page if possible)
                # for simplicity, just pick the first for now
                targets.append(word_id(cand2[0]))
            else:
                # unresolved: keep token itself
                targets.append(nk)
        return targets
    for e in entries:
        e.crossRefTargets = resolve_list(e.crossRefs)
        e.seeAlsoTargets = resolve_list(e.seeAlso)
    return entries


def parse_pages_arg(pages_arg: str, default: List[int]) -> List[int]:
    if not pages_arg:
        return default
    result = []
    parts = [s.strip() for s in pages_arg.split(',') if s.strip()]
    for part in parts:
        if '-' in part:
            a, b = part.split('-', 1)
            try:
                a, b = int(a), int(b)
                result.extend(list(range(min(a, b), max(a, b) + 1)))
            except ValueError:
                pass
        else:
            try:
                result.append(int(part))
            except ValueError:
                pass
    # unique & sorted
    return sorted(set(result))


def main():
    parser = argparse.ArgumentParser(description="Extract dictionary entries (prototype) using PyMuPDF")
    parser.add_argument('--pdf', default='qaam.pdf', help='Path to PDF (default: qaam.pdf)')
    parser.add_argument('--pages', default='1-3', help='Pages to parse, e.g. "1-3,10" (1-based)')
    parser.add_argument('--out', default='data/entries_preview.json', help='Output JSON path')
    parser.add_argument('--debug', action='store_true', help='Write debug overlay images')
    parser.add_argument('--debug-dir', default='data/debug', help='Directory for debug images')
    args = parser.parse_args()

    pdf_path = args.pdf
    if not os.path.isabs(pdf_path):
        pdf_path = os.path.join(os.path.dirname(__file__), '..', pdf_path)
        pdf_path = os.path.normpath(pdf_path)

    # Resolve pages (support 'all')
    if isinstance(args.pages, str) and args.pages.lower() in ('all', '*'):
        try:
            doc_tmp = fitz.open(pdf_path)
            pages = list(range(1, doc_tmp.page_count + 1))
            doc_tmp.close()
        except Exception:
            pages = [1, 2, 3]
    else:
        pages = parse_pages_arg(args.pages, [1, 2, 3])

    print(f"Parsing {pdf_path} pages {pages} ...")
    entries = parse_pages(pdf_path, pages, debug=args.debug, debug_dir=args.debug_dir)
    simple = entries_to_simple(entries)

    os.makedirs(os.path.dirname(os.path.join(os.path.dirname(__file__), '..', args.out)), exist_ok=True)
    out_path = args.out
    if not os.path.isabs(out_path):
        out_path = os.path.join(os.path.dirname(__file__), '..', out_path)
        out_path = os.path.normpath(out_path)

    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump({
            'source': os.path.basename(pdf_path),
            'pages': pages,
            'count': len(simple),
            'entries': simple
        }, f, ensure_ascii=False, indent=2)

    print(f"Wrote {out_path} with {len(simple)} entries")


if __name__ == '__main__':
    main()
