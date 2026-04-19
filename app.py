from flask import Flask, jsonify, request
import os, requests, threading, time, json, hmac, hashlib
from openai import OpenAI

app = Flask(__name__)

# ✅ ROUTES (always register)
@app.route('/test')
def t(): return jsonify({"ok": True, "version": "paystack-safe"}), 200
@app.route('/health')
def h(): return jsonify({"status": "ok"}), 200
@app.route('/')
def home(): return "<h1>✅ Deboo AI Safe Checkout</h1>"

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
        tid, oid = meta.get("telegram_id"), meta.get("order_id")
        if oid and sb:
            try:
                sb.table("orders").update({"status": "paid", "payment_ref": ref}).eq("id", oid).execute()
                if tid: send(tid, f"✅ *Payment Confirmed!* 🎉\nRef: `{ref}`\nWe'll ship your order shortly.", os.environ["TELEGRAM_BOT_TOKEN"])
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
            "description": "Generate Paystack payment link. Requires EXACTLY: product_name, price, customer_email, delivery_address",
            "parameters": {"type": "object", "properties": {
                "product_name": {"type": "string"}, "price": {"type": "number"},
                "customer_email": {"type": "string"}, "delivery_address": {"type": "string"}
            }, "required": ["product_name", "price", "customer_email", "delivery_address"]}
        }
    }, {
        "type": "function", "function": {
            "name": "list_products", "description": "Fetch available products from database", "parameters": {"type": "object", "properties": {}}
        }
    }]

    SYSTEM_PROMPT = """You are Deboo, a direct Nigerian shopping assistant.
RULES:
1. Reply in user's language. Be concise. NEVER apologize. NEVER use filler.
2. NEVER ask for Telegram ID, name, or phone.
3. When user wants to buy: ask ONLY for EMAIL & DELIVERY ADDRESS.
4. Once you have product, price, email, address: CALL process_checkout() IMMEDIATELY.
5. If tool returns a link: send EXACTLY "🔗 Pay securely: <url>"
6. If tool returns error: state plainly "⚠️ Payment setup failed: <error>. Please retry."
7. NEVER loop. Execute tools on first valid attempt."""

    def send(cid, txt, token, parse="HTML"):
        try: requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": cid, "text": txt, "parse_mode": parse}, timeout=5)
        except: pass

    def run_agent(cid, txt, token):
        if cid not in user_histories: user_histories[cid] = [{"role": "system", "content": SYSTEM_PROMPT}]
        user_histories[cid].append({"role": "user", "content": txt})
        if len(user_histories[cid]) > 8: user_histories[cid] = [user_histories[cid][0]] + user_histories[cid][-6:]

        try:
            res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=user_histories[cid], tools=TOOLS, temperature=0.2)
            msg = res.choices[0].message
            
            if msg.tool_calls:
                user_histories[cid].append(msg)
                for tool in msg.tool_calls:
                    # 🔒 Safe argument parsing
                    try: args = json.loads(tool.function.arguments)
                    except: args = {}
                    
                    if tool.function.name == "list_products":
                        try: data = sb.table("products").select("*").execute().data
                        except: data = []
                        user_histories[cid].append({"role":"tool","tool_call_id":tool.id,"content":json.dumps(data, default=str)})
                        
                    elif tool.function.name == "process_checkout":
                        try:
                            # Validate required fields
                            if not all(k in args for k in ["product_name", "price", "customer_email", "delivery_address"]):
                                user_histories[cid].append({"role":"tool","tool_call_id":tool.id,"content":json.dumps({"success": False, "error": "Missing required checkout fields"})})
                                continue

                            # 1. Save order
                            order_res = sb.table("orders").insert({
                                "product": args["product_name"], "price": float(args["price"]),
                                "address": args["delivery_address"], "telegram_id": str(cid),
                                "customer_email": args["customer_email"], "status": "pending"
                            }).execute()
                            order_id = order_res.data[0]["id"] if order_res.data else None
                            
                            # 2. Paystack
                            headers = {"Authorization": f"Bearer {os.environ['PAYSTACK_SECRET_KEY']}", "Content-Type": "application/json"}
                            payload = {"email": args["customer_email"], "amount": int(float(args["price"]) * 100), "metadata": {"telegram_id": str(cid), "order_id": order_id}}
                            
                            print("💳 Calling Paystack...", flush=True)
                            r = requests.post("https://api.paystack.co/transaction/initialize", json=payload, headers=headers, timeout=15)
                            print(f"💳 STATUS: {r.status_code} | RAW: {r.text[:300]}", flush=True) # 🔍 DEBUG LOG
                            
                            # 🔒 Safe JSON parsing
                            try: pay_res = r.json()
                            except: pay_res = {"status": False, "message": f"Paystack returned invalid JSON: {r.text[:100]}"}
                            
                            if pay_res.get("status") and pay_res.get("data", {}).get("authorization_url"):
                                user_histories[cid].append({"role":"tool","tool_call_id":tool.id,"content":json.dumps({"success": True, "link": pay_res["data"]["authorization_url"]})})
                            else:
                                user_histories[cid].append({"role":"tool","tool_call_id":tool.id,"content":json.dumps({"success": False, "error": pay_res.get("message", "Unknown Paystack error")})})
                                
                        except Exception as e:
                            print(f"🔴 Checkout crash: {e}", flush=True)
                            user_histories[cid].append({"role":"tool","tool_call_id":tool.id,"content":json.dumps({"success": False, "error": str(e)})})

                res2 = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=user_histories[cid], temperature=0.2)
                final = res2.choices[0].message.content
                user_histories[cid].append({"role":"assistant","content":final})
                return final
            else:
                user_histories[cid].append(msg)
                return msg.content
        except Exception as e:
            print(f"🔴 Agent error: {e}", flush=True)
            return "⚠️ System busy. Retry in a moment."

    def poll():
        token = os.environ["TELEGRAM_BOT_TOKEN"]
        off = 0
        print("🤖 Safe agent poller started", flush=True)
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
                            print(f"💬 {cid}: {txt}", flush=True)
                            send(cid, run_agent(cid, txt, token), token)
                time.sleep(1)
            except Exception as e:
                print(f"❌ Poll error: {e}", flush=True)
                time.sleep(5)

    threading.Thread(target=poll, daemon=True).start()
