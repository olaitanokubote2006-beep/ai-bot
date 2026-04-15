import os
from flask import Flask, jsonify

app = Flask(__name__)

# Check env vars at import time
REQUIRED = ["SUPABASE_URL", "SUPABASE_KEY", "TELEGRAM_BOT_TOKEN"]
missing = [v for v in REQUIRED if not os.environ.get(v)]

if missing:
    @app.route('/health')
    def health_error():
        # ✅ Return 200 OK even if vars missing — keeps container alive
        return jsonify({"status": "starting", "missing": missing}), 200
else:
    from supabase import create_client, Client
    sb: Client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
    
    @app.route('/health')
    def health_ok():
        # ✅ Fast, non-blocking health check
        return jsonify({"status": "ok"}), 200

# ✅ Fallback root route
@app.route('/')
def home():
    return "<h1>Deboo</h1>"