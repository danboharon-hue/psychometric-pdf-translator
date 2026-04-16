from flask_cloudflared import run_with_cloudflared
import sys
sys.path.insert(0, r"C:\Users\דן\pdf_translator")
from app import app

run_with_cloudflared(app)
app.run(port=5055, debug=False)
