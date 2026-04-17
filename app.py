import os, sys, time, threading, requests
from flask import Flask, jsonify

app = Flask(__name__)

print("🟢 DEPLOY v3.2 LOADED", flush=True)

# ✅ ROUTES REGISTERED FIRST (always available)
@app.route('/test')
def test_env():
    return jsonify({
        "app_version": "v3.2",
        "SUPABASE_URL": "✓" if os.environ.get("SUPABASE_URL") else "✗",
        "TELEGRAM_BOT_TOKEN": "✓" if os.environ.get("TELEGRAM_BOT_TOKEN") else "✗"
    }), 200

@app.route('/health')
def health(): return jsonify({"status":"ok"}), 200

@app.route('/')
def home(): return "<h1>✅ Deboo v3.2 Running</h1>"

# ─────────────────────────────────────────────────────────────
# APP LOGIC (runs after routes are registered)
# ─────────────────────────────────────────────────────────────
REQUIRED = ["SUPABASE_URL", "SUPABASE_KEY", "TELEGRAM_BOT_TOKEN"]
missing = [v for v in REQUIRED if not os.environ.get(v)]

if missing:
    print(f"⚠️ Missing: {missing}", flush=True)
else:
    print("✅ All env vars found", flush=True)
    try:
        from supabase import create_client
        sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
        print("✅ Supabase connected", flush=True)
    except Exception as e:
        print(f"🔴 Supabase error: {e}", flush=True)

    # Telegram poller
    def run_poller():
        token = os.environ["TELEGRAM_BOT_TOKEN"]
        print(f"🚀 Poller starting...", flush=True)
        offset = 0
        while True:
            try:
                r = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", 
                                params={"offset": offset, "timeout": 30}, timeout=35)
                data = r.json()
                if data.get("ok"):
                    updates = data.get("result", [])
                    if updates: print(f"📨 {len(updates)} update(s)", flush=True)
                    for u in updates:
                        offset = u["update_id"] + 1
                        if "message" in u and "text" in u["message"]:
                            cid = u["message"]["chat"]["id"]
                            txt = u["message"]["text"]
                            print(f"💬 '{txt}' from {cid}", flush=True)
                            requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                                         json={"chat_id": cid, "text": f"✅ Got: {txt}"}, timeout=5)
                time.sleep(1)
            except Exception as e:
                print(f"❌ {e}", flush=True)
                time.sleep(5)

    threading.Thread(target=run_poller, daemon=True).start()
    print("✅ Polling thread active", flush=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
