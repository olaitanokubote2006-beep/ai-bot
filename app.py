from flask import Flask, jsonify, request
import os, requests, threading, time, json, hmac, hashlib
from openai import OpenAI

app = Flask(__name__)

# ✅ ROUTES
@app.route('/test')
def t(): return jsonify({"ok": True, "version": "paystack-clean"}), 200
@app.route('/health')
def h(): return jsonify({"status": "ok"}), 200
@app.route('/')
def home(): return "<h1>✅ Deboo AI + Paystack Live</h1>"

@app.route('/webhook/paystack', methods=['POST'])
def paystack_webhook():
    secret = os.environ.get("PAYSTACK_SECRET_KEY", "")
    signature = request.headers.get("x-paystack-signature", "")
    payload = request.get_data()
    expected = hmac.new(secret.encode(), payload, hashlib.sha512).hexdigest()
    if signature != expected: return jsonify({"error": "invalid signature"}), 401
    event = json.loads(payload)
    if event.get("event") == "charge.success":
        data = event.get("data", {})
        ref = data.get("reference", "")
        meta = data.get("metadata", {})
        tid = meta.get("telegram_id")
        oid = meta.get("order_id")
        if oid and sb:
            try:
                sb.table("orders").update({"status": "paid", "payment_ref": ref}).eq("id", oid).execute()
                if tid: send(tid, f"✅ *Payment Confirmed!* 🎉\nRef: `{ref}`\nStatus: PAID", os.environ["TELEGRAM_BOT_TOKEN"])
            except Exception as e: print(f"🔴 Webhook DB: {e}", flush=True)
    return jsonify({"ok": True}), 200

# ✅ APP LOGIC
REQUIRED = ["SUPABASE_URL", "SUPABASE_KEY", "TELEGRAM_BOT_TOKEN", "GROQ_API_KEY", "PAYSTACK_SECRET_KEY"]
if all(os.environ.get(v) for v in REQUIRED):
    try:
        from supabase import create_client
        sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
        print("✅ Supabase connected", flush=True)
    except Exception as e:
        print(f"🔴 Supabase: {e}", flush=True)
        sb = None

    client = OpenAI(api_key=os.environ["GROQ_API_KEY"], base_url="https://api.groq.com/openai/v1")
    user_histories = {}

    TOOLS = [{
        "type": "function", "function": {
            "name": "process_checkout",
            "description": "Save order & generate Paystack link. Requires: product_name, price, address, customer_email",
            "parameters": {"type": "object", "properties": {
                "product_name": {"type": "string"}, "price": {"type": "number"},
                "address": {"type": "string"}, "customer_email": {"type": "string"}
            }, "required": ["product_name", "price", "address", "customer_email"]}
        }
    }, {
        "type": "function", "function": {
            "name": "list_products", "description": "Fetch all available products", "parameters": {"type": "object", "properties": {}}
        }
    }]

    SYSTEM_PROMPT = """You are Deboo, a friendly Nigerian AI shopping assistant.
- Reply in user's language (English, Pidgin, Yoruba, Igbo, Hausa)
- Use markdown. Be concise & culturally aware.
- When asked for products: call list_products()
- When user confirms purchase: ask for EMAIL & DELIVERY ADDRESS
- Once you have all 4 fields: call process_checkout() EXACTLY ONCE
- CRITICAL: When the tool returns a payment link, send it EXACTLY as: 
  🔗 Pay securely: https://checkout.paystack.com/...
  DO NOT wrap the URL in asterisks, underscores, or markdown. DO NOT modify a single character of the URL.
- Never make up prices."""

    def send(cid, txt, token, parse="HTML"):
        # Use HTML mode to safely render links
        try: 
            requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": cid, "text": txt, "parse_mode": parse}, timeout=5)
        except Exception as e:
            print(f"📤 Send error: {e}", flush=True)

    def run_agent(cid, txt, token):
        if cid not in user_histories: user_histories[cid] = [{"role": "system", "content": SYSTEM_PROMPT}]
        user_histories[cid].append({"role": "user", "content": txt})
        if len(user_histories[cid]) > 15: user_histories[cid] = [user_histories[cid][0]] + user_histories[cid][-10:]

        try:
            res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=user_histories[cid], tools=TOOLS, temperature=0.3)
            msg = res.choices[0].message
            if msg.tool_calls:
                user_histories[cid].append(msg)
                for tool in msg.tool_calls:
                    args = json.loads(tool.function.arguments)
                    if tool.function.name == "list_products":
                        try: data = sb.table("products").select("*").execute().data
                        except: data = []
                        user_histories[cid].append({"role":"tool","tool_call_id":tool.id,"content":json.dumps(data, default=str)})
                    elif tool.function.name == "process_checkout":
                        try:
                            order_res = sb.table("orders").insert({"product": args["product_name"], "price": args["price"], "address": args["address"], "telegram_id": str(cid), "customer_email": args["customer_email"], "status": "pending"}).execute()
                            order_id = order_res.data[0]["id"] if order_res.data else None
                            headers = {"Authorization": f"Bearer {os.environ['PAYSTACK_SECRET_KEY']}", "Content-Type": "application/json"}
                            payload = {"email": args["customer_email"], "amount": int(float(args["price"]) * 100), "metadata": {"telegram_id": str(cid), "order_id": order_id}}
                            r = requests.post("https://api.paystack.co/transaction/initialize", json=payload, headers=headers, timeout=10)
                            pay_res = r.json()
                            print(f"💳 RAW PAYSTACK RESPONSE: {json.dumps(pay_res)}", flush=True) # 🔍 DEBUG LOG
                            
                            if pay_res.get("status") and pay_res["data"].get("authorization_url"):
                                url = pay_res["data"]["authorization_url"]
                                user_histories[cid].append({"role":"tool","tool_call_id":tool.id,"content":json.dumps({"success": True, "link": url, "order_id": order_id})})
                            else:
                                user_histories[cid].append({"role":"tool","tool_call_id":tool.id,"content":json.dumps({"success": False, "error": pay_res.get("message", "Paystack error")})})
                        except Exception as e:
                            user_histories[cid].append({"role":"tool","tool_call_id":tool.id,"content":json.dumps({"success": False, "error": str(e)})})
                res2 = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=user_histories[cid], temperature=0.3)
                final = res2.choices[0].message.content
                user_histories[cid].append({"role":"assistant","content":final})
                return final
            else:
                user_histories[cid].append(msg)
                return msg.content
        except Exception as e:
            print(f"🔴 Agent error: {e}", flush=True)
            return "⚠️ System busy. Try again."

    def poll():
        token = os.environ["TELEGRAM_BOT_TOKEN"]
        off = 0
        print("🤖 Agent + Paystack poller started", flush=True)
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
                            send(cid, run_agent(cid, txt, token), token)
                time.sleep(1)
            except Exception as e:
                print(f"❌ Poll error: {e}", flush=True)
                time.sleep(5)

    threading.Thread(target=poll, daemon=True).start()
