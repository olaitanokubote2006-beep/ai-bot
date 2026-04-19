from flask import Flask, jsonify
import os, requests, threading, time

app = Flask(__name__)

# ✅ ROUTES (registered FIRST, always work)
@app.route('/health')
def health(): return jsonify({"status": "ok"}), 200
@app.route('/')
def home(): return "<h1>✅ Deboo Live</h1>"
@app.route('/test')
def test(): return jsonify({"ok": True}), 200

# ✅ APP LOGIC (runs after routes register)
REQUIRED = ["SUPABASE_URL", "SUPABASE_KEY", "TELEGRAM_BOT_TOKEN", "GROQ_API_KEY", "PAYSTACK_SECRET_KEY"]
if all(os.environ.get(v) for v in REQUIRED):
    try:
        from supabase import create_client
        sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
        print("✅ Supabase connected", flush=True)
    except Exception as e:
        print(f"🔴 Supabase init failed: {e}", flush=True)
        sb = None

    # 🤖 Simple AI Client (Groq via OpenAI-compatible SDK)
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.environ["GROQ_API_KEY"], base_url="https://api.groq.com/openai/v1")
        print("✅ Groq client ready", flush=True)
    except Exception as e:
        print(f"🔴 Groq init failed: {e}", flush=True)
        client = None

    user_histories = {}

    # 🛠️ Simple Tools
    TOOLS = [{
        "type": "function", "function": {
            "name": "list_products",
            "description": "List available products",
            "parameters": {"type": "object", "properties": {}}
        }
    }]

    SYSTEM_PROMPT = """You are Deboo, a friendly Nigerian shopping assistant.
- Reply in user's language (English, Pidgin, Yoruba, Igbo, Hausa)
- Be concise. Never apologize. Never ask for Telegram ID.
- When asked for products: call list_products()
- For checkout: ask for email + address, then say "🔗 Pay: [link]" (we'll handle Paystack separately for now)"""

    def send(cid, txt, token):
        try: requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": cid, "text": txt, "parse_mode": "HTML"}, timeout=5)
        except: pass

    def run_agent(cid, txt, token):
        if cid not in user_histories: user_histories[cid] = [{"role": "system", "content": SYSTEM_PROMPT}]
        user_histories[cid].append({"role": "user", "content": txt})
        if len(user_histories[cid]) > 10: user_histories[cid] = [user_histories[cid][0]] + user_histories[cid][-8:]

        if not client:
            return "⚠️ AI service initializing. Try again in 10s."

        try:
            res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=user_histories[cid], tools=TOOLS, temperature=0.3)
            msg = res.choices[0].message
            if msg.tool_calls and msg.tool_calls[0].function.name == "list_products" and sb:
                try:
                    data = sb.table("products").select("*").execute().data
                    items = "\n".join([f"{i+1}. {p['name']} - ₦{p['price']:,.0f}" for i,p in enumerate(data)]) if data else "No products yet"
                    return f"🛍️ Available:\n{items}\n\nReply with number to order"
                except: return "⚠️ Product fetch failed"
            user_histories[cid].append(msg)
            return msg.content or "✅ Got it"
        except Exception as e:
            print(f"🔴 Agent error: {e}", flush=True)
            return "⚠️ Busy. Retry shortly."

    def poll():
        token = os.environ["TELEGRAM_BOT_TOKEN"]
        off = 0
        print("🤖 Poller started", flush=True)
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
                            send(cid, run_agent(cid, txt, token), token)
                time.sleep(1)
            except: time.sleep(5)

    threading.Thread(target=poll, daemon=True).start()
