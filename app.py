import os, json, requests, datetime, time, threading, random
from flask import Flask, request
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
PAY_KEY = os.environ["PAYSTACK_SECRET_KEY"]
BASE_URL = os.environ.get("BASE_URL", "https://example.com")
active_bots = {}

# ─────────────────────────────────────────────────────────────
# DATABASE HELPERS
# ─────────────────────────────────────────────────────────────
def get_business(biz_id):
    return sb.table("businesses").select("*").eq("id", biz_id).single().execute().data

def db_get(uid, biz_id):
    r = sb.table("conversations").select("*").eq("user_platform_id", "tg_" + str(uid)).eq("business_id", biz_id).execute()
    return r.data[0] if r.data else None

def db_new(uid, name, biz_id):
    sb.table("conversations").insert({"user_platform_id": "tg_" + str(uid), "platform": "telegram", "business_id": biz_id, "current_state": "ENQUIRY", "context": {"name": name}}).execute()

def db_upd(uid, st, ctx, biz_id):
    sb.table("conversations").update({"current_state": st, "context": ctx, "last_activity": datetime.datetime.now(datetime.timezone.utc).isoformat()}).eq("user_platform_id", "tg_" + str(uid)).eq("business_id", biz_id).execute()

def verify_paystack(ref):
    try:
        r = requests.get("https://api.paystack.co/transaction/verify/" + ref, headers={"Authorization": "Bearer " + PAY_KEY})
        return r.json().get("data", {}).get("status") == "success"
    except: return False

# ─────────────────────────────────────────────────────────────
# LANGUAGE DETECTION & RESPONSES
# ─────────────────────────────────────────────────────────────
def detect_language(txt):
    txt_l = txt.lower()
    # Yoruba markers
    if any(w in txt_l for w in ["bawo", "se", "omo", "abi", "jowo", "epe", "mo", "ti", "ni"]): return "yo"
    # Igbo markers
    if any(w in txt_l for w in ["kedu", "nnoo", "daalu", "afa", "m", "gi", "anyi", "bu"]): return "ig"
    # Hausa markers
    if any(w in txt_l for w in ["sannu", "yaya", "ina", "kai", "kada", "muna", "da", "shi"]): return "ha"
    # Pidgin markers
    if any(w in txt_l for w in ["wetin", "abeg", "wahala", "dey", "na", "no", "go", "e", "sharp", "how far"]): return "pcm"
    return "en"  # Default English

