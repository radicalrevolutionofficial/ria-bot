import os
import json
import requests
from flask import Flask, request, jsonify
from google.oauth2.service_account import Credentials
import gspread
from datetime import datetime

app = Flask(__name__)

# ============================================
# CONFIGURATION — all values from environment
# variables set in Render dashboard
# ============================================
BOT_TOKEN     = os.environ.get("BOT_TOKEN")
SHEET_ID      = os.environ.get("SHEET_ID")
SHEET_NAME    = os.environ.get("SHEET_NAME", "Sheet1")
BOT_ID        = int(os.environ.get("BOT_ID", "8726579895"))
YT_API_KEY    = os.environ.get("YT_API_KEY")
YT_CHANNEL    = os.environ.get("YT_CHANNEL")
FB_PAGE_TOKEN = os.environ.get("FB_PAGE_TOKEN")
FB_PAGE_ID    = os.environ.get("FB_PAGE_ID")
IG_ACCOUNT_ID = os.environ.get("IG_ACCOUNT_ID")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"


# ============================================
# WEBHOOK ENDPOINT
# Telegram sends all updates here instantly.
# Flask responds immediately so Telegram never retries.
# ============================================
@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.get_json()

    if "callback_query" in update:
        handle_callback(update["callback_query"])
        return jsonify({"ok": True})

    message = update.get("message")
    if not message or "text" not in message:
        return jsonify({"ok": True})

    sender = message.get("from", {})

    if sender.get("id") == BOT_ID:
        return jsonify({"ok": True})

    if sender.get("is_bot"):
        return jsonify({"ok": True})

    text       = message["text"].strip()
    chat_id    = message["chat"]["id"]
    message_id = str(message["message_id"])

    if text == "/start":
        send_menu(chat_id)
        return jsonify({"ok": True})

    # -----------------------------------------------
    # INPUT C2 FLOW
    # -----------------------------------------------
    lines = text.split("\n")
    if len(lines) < 3:
        return jsonify({"ok": True})

    c2      = lines[0].strip()
    likes   = lines[1].lower().replace("likes:", "").strip()
    reached = lines[2].lower().replace("reached:", "").strip()

    result = save_to_sheet(message_id, c2, likes, reached)

    if result == "duplicate":
        send_message(chat_id, "⚠️ Already exists in the database!")
    elif result == "saved":
        send_message(chat_id, "✅ Added to the database!")
    else:
        send_message(chat_id, "❌ Error saving. Please try again.")

    return jsonify({"ok": True})


# ============================================
# HANDLE BUTTON CLICKS
# ============================================
def handle_callback(callback):
    chat_id     = callback["message"]["chat"]["id"]
    data        = callback["data"]
    callback_id = callback["id"]

    answer_callback(callback_id)

    if data == "followers":
        fb = get_facebook_followers()
        ig = get_instagram_followers()
        yt = get_youtube_subscribers()
        send_message(chat_id,
            f"📊 Radical Revolution Followers\n\n"
            f"👍 Facebook: {fb}\n"
            f"📸 Instagram: {ig}\n"
            f"▶️ YouTube: {yt}\n\n"
            f"🎵 TikTok — coming soon!"
        )

    if data == "input_c2":
        send_message(chat_id,
            "✍️ Send your A-RR entry in this format:\n\n"
            "C2 text\n"
            "Likes: [number]\n"
            "Reached: [number]\n\n"
            "Example:\n"
            "I don't understand but I trust You Lord\n"
            "Likes: 5000\n"
            "Reached: 80000"
        )


# ============================================
# SAVE TO GOOGLE SHEET
# ============================================
def save_to_sheet(message_id, c2, likes, reached):
    try:
        gc    = get_sheets_client()
        sheet = gc.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
        rows  = sheet.get_all_values()

        if len(rows) == 0:
            sheet.append_row(["Message ID", "Date Added", "C2 Text", "Likes", "Reached", "Platform"])
            rows = sheet.get_all_values()

        for row in rows[1:]:
            if str(row[0]).strip() == message_id:
                return "duplicate"

        for row in rows[1:]:
            if (str(row[2]).strip() == c2 and
                str(row[3]).strip() == likes and
                str(row[4]).strip() == reached):
                return "duplicate"

        sheet.append_row([
            message_id,
            datetime.now().strftime("%m/%d/%Y"),
            c2, likes, reached, "Facebook"
        ])
        return "saved"

    except Exception as e:
        import traceback
        print(f"Sheet error: {e}")
        print(traceback.format_exc())
        return "error"


# ============================================
# GET YOUTUBE SUBSCRIBERS
# Fetches exact count with commas formatting.
# ============================================
def get_youtube_subscribers():
    try:
        url    = f"https://www.googleapis.com/youtube/v3/channels?part=statistics&id={YT_CHANNEL}&key={YT_API_KEY}"
        result = requests.get(url).json()
        count  = int(result["items"][0]["statistics"]["subscriberCount"])
        return f"{count:,}"
    except Exception as e:
        print(f"YouTube error: {e}")
        return "unavailable"


# ============================================
# GET FACEBOOK FOLLOWERS
# Fetches exact count with commas formatting.
# ============================================
def get_facebook_followers():
    try:
        url    = f"https://graph.facebook.com/{FB_PAGE_ID}?fields=followers_count&access_token={FB_PAGE_TOKEN}"
        result = requests.get(url).json()
        count  = int(result["followers_count"])
        return f"{count:,}"
    except Exception as e:
        print(f"Facebook error: {e}")
        return "unavailable"


# ============================================
# GET INSTAGRAM FOLLOWERS
# Fetches exact count using Instagram Business
# Account ID with commas formatting.
# ============================================
def get_instagram_followers():
    try:
        url    = f"https://graph.facebook.com/{IG_ACCOUNT_ID}?fields=followers_count&access_token={FB_PAGE_TOKEN}"
        result = requests.get(url).json()
        count  = int(result["followers_count"])
        return f"{count:,}"
    except Exception as e:
        print(f"Instagram error: {e}")
        return "unavailable"


# ============================================
# GOOGLE SHEETS CLIENT
# ============================================
def get_sheets_client():
    creds_json = os.environ.get("GOOGLE_CREDS")
    creds_dict = json.loads(creds_json)
    scopes     = ["https://www.googleapis.com/auth/spreadsheets"]
    creds      = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)


# ============================================
# SEND MENU
# ============================================
def send_menu(chat_id):
    requests.post(f"{TELEGRAM_API}/sendMessage", json={
        "chat_id": chat_id,
        "text": "👋 Welcome to Ria Bot!\n\nWhat do you want to do?",
        "reply_markup": {
            "inline_keyboard": [[
                {"text": "📊 Followers", "callback_data": "followers"},
                {"text": "✍️ Input C2",  "callback_data": "input_c2"}
            ]]
        }
    })


# ============================================
# SEND MESSAGE
# ============================================
def send_message(chat_id, text):
    requests.post(f"{TELEGRAM_API}/sendMessage", json={
        "chat_id": chat_id,
        "text": text
    })


# ============================================
# ANSWER CALLBACK
# ============================================
def answer_callback(callback_id):
    requests.post(f"{TELEGRAM_API}/answerCallbackQuery", json={
        "callback_query_id": callback_id
    })


# ============================================
# HEALTH CHECK
# ============================================
@app.route("/", methods=["GET"])
def health():
    return "Ria Bot is running!", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
