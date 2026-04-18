from flask import Flask, jsonify, request
import os, requests, threading, time, json, hmac, hashlib
from openai import OpenAI

app = Flask(__name__)

# ✅ ROUTES (registered first)
@app.route('/test')
def t(): return jsonify({"ok": True, "version": "paystack-v1"}), 200
@app.route('/health')
def h(): return jsonify({"status": "ok"}), 200
@app.route('/')
def home(): return "<h1>✅ Deboo AI + Paystack Live</h1>"

# 💳 PAYSTACK WEBHOOK (must be top-level)
@app.route('/webhook/paystack', methods=['POST'])
def paystack_webhook():
    secret = os.environ.get("PAYSTACK_SECRET_KEY", "")
    signature = request.headers.get("x-paystack-signature", "")
    payload = request.get_data()
    
    # Verify signature
    expected = hmac.new(secret.encode(), payload, hashlib.sha512).hexdigest()
    if signature != expected:
        return jsonify({"error": "invalid signature"}), 401
    
    event = json.loads(payload)
    if event.get("event") == "charge.success":
        data = event.get("data", {})
        ref = data.get("reference", "")
        meta = data.get("metadata", {})
        telegram_id = meta.get("telegram_id")
        order_id = meta.get("order_id")
        
        if order_id and sb:
            try:
                sb.table("orders").update({"status": "paid", "payment_ref": ref}).eq("id", order_id).execute()
                if telegram_id:
                    lang = user_histories.get(telegram_id, [{}])[0].get("lang", "english")
                    receipt = {
                        "english": f"✅ *Payment Successful!*\nRef: `{ref}`\nStatus: PAID\nWe'll prepare your order now. 📦",
                        "pidgin": f"✅ *Payment don land!*\nRef: `{ref}`\nStatus: PAID\nWe go prepare your order sharp-sharp. 📦",
                        "yoruba": f"✅ *Isanwo ti ṣe!*\nRef: `{ref}`\nStatus: PAID\nA n ṣetọju aṣẹ rẹ bayi. 📦",
                        "igbo": f"✅ *Ịkwụ ụgwọ gasịrị!*\nRef: `{ref}`\nStatus: PAID\nAnyị na-akwadebe iwu gị ugbu a. 📦",
                        "hausa": f"✅ *An yi biyan kuɗi!*\nRef: `{ref}`\nStatus: PAID\nMuna shirya odar ku yanzu. 📦"
                    }
                    send(telegram_id, receipt.get(lang, receipt["english"]), os.environ["TELEGRAM_BOT_TOKEN"])
            except Exception as e:
                print(f"🔴 Webhook DB error: {e}", flush=True)
    return jsonify({"ok": True}), 200

