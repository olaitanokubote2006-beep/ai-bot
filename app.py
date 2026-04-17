import os, sys, time, threading, requests
from flask import Flask, jsonify

app = Flask(__name__)
print("🟢 DEPLOY LOADED", flush=True)

@app.route('/test')
def test_env():
    return jsonify({
        "SUPABASE_URL": "✓" if os.environ.get("SUPABASE_URL") else "✗",
        "TELEGRAM_BOT_TOKEN": "✓" if os.environ.get("TELEGRAM_BOT_TOKEN") else "✗"
    }), 200

@app.route('/health')
def health(): return jsonify({"status":"ok"}), 200

@app.route('/')
def home(): return "<h1>✅ Deboo Running</h1>"

REQUIRED = ["SUPABASE_URL", "SUPABASE_KEY", "TELEGRAM_BOT_TOKEN"]
missing = [v for v in REQUIRED if not os.environ.get(v)]

if not missing:
    try:
        from supabase import create_client
        sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
        print("✅ Supabase connected", flush=True)
    except Exception as e:
        print(f"🔴 Supabase: {e}", flush=True)

    def poller():
        token = os.environ["TELEGRAM_BOT_TOKEN"]
        print("🚀 Poller started", flush=True)
        offset = 0
        while True:
            try:
                r = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", 
                                params={"offset": offset, "timeout": 30}, timeout=35)
                data = r.json()
                if data.get("ok"):
                    for u in data.get("result", []):
                        offset = u["update_id"] + 1
                        if "message" in u and "text" in u["message"]:
                            cid = u["message"]["chat"]["id"]
                            txt = u["message"]["text"]
                            print(f"💬 '{txt}' from {cid}", flush=True)
                            requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                                         json={"chat_id": cid, "text": f"✅ Got: {txt}"}, timeout=5)
                time.sleep(1)
            except: time.sleep(5)
    
    threading.Thread(target=poller, daemon=True).start()
