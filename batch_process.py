import os
import re
import json
import shutil
import sys
from pathlib import Path
from datetime import datetime

# Fix encoding for Hebrew on Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from flask import Flask
import fitz  # PyMuPDF
import openpyxl
import nltk
from nltk.stem import WordNetLemmatizer

for pkg in ['wordnet', 'averaged_perceptron_tagger_eng', 'punkt_tab']:
    nltk.download(pkg, quiet=True)

BASE_DIR      = Path(__file__).parent
PRELOADED_DIR = BASE_DIR / "preloaded"
OUTPUT_DIR    = BASE_DIR / "output"
PROCESSED_DIR = BASE_DIR / "processed"

PROCESSED_DIR.mkdir(exist_ok=True)

# ── Word lists ────────────────────────────────────────────────────────────────

def load_word_lists():
    lists = {}
    # NGSL
    ngsl_path = BASE_DIR / "ngsl_he.json"
    if ngsl_path.exists():
        with open(ngsl_path, encoding="utf-8") as f:
            lists["NGSL"] = json.load(f)
    # Campus / Psychometric
    campus_path = BASE_DIR / "campus_he.json"
    if campus_path.exists():
        with open(campus_path, encoding="utf-8") as f:
            lists["מילון הפסיכומטרי של המדינה"] = json.load(f)
    return lists

WORD_LISTS = load_word_lists()

# ── NLP helpers ───────────────────────────────────────────────────────────────

_lem = WordNetLemmatizer()

_IRREGULAR = {
    'me':'i','my':'i','mine':'i','myself':'i',
    'your':'you','yours':'you','yourself':'you','yourselves':'you',
    'him':'he','his':'he','himself':'he',
    'her':'she','hers':'she','herself':'she',
    'its':'it','itself':'it',
    'them':'they','their':'they','theirs':'they','themselves':'they',
    'us':'we','our':'we','ours':'we','ourselves':'we',
    'was':'be','were':'be','been':'be','am':'be','is':'be','are':'be',
    'had':'have','has':'have',
    'did':'do','does':'do','done':'do',
    'went':'go','gone':'go','goes':'go',
    'said':'say','says':'say',
    'got':'get','gotten':'get','gets':'get',
    'knew':'know','known':'know','knows':'know',
    'thought':'think','thinks':'think',
    'made':'make','makes':'make',
    'saw':'see','seen':'see','sees':'see',
    'came':'come','comes':'come',
    'took':'take','taken':'take','takes':'take',
    'gave':'give','given':'give','gives':'give',
    'found':'find','finds':'find',
    'told':'tell','tells':'tell',
    'felt':'feel','feels':'feel',
    'left':'leave','leaves':'leave',
    'kept':'keep','keeps':'keep',
    'meant':'mean','means':'mean',
    'led':'lead','leads':'lead',
    'began':'begin','begun':'begin','begins':'begin',
    'ran':'run','runs':'run',
    'brought':'bring','brings':'bring',
    'bought':'buy','buys':'buy',
    'taught':'teach','teaches':'teach',
    'caught':'catch','catches':'catch',
    'wrote':'write','written':'write','writes':'write',
    'read':'read',
    'spoke':'speak','spoken':'speak','speaks':'speak',
    'grew':'grow','grown':'grow','grows':'grow',
    'drew':'draw','drawn':'draw','draws':'draw',
    'chose':'choose','chosen':'choose','chooses':'choose',
    'lost':'lose','loses':'lose',
    'met':'meet','meets':'meet',
    'paid':'pay','pays':'pay',
    'sent':'send','sends':'send',
    'spent':'spend','spends':'spend',
    'stood':'stand','stands':'stand',
    'understood':'understand','understands':'understand',
    'won':'win','wins':'win',
    'wore':'wear','worn':'wear','wears':'wear',
    'broke':'break','broken':'break','breaks':'break',
    'showed':'show','shown':'show','shows':'show',
    'heard':'hear','hears':'hear',
    'held':'hold','holds':'hold',
    'laid':'lay','lays':'lay',
    'built':'build','builds':'build',
    'cut':'cut','cuts':'cut',
    'put':'put','puts':'put',
    'set':'set','sets':'set',
    'hit':'hit','hits':'hit',
    'let':'let','lets':'let',
    'better':'good','best':'good',
    'worse':'bad','worst':'bad',
}

