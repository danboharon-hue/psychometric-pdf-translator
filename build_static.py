# -*- coding: utf-8 -*-
"""Generates a single self-contained index.html with all PDFs embedded as base64."""
import base64, os, re, sys
sys.stdout.reconfigure(encoding='utf-8')

PRELOADED = r"C:\Users\דן\pdf_translator\preloaded"
OUT       = r"C:\Users\דן\pdf_translator\index.html"

SEASON_ORDER = {'אביב': 1, 'קיץ': 2, 'סתיו': 3, 'חורף': 4}

def sort_key(name):
    m = re.search(r'(\S+)\s+(\d{4})\s+פרק\s+(\d+)', name)
    if m:
        season, year, part = m.group(1), int(m.group(2)), int(m.group(3))
        return (-year, SEASON_ORDER.get(season, 99), part)
    return (9999, 99, 99)

pdfs = sorted([f for f in os.listdir(PRELOADED) if f.endswith('.pdf')], key=sort_key)

# Encode each PDF as base64 data URI
pdf_data = {}
for name in pdfs:
    with open(os.path.join(PRELOADED, name), 'rb') as f:
        b64 = base64.b64encode(f.read()).decode('ascii')
    pdf_data[name] = f"data:application/pdf;base64,{b64}"

# Build PDF list items HTML
items_html = ""
for i, name in enumerate(pdfs):
    sel = " sel" if i == 0 else ""
    items_html += f'''
        <div class="pdf-item{sel}" onclick="pickPdf(this)" data-name="{name}">
          <div class="rdot"></div>
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" style="flex-shrink:0">
            <rect x="2" y="1" width="9" height="12" rx="1.5" stroke="#6a8ca0" stroke-width="1.3"/>
            <path d="M5 1v3.5h4" stroke="#6a8ca0" stroke-width="1.1" stroke-linecap="round" stroke-linejoin="round"/>
            <line x1="4" y1="7" x2="10" y2="7" stroke="#6a8ca0" stroke-width="1" stroke-linecap="round"/>
            <line x1="4" y1="9.5" x2="8" y2="9.5" stroke="#6a8ca0" stroke-width="1" stroke-linecap="round"/>
          </svg>
          <span class="pdf-name">{name.replace(".pdf","")}</span>
        </div>'''

# Build JS object mapping name -> data URI
js_map = "const PDF_DATA = {\n"
for name in pdfs:
    escaped = name.replace('"', '\\"')
    js_map += f'  "{escaped}": "{pdf_data[name]}",\n'
js_map += "};"

first_pdf = pdfs[0] if pdfs else ""
first_uri = pdf_data.get(first_pdf, "")

