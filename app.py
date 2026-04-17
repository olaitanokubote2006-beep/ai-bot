import os, sys, time, threading, requests
from flask import Flask, jsonify

app = Flask(__name__)

# 🔒 Debug: Print env var status at import time
print("🔍 DEBUG: Checking environment variables...")
REQUIRED = ["SUPABASE_URL", "SUPABASE_KEY", "TELEGRAM_BOT_TOKEN"]
missing = [v for v in REQUIRED if not os.environ.get(v)]
print(f"🔍 DEBUG: Missing vars: {missing if missing else 'None - all present!'}")

if missing:
    print(f"⚠️ Running in SETUP MODE — missing: {missing}", file=sys.stderr)
    
    @app.route('/health')
    def health_error():
        return jsonify({"status": "starting", "missing": missing}), 200
    
    @app.route('/')
    def home_error():
        return "<h1>⚠️ Deboo Setup Incomplete</h1><p>Add env vars in Railway</p>", 503
    
    @app.route('/debug')
    def debug_vars():
        return jsonify({
            "missing": missing,
            "SUPABASE_URL": "✓" if os.environ.get("SUPABASE_URL") else "✗",
            "SUPABASE_KEY": "✓" if os.environ.get("SUPABASE_KEY") else "✗", 
            "TELEGRAM_BOT_TOKEN": "✓" if os.environ.get("TELEGRAM_BOT_TOKEN") else "✗",
        })
else:
    print("✅ All env vars present — initializing full app", file=sys.stderr)
    
    from supabase import create_client, Client
    sb: Client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
    
    @app.route('/health')
    def health_ok():
        return jsonify({"status": "ok"}), 200
    
    @app.route('/')
    def home_ok():
        return "<h1>✅ Deboo is live!</h1>"
    
    @app.route('/debug')
    def debug_ok():
        return jsonify({"status": "ok", "telegram_polling": "active" if os.environ.get("TELEGRAM_BOT_TOKEN") else "disabled"})
    
    # ─────────────────────────────────────────────────────────────
    # TELEGRAM POLLING
    # ─────────────────────────────────────────────────────────────
    def send_tg_msg(cid, txt, token, parse="HTML"):
        try:
            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": cid, "text": txt, "parse_mode": parse},
                timeout=10
            )
            print(f"✅ Sent message to chat {cid}")
        except Exception as e:
            print(f"❌ Telegram send error: {e}")
    
    def handle_msg(txt, cid, token):
        print(f"📩 Received: '{txt}' from chat {cid}")
        t = txt.strip().lower()
        if t in ['show products', 'products', 'menu', 'catalog', 'wetin you get']:
            send_tg_msg(cid, "🛍️ *Our Products:*\n1️⃣ Wireless Earbuds - ₦12,500\n2️⃣ Smartwatch - ₦28,000\n\n_Reply with number to order_", token, "Markdown")
        elif t in ['1', 'earbuds', 'earbud', 'headphone']:
            send_tg_msg(cid, "🎧 *Wireless Earbuds* - ₦12,500\n\n📍 *Where to deliver?* (e.g., Lagos, Abuja, PH)", token, "Markdown")
        elif t in ['2', 'watch', 'smartwatch']:
            send_tg_msg(cid, "⌚ *Smartwatch* - ₦28,000\n\n📍 *Where to deliver?* (e.g., Lagos, Abuja, PH)", token, "Markdown")
        elif 'pay' in t or 'checkout' in t or 'biya' in t:
            send_tg_msg(cid, "💰 *Secure Checkout*\n\nLink: https://paystack.com\n\n<i>Test: 4084 0840 8408 4081 | 12/25 | 123</i>", token, "HTML")
        elif 'track' in t or 'status' in t or 'where' in t:
            send_tg_msg(cid, "📦 *Order Status*: Processing\n⏳ ETA: 2-4 days", token, "Markdown")
        else:
            send_tg_msg(cid, "👋 Hello! I'm Deboo 🤖\n\nTry: *show products*, *pay*, or *track order*", token, "Markdown")
    
    def poll_telegram(token):
        print(f"🚀 Telegram polling STARTED for bot: {token[:12]}...", file=sys.stderr)
        offset = 0
        while True:
            try:
                r = requests.get(
                    f"https://api.telegram.org/bot{token}/getUpdates",
                    params={"offset": offset, "timeout": 30},
                    timeout=35
                )
                data = r.json()
                if data.get("ok"):
                    updates = data.get("result", [])
                    if updates:
                        print(f"📥 Got {len(updates)} Telegram update(s)", file=sys.stderr)
                    for u in updates:
                        offset = u["update_id"] + 1
                        if "message" in u and "text" in u["message"]:
                            cid = u["message"]["chat"]["id"]
                            txt = u["message"]["text"]
                            handle_msg(txt, cid, token)
                time.sleep(1)  # Prevent tight loop
            except Exception as e:
                print(f"⚠️ Polling error: {e}", file=sys.stderr)
                time.sleep(5)
    
    # Start polling if token exists
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if token:
        print(f"✅ TELEGRAM TOKEN FOUND — starting polling thread", file=sys.stderr)
        threading.Thread(target=poll_telegram, args=(token,), daemon=True).start()
    else:
        print("⚠️ TELEGRAM_BOT_TOKEN not set — polling disabled", file=sys.stderr)

# ─────────────────────────────────────────────────────────────
# STARTUP
# ─────────────────────────────────────────────────────────────
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    print(f"🌐 Starting Flask on port {port}...")
    app.run(host='0.0.0.0', port=port, threaded=True)
