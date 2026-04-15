import os, sys
from flask import Flask, jsonify

app = Flask(__name__)

# 🔒 Check env vars at import time (safe for gunicorn)
REQUIRED = ["SUPABASE_URL", "SUPABASE_KEY", "TELEGRAM_BOT_TOKEN"]
missing = [v for v in REQUIRED if not os.environ.get(v)]

if missing:
    print(f"⚠️ Missing env vars: {missing}", file=sys.stderr)
    
    @app.route('/')
    def home():
        return f"<h1>⚠️ Setup Incomplete</h1><p>Missing: {missing}</p>", 503
    
    @app.route('/health')
    def health():
        return jsonify({"status": "error", "missing": missing}), 503
else:
    # ✅ All vars present — import and init Supabase
    from supabase import create_client, Client
    sb: Client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
    PAY_KEY = os.environ.get("PAYSTACK_SECRET_KEY", "")
    BASE_URL = os.environ.get("BASE_URL", "http://localhost:5000")
    
    @app.route('/')
    def home():
        return "<h1>✅ Deboo is live!</h1>"
    
    @app.route('/health')
    def health():
        # ✅ Fast, lightweight health check for Railway
        return jsonify({"status": "ok", "timestamp": os.popen('date -u +%Y-%m-%dT%H:%M:%SZ').read().strip()})

# ⚠️ NO if __name__ == '__main__' block needed — gunicorn handles startup