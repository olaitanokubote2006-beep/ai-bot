import os, sys
from flask import Flask, jsonify

app = Flask(__name__)

# 🔒 CRITICAL: Check env vars BEFORE any code that uses them
REQUIRED = ["SUPABASE_URL", "SUPABASE_KEY", "TELEGRAM_BOT_TOKEN"]
missing = [v for v in REQUIRED if not os.environ.get(v)]

if missing:
    print(f"❌ Missing env vars: {missing}", file=sys.stderr)
    @app.route('/')
    def error_home():
        return f"<h1>⚠️ Deboo Setup Incomplete</h1><p>Missing: {missing}</p><p>Fix: Add in Railway → Variables tab</p>", 503
    @app.route('/health')
    def health_error():
        return jsonify({"status": "error", "missing": missing}), 503
else:
    from supabase import create_client
    import requests, datetime, time, threading
    from flask import request
    from dotenv import load_dotenv
    load_dotenv()
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
    PAY_KEY = os.environ.get("PAYSTACK_SECRET_KEY", "")
    BASE_URL = os.environ.get("BASE_URL", "http://localhost:5000")
    active_bots = {}
    @app.route('/')
    def home(): return "<h1>✅ Deboo is live!</h1>"
    @app.route('/health')
    def health(): return jsonify({"status": "ok", "active_bots": len(active_bots)})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