RESPONSES = {
    "en": {
        "greet": "👋 Hello! How can I help you today?",
        "catalog": "🛍️ Our Products:\n1️⃣ Wireless Earbuds ₦12,500\n2️⃣ Smartwatch ₦28,000\nWhich interests you?",
        "pending_fee": "📍 Where should we deliver? (e.g., Lagos, Abuja, PH)",
        "payment_ready": "💰 Total: ₦{total}\nReply 'pay' to get secure checkout link.",
        "payment_link": "🔗 Pay securely: {link}\n<i>Test card: 4084 0840 8408 4081 | 12/25 | 123</i>\n💡 After paying, just reply anything.",
        "payment_confirmed": "🎉 Payment confirmed!\nOrder: {order_id}\n📦 ETA: 2-4 business days",
        "tracking": "📦 Status: Processing\n⏳ ETA: 2-4 days\n📍 {location}\nWe'll notify you when it ships!",
        "confirmation": "🙏 Great! Please rate your experience 1-5 ⭐",
        "closed": "🌟 Thank you for {rating}/5! ❤️ Order complete. Need anything else?",
        "complaint": "📝 Complaint logged. Ticket: {ticket}\nWe'll resolve this within 24 hours.",
        "fallback": "👋 I'm here to help! Ask about products, delivery, tracking, or refunds."
    },
    "pcm": {
        "greet": "👋 How far! Wetin I fit do for you today?",
        "catalog": "🛍️ See our fresh stock:\n1️⃣ Wireless Earbuds ₦12,500\n2️⃣ Smartwatch ₦28,000\nWhich one catch your eye?",
        "pending_fee": "📍 Abeg, where we dey send am? (e.g., Ikeja, Abuja, PH)",
        "payment_ready": "💰 Total: ₦{total}\nReply 'pay' or 'yes' make I send you secure link.",
        "payment_link": "🔗 Pay here sharp sharp: {link}\n<i>Test: 4084 0840 8408 4081 | 12/25 | 123</i>\n💡 After paying, just reply anything.",
        "payment_confirmed": "🎉 E don set! Payment confirmed.\nOrder: {order_id}\n📦 We go send update 2-4 days.",
        "tracking": "📦 Your order dey process sharp sharp\n⏳ ETA: 2-4 days\n📍 {location}\nI go ping you when e move.",
        "confirmation": "🙏 E don land! Abeg rate us 1-5 ⭐ make we know how we do.",
        "closed": "🌟 Thanks for {rating}/5! You be star. ❤️ Order don complete. Need anything else? I dey for you!",
        "complaint": "📝 I hear you. Ticket: {ticket}. No wahala, our team go sort am within 24hrs.",
        "fallback": "👋 How far! Ask about products, delivery, tracking, or refunds. I dey for you! 🤝"
    },
    "yo": {
        "greet": "👋 Bawo ni! Bawo ni mo le ran yin lowo loni?",
        "catalog": "🛍️ Awọn ohun wa:\n1️⃣ Wireless Earbuds ₦12,500\n2️⃣ Smartwatch ₦28,000\nEwo ni o fẹ?",
        "pending_fee": "📍 Jowo, ibo ni a o fi ranṣẹ? (e.g., Ikeja, Abuja, PH)",
        "payment_ready": "💰 Lapapọ: ₦{total}\nFi 'pay' ranṣẹ lati gba ọna asopọ isanwo to ni aabo.",
        "payment_link": "🔗 Sanwo ni aabo: {link}\n<i>Kaadi idanwo: 4084 0840 8408 4081 | 12/25 | 123</i>\n💡 Lẹhin isanwo, fi eyikeyi ranṣẹ.",
        "payment_confirmed": "🎉 Isanwo ti gba! \nOrder: {order_id}\n📦 A o fi imudojuiwọn ranṣẹ ni ọjọ 2-4.",
        "tracking": "📦 Iṣẹ n lọ lọwọ\n⏳ ETA: ọjọ 2-4\n📍 {location}\nA o fi imeeli ranṣẹ nigba ti o ba lọ.",
        "confirmation": "🙏 O ti de! Jowo fi 1-5 ⭐ sọ bí a ṣe ṣe.",
        "closed": "🌟 O ṣeun fun {rating}/5! ❤️ Order ti pari. Nkan miiran? Mo wa fun ọ!",
        "complaint": "📝 A ti gba ẹdun ọkan. Tikẹti: {ticket}. A o yanju rẹ ni wakati 24.",
        "fallback": "👋 Bawo ni! Beere nipa awọn ohun, ifijiṣẹ, titoju, tabi agbapada. Mo wa fun ọ! 🤝"
    },
    "ig": {
        "greet": "👋 Kedu! Kedu ka m ga-enyere gi aka taa?",
        "catalog": "🛍️ Ngwa anyị:\n1️⃣ Wireless Earbuds ₦12,500\n2️⃣ Smartwatch ₦28,000\nKedu nke ị chọrọ?",
        "pending_fee": "📍 Biko, ebee ka anyi ga-eziga ya? (dịka Ikeja, Abuja, PH)",
        "payment_ready": "💰 Ngụkọta: ₦{total}\nZite 'pay' ka m ziga gị njikọ ịkwụ ụgwọ dị nchebe.",
        "payment_link": "🔗 Kwụọ ụgwọ n'ebe nchebe: {link}\n<i>Kaadị nnwale: 4084 0840 8408 4081 | 12/25 | 123</i>\n💡 Mgbe ị kwụsịrị ụgwọ, zite ihe ọ bụla.",
        "payment_confirmed": "🎉 Ekwentị ekwentị! Ekwentị ekwentị.\nOrder: {order_id}\n📦 Anyi ga-eziga mmelite n'ime ụbọchị 2-4.",
        "tracking": "📦 Iwu gị na-aga n'ihu\n⏳ ETA: ụbọchị 2-4\n📍 {location}\nAnyi ga-akpọtụrụ gị mgbe ọ ga-aga.",
        "confirmation": "🙏 Ọ ruru! Biko nye anyi 1-5 ⭐ ka anyi mara otu anyi si mee.",
        "closed": "🌟 Daalụ maka {rating}/5! ❤️ Iwu agwụla. Ihe ọzọ? M dị maka gị!",
        "complaint": "📝 Anyị nụrụ gị. Tiketi: {ticket}. Enweghị nsogbu, ndị otu anyị ga-edozi ya n'ime awa 24.",
        "fallback": "👋 Kedu! Jụọ banyere ngwa, nnyefe, nchịkọta, ma ọ bụ nloghachi ego. M dị maka gị! 🤝"
    },
    "ha": {
        "greet": "👋 Sannu! Yaya zan iya taimaka maka yau?",
        "catalog": "🛍️ Kayan mu:\n1️⃣ Wireless Earbuds ₦12,500\n2️⃣ Smartwatch ₦28,000\nWanne kake so?",
        "pending_fee": "📍 Don Allah, ina za mu aika? (misali Ikeja, Abuja, PH)",
        "payment_ready": "💰 Jimla: ₦{total}\nAika 'pay' don in ba ka hanyar biya mai tsaro.",
        "payment_link": "🔗 Biya a wurin tsaro: {link}\n<i>Katin gwaji: 4084 0840 8408 4081 | 12/25 | 123</i>\n💡 Bayan biya, aika kowane abu.",
        "payment_confirmed": "🎉 An tabbatar da biya!\nOrder: {order_id}\n📦 Za mu aika sabuntawa cikin kwana 2-4.",
        "tracking": "📦 Odar ku tana ci gaba\n⏳ ETA: kwana 2-4\n📍 {location}\nZa mu sanar da ku lokacin da ta tashi.",
        "confirmation": "🙏 Ya isa! Don Allah ba mu 1-5 ⭐ don mu san yadda muka yi.",
        "closed": "🌟 Na gode da {rating}/5! ❤️ Odar ta kare. Wani abu? Ina nan domin ku!",
        "complaint": "📝 Mun ji ku. Tikiti: {ticket}. Babu matsala, ƙungiyarmu za ta warware shi cikin awa 24.",
        "fallback": "👋 Sannu! Yi tambaya game da kayayyaki, isarwa, bin diddigi, ko dawo da kudi. Ina nan domin ku! 🤝"
    }
}

