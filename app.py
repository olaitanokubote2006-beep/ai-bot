cat > app.py << 'EOF'
import os, sys, time, threading, requests
from flask import Flask, jsonify

app = Flask(__name__)

# 🔒 Check env vars at import time
REQUIRED = ["SUPABASE_URL", "SUPABASE_KEY", "TELEGRAM_BOT_TOKEN"]
missing = [v for v in REQUIRED if not os.environ.get(v)]

if missing:
    # 🚨 Missing vars — lightweight routes only
    @app.route('/health')
    def health_error():
        return jsonify({"status": "starting", "missing": missing}), 200
    @app.route('/')
    def home_error():
        return "<h1>⚠️ Deboo Setup Incomplete</h1>", 503
else:
    # ✅ All vars present — full app + Telegram polling
    from supabase import create_client, Client
    sb: Client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
    
    # ─────────────────────────────────────────────────────────────
    # WEB ROUTES
    # ─────────────────────────────────────────────────────────────
    @app.route('/health')
    def health_ok():
        return jsonify({"status": "ok"}), 200
    @app.route('/')
    def home_ok():
        return "<h1>✅ Deboo is live!</h1>"
    
    # ─────────────────────────────────────────────────────────────
    # TELEGRAM POLLING (24/7 Message Handler)
    # ─────────────────────────────────────────────────────────────
    def send_tg_msg(cid, txt, token, parse="HTML"):
        """Send Telegram message"""
        try:
            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": cid, "text": txt, "parse_mode": parse},
                timeout=10
            )
        except Exception as e:
            print(f"Telegram send error: {e}")
    
    def handle_msg(txt, cid, token):
        """Simple command router"""
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
            send_tg_msg(cid, "📦 *Order Status*: Processing\n⏳ ETA: 2-4 days\n\nWe'll ping you when it ships!", token, "Markdown")
        else:
            send_tg_msg(cid, "👋 Hello! I'm Deboo 🤖\n\nTry: *show products*, *pay*, or *track order*", token, "Markdown")
    
    def poll_telegram(token):
        """Long-polling loop"""
        print(f"🚀 Telegram polling started for bot: {token[:12]}...")
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
                    for u in data.get("result", []):
                        offset = u["update_id"] + 1
                        if "message" in u and "text" in u["message"]:
                            cid = u["message"]["chat"]["id"]
                            txt = u["message"]["text"]
                            handle_msg(txt, cid, token)
            except Exception as e:
                print(f"⚠️ Poll error: {e}")
                time.sleep(5)
    
    # Auto-start polling if token exists (inside else block ✅)
    if os.environ.get("TELEGRAM_BOT_TOKEN"):
        token = os.environ["TELEGRAM_BOT_TOKEN"]
        threading.Thread(target=poll_telegram, args=(token,), daemon=True).start()
        print("✅ Telegram bot listening for messages...")

# ─────────────────────────────────────────────────────────────
# STARTUP (Gunicorn ignores this, but local dev uses it)
# ─────────────────────────────────────────────────────────────
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    print(f"🌐 Starting Flask on port {port}...")
    app.run(host='0.0.0.0', port=port, threaded=True)
EOF