from flask import Flask, jsonify
import os, requests, threading, time

app = Flask(__name__)

# ✅ ROUTES (registered first)
@app.route('/test')
def t(): return jsonify({"ok": True, "version": "catalog-v1"}), 200
@app.route('/health')
def h(): return jsonify({"status": "ok"}), 200
@app.route('/')
def home(): return "<h1>✅ Deboo Live</h1>"

# ✅ APP LOGIC
REQUIRED = ["SUPABASE_URL", "SUPABASE_KEY", "TELEGRAM_BOT_TOKEN"]
if all(os.environ.get(v) for v in REQUIRED):
    try:
        from supabase import create_client
        sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
        print("✅ Supabase connected", flush=True)
    except Exception as e:
        print(f"🔴 Supabase error: {e}", flush=True)
        sb = None

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
                            txt = u["message"]["text"].strip().lower()
                            print(f"💬 '{txt}' from {cid}", flush=True)

                            # 🛍️ SMART PRODUCT CATALOG
                            if txt in ['show products', 'products', 'menu', 'catalog', 'wetin you get']:
                                if sb:
                                    try:
                                        res = sb.table("products").select("*").execute()
                                        items = res.data
                                        if items:
                                            msg = "🛍️ *Available Products:*\n\n"
                                            for i, p in enumerate(items, 1):
                                                price = f"₦{p['price']:,.0f}" if p.get('price') else "₦0"
                                                msg += f"{i}️⃣ *{p['name']}* - {price}\n"
                                                if p.get('description'): msg += f"   _{p['description']}_\n"
                                                msg += "\n"
                                            msg += "_Reply with a number to order!_"
                                        else:
                                            msg = "📦 No products yet. Add via Supabase!"
                                    except Exception as e:
                                        msg = f"⚠️ DB Error: {str(e)[:50]}"
                                else:
                                    msg = "🔴 Supabase not connected"
                                requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": cid, "text": msg, "parse_mode": "Markdown"}, timeout=5)
                            else:
                                requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": cid, "text": f"✅ Got: {txt}"}, timeout=5)
                time.sleep(1)
            except Exception as e:
                print(f"❌ Poll error: {e}", flush=True)
                time.sleep(5)

    threading.Thread(target=poll, daemon=True).start()
    print("🚀 Polling active", flush=True)
