import os
import json
import requests
from flask import Flask, request, jsonify, redirect
from google.oauth2.service_account import Credentials
import gspread
from datetime import datetime, timezone, timedelta

app = Flask(__name__)

# ============================================
# CONFIGURATION
# ============================================
BOT_TOKEN       = os.environ.get("BOT_TOKEN")
SHEET_ID        = os.environ.get("SHEET_ID")
SHEET_NAME      = os.environ.get("SHEET_NAME", "Sheet1")
TESTING_SHEET   = "testing C2"
BOT_ID          = int(os.environ.get("BOT_ID", "8726579895"))
ADMIN_CHAT_ID   = os.environ.get("ADMIN_CHAT_ID")
YT_API_KEY      = os.environ.get("YT_API_KEY")
YT_CHANNEL      = os.environ.get("YT_CHANNEL")
FB_PAGE_TOKEN   = os.environ.get("FB_PAGE_TOKEN")
FB_PAGE_ID      = os.environ.get("FB_PAGE_ID")
IG_ACCOUNT_ID   = os.environ.get("IG_ACCOUNT_ID")
THREADS_TOKEN   = os.environ.get("THREADS_TOKEN")
THREADS_USER_ID = os.environ.get("THREADS_USER_ID")
LIKES_THRESHOLD    = 10000
DAYS_BEFORE_DELETE = 7

APP_ID       = "1619028032581015"
APP_SECRET   = "9d84a34bc4cbbfaebc7c07ea1d977114"
REDIRECT_URI = "https://ria-bot-16zn.onrender.com/threads-callback"
PH_TZ        = timezone(timedelta(hours=8))

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"


def get_google_creds():
    creds_json = os.environ.get("GOOGLE_CREDS")
    creds_dict = json.loads(creds_json)
    scopes     = ["https://www.googleapis.com/auth/spreadsheets"]
    return Credentials.from_service_account_info(creds_dict, scopes=scopes)


def get_sheets_client():
    return gspread.authorize(get_google_creds())