VOICE_NOTES = {
    "greet": "https://www.soundjay.com/buttons/button-1.mp3",  # Replace with your TTS/recorded audio
    "payment_confirmed": "https://www.soundjay.com/buttons/button-4.mp3",
    "closed": "https://www.soundjay.com/buttons/sounds/button-16.mp3"
}

# ─────────────────────────────────────────────────────────────
# PAYMENT & DELIVERY
# ─────────────────────────────────────────────────────────────
DELIVERY_FEES = {"lagos": 1500, "ikeja": 1500, "abuja": 3500, "ph": 4000, "other": 4500}
def calc_fee(loc):
    loc = loc.lower()
    for k, v in DELIVERY_FEES.items():
        if k in loc: return v
    return 3500

def generate_paystack_link(amount, email, ref, callback):
    try:
        r = requests.post(
            "https://api.paystack.co/transaction/initialize",
            headers={"Authorization": "Bearer " + PAY_KEY},
            json={
                "email": email,
                "amount": int(amount) * 100,
                "currency": "NGN",
                "reference": ref,
                "callback_url": callback
            }
        )
        return r.json()["data"]["authorization_url"]
    except Exception as e:
        print("Paystack error:", e)
        return "https://paystack.com"

# ─────────────────────────────────────────────────────────────
# AI LOGIC (Multilingual + Voice Support)
# ─────────────────────────────────────────────────────────────
def ai_logic(txt, st, ctx, biz, lang):
    txt_l = txt.lower()
    R = RESPONSES.get(lang, RESPONSES["en"])
    
    # Auto-verify payment
    if st in ["PAYMENT", "PENDING_VERIFY"] and ctx.get("ref"):
        if verify_paystack(ctx["ref"]):
            ctx["order_id"] = "ORD-" + str(int(time.time()))
            ctx["paid"] = True
            return "PROCESSING", R["payment_confirmed"].format(order_id=ctx["order_id"]), {"voice": "payment_confirmed"}
        return st, "⏳ I no see payment yet. Reply 'check' to retry.", {}
    
    # Product enquiry
    if any(w in txt_l for w in ["product", "show", "menu", "catalog", "wetin", "sell", "bawo", "kedu", "sannu"]):
        return "ENQUIRY", R["catalog"], {}
    
    # Product selection
    if "earbud" in txt_l:
        ctx["amount"] = 12500; ctx["product"] = "Earbuds"
        return "PENDING_FEE", R["pending_fee"], {}
    if "watch" in txt_l:
        ctx["amount"] = 28000; ctx["product"] = "Smartwatch"
        return "PENDING_FEE", R["pending_fee"], {}
    
    # Delivery fee
    if st == "PENDING_FEE":
        fee = calc_fee(txt)
        ctx["delivery_fee"] = fee
        ctx["total"] = ctx["amount"] + fee
        ctx["location"] = txt
        return "PAYMENT", R["payment_ready"].format(total=ctx["total"]), {}
    
    # Payment request
    if "pay" in txt_l or "yes" in txt_l or "checkout" in txt_l or "biya" in txt_l or "sanwo" in txt_l:
        return "PAYMENT", "🔄 Generating link...", {"gen_link": True}
    
    # Tracking
    if "track" in txt_l or "status" in txt_l or "where" in txt_l or "ibo" in txt_l:
        loc = ctx.get("location", "Lagos")
        return "TRACKING", R["tracking"].format(location=loc), {}
    
    # Delivery confirmation
    if "received" in txt_l or "got" in txt_l or "delivered" in txt_l or "de" in txt_l:
        return "CONFIRMATION", R["confirmation"], {"voice": "greet"}
    
    # Rating
    if txt_l in ["1","2","3","4","5"]:
        return "CLOSED", R["closed"].format(rating=txt_l), {"voice": "closed"}
    
    # Complaints
    if "complaint" in txt_l or "issue" in txt_l or "wahala" in txt_l or "matsala" in txt_l:
        ctx["ticket"] = "TKT-" + str(int(time.time()))
        return "COMPLAINT", R["complaint"].format(ticket=ctx["ticket"]), {}
    
    # Default
    brand = biz.get("brand_name", "My Store")
    return st, R["fallback"], {}