html = f'''<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>מבחן פסיכומטרי — כמה מילים תדע?</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    :root {{
      --bg:      #e9f3fa;
      --surface: #ffffff;
      --border:  #b8d8ed;
      --accent:  #2a7dc9;
      --accent2: #1a5f9e;
      --text:    #1a2d3d;
      --muted:   #6a8ca0;
      --r:       10px;
      --line-h:  28px;
      --line-c:  #c5dff0;
      --margin-c:#e89090;
    }}
    html, body {{ height: 100%; overflow: hidden; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
      color: var(--text); font-size: 14px;
      background-color: var(--bg);
      background-image:
        repeating-linear-gradient(
          transparent 0px,
          transparent calc(var(--line-h) - 1px),
          var(--line-c) calc(var(--line-h) - 1px),
          var(--line-c) var(--line-h)
        ),
        linear-gradient(to left, var(--margin-c) 0px, var(--margin-c) 2px, transparent 2px);
    }}

    /* TOP BAR */
    .topbar {{
      position: fixed; top: 0; left: 0; right: 0; z-index: 100;
      height: 50px; background: var(--accent2);
      border-bottom: 1px solid #164e84;
      display: none; align-items: center; gap: 10px; padding: 0 16px;
    }}
    .topbar.on {{ display: flex; }}
    .tb-logo {{
      display: flex; align-items: center; gap: 7px;
      font-weight: 700; font-size: 13px; white-space: nowrap; color: #fff; flex-shrink: 0;
    }}
    .tb-sep {{ width: 1px; height: 20px; background: rgba(255,255,255,.2); flex-shrink: 0; }}
    .tb-file {{
      font-size: 11px; color: rgba(255,255,255,.55); overflow: hidden;
      text-overflow: ellipsis; white-space: nowrap; flex: 1; direction: rtl;
    }}
    .tb-btn {{
      display: inline-flex; align-items: center; gap: 5px;
      height: 30px; padding: 0 12px; border-radius: 7px;
      font-size: 12px; font-weight: 600; cursor: pointer; border: 1px solid;
      font-family: inherit; white-space: nowrap; transition: background .15s; flex-shrink: 0;
    }}
    .tb-back {{ background: rgba(255,255,255,.1); color: rgba(255,255,255,.8); border-color: rgba(255,255,255,.2); }}
    .tb-back:hover {{ background: rgba(255,255,255,.2); color: #fff; }}

    /* MAIN */
    .main {{ height: 100vh; display: flex; }}

    /* SETUP */
    .setup {{
      flex: 1; display: flex; align-items: center; justify-content: center; padding: 40px 20px;
    }}
    .card {{
      background: rgba(255,255,255,.90); backdrop-filter: blur(6px);
      border: 1px solid var(--border); border-radius: 16px;
      padding: 34px 36px 36px; width: 100%; max-width: 500px;
    }}
    .card-title {{
      font-size: 20px; font-weight: 800; letter-spacing: -.5px;
      color: var(--accent2); margin-bottom: 5px; line-height: 1.25;
      display: flex; align-items: center; gap: 9px;
    }}
    .card-sub {{ color: var(--muted); font-size: 12.5px; margin-bottom: 26px; line-height: 1.55; }}

    /* Word list cards */
    .wl-label {{
      font-size: 11px; font-weight: 700; letter-spacing: .6px;
      text-transform: uppercase; color: var(--muted); margin-bottom: 8px;
    }}
    .wl-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 20px; }}
    .wl-card {{
      position: relative; cursor: default;
      border: 2px solid var(--border); border-radius: 11px;
      padding: 14px 13px 13px; background: var(--surface);
      text-align: center; display: flex; flex-direction: column; align-items: center; gap: 5px;
    }}
    .wl-card.sel {{ border-color: var(--accent); background: #eef6fd; }}
    .wl-icon-wrap {{
      width: 38px; height: 38px; border-radius: 9px;
      display: flex; align-items: center; justify-content: center; background: #dbeafe;
    }}
    .wl-card.sel .wl-icon-wrap {{ background: #bfdbfe; }}
    .wl-name {{ font-size: 12px; font-weight: 700; color: var(--text); line-height: 1.3; }}
    .wl-desc {{ font-size: 10.5px; color: var(--muted); line-height: 1.35; }}
    .wl-badge {{
      margin-top: 2px; display: inline-block; font-size: 9.5px; font-weight: 700;
      background: #dbeafe; color: var(--accent2);
      padding: 1px 8px; border-radius: 99px; border: 1px solid #bfdbfe;
    }}

    .divider {{ height: 1px; background: var(--border); margin: 2px 0 18px; opacity: .6; }}

    /* Source list */
    .field-label {{
      font-size: 13px; font-weight: 700; color: var(--accent2);
      margin-bottom: 9px; border-bottom: 2px solid var(--accent2);
      display: inline-block; padding-bottom: 2px;
    }}
    .pdf-list {{
      display: flex; flex-direction: column; gap: 5px;
      max-height: 210px; overflow-y: auto; padding-left: 2px;
      scrollbar-width: thin; scrollbar-color: var(--border) transparent;
    }}
    .pdf-list::-webkit-scrollbar {{ width: 5px; }}
    .pdf-list::-webkit-scrollbar-track {{ background: transparent; }}
    .pdf-list::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 99px; }}
    .pdf-item {{
      display: flex; align-items: center; gap: 8px; padding: 10px 12px;
      border: 1px solid var(--border); border-radius: 9px;
      cursor: pointer; transition: border-color .15s; background: var(--surface);
    }}
    .pdf-item:hover {{ border-color: var(--accent); }}
    .pdf-item.sel {{ border-color: var(--accent); background: #eef6fd; }}
    .rdot {{
      width: 14px; height: 14px; border: 2px solid #bbb; border-radius: 50%;
      flex-shrink: 0; display: flex; align-items: center; justify-content: center;
      transition: border-color .15s;
    }}
    .rdot::after {{
      content:''; width:6px; height:6px; border-radius:50%;
      background: var(--accent); opacity:0; transition:opacity .15s;
    }}
    .pdf-item.sel .rdot {{ border-color: var(--accent); }}
    .pdf-item.sel .rdot::after {{ opacity: 1; }}
    .pdf-name {{ font-size: 12.5px; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}

    /* Open button */
    .proc-btn {{
      width: 100%; height: 42px; margin-top: 20px;
      background: var(--accent); color: #fff; border: none; border-radius: var(--r);
      font-size: 14px; font-weight: 700; cursor: pointer;
      transition: background .15s; font-family: inherit;
      display: flex; align-items: center; justify-content: center; gap: 8px;
    }}
    .proc-btn:hover {{ background: var(--accent2); }}

    /* VIEWER */
    .viewer {{ display: none; flex: 1; flex-direction: column; min-height: 0; margin-top: 50px; }}
    .viewer.on {{ display: flex; }}
    .frame {{ flex: 1; min-height: 0; border: none; display: block; width: 100%; background: #525659; }}
  </style>
</head>
<body>

<header class="topbar" id="topbar">
  <div class="tb-logo">
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
      <rect x="2" y="2" width="6" height="14" rx="1.5" fill="rgba(255,255,255,.35)"/>
      <rect x="10" y="2" width="6" height="14" rx="1.5" fill="rgba(255,255,255,.35)"/>
      <rect x="8" y="1" width="2" height="16" rx="1" fill="rgba(255,255,255,.6)"/>
    </svg>
    פסיכומטרי
  </div>
  <div class="tb-sep"></div>
  <div class="tb-file" id="tbFile"></div>
  <button class="tb-btn tb-back" onclick="goBack()">
    <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
      <path d="M8 2.5L4.5 6.5L8 10.5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
    חזרה
  </button>
</header>

<div class="main">
  <div class="setup" id="setup">
    <div class="card">

      <div class="card-title">
        <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
          <rect x="2" y="3" width="8" height="16" rx="2" fill="#bfdbfe"/>
          <rect x="12" y="3" width="8" height="16" rx="2" fill="#bfdbfe"/>
          <rect x="9.5" y="2" width="3" height="18" rx="1.5" fill="#93c5fd"/>
          <line x1="4" y1="7" x2="8" y2="7" stroke="#2a7dc9" stroke-width="1.2" stroke-linecap="round"/>
          <line x1="4" y1="10" x2="8" y2="10" stroke="#2a7dc9" stroke-width="1.2" stroke-linecap="round"/>
          <line x1="4" y1="13" x2="8" y2="13" stroke="#2a7dc9" stroke-width="1.2" stroke-linecap="round"/>
          <line x1="14" y1="7" x2="18" y2="7" stroke="#2a7dc9" stroke-width="1.2" stroke-linecap="round"/>
          <line x1="14" y1="10" x2="18" y2="10" stroke="#2a7dc9" stroke-width="1.2" stroke-linecap="round"/>
          <line x1="14" y1="13" x2="18" y2="13" stroke="#2a7dc9" stroke-width="1.2" stroke-linecap="round"/>
        </svg>
        בחר מבחן פסיכומטרי
      </div>
      <p class="card-sub">בחר מבחן מהרשימה וצפה בו ישירות בדפדפן</p>

      <div class="wl-label">רשימת המילים</div>
      <div class="wl-grid">
        <div class="wl-card sel">
          <div class="wl-icon-wrap">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              <circle cx="10" cy="10" r="7.5" stroke="#2a7dc9" stroke-width="1.6"/>
              <path d="M10 2.5C10 2.5 7.5 5.5 7.5 10s2.5 7.5 2.5 7.5" stroke="#2a7dc9" stroke-width="1.4" stroke-linecap="round"/>
              <path d="M10 2.5C10 2.5 12.5 5.5 12.5 10s-2.5 7.5-2.5 7.5" stroke="#2a7dc9" stroke-width="1.4" stroke-linecap="round"/>
              <line x1="2.5" y1="10" x2="17.5" y2="10" stroke="#2a7dc9" stroke-width="1.4"/>
            </svg>
          </div>
          <span class="wl-name">NGSL</span>
          <span class="wl-desc">רשימה בינלאומית שנוצרה על ידי חוקרים</span>
          <span class="wl-badge">2,807 מילים</span>
        </div>
        <div class="wl-card">
          <div class="wl-icon-wrap">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              <rect x="3.5" y="2" width="11" height="14.5" rx="2" stroke="#2a7dc9" stroke-width="1.6"/>
              <line x1="6" y1="6" x2="12" y2="6" stroke="#2a7dc9" stroke-width="1.4" stroke-linecap="round"/>
              <line x1="6" y1="9" x2="12" y2="9" stroke="#2a7dc9" stroke-width="1.4" stroke-linecap="round"/>
              <line x1="6" y1="12" x2="9" y2="12" stroke="#2a7dc9" stroke-width="1.4" stroke-linecap="round"/>
              <circle cx="15" cy="15" r="4" fill="#2a7dc9"/>
              <path d="M12.8 15l1.5 1.5 2.5-2.5" stroke="white" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </div>
          <span class="wl-name">מילון הפסיכומטרי של המדינה</span>
          <span class="wl-desc">רשימת מילים מהקורס של הפסיכומטרי של המדינה</span>
          <span style="font-size:9.5px;color:var(--muted);opacity:.8;">(לא מכיל מילים בסיסיות)</span>
          <span class="wl-badge">3,517 מילים</span>
        </div>
      </div>

      <div class="divider"></div>

      <div style="margin-bottom:14px;">
        <div class="field-label">מבחני הפסיכומטרי</div>
        <div class="pdf-list" id="pdfList">
{items_html}
        </div>
      </div>

      <button class="proc-btn" onclick="openPdf()">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <rect x="2" y="1" width="10" height="13" rx="1.5" stroke="white" stroke-width="1.6"/>
          <path d="M5 5h6M5 8h6M5 11h3" stroke="white" stroke-width="1.3" stroke-linecap="round"/>
        </svg>
        פתח מבחן
      </button>

    </div>
  </div>

  <div class="viewer" id="viewer">
    <iframe class="frame" id="frame" src=""></iframe>
  </div>
</div>

<script>
{js_map}

let selectedName = "{first_pdf}";

function pickPdf(el) {{
  document.querySelectorAll('.pdf-item').forEach(x => x.classList.remove('sel'));
  el.classList.add('sel');
  selectedName = el.dataset.name;
}}

function openPdf() {{
  if (!selectedName || !PDF_DATA[selectedName]) return;
  document.getElementById('tbFile').textContent = selectedName.replace('.pdf','');
  document.getElementById('frame').src = PDF_DATA[selectedName];
  document.getElementById('setup').style.display = 'none';
  document.getElementById('topbar').classList.add('on');
  document.getElementById('viewer').classList.add('on');
}}

function goBack() {{
  document.getElementById('viewer').classList.remove('on');
  document.getElementById('topbar').classList.remove('on');
  document.getElementById('setup').style.display = '';
  document.getElementById('frame').src = '';
}}
</script>
</body>
</html>'''

with open(OUT, 'w', encoding='utf-8') as f:
    f.write(html)

size_mb = os.path.getsize(OUT) / 1024 / 1024
print(f"Done! {OUT}")
print(f"File size: {size_mb:.1f} MB")
