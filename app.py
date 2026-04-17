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
# ─────────────────────────────────────────────────────────────
# TELEGRAM POLLING (Add this inside the `else:` block)
# ─────────────────────────────────────────────────────────────
import threading, time, requests

def handle_telegram_update(update, bot_token):
    """Process a single Telegram message update"""
    if 'message' not in update or 'text' not in update['message']:
        return
    
    chat_id = update['message']['chat']['id']
    user_id = update['message']['from']['id']
    text = update['message']['text'].strip().lower()
    
    # Simple command handler (expand this later)
    if text in ['show products', 'products', 'menu', 'catalog']:
        reply = "🛍️ *Our Products:*\n1️⃣ Wireless Earbuds - ₦12,500\n2️⃣ Smartwatch - ₦28,000\n\nReply with the number to order!"
        send_telegram_message(chat_id, reply, bot_token, parse_mode="Markdown")
    elif text in ['1', 'earbuds', 'earbud']:
        reply = "🎧 You selected *Wireless Earbuds* (₦12,500)\n\n📍 Where should we deliver? (e.g., Lagos, Abuja, PH)"
        send_telegram_message(chat_id, reply, bot_token, parse_mode="Markdown")
    elif text in ['pay', 'checkout', 'payment']:
        reply = "💰 Payment link: https://paystack.com\n\n<i>Test card: 4084 0840 8408 4081 | 12/25 | 123</i>"
        send_telegram_message(chat_id, reply, bot_token, parse_mode="HTML")
    else:
        reply = "👋 Hello! I'm Deboo 🤖\n\nTry: *show products*, *pay*, or *track order*"
        send_telegram_message(chat_id, reply, bot_token, parse_mode="Markdown")

def send_telegram_message(chat_id, text, bot_token, parse_mode="HTML"):
    """Send a message via Telegram Bot API"""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        requests.post(url, json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode
        }, timeout=10)
    except Exception as e:
        print(f"Telegram send error: {e}")

def start_telegram_polling(bot_token):
    """Long-polling loop for Telegram updates"""
    print(f"🚀 Starting Telegram polling for bot: {bot_token[:10]}...")
    offset = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
            resp = requests.get(url, params={"offset": offset, "timeout": 30}, timeout=35)
            data = resp.json()
            
            if data.get("ok"):
                for update in data.get("result", []):
                    offset = update["update_id"] + 1
                    handle_telegram_update(update, bot_token)
        except Exception as e:
            print(f"⚠️ Polling error: {e}")
            time.sleep(5)

# Auto-start polling if Telegram token is present
if os.environ.get("TELEGRAM_BOT_TOKEN"):
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    # Run polling in background thread so it doesn't block Flask
    threading.Thread(target=start_telegram_polling, args=(token,), daemon=True).start()
    print("✅ Telegram polling started in background")
@app.route('/')
def home(): return "<h1>Deboo</h1>"
EOF

# ─────────────────────────────────────────────────────────────
# STARTUP (Gunicorn ignores this, but local dev uses it)
# ─────────────────────────────────────────────────────────────
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    print(f"🌐 Starting Flask on port {port}...")
    app.run(host='0.0.0.0', port=port, threaded=True)