def send_tg_text(cid, txt, token):
    requests.post("https://api.telegram.org/bot" + token + "/sendMessage", json={"chat_id": cid, "text": txt, "parse_mode": "HTML"})

def send_tg_voice(cid, audio_url, token, caption=""):
    try:
        # Telegram requires file_id or URL upload; for MVP we use URL
        requests.post(
            "https://api.telegram.org/bot" + token + "/sendVoice",
            json={
                "chat_id": cid,
                "voice": audio_url,
                "caption": caption,
                "parse_mode": "HTML"
            }
        )
    except Exception as e:
        print("Voice send error:", e)

# ─────────────────────────────────────────────────────────────
# MESSAGE HANDLER
# ─────────────────────────────────────────────────────────────
def handle_msg(m, biz_id):
    cid, uid, txt = m['chat']['id'], m['from']['id'], m['text']
    biz = get_business(biz_id)
    lang = detect_language(txt)
    
    conv = db_get(uid, biz_id)
    st, ctx = ("ENQUIRY", {"name": m['from'].get('first_name','User'), "lang": lang}) if not conv else (conv['current_state'], conv.get('context',{}))
    if not conv: db_new(uid, ctx['name'], biz_id)
    
    st, msg, action = ai_logic(txt, st, ctx, biz, lang)
    
    # Generate real Paystack link
    if action.get("gen_link") and not ctx.get("paid"):
        ref = "pay_" + str(uid) + "_" + str(int(time.time()))
        total = ctx.get('total', ctx.get('amount', 0))
        ctx.update({"ref": ref, "amount": total, "chat_id": cid})
        callback = BASE_URL + "/pay-callback"
        link = generate_paystack_link(total, str(uid) + "@customer.ng", ref, callback)
        R = RESPONSES.get(lang, RESPONSES["en"])
        msg = R["payment_link"].format(link=link)
    
    db_upd(uid, st, ctx, biz_id)
    
    # Send text
    send_tg_text(cid, msg, biz["telegram_bot_token"])
    
    # Send voice note if action requests it
    if action.get("voice") and VOICE_NOTES.get(action["voice"]):
        send_tg_voice(cid, VOICE_NOTES[action["voice"]], biz["telegram_bot_token"], caption=msg[:50] + "...")

