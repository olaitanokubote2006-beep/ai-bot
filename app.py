import os, sys
from flask import Flask, jsonify

app = Flask(__name__)

# 🔒 STEP 1: Check env vars BEFORE any code that uses them
REQUIRED = ["SUPABASE_URL", "SUPABASE_KEY", "TELEGRAM_BOT_TOKEN"]
missing = [v for v in REQUIRED if not os.environ.get(v)]

if missing:
    # 🚨 Missing vars — show error page, don't crash
    print(f"❌ Missing env vars: {missing}", file=sys.stderr)
    
    @app.route('/')
    def error_home():
        return f"<h1>⚠️ Deboo Setup Incomplete</h1><p>Missing: {missing}</p><p>Fix: Add in Railway → Variables tab</p>", 503
    
    @app.route('/health')
    def health_error():
        return jsonify({"status": "error", "missing": missing}), 503
    
    @app.route('/debug-vars')
    def debug_error():
        return jsonify({v: "✗ MISSING" for v in REQUIRED})

else:
    # ✅ All vars present — now import and run normal code
    from supabase import create_client
    import requests, datetime, time, threading
    from flask import request
    from dotenv import load_dotenv
    load_dotenv()
    
    # Initialize with YOUR Supabase credentials
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
    PAY_KEY = os.environ.get("PAYSTACK_SECRET_KEY", "")
    BASE_URL = os.environ.get("BASE_URL", "http://localhost:5000")
    active_bots = {}
    
    # ─────────────────────────────────────────────────────────────
    # [ADD YOUR EXISTING CODE HERE LATER — ONE FUNCTION AT A TIME]
    # ─────────────────────────────────────────────────────────────
    
    # Simple test route to verify it works
    @app.route('/')
    def home():
        return "<h1>✅ Deboo is live!</h1><a href='/health'>Health Check</a>"
    
    @app.route('/health')
    def health():
        return jsonify({"status": "ok", "active_bots": len(active_bots)})
    
    @app.route('/debug-vars')
    def debug_vars():
        return jsonify({
            "PORT": os.environ.get("PORT"),
            "SUPABASE_URL": "✓",
            "SUPABASE_KEY": "✓", 
            "TELEGRAM_BOT_TOKEN": "✓",
        })

# ─────────────────────────────────────────────────────────────
# STARTUP
# ─────────────────────────────────────────────────────────────
if __name__ == '__main__':
    if missing:
        print(f"⚠️ Setup error: {missing}")
    else:
        print("✅ Env vars loaded, Deboo starting...")
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)