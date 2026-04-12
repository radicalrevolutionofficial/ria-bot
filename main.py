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
# variables set in Railway dashboard
# ============================================
BOT_TOKEN  = os.environ.get("BOT_TOKEN")
SHEET_ID   = os.environ.get("SHEET_ID")
SHEET_NAME = os.environ.get("SHEET_NAME", "Sheet1")
BOT_ID     = int(os.environ.get("BOT_ID", "8726579895"))
YT_API_KEY = os.environ.get("YT_API_KEY")
YT_CHANNEL = os.environ.get("YT_CHANNEL")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"


# ============================================
# WEBHOOK ENDPOINT
# Telegram sends all updates here instantly.
# Flask responds immediately so Telegram
# never retries.
# ============================================
@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.get_json()

    # Handle button clicks
    if "callback_query" in update:
        handle_callback(update["callback_query"])
        return jsonify({"ok": True})

    # Handle messages
    message = update.get("message")
    if not message or "text" not in message:
        return jsonify({"ok": True})

    sender = message.get("from", {})

    # Block bot's own messages using hardcoded bot ID
    if sender.get("id") == BOT_ID:
        return jsonify({"ok": True})

    # Block any other bot messages
    if sender.get("is_bot"):
        return jsonify({"ok": True})

    text       = message["text"].strip()
    chat_id    = message["chat"]["id"]
    message_id = str(message["message_id"])

    # Show main menu when user sends /start
    if text == "/start":
        send_menu(chat_id)
        return jsonify({"ok": True})

    # -----------------------------------------------
    # INPUT C2 FLOW
    # Processes 3-line input and saves to Google Sheet
    # -----------------------------------------------
    lines = text.split("\n")
    if len(lines) < 3:
        return jsonify({"ok": True})

    c2      = lines[0].strip()
    likes   = lines[1].lower().replace("likes:", "").strip()
    reached = lines[2].lower().replace("reached:", "").strip()

    # Save to Google Sheet
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
# Processes inline keyboard button presses
# ============================================
def handle_callback(callback):
    chat_id     = callback["message"]["chat"]["id"]
    data        = callback["data"]
    callback_id = callback["id"]

    # Answer callback to remove loading spinner
    answer_callback(callback_id)

    if data == "followers":
        subscribers = get_youtube_subscribers()
        send_message(chat_id,
            f"📊 Radical Revolution Followers\n\n"
            f"▶️ YouTube: {subscribers} subscribers\n\n"
            f"More platforms coming soon!"
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
# Checks for duplicates using message_id first,
# then saves new entry to the sheet.
# ============================================
def save_to_sheet(message_id, c2, likes, reached):
    try:
        gc    = get_sheets_client()
        sheet = gc.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
        rows  = sheet.get_all_values()

        # Add header if sheet is empty
        if len(rows) == 0:
            sheet.append_row(["Message ID", "Date Added", "C2 Text", "Likes", "Reached", "Platform"])
            rows = sheet.get_all_values()

        # Check for duplicate message_id
        for row in rows[1:]:
            if str(row[0]).strip() == message_id:
                return "duplicate"

        # Check for duplicate C2 + Likes + Reached
        for row in rows[1:]:
            if (str(row[2]).strip() == c2 and
                str(row[3]).strip() == likes and
                str(row[4]).strip() == reached):
                return "duplicate"

        # Save new entry
        sheet.append_row([
            message_id,
            datetime.now().strftime("%m/%d/%Y"),
            c2,
            likes,
            reached,
            "Facebook"
        ])
        return "saved"

    except Exception as e:
        print(f"Sheet error: {e}")
        return "error"


# ============================================
# GET YOUTUBE SUBSCRIBERS
# Fetches exact subscriber count from YouTube
# Data API v3.
# ============================================
def get_youtube_subscribers():
    try:
        url    = f"https://www.googleapis.com/youtube/v3/channels?part=statistics&id={YT_CHANNEL}&key={YT_API_KEY}"
        result = requests.get(url).json()
        count  = result["items"][0]["statistics"]["subscriberCount"]
        return count
    except Exception as e:
        print(f"YouTube error: {e}")
        return "unavailable"


# ============================================
# GOOGLE SHEETS CLIENT
# Authenticates using service account credentials
# stored as environment variable in Railway.
# ============================================
def get_sheets_client():
    creds_json = os.environ.get("GOOGLE_CREDS")
    creds_dict = json.loads(creds_json)
    scopes     = ["https://www.googleapis.com/auth/spreadsheets"]
    creds      = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)


# ============================================
# SEND MENU
# Sends the main menu with 2 inline buttons.
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
# Sends a plain text message to a Telegram chat.
# ============================================
def send_message(chat_id, text):
    requests.post(f"{TELEGRAM_API}/sendMessage", json={
        "chat_id": chat_id,
        "text": text
    })


# ============================================
# ANSWER CALLBACK
# Removes the loading spinner on inline buttons.
# ============================================
def answer_callback(callback_id):
    requests.post(f"{TELEGRAM_API}/answerCallbackQuery", json={
        "callback_query_id": callback_id
    })


# ============================================
# HEALTH CHECK
# Railway uses this to confirm the app is running.
# ============================================
@app.route("/", methods=["GET"])
def health():
    return "Ria Bot is running!", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
