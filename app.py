import os, sys, time, threading
# 🔥 Force immediate output so Railway shows logs
print("🟢 APP STARTING - Flushing logs...", flush=True)

from flask import Flask, jsonify
app = Flask(__name__)

print("🟢 Checking env vars...", flush=True)
REQUIRED = ["SUPABASE_URL", "SUPABASE_KEY", "TELEGRAM_BOT_TOKEN"]
missing = [v for v in REQUIRED if not os.environ.get(v)]
print(f"🟢 Missing: {missing if missing else 'NONE - All present!'}", flush=True)

    @app.route('/status')
    def check_status():
        import requests as rq
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "MISSING")
        try:
            res = rq.get(f"https://api.telegram.org/bot{token}/getMe", timeout=5)
            bot_info = res.json().get("result", {})
            return {
                "env_supabase": "✓" if os.environ.get("SUPABASE_URL") else "✗",
                "env_telegram": "✓" if token != "MISSING" else "✗",
                "bot_username": bot_info.get("username"),
                "webhook_info": "Check via @BotFather or /deleteWebhook",
                "status": "active"
            }
        except Exception as e:
            return {"error": str(e)}
else:
    print("🟢 Env vars found. Importing supabase...", flush=True)
    try:
        from supabase import create_client, Client
        sb: Client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
        print("🟢 Supabase connected successfully!", flush=True)
    except Exception as e:
        print(f"🔴 Supabase init failed: {e}", flush=True)
    
    @app.route('/health')
    def h(): return jsonify({"status":"ok"}), 200
    @app.route('/')
    def home(): return "<h1>✅ Deboo Live</h1>"
    
    # Minimal placeholder poller (won't block, just proves thread starts)
    if os.environ.get("TELEGRAM_BOT_TOKEN"):
        def poll_placeholder():
            print("🟢 Telegram thread started (placeholder)", flush=True)
            while True: time.sleep(30)
        threading.Thread(target=poll_placeholder, daemon=True).start()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