def find_match(word, word_dict):
    w = word.lower()
    w = re.sub(r"'s$", "", w)

    if w in _IRREGULAR and _IRREGULAR[w] in word_dict:
        return _IRREGULAR[w]

    if w in word_dict:
        return w

    for pos in ['v', 'n', 'a', 'r']:
        lemma = _lem.lemmatize(w, pos)
        if lemma in word_dict:
            return lemma

    for suffix, replace in [('ness',''), ('ment',''), ('tion','te'), ('tion',''),
                             ('ies','y'), ('ied','y'), ('ier','y'), ('iest','y')]:
        if w.endswith(suffix) and len(w) > len(suffix) + 2:
            stem = w[:-len(suffix)] + replace
            if stem in word_dict:
                return stem

    return None

def is_english(word):
    return bool(re.match(r"^[a-zA-Z'-]+$", word)) and len(word) >= 2

def clean(word):
    return re.sub(r"[^a-zA-Z'-]", "", word).strip("'-")

# ── Font ─────────────────────────────────────────────────────────────────────

HEBREW_FONT_PATH = next(
    (p for p in [
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/ARIAL.TTF",
        "C:/Windows/Fonts/tahoma.ttf",
        "C:/Windows/Fonts/TAHOMA.TTF",
    ] if os.path.exists(p)),
    None
)
_HE_FONT = fitz.Font(fontfile=HEBREW_FONT_PATH) if HEBREW_FONT_PATH else fitz.Font("helv")

# ── PDF processing ────────────────────────────────────────────────────────────

COLOR_ABOVE = (0.10, 0.37, 0.85)
COLOR_WHITE = (1.0,  1.0,  1.0)
HL_YELLOW   = [1.0, 0.88, 0.10]
HL_ORANGE   = [1.0, 0.70, 0.20]
FSIZE_ABOVE = 7.0
STROKE_OFF  = 0.55

def _append_with_stroke(tw_white, tw_blue, point, text, font, fsize):
    for dx, dy in [(-STROKE_OFF,0),(STROKE_OFF,0),(0,-STROKE_OFF),(0,STROKE_OFF),
                   (-STROKE_OFF,-STROKE_OFF),(STROKE_OFF,-STROKE_OFF),
                   (-STROKE_OFF, STROKE_OFF),(STROKE_OFF, STROKE_OFF)]:
        tw_white.append(fitz.Point(point.x+dx, point.y+dy),
                        text, font=font, fontsize=fsize, right_to_left=1)
    tw_blue.append(point, text, font=font, fontsize=fsize, right_to_left=1)