# ─────────────────────────────────────────────────────────────
# POLLING ENGINE
# ─────────────────────────────────────────────────────────────
def start_polling(biz_id, token):
    if biz_id in active_bots: return
    print("🚀 Starting bot for", biz_id)
    def poll():
        offset = 0
        while True:
            try:
                r = requests.get("https://api.telegram.org/bot" + token + "/getUpdates", params={"offset": offset, "timeout": 30})
                for u in r.json().get("result", []):
                    offset = u["update_id"] + 1
                    if "message" in u and "text" in u["message"]:
                        handle_msg(u["message"], biz_id)
            except Exception as e:
                print("⚠️ Poll error", biz_id, ":", e)
                time.sleep(5)
    t = threading.Thread(target=poll, daemon=True)
    t.start()
    active_bots[biz_id] = t

def load_all_bots():
    bizs = sb.table("businesses").select("id, telegram_bot_token").eq("status", "active").execute().data
    for b in bizs:
        if b.get("telegram_bot_token"):
            start_polling(b["id"], b["telegram_bot_token"])

# ─────────────────────────────────────────────────────────────
# WEB ROUTES
# ─────────────────────────────────────────────────────────────
@app.route('/')
def home(): return "<h1>✅ Deboo SaaS (Multilingual + Voice 🎙️)</h1><a href='/signup'>Sign Up</a>"

@app.route('/signup', methods=['GET','POST'])
def signup():
    if request.method == 'POST':
        email, pwd, name = request.form.get('email'), request.form.get('password'), request.form.get('business_name')
        try:
            res = sb.auth.sign_up({"email": email, "password": pwd})
            if res.user:
                sb.table("businesses").insert({"owner_email": email, "business_name": name, "status": "active"}).execute()
                return "<h2>✅ Created!</h2><a href='/dashboard?email=" + email + "'>Activate Bot →</a>"
        except Exception as e: return "<p style='color:red'>" + str(e)[:100] + "</p><a href='/signup'>← Back</a>"
    return "<form method='post'><input name='email' placeholder='Email' required><br><input name='password' type='password' placeholder='Password' required><br><input name='business_name' placeholder='Business Name' required><br><button type='submit'>Create</button></form>"

@app.route('/dashboard')
def dashboard():
    email = request.args.get('email', '')
    return "<h2>Dashboard: " + email + "</h2><form method='post' action='/activate'><input type='hidden' name='email' value='" + email + "'><input name='token' placeholder='Telegram Bot Token' required><button type='submit'>Activate</button></form>"

@app.route('/activate', methods=['POST'])
def activate():
    email, token = request.form.get('email'), request.form.get('token')
    biz = sb.table("businesses").select("id,business_name").eq("owner_email", email).single().execute().data
    if biz:
        sb.table("businesses").update({"telegram_bot_token": token}).eq("id", biz["id"]).execute()
        start_polling(biz["id"], token)
        return "<h2>🤖 Activated!</h2><p>" + biz['business_name'] + " is live. Message your bot now.</p>"
    return "Not found."

@app.route('/pay-callback')
def pay_callback():
    return "<h1>✅ Payment received! Bot will confirm shortly.</h1>"

@app.route('/health')
def health(): return {"status": "ok", "active_bots": len(active_bots)}

# ─────────────────────────────────────────────────────────────
# STARTUP
# ─────────────────────────────────────────────────────────────
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)