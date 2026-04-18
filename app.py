from flask import Flask, jsonify
import os, requests, threading, time, json
from openai import OpenAI

app = Flask(__name__)

# ✅ ROUTES
@app.route('/test')
def t(): return jsonify({"ok": True, "version": "agent-v1"}), 200
@app.route('/health')
def h(): return jsonify({"status": "ok"}), 200
@app.route('/')
def home(): return "<h1>✅ Deboo AI Agent Live</h1>"

# ✅ APP LOGIC
REQUIRED = ["SUPABASE_URL", "SUPABASE_KEY", "TELEGRAM_BOT_TOKEN", "GROQ_API_KEY"]
if all(os.environ.get(v) for v in REQUIRED):
    try:
        from supabase import create_client
        sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
        print("✅ Supabase connected", flush=True)
    except Exception as e:
        print(f"🔴 Supabase error: {e}", flush=True)
        sb = None

    # 🤖 AI Client (Groq via OpenAI-compatible SDK)
    client = OpenAI(api_key=os.environ["GROQ_API_KEY"], base_url="https://api.groq.com/openai/v1")

    # 🧠 Conversation Memory (per user, in-memory)
    user_histories = {}

    # 🛠️ Tool Definitions for LLM
    TOOLS = [
        {
            "type": "function",
            "function": {
                "name": "list_products",
                "description": "List all available products from the database",
                "parameters": {"type": "object", "properties": {}}
            }
        },
        {
            "type": "function",
            "function": {
                "name": "create_order",
                "description": "Save a new order after user confirms product & address",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "product_name": {"type": "string"},
                        "price": {"type": "number"},
                        "address": {"type": "string"},
                        "customer_telegram_id": {"type": "string"}
                    },
                    "required": ["product_name", "price", "address", "customer_telegram_id"]
                }
            }
        }
    ]

    # 🌍 SYSTEM PROMPT
    SYSTEM_PROMPT = """You are Deboo, a friendly AI shopping assistant for Nigeria. 
- Always reply in the user's language (English, Pidgin, Yoruba, Igbo, or Hausa)
- Be concise, culturally aware, and helpful
- Use markdown formatting for lists, prices, and emphasis
- When user asks for products: call list_products() first, then format the response
- When user confirms an order: call create_order() with exact details
- Never make up prices or products. Only use tool responses.
- If unsure, ask clarifying questions politely."""

    def send(cid, txt, token, parse="Markdown"):
        try: requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": cid, "text": txt, "parse_mode": parse}, timeout=5)
        except: pass

    def run_agent(cid, txt, token):
        if cid not in user_histories:
            user_histories[cid] = [{"role": "system", "content": SYSTEM_PROMPT}]
        
        user_histories[cid].append({"role": "user", "content": txt})
        
        # Keep context window manageable
        if len(user_histories[cid]) > 15:
            user_histories[cid] = [user_histories[cid][0]] + user_histories[cid][-12:]

        try:
            res = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=user_histories[cid],
                tools=TOOLS,
                temperature=0.4
            )
            msg = res.choices[0].message
            
            if msg.tool_calls:
                user_histories[cid].append(msg)
                for tool in msg.tool_calls:
                    if tool.function.name == "list_products":
                        try:
                            data = sb.table("products").select("*").execute().data
                            content = json.dumps(data, default=str)
                        except Exception as e:
                            content = f"Error fetching products: {str(e)}"
                        user_histories[cid].append({"role": "tool", "tool_call_id": tool.id, "content": content})
                    
                    elif tool.function.name == "create_order":
                        args = json.loads(tool.function.arguments)
                        try:
                            sb.table("orders").insert({
                                "product": args["product_name"],
                                "price": args["price"],
                                "address": args["address"],
                                "telegram_id": args["customer_telegram_id"],
                                "status": "pending"
                            }).execute()
                            content = json.dumps({"success": True, "message": "Order saved successfully"})
                        except Exception as e:
                            content = json.dumps({"success": False, "error": str(e)})
                        user_histories[cid].append({"role": "tool", "tool_call_id": tool.id, "content": content})

                # Second LLM call to process tool results
                res2 = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=user_histories[cid],
                    temperature=0.4
                )
                final_msg = res2.choices[0].message.content
                user_histories[cid].append({"role": "assistant", "content": final_msg})
                return final_msg
            else:
                user_histories[cid].append(msg)
                return msg.content
        except Exception as e:
            print(f"🔴 Agent error: {e}", flush=True)
            return "⚠️ I'm having a moment. Please try again in a sec."

    def poll():
        token = os.environ["TELEGRAM_BOT_TOKEN"]
        off = 0
        print("🤖 AI Agent poller started", flush=True)
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

    # ✅ Create orders table if it doesn't exist
    try:
        sb.table("orders").select("id").limit(1).execute()
    except:
        try:
            sb.rpc("create_orders_table").execute() # Fallback or use SQL editor manually
        except: pass

    threading.Thread(target=poll, daemon=True).start()