# ✅ APP LOGIC
REQUIRED = ["SUPABASE_URL", "SUPABASE_KEY", "TELEGRAM_BOT_TOKEN", "GROQ_API_KEY", "PAYSTACK_SECRET_KEY"]
if all(os.environ.get(v) for v in REQUIRED):
    try:
        from supabase import create_client
        sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
        print("✅ Supabase connected", flush=True)
    except Exception as e:
        print(f"🔴 Supabase error: {e}", flush=True)
        sb = None

    client = OpenAI(api_key=os.environ["GROQ_API_KEY"], base_url="https://api.groq.com/openai/v1")
    user_histories = {}
    BASE_URL = os.environ.get("BASE_URL", "https://your-app.up.railway.app")

    # 🛠️ TOOLS
    TOOLS = [
        {"type":"function","function":{"name":"list_products","description":"List all available products","parameters":{"type":"object","properties":{}}}},
        {"type":"function","function":{"name":"create_payment","description":"Generate Paystack link for confirmed order. Requires product_name, price, customer_email, telegram_id","parameters":{"type":"object","properties":{"product_name":{"type":"string"},"price":{"type":"number"},"customer_email":{"type":"string"},"telegram_id":{"type":"string"}},"required":["product_name","price","customer_email","telegram_id"]}}},
        {"type":"function","function":{"name":"save_order","description":"Save pending order before payment","parameters":{"type":"object","properties":{"product_name":{"type":"string"},"price":{"type":"number"},"address":{"type":"string"},"customer_email":{"type":"string"},"telegram_id":{"type":"string"}},"required":["product_name","price","address","customer_email","telegram_id"]}}}
    ]

    SYSTEM_PROMPT = """You are Deboo, a friendly AI shopping assistant for Nigeria. 
- Always reply in the user's language (English, Pidgin, Yoruba, Igbo, or Hausa)
- Be concise, culturally aware, and helpful
- Use markdown formatting
- When user asks for products: call list_products()
- When user confirms order with email & address: 
  1. Call save_order() first to store pending order
  2. Then call create_payment() with the order details
  3. Send the payment link to the user
- If email is missing, politely ask for it before proceeding
- Never make up prices or products. Only use tool responses."""

    def send(cid, txt, token, parse="Markdown"):
        try: requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": cid, "text": txt, "parse_mode": parse}, timeout=5)
        except: pass

    def run_agent(cid, txt, token):
        if cid not in user_histories:
            user_histories[cid] = [{"role": "system", "content": SYSTEM_PROMPT, "lang": "english"}]
        
        # Detect language for context
        t_lower = txt.lower()
        lang = "english"
        if any(w in t_lower for w in ['wetin','abi','dey','oya','guy']): lang = "pidgin"
        elif any(w in t_lower for w in ['bawo','omo','sugbon','ko si']): lang = "yoruba"
        elif any(w in t_lower for w in ['kedu','daalu','nnoo','anyi']): lang = "igbo"
        elif any(w in t_lower for w in ['sannu','yaya','kwana','muna']): lang = "hausa"
        
        user_histories[cid][-1]["lang"] = lang
        user_histories[cid].append({"role": "user", "content": txt})
        if len(user_histories[cid]) > 20:
            user_histories[cid] = [user_histories[cid][0]] + user_histories[cid][-15:]

        try:
            res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=user_histories[cid], tools=TOOLS, temperature=0.3)
            msg = res.choices[0].message
            
            if msg.tool_calls:
                user_histories[cid].append(msg)
                for tool in msg.tool_calls:
                    args = json.loads(tool.function.arguments)
                    args["telegram_id"] = str(cid)
                    
                    if tool.function.name == "list_products":
                        try: data = sb.table("products").select("*").execute().data
                        except Exception as e: data = []
                        user_histories[cid].append({"role":"tool","tool_call_id":tool.id,"content":json.dumps(data, default=str)})
                    
                    elif tool.function.name == "save_order":
                        try:
                            res = sb.table("orders").insert({
                                "product": args["product_name"], "price": args["price"],
                                "address": args["address"], "telegram_id": str(cid),
                                "customer_email": args["customer_email"], "status": "pending"
                            }).execute()
                            user_histories[cid].append({"role":"tool","tool_call_id":tool.id,"content":json.dumps({"order_id": res.data[0]["id"]})})
                        except Exception as e:
                            user_histories[cid].append({"role":"tool","tool_call_id":tool.id,"content":json.dumps({"error": str(e)})})
                    
                    elif tool.function.name == "create_payment":
                        try:
                            paystack_url = "https://api.paystack.co/transaction/initialize"
                            headers = {"Authorization": f"Bearer {os.environ['PAYSTACK_SECRET_KEY']}", "Content-Type": "application/json"}
                            payload = {
                                "email": args["customer_email"],
                                "amount": int(args["price"] * 100),
                                "metadata": {"telegram_id": str(cid), "order_id": args.get("order_id")}
                            }
                            r = requests.post(paystack_url, json=payload, headers=headers, timeout=10)
                            pay_data = r.json()
                            link = pay_data["data"]["authorization_url"] if pay_data.get("status") else "error"
                            user_histories[cid].append({"role":"tool","tool_call_id":tool.id,"content":json.dumps({"link": link})})
                        except Exception as e:
                            user_histories[cid].append({"role":"tool","tool_call_id":tool.id,"content":json.dumps({"error": str(e)})})

                res2 = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=user_histories[cid], temperature=0.3)
                final = res2.choices[0].message.content
                user_histories[cid].append({"role":"assistant","content":final})
                return final
            else:
                user_histories[cid].append(msg)
                return msg.content
        except Exception as e:
            print(f"🔴 Agent error: {e}", flush=True)
            return "⚠️ I'm having a moment. Please try again in a sec."

    def poll():
        token = os.environ["TELEGRAM_BOT_TOKEN"]
        off = 0
        print("🤖 AI Agent + Paystack poller started", flush=True)
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
                            print(f"💬 User {cid}: {txt}", flush=True)
                            reply = run_agent(cid, txt, token)
                            send(cid, reply, token)
                time.sleep(1)
            except Exception as e:
                print(f"❌ Poll error: {e}", flush=True)
                time.sleep(5)

    threading.Thread(target=poll, daemon=True).start()