# ============================================
# EVERY 5 MINUTES JOB
#
# testing C2 columns:
#   Content ID | Date & Time Posted | C2 Text
#   | Reactions | Comments | Shares | Image URL
#
# Sheet1 columns:
#   Message ID | Date & Time Added | C2 Text
#   | Reactions | Comments | Shares | Image URL
# ============================================
@app.route("/poll-posts", methods=["GET"])
def poll_posts():
    try:
        gc     = get_sheets_client()
        sheet  = gc.open_by_key(SHEET_ID).worksheet(TESTING_SHEET)
        sheet1 = gc.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
        rows   = sheet.get_all_values()
        rows1  = sheet1.get_all_values()

        if len(rows) == 0:
            sheet.append_row([
                "Content ID", "Date & Time Posted", "C2 Text",
                "Reactions", "Comments", "Shares", "Image URL"
            ])
            rows = sheet.get_all_values()

        if len(rows1) == 0:
            sheet1.append_row([
                "Message ID", "Date & Time Added", "C2 Text",
                "Reactions", "Comments", "Shares", "Image URL"
            ])
            rows1 = sheet1.get_all_values()

        testing_ids = set()
        for row in rows[1:]:
            if row:
                testing_ids.add(str(row[0]).strip())

        sheet1_ids = set()
        for row in rows1[1:]:
            if row:
                sheet1_ids.add(str(row[0]).strip())

        all_known_ids = testing_ids | sheet1_ids

        # ----------------------------------------
        # STEP 1 — Fetch new photo posts from FB
        # ----------------------------------------
        url = (
            f"https://graph.facebook.com/{FB_PAGE_ID}/posts"
            f"?fields=id,message,created_time,"
            f"attachments{{media{{image{{src,width,height}}}},type}}"
            f"&limit=10"
            f"&access_token={FB_PAGE_TOKEN}"
        )
        result = requests.get(url).json()
        posts  = list(reversed(result.get("data", [])))

        for post in posts:
            post_id      = post.get("id", "")
            message      = post.get("message", "")
            created_time = post.get("created_time", "")
            attachments  = post.get("attachments", {}).get("data", [])

            if post_id in all_known_ids:
                continue

            has_photo = any(a.get("type") in ["photo", "album"] for a in attachments)
            if not has_photo:
                continue

            image_url = get_hq_image_url(attachments, post_id)

            try:
                utc_time = datetime.strptime(created_time, "%Y-%m-%dT%H:%M:%S+0000")
                ph_time  = utc_time.replace(tzinfo=timezone.utc).astimezone(PH_TZ)
                formatted_date = ph_time.strftime("%m/%d/%Y %I:%M %p")
            except:
                formatted_date = datetime.now(PH_TZ).strftime("%m/%d/%Y %I:%M %p")

            c2_text                     = message.split("\n")[0].strip()
            reactions, comments, shares = get_post_stats(post_id)

            sheet.append_row([
                post_id, formatted_date, c2_text,
                f"{reactions:,}", f"{comments:,}", f"{shares:,}", image_url
            ])
            all_known_ids.add(post_id)
            testing_ids.add(post_id)

        # ----------------------------------------
        # STEP 2 — Update stats in Sheet1
        # ----------------------------------------
        rows1 = sheet1.get_all_values()
        for i, row in enumerate(rows1[1:], start=2):
            if len(row) < 1 or not row[0].strip():
                continue
            post_id                     = row[0].strip()
            reactions, comments, shares = get_post_stats(post_id)
            sheet1.update_cell(i, 4, f"{reactions:,}")
            sheet1.update_cell(i, 5, f"{comments:,}")
            sheet1.update_cell(i, 6, f"{shares:,}")

        # ----------------------------------------
        # STEP 3 — Check winners and old losers
        # ----------------------------------------
        rows = sheet.get_all_values()
        now  = datetime.now(PH_TZ)

        ids_to_delete = []
        ids_to_sheet1 = []

        for row in rows[1:]:
            if len(row) < 4 or not row[0].strip():
                continue

            post_id    = row[0].strip()
            created_at = row[1].strip()
            c2_text    = row[2].strip()
            image_url  = row[6] if len(row) > 6 else ""

            reactions, comments, shares = get_post_stats(post_id)

            try:
                post_date = datetime.strptime(created_at, "%m/%d/%Y %I:%M %p")
                post_date = post_date.replace(tzinfo=PH_TZ)
                age_days  = (now - post_date).days
            except:
                age_days = 0

            preview = c2_text[:60] + "..." if len(c2_text) > 60 else c2_text

            # Winner — reactions >= 10,000
            if reactions >= LIKES_THRESHOLD:
                if post_id not in sheet1_ids:
                    ids_to_sheet1.append({
                        "post_id":   post_id,
                        "posted_at": created_at,
                        "c2_text":   c2_text,
                        "reactions": reactions,
                        "comments":  comments,
                        "shares":    shares,
                        "image_url": image_url,
                        "preview":   preview
                    })
                ids_to_delete.append(post_id)

            # Loser — older than 7 days
            elif age_days >= DAYS_BEFORE_DELETE:
                notify(
                    f"🗑️ Content deleted from testing C2\n\n"
                    f"📝 \"{preview}\"\n"
                    f"❤️ Only reached {reactions:,} reactions in {age_days} days\n"
                    f"❌ Did not reach {LIKES_THRESHOLD:,} reactions threshold\n"
                    f"🆔 ID: {post_id}"
                )
                ids_to_delete.append(post_id)

        # Save winners to Sheet1 — use original posted_at date & time
        for winner in ids_to_sheet1:
            sheet1.append_row([
                winner["post_id"],
                winner["posted_at"],
                winner["c2_text"],
                f"{winner['reactions']:,}",
                f"{winner['comments']:,}",
                f"{winner['shares']:,}",
                winner["image_url"]
            ])
            sheet1_ids.add(winner["post_id"])
            notify(
                f"🏆 A-RR Winner!\n\n"
                f"📝 \"{winner['preview']}\"\n"
                f"❤️ Reactions: {winner['reactions']:,}\n"
                f"💬 Comments: {winner['comments']:,}\n"
                f"🔁 Shares: {winner['shares']:,}\n\n"
                f"✅ Moved to Sheet1\n"
                f"🖼️ Image URL saved\n"
                f"🆔 ID: {winner['post_id']}"
            )

        # Update reactions for all posts in testing C2
        rows = sheet.get_all_values()
        for i, row in enumerate(rows[1:], start=2):
            if len(row) < 1 or not row[0].strip():
                continue
            post_id                     = row[0].strip()
            reactions, comments, shares = get_post_stats(post_id)
            sheet.update_cell(i, 4, f"{reactions:,}")
            sheet.update_cell(i, 5, f"{comments:,}")
            sheet.update_cell(i, 6, f"{shares:,}")
            image_url = row[6] if len(row) > 6 else ""
            if not image_url:
                img = get_post_image_url_hq(post_id)
                if img:
                    sheet.update_cell(i, 7, img)

        # Delete rows — read fresh, delete from bottom up
        if ids_to_delete:
            rows = sheet.get_all_values()
            rows_to_delete = []
            for i, row in enumerate(rows[1:], start=2):
                if row and str(row[0]).strip() in ids_to_delete:
                    rows_to_delete.append(i)
            for row_num in sorted(rows_to_delete, reverse=True):
                sheet.delete_rows(row_num)

        return f"Done! Updated {len(rows)-1} posts.", 200

    except Exception as e:
        import traceback
        print(f"Poll error: {e}")
        print(traceback.format_exc())
        return f"Error: {e}", 500


def get_post_stats(post_id):
    try:
        url = (
            f"https://graph.facebook.com/{post_id}"
            f"?fields=reactions.summary(true),comments.summary(true),shares"
            f"&access_token={FB_PAGE_TOKEN}"
        )
        result    = requests.get(url).json()
        reactions = result.get("reactions", {}).get("summary", {}).get("total_count", 0)
        comments  = result.get("comments", {}).get("summary", {}).get("total_count", 0)
        shares    = result.get("shares", {}).get("count", 0)
        return reactions, comments, shares
    except:
        return 0, 0, 0