def process_pdf(pdf_path, word_dict, output_path, mode="above"):
    doc = fitz.open(str(pdf_path))

    found_words      = {}
    total_ngsl_hits  = 0
    proper_noun_set  = set()
    proper_noun_hits = 0
    unknown_set      = set()
    unknown_hits     = 0
    total_english    = 0

    for page in doc:
        raw_words = page.get_text("words")
        page_text = page.get_text("text")

        sentence_starters = set()
        try:
            for sent in nltk.sent_tokenize(page_text):
                toks = sent.split()
                if toks:
                    sentence_starters.add(toks[0].lower())
        except Exception:
            pass

        ngsl_matches = []

        for w_info in raw_words:
            x0, y0, x1, y1 = w_info[0], w_info[1], w_info[2], w_info[3]
            raw_word = w_info[4]
            word     = clean(raw_word)

            if not is_english(word):
                continue

            total_english += 1
            key         = word.lower()
            rect        = fitz.Rect(x0, y0, x1, y1)
            matched_key = find_match(word, word_dict)

            is_cap    = raw_word[0].isupper() if raw_word else False
            is_sent_s = key in sentence_starters
            is_proper = is_cap and not is_sent_s and matched_key is None

            if is_proper:
                proper_noun_set.add(raw_word)
                proper_noun_hits += 1
                hi = page.add_highlight_annot(rect)
                hi.set_colors(stroke=HL_ORANGE)
                hi.update()
                continue

            if matched_key and word_dict.get(matched_key):
                translation = word_dict[matched_key]
                found_words[matched_key] = translation
                total_ngsl_hits += 1
                ngsl_matches.append((rect, translation))
                continue

            unknown_set.add(key)
            unknown_hits += 1

        tw_white = fitz.TextWriter(page.rect, color=COLOR_WHITE)
        tw_blue  = fitz.TextWriter(page.rect, color=COLOR_ABOVE)

        for rect, translation in ngsl_matches:
            hi = page.add_highlight_annot(rect)
            hi.set_colors(stroke=HL_YELLOW)
            hi.update()

            text_w   = _HE_FONT.text_length(translation, FSIZE_ABOVE)
            word_cx  = (rect.x0 + rect.x1) / 2
            anchor_x = word_cx - text_w / 2

            baseline_y = rect.y0 - 1.5
            if baseline_y - FSIZE_ABOVE < 0:
                baseline_y = rect.y1 + FSIZE_ABOVE + 1.5

            _append_with_stroke(tw_white, tw_blue,
                                fitz.Point(anchor_x, baseline_y),
                                translation, _HE_FONT, FSIZE_ABOVE)

        tw_white.write_text(page)
        tw_blue.write_text(page)

    doc.save(str(output_path))
    doc.close()

    total_english_no_proper = total_english - proper_noun_hits
    return {
        "total_english":         total_english,
        "total_english_no_proper": total_english_no_proper,
        "total_matches":         total_ngsl_hits,
        "unique_words":          len(found_words),
        "proper_noun_count":     len(proper_noun_set),
        "proper_noun_hits":      proper_noun_hits,
        "unknown_count":         len(unknown_set),
        "unknown_hits":          unknown_hits,
        "translations":          dict(sorted(found_words.items())),
    }

# ── Main batch processing ─────────────────────────────────────────────────────

print("=" * 80)
print("BATCH PROCESSING - All PDFs")
print("=" * 80)

if not PRELOADED_DIR.exists():
    print(f"❌ Preloaded directory not found: {PRELOADED_DIR}")
    exit(1)

pdf_files = sorted(list(PRELOADED_DIR.glob("*.pdf")))
print(f"Found {len(pdf_files)} PDFs\n")

if not pdf_files:
    print("❌ No PDFs found!")
    exit(1)

results = {}

for word_list_name, word_dict in WORD_LISTS.items():
    print(f"\n{'='*80}")
    print(f"Processing with: {word_list_name} ({len(word_dict)} words)")
    print(f"{'='*80}\n")

    list_output_dir = PROCESSED_DIR / word_list_name.replace(" ", "_")
    list_output_dir.mkdir(exist_ok=True)

    results[word_list_name] = {}

    for i, pdf_path in enumerate(pdf_files, 1):
        pdf_name = pdf_path.stem
        output_name = f"{pdf_name}_translated.pdf"
        output_path = list_output_dir / output_name

        print(f"[{i}/{len(pdf_files)}] Processing: {pdf_path.name}...", end=" ", flush=True)

        try:
            stats = process_pdf(pdf_path, word_dict, output_path)
            results[word_list_name][pdf_name] = stats
            print(f"✅ ({stats['total_matches']} matches, {stats['unique_words']} unique words)")
        except Exception as e:
            print(f"❌ ERROR: {str(e)}")
            results[word_list_name][pdf_name] = {"error": str(e)}

# ── Save results summary ──────────────────────────────────────────────────────

summary_path = PROCESSED_DIR / "processing_summary.json"
with open(summary_path, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f"\n{'='*80}")
print("✅ BATCH PROCESSING COMPLETE!")
print(f"{'='*80}")
print(f"Processed PDFs saved in: {PROCESSED_DIR}")
print(f"Summary saved: {summary_path}")
print(f"\nTotal PDFs processed: {len(pdf_files)} × {len(WORD_LISTS)} = {len(pdf_files) * len(WORD_LISTS)} files")
