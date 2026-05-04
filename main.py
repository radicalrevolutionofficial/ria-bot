import os
import requests
from flask import Flask, request, jsonify, redirect
from datetime import datetime

from config import BOT_ID, APP_ID, APP_SECRET, REDIRECT_URI, PH_TZ
from telegram import send_message, send_menu, answer_callback, notify
from socials import get_all_followers
from sheets import save_manual_input
from jobs import run_poll

app = Flask(__name__)


# ============================================
# HEALTH CHECK
# Render uses this to confirm app is running.
# ============================================
@app.route("/", methods=["GET"])
def health():
    return "Ria Bot is running!", 200


# ============================================
# EVERY 5 MINUTES POLL JOB
# Called by cron-job.org every 5 minutes.
# ============================================
@app.route("/poll-posts", methods=["GET"])
def poll_posts():
    try:
        count = run_poll()
        return f"Done! Updated {count} posts.", 200
    except Exception as e:
        import traceback
        print(f"Poll error: {e}")
        print(traceback.format_exc())
        return f"Error: {e}", 500


# ============================================
# TELEGRAM WEBHOOK
# Receives all Telegram updates.
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
    if sender.get("id") == BOT_ID:
        return jsonify({"ok": True})
    if sender.get("is_bot"):
        return jsonify({"ok": True})

    text       = message["text"].strip()
    chat_id    = message["chat"]["id"]
    message_id = str(message["message_id"])

    # Show main menu
    if text == "/start":
        send_menu(chat_id)
        return jsonify({"ok": True})

    # Handle Input C2 — 3 lines format
    lines = text.split("\n")
    if len(lines) < 3:
        return jsonify({"ok": True})

    c2      = lines[0].strip()
    likes   = lines[1].lower().replace("likes:", "").strip()
    reached = lines[2].lower().replace("reached:", "").strip()

    date_time = datetime.now(PH_TZ).strftime("%m/%d/%Y %I:%M %p")
    result    = save_manual_input(message_id, date_time, c2, likes)

    if result == "duplicate":
        send_message(chat_id, "⚠️ Already exists in the database!")
    elif result == "saved":
        send_message(chat_id, "✅ Added to the database!")
    else:
        send_message(chat_id, "❌ Error saving. Please try again.")

    return jsonify({"ok": True})


# ============================================
# HANDLE INLINE BUTTON CLICKS
# ============================================
def handle_callback(callback):
    chat_id     = callback["message"]["chat"]["id"]
    data        = callback["data"]
    callback_id = callback["id"]

    answer_callback(callback_id)

    if data == "followers":
        send_message(chat_id, get_all_followers())

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
# THREADS OAUTH SETUP PAGE
# Visit this URL to authorize Threads access.
# ============================================
@app.route("/threads-setup")
def threads_setup():
    auth_url = (
        f"https://threads.net/oauth/authorize"
        f"?client_id={APP_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&scope=threads_basic"
        f"&response_type=code"
    )
    return redirect(auth_url)


# ============================================
# THREADS OAUTH CALLBACK
# Exchanges auth code for long-lived token.
# ============================================
@app.route("/threads-callback")
def threads_callback():
    code = request.args.get("code")
    if not code:
        return "Error: No code received", 400

    response = requests.post("https://graph.threads.net/oauth/access_token", data={
        "client_id":     APP_ID,
        "client_secret": APP_SECRET,
        "grant_type":    "authorization_code",
        "redirect_uri":  REDIRECT_URI,
        "code":          code
    })
    data = response.json()
    if "access_token" not in data:
        return f"Error: {data}", 400

    short_token = data["access_token"]
    user_id     = data["user_id"]

    ll_response = requests.get(
        f"https://graph.threads.net/access_token"
        f"?grant_type=th_exchange_token"
        f"&client_secret={APP_SECRET}"
        f"&access_token={short_token}"
    )
    long_token = ll_response.json().get("access_token", short_token)

    return f"""
    <h2>✅ Threads Connected!</h2>
    <p><strong>User ID:</strong> {user_id}</p>
    <p><strong>Token:</strong><br>
    <textarea rows="4" cols="80">{long_token}</textarea></p>
    <p>Add to Render environment variables:<br>
    <strong>THREADS_USER_ID</strong> = {user_id}<br>
    <strong>THREADS_TOKEN</strong> = token above</p>
    """


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# ============================================
# MORNING SCHEDULE CHECK
# Called by cron-job.org every morning at 7AM.
# Checks FB scheduled posts for next 3 days.
# ============================================
@app.route("/check-schedule", methods=["GET"])
def check_schedule():
    try:
        from scheduler import check_scheduled_posts
        count = check_scheduled_posts()
        return f"Schedule check done! {count} posts found in next 3 days.", 200
    except Exception as e:
        return f"Error: {e}", 500
