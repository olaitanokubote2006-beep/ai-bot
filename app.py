import os, sys, time, threading
# 🔥 Force immediate output so Railway shows logs
print("🟢 APP STARTING - Flushing logs...", flush=True)

from flask import Flask, jsonify
app = Flask(__name__)

print("🟢 Checking env vars...", flush=True)
REQUIRED = ["SUPABASE_URL", "SUPABASE_KEY", "TELEGRAM_BOT_TOKEN"]
missing = [v for v in REQUIRED if not os.environ.get(v)]
print(f"🟢 Missing: {missing if missing else 'NONE - All present!'}", flush=True)

if missing:
    @app.route('/health')
    def h(): return jsonify({"status":"error","missing":missing}), 200
    @app.route('/')
    def home(): return "<h1>⚠️ Add env vars in Railway</h1>", 503
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
