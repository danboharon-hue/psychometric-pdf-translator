import os
import re
import json
import shutil
from pathlib import Path

from flask import Flask, render_template, request, send_file, jsonify
import fitz  # PyMuPDF
import openpyxl
import nltk
from nltk.stem import WordNetLemmatizer

for pkg in ['wordnet', 'averaged_perceptron_tagger_eng', 'punkt_tab']:
    nltk.download(pkg, quiet=True)

app = Flask(__name__)
BASE_DIR      = Path(__file__).parent
UPLOAD_DIR    = BASE_DIR / "uploads"
OUTPUT_DIR    = BASE_DIR / "output"
PRELOADED_DIR = BASE_DIR / "preloaded"
WORDLISTS_DIR = BASE_DIR / "wordlists"

for d in [UPLOAD_DIR, OUTPUT_DIR, PRELOADED_DIR, WORDLISTS_DIR]:
    d.mkdir(exist_ok=True)


NGSL_SRC = r"C:\Users\דן\Downloads\NGSL_1.2_stats (2).xlsx"
if os.path.exists(NGSL_SRC):
    _dest = WORDLISTS_DIR / "NGSL_1.2_stats.xlsx"
    if not _dest.exists():
        shutil.copy2(NGSL_SRC, _dest)


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

# צורות לא-סדירות של מילים הנמצאות ברשימה כ-lemma
_IRREGULAR = {
    # כינויי גוף
    'me':'i','my':'i','mine':'i','myself':'i',
    'your':'you','yours':'you','yourself':'you','yourselves':'you',
    'him':'he','his':'he','himself':'he',
    'her':'she','hers':'she','herself':'she',
    'its':'it','itself':'it',
    'them':'they','their':'they','theirs':'they','themselves':'they',
    'us':'we','our':'we','ours':'we','ourselves':'we',
    # פעלים לא-סדירים נפוצים
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
    'read':'read',  # same form
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
    """
    Returns the matching key in word_dict, or None.
    Tries: irregular forms → direct → lemmatizer → suffix stripping.
    """
    w = word.lower()
    w = re.sub(r"'s$", "", w)   # strip possessive

    # 1. Irregular form table
    if w in _IRREGULAR and _IRREGULAR[w] in word_dict:
        return _IRREGULAR[w]

    # 2. Direct match
    if w in word_dict:
        return w

    # 3. NLTK lemmatizer for all POS
    for pos in ['v', 'n', 'a', 'r']:
        lemma = _lem.lemmatize(w, pos)
        if lemma in word_dict:
            return lemma

    # 4. Manual suffix stripping for edge cases
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

COLOR_ABOVE = (0.10, 0.37, 0.85)   # blue text for translations
COLOR_WHITE = (1.0,  1.0,  1.0)    # white stroke around letters
HL_YELLOW   = [1.0, 0.88, 0.10]    # yellow highlight
HL_ORANGE   = [1.0, 0.70, 0.20]    # orange highlight for proper nouns
FSIZE_ABOVE = 7.0                   # Hebrew label font size
STROKE_OFF  = 0.55                  # offset in pts for white stroke simulation


def _append_with_stroke(tw_white, tw_blue, point, text, font, fsize):
    """Write text with a thin white stroke by layering white offsets then blue on top."""
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

        # Collect NGSL matches for this page before modifying
        ngsl_matches = []   # list of (rect, translation)

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

            # ── Proper noun ──────────────────────────────────────────────
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

            # ── NGSL match ───────────────────────────────────────────────
            if matched_key and word_dict.get(matched_key):
                translation = word_dict[matched_key]
                found_words[matched_key] = translation
                total_ngsl_hits += 1
                ngsl_matches.append((rect, translation))
                continue

            # ── Unknown ──────────────────────────────────────────────────
            unknown_set.add(key)
            unknown_hits += 1

        # ── Apply matches to page ─────────────────────────────────────────
        tw_white = fitz.TextWriter(page.rect, color=COLOR_WHITE)
        tw_blue  = fitz.TextWriter(page.rect, color=COLOR_ABOVE)

        for rect, translation in ngsl_matches:
            # Yellow highlight
            hi = page.add_highlight_annot(rect)
            hi.set_colors(stroke=HL_YELLOW)
            hi.update()

            # Center Hebrew text above the word.
            # With right_to_left=1, pos is the LEFT start of glyph stream
            # (chars are reversed), so center = pos.x + text_w/2 → pos.x = cx - text_w/2
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


# ── Routes ────────────────────────────────────────────────────────────────────

_SEASON_ORDER = {'אביב': 1, 'קיץ': 2, 'סתיו': 3, 'חורף': 4}

def _pdf_sort_key(name):
    m = re.search(r'(\S+)\s+(\d{4})\s+פרק\s+(\d+)', name)
    if m:
        season, year, part = m.group(1), int(m.group(2)), int(m.group(3))
        return (-year, _SEASON_ORDER.get(season, 99), part)
    return (9999, 99, 99)

@app.route("/")
def index():
    word_list_names = list(WORD_LISTS.keys())
    word_list_sizes = {name: len(d) for name, d in WORD_LISTS.items()}
    preloaded = sorted(
        (f.name for f in PRELOADED_DIR.iterdir() if f.suffix.lower() == ".pdf"),
        key=_pdf_sort_key
    )
    return render_template("index.html",
                           word_lists=word_list_names,
                           word_list_sizes=word_list_sizes,
                           preloaded_pdfs=preloaded)


@app.route("/process", methods=["POST"])
def process():
    word_list_name = request.form.get("word_list")
    pdf_source     = request.form.get("pdf_source")
    preloaded_name = request.form.get("preloaded_pdf")
    mode           = request.form.get("mode", "above")   # "above" | "replace"

    if word_list_name not in WORD_LISTS:
        return jsonify({"error": "רשימת מילים לא נמצאה"}), 400

    word_dict = WORD_LISTS[word_list_name]

    if pdf_source == "upload":
        if "pdf_file" not in request.files or not request.files["pdf_file"].filename:
            return jsonify({"error": "לא הועלה קובץ PDF"}), 400
        f = request.files["pdf_file"]
        pdf_path = UPLOAD_DIR / f.filename
        f.save(str(pdf_path))
    else:
        if not preloaded_name:
            return jsonify({"error": "לא נבחר קובץ PDF"}), 400
        pdf_path = PRELOADED_DIR / preloaded_name
        if not pdf_path.exists():
            return jsonify({"error": "קובץ PDF לא נמצא"}), 404

    output_name = f"translated_{mode}_{pdf_path.stem}.pdf"
    output_path = OUTPUT_DIR / output_name

    try:
        stats = process_pdf(pdf_path, word_dict, output_path, mode)
        stats["output_file"]   = output_name
        stats["original_name"] = pdf_path.name
        return jsonify(stats)
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500


@app.route("/view/<path:filename>")
def view(filename):
    path = OUTPUT_DIR / filename
    if not path.exists():
        return "File not found", 404
    return send_file(str(path), mimetype="application/pdf")


@app.route("/download/<path:filename>")
def download(filename):
    path = OUTPUT_DIR / filename
    if not path.exists():
        return "File not found", 404
    return send_file(str(path), as_attachment=True, download_name=filename)


if __name__ == "__main__":
    app.run(debug=False, port=5055)