def get_hq_image_url(attachments, post_id):
    try:
        for attachment in attachments:
            media = attachment.get("media", {})
            image = media.get("image", {})
            src   = image.get("src", "")
            if src:
                return src
        return get_post_image_url_hq(post_id)
    except:
        return get_post_image_url_hq(post_id)


def get_post_image_url_hq(post_id):
    try:
        url    = (
            f"https://graph.facebook.com/{post_id}"
            f"?fields=attachments{{media{{image{{src,width,height}}}}}}"
            f"&access_token={FB_PAGE_TOKEN}"
        )
        result      = requests.get(url).json()
        attachments = result.get("attachments", {}).get("data", [])
        for attachment in attachments:
            media = attachment.get("media", {})
            image = media.get("image", {})
            src   = image.get("src", "")
            if src:
                return src
        url2    = f"https://graph.facebook.com/{post_id}?fields=full_picture&access_token={FB_PAGE_TOKEN}"
        result2 = requests.get(url2).json()
        return result2.get("full_picture", "")
    except:
        return ""


def notify(text):
    if not ADMIN_CHAT_ID:
        return
    send_message(ADMIN_CHAT_ID, text)


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


@app.route("/threads-callback")
def threads_callback():
    code = request.args.get("code")
    if not code:
        return "Error: No code received", 400
    response = requests.post("https://graph.threads.net/oauth/access_token", data={
        "client_id": APP_ID, "client_secret": APP_SECRET,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI, "code": code
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
    <p>Add to Render:<br>
    <strong>THREADS_USER_ID</strong> = {user_id}<br>
    <strong>THREADS_TOKEN</strong> = token above</p>
    """


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


def handle_callback(callback):
    chat_id     = callback["message"]["chat"]["id"]
    data        = callback["data"]
    callback_id = callback["id"]
    answer_callback(callback_id)
    if data == "followers":
        fb = get_facebook_followers()
        ig = get_instagram_followers()
        yt = get_youtube_subscribers()
        th = get_threads_followers()
        send_message(chat_id,
            f"📊 Radical Revolution Followers\n\n"
            f"👍 Facebook: {fb}\n"
            f"📸 Instagram: {ig}\n"
            f"🧵 Threads: {th}\n"
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


def save_to_sheet(message_id, c2, likes, reached):
    try:
        gc    = get_sheets_client()
        sheet = gc.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
        rows  = sheet.get_all_values()
        if len(rows) == 0:
            sheet.append_row([
                "Message ID", "Date & Time Added", "C2 Text",
                "Reactions", "Comments", "Shares", "Image URL"
            ])
            rows = sheet.get_all_values()
        for row in rows[1:]:
            if str(row[0]).strip() == message_id:
                return "duplicate"
        for row in rows[1:]:
            if (str(row[2]).strip() == c2 and str(row[3]).strip() == likes):
                return "duplicate"
        sheet.append_row([
            message_id,
            datetime.now(PH_TZ).strftime("%m/%d/%Y %I:%M %p"),
            c2, likes, "", "", ""
        ])
        return "saved"
    except Exception as e:
        import traceback
        print(f"Sheet error: {e}")
        print(traceback.format_exc())
        return "error"


def get_youtube_subscribers():
    try:
        url    = f"https://www.googleapis.com/youtube/v3/channels?part=statistics&id={YT_CHANNEL}&key={YT_API_KEY}"
        result = requests.get(url).json()
        return f"{int(result['items'][0]['statistics']['subscriberCount']):,}"
    except:
        return "unavailable"

def get_facebook_followers():
    try:
        url    = f"https://graph.facebook.com/{FB_PAGE_ID}?fields=followers_count&access_token={FB_PAGE_TOKEN}"
        result = requests.get(url).json()
        return f"{int(result['followers_count']):,}"
    except:
        return "unavailable"

def get_instagram_followers():
    try:
        url    = f"https://graph.facebook.com/{IG_ACCOUNT_ID}?fields=followers_count&access_token={FB_PAGE_TOKEN}"
        result = requests.get(url).json()
        return f"{int(result['followers_count']):,}"
    except:
        return "unavailable"

def get_threads_followers():
    try:
        if not THREADS_TOKEN or not THREADS_USER_ID:
            return "coming soon!"
        url    = f"https://graph.threads.net/v1.0/{THREADS_USER_ID}?fields=followers_count&access_token={THREADS_TOKEN}"
        result = requests.get(url).json()
        return f"{int(result['followers_count']):,}"
    except:
        return "unavailable"

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

def send_message(chat_id, text):
    requests.post(f"{TELEGRAM_API}/sendMessage", json={"chat_id": chat_id, "text": text})

def answer_callback(callback_id):
    requests.post(f"{TELEGRAM_API}/answerCallbackQuery", json={"callback_query_id": callback_id})

@app.route("/", methods=["GET"])
def health():
    return "Ria Bot is running!", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
