from flask import Flask, jsonify
import os, requests, threading, time

app = Flask(__name__)

# ✅ ROUTES FIRST - always registered
@app.route('/test')
def t(): return jsonify({"ok": True, "version": "minimal"}), 200

@app.route('/health')
def h(): return jsonify({"status": "ok"}), 200

@app.route('/')
def home(): return "<h1>Deboo</h1>"

# ✅ APP LOGIC (runs after routes)
if all([os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"), os.environ.get("TELEGRAM_BOT_TOKEN")]):
    try:
        from supabase import create_client
        sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
        print("✅ Supabase OK", flush=True)
    except: pass
    
    def poll():
        token = os.environ["TELEGRAM_BOT_TOKEN"]
        off = 0
        while True:
            try:
                r = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", params={"offset": off, "timeout": 30}, timeout=35)
                d = r.json()
                if d.get("ok"):
                    for u in d.get("result", []):
                        off = u["update_id"] + 1
                        if "message" in u and "text" in u["message"]:
                            cid = u["message"]["chat"]["id"]
                            txt = u["message"]["text"]
                            requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": cid, "text": f"✅ {txt}"}, timeout=5)
                time.sleep(1)
            except: time.sleep(5)
    
    threading.Thread(target=poll, daemon=True).start()
    print("🚀 Polling active", flush=True)
