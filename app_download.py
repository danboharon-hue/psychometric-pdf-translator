import os
import json
import sys
from pathlib import Path

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from flask import Flask, render_template, send_file, jsonify

app = Flask(__name__)
BASE_DIR = Path(__file__).parent
PROCESSED_DIR = BASE_DIR / "processed"

# Load processing summary
SUMMARY = {}
summary_path = PROCESSED_DIR / "processing_summary.json"
if summary_path.exists():
    with open(summary_path, "r", encoding="utf-8") as f:
        SUMMARY = json.load(f)

# Get all processed PDFs
def get_pdf_list():
    pdfs = {}
    if not PROCESSED_DIR.exists():
        return pdfs
    for word_list_dir in PROCESSED_DIR.iterdir():
        if word_list_dir.is_dir() and word_list_dir.name not in ["__pycache__", "NGSL", "מילון_הפסיכומטרי_של_המדינה"]:
            continue
        if word_list_dir.is_dir():
            # Map back the underscore name to proper name
            if word_list_dir.name == "מילון_הפסיכומטרי_של_המדינה":
                word_list_name = "מילון הפסיכומטרי של המדינה"
            else:
                word_list_name = word_list_dir.name

            pdf_files = sorted([f.name for f in word_list_dir.glob("*.pdf")])
            if pdf_files:
                pdfs[word_list_name] = pdf_files
    return pdfs

@app.route("/")
def index():
    pdfs = get_pdf_list()
    return render_template("download.html", pdfs=pdfs, summary=SUMMARY, cache_bust=True)

@app.route("/api/pdfs")
def api_pdfs():
    pdfs = get_pdf_list()
    return jsonify(pdfs)

@app.route("/download/<word_list>/<filename>")
def download(word_list, filename):
    word_list_dir = PROCESSED_DIR / word_list.replace(" ", "_")
    pdf_path = word_list_dir / filename

    if not pdf_path.exists():
        return "File not found", 404

    return send_file(str(pdf_path), as_attachment=True, download_name=filename)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5055))
    print(f"🚀 Starting server on http://localhost:{port}")
    app.run(debug=False, host="0.0.0.0", port=port)
