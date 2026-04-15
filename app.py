cat > app.py << 'EOF'
import os
from flask import Flask, jsonify

app = Flask(__name__)
REQUIRED = ["SUPABASE_URL", "SUPABASE_KEY", "TELEGRAM_BOT_TOKEN"]
missing = [v for v in REQUIRED if not os.environ.get(v)]

if missing:
    @app.route('/health')
    def health(): return jsonify({"status": "starting", "missing": missing}), 200
else:
    from supabase import create_client, Client
    sb: Client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
    @app.route('/health')
    def health(): return jsonify({"status": "ok"}), 200

@app.route('/')
def home(): return "<h1>Deboo</h1>"
EOF