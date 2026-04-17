import os, sys, time, threading, requests
from flask import Flask, jsonify

app = Flask(__name__)

print("🟢 APP STARTING...", flush=True)

REQUIRED = ["SUPABASE_URL", "SUPABASE_KEY", "TELEGRAM_BOT_TOKEN"]
missing = [v for v in REQUIRED if not os.environ.get(v)]

if missing:
    print(f"⚠️ Missing vars: {missing}", flush=True)
    @app.route('/health')
    def health(): return jsonify({"status": "missing", "vars": missing}), 200
else:
    print("✅ All vars present", flush=True)
    try:
        from supabase import create_client
        sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
        print("✅ Supabase connected", flush=True)
    except Exception as e:
        print(f"🔴 Supabase error: {e}", flush=True)

    @app.route('/health')
    def health(): return jsonify({"status": "ok"}), 200

    # 🧪 MANUAL TEST: See if Telegram is actually sending updates to this token
    @app.route('/test-poll')
    def test_poll():
        token = os.environ["TELEGRAM_BOT_TOKEN"]
        try:
            r = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=10)
            return r.json()
        except Exception as e:
            return {"error": str(e)}

    # 🔄 ACTUAL POLLER (with explicit logging)
    def run_poller():
        token = os.environ["TELEGRAM_BOT_TOKEN"]
        print(f"🚀 Poller starting for {token[:10]}...", flush=True)
        offset = 0
        while True:
            try:
                url = f"https://api.telegram.org/bot{token}/getUpdates"
                r = requests.get(url, params={"offset": offset, "timeout": 30}, timeout=35)
                data = r.json()
                
                if data.get("ok"):
                    updates = data.get("result", [])
                    if updates:
                        print(f"📨 Got {len(updates)} update(s)", flush=True)
                    for u in updates:
                        offset = u["update_id"] + 1
                        if "message" in u and "text" in u["message"]:
                            cid = u["message"]["chat"]["id"]
                            txt = u["message"]["text"]
                            print(f"💬 Received: '{txt}' from chat {cid}", flush=True)
                            
                            # Simple reply
                            reply = f"✅ Deboo received: {txt}"
                            requests.post(
                                f"https://api.telegram.org/bot{token}/sendMessage",
                                json={"chat_id": cid, "text": reply},
                                timeout=5
                            )
                time.sleep(1)  # Prevent tight loop
            except Exception as e:
                print(f"❌ Poll error: {e}", flush=True)
                time.sleep(5)

    # Launch poller thread
    if os.environ.get("TELEGRAM_BOT_TOKEN"):
        t = threading.Thread(target=run_poller, daemon=True)
        t.start()
        print("✅ Polling thread launched", flush=True)
    else:
        print("⚠️ No Telegram token found", flush=True)
