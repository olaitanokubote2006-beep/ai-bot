from flask import Flask, jsonify
import os, requests, threading, time

app = Flask(__name__)

# ✅ ROUTES
@app.route('/test')
def t(): return jsonify({"ok": True, "version": "multilingual-v1"}), 200
@app.route('/health')
def h(): return jsonify({"status": "ok"}), 200
@app.route('/')
def home(): return "<h1>✅ Deboo Live (Multilingual)</h1>"

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

    # 🌍 MULTILINGUAL ENGINE (Rule-based, zero API cost)
    def detect_lang(text):
        t = text.lower().strip()
        keys = {
            'pidgin': ['wetin', 'abi', 'na', 'dey', 'how far', 'oya', 'guy', 'make i', 'no dey', 'abi you'],
            'yoruba': ['bawo', 'e se', 'daada', 'omo', 'sugbon', 'ko si', 'wa', 'ni', 'ti wa'],
            'igbo': ['kedu', 'daalu', 'nnoo', 'karia', 'ma', 'ga', 'na-eme', 'anyi', 'ka m'],
            'hausa': ['sannu', 'yaya', 'kwana', 'ina', 'ka', 'ki', 'ba', 'da', 'muna']
        }
        scores = {lang: sum(1 for k in kw if k in t) for lang, kw in keys.items()}
        best = max(scores, key=scores.get)
        return best if scores[best] > 0 else 'english'

    MSGS = {
        'greeting': {
            'english': "👋 Hello! I'm Deboo 🤖\n\nTry: *show products*, *pay*, or *track order*",
            'pidgin': "👋 How far my pesin! I be Deboo 🤖\n\nTry: *show products*, *pay*, or *track order*",
            'yoruba': "👋 Bawo! Oruko mi ni Deboo 🤖\n\nTry: *show products*, *pay*, or *track order*",
            'igbo': "👋 Kedụ! Abụ m Deboo 🤖\n\nTry: *show products*, *pay*, or *track order*",
            'hausa': "👋 Sannu! Ni ne Deboo 🤖\n\nTry: *show products*, *pay*, or *track order*"
        },
        'prod_head': {
            'english': "🛍️ *Available Products:*\n\n",
            'pidgin': "🛍️ *Wetin we dey sell:*\n\n",
            'yoruba': "🛍️ *Ohun ti a n ta ni:*\n\n",
            'igbo': "🛍️ *Ihe anyị na-ere:*\n\n",
            'hausa': "🛍️ *Abin da muke sayarwa:*\n\n"
        },
        'prod_foot': {
            'english': "_Reply with a number to order!_",
            'pidgin': "_Reply with number make you order!_",
            'yoruba': "_Fi nọmba ranṣẹ lati ra!_",
            'igbo': "_Za nọmba ka ị zụta!_",
            'hausa': "_Amsa da lamba don sayayya!_"
        },
        'no_prod': {
            'english': "📦 No products yet. Check back later!",
            'pidgin': "📦 No product dey for now. Abeg wait!",
            'yoruba': "📦 Ko si oja kan lọwọlọwọ.",
            'igbo': "📦 Ihe ọ bụla adịghị ugbu a.",
            'hausa': "📦 Babu abu a yanzu."
        }
    }

    def send(cid, txt, token, parse="Markdown"):
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": cid, "text": txt, "parse_mode": parse}, timeout=5)

    def poll():
        token = os.environ["TELEGRAM_BOT_TOKEN"]
        off = 0
        print("🌍 Multilingual poller started", flush=True)
        while True:
            try:
                r = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", params={"offset": off, "timeout": 30}, timeout=35)
                d = r.json()
                if d.get("ok"):
                    for u in d.get("result", []):
                        off = u["update_id"] + 1
                        if "message" in u and "text" in u["message"]:
                            cid = u["message"]["chat"]["id"]
                            txt = u["message"]["text"].strip()
                            lang = detect_lang(txt)
                            t_lower = txt.lower()

                            if t_lower in ['show products', 'products', 'menu', 'catalog', 'wetin you get', 'bawo ni', 'kedu ihe', 'menene']:
                                if sb:
                                    try:
                                        res = sb.table("products").select("*").execute()
                                        items = res.data
                                        if items:
                                            msg = MSGS['prod_head'][lang]
                                            for i, p in enumerate(items, 1):
                                                price = f"₦{p['price']:,.0f}" if p.get('price') else "₦0"
                                                msg += f"{i}️⃣ *{p['name']}* - {price}\n"
                                                if p.get('description'): msg += f"   _{p['description']}_\n"
                                                msg += "\n"
                                            msg += MSGS['prod_foot'][lang]
                                        else:
                                            msg = MSGS['no_prod'][lang]
                                    except Exception as e:
                                        msg = f"⚠️ DB Error: {str(e)[:50]}"
                                else:
                                    msg = "🔴 Database not connected"
                                send(cid, msg, token)
                            else:
                                send(cid, MSGS['greeting'][lang], token)
                time.sleep(1)
            except Exception as e:
                print(f"❌ Poll error: {e}", flush=True)
                time.sleep(5)

    threading.Thread(target=poll, daemon=True).start()
