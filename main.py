import os
import json
import requests
from flask import Flask, request, jsonify, redirect
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import gspread
from datetime import datetime, timezone, timedelta
import io

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
DRIVE_FOLDER_ID = "1mCEdx7wAxbUGBkAmtgy6XTEbBDtGqDl4"
LIKES_THRESHOLD    = 10000
DAYS_BEFORE_DELETE = 7

APP_ID       = "1619028032581015"
APP_SECRET   = "9d84a34bc4cbbfaebc7c07ea1d977114"
REDIRECT_URI = "https://ria-bot-16zn.onrender.com/threads-callback"
PH_TZ        = timezone(timedelta(hours=8))

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"


# ============================================
# GOOGLE CREDENTIALS HELPER
# ============================================
def get_google_creds():
    creds_json = os.environ.get("GOOGLE_CREDS")
    creds_dict = json.loads(creds_json)
    scopes     = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    return Credentials.from_service_account_info(creds_dict, scopes=scopes)


# ============================================
# GOOGLE SHEETS CLIENT
# ============================================
def get_sheets_client():
    return gspread.authorize(get_google_creds())


# ============================================
# HOURLY POLL JOB
# Runs every hour via cron-job.org.
# Fetches latest photo posts from Facebook Page
# and saves new ones to testing C2 sheet.
# No webhook or app review needed.
# ============================================
@app.route("/poll-posts", methods=["GET"])
def poll_posts():
    try:
        gc    = get_sheets_client()
        sheet = gc.open_by_key(SHEET_ID).worksheet(TESTING_SHEET)
        rows  = sheet.get_all_values()

        # Add header if sheet is empty
        if len(rows) == 0:
            sheet.append_row([
                "Content ID", "Date & Time Posted",
                "C2 Text", "Likes", "Reached"
            ])
            rows = sheet.get_all_values()

        # Get existing post IDs to avoid duplicates
        existing_ids = set()
        for row in rows[1:]:
            if row:
                existing_ids.add(str(row[0]).strip())

        # Fetch latest photo posts from Facebook Page
        url = (
            f"https://graph.facebook.com/{FB_PAGE_ID}/posts"
            f"?fields=id,message,created_time,attachments"
            f"&limit=10"
            f"&access_token={FB_PAGE_TOKEN}"
        )
        result = requests.get(url).json()
        posts  = result.get("data", [])

        new_count = 0
        for post in posts:
            post_id     = post.get("id", "")
            message     = post.get("message", "")
            created_time = post.get("created_time", "")
            attachments  = post.get("attachments", {}).get("data", [])

            # Skip if already in sheet
            if post_id in existing_ids:
                continue

            # Only process posts with photo attachments
            has_photo = any(
                a.get("type") in ["photo", "album"] 
                for a in attachments
            )
            if not has_photo:
                continue

            # Format date to PH time
            try:
                utc_time = datetime.strptime(created_time, "%Y-%m-%dT%H:%M:%S+0000")
                ph_time  = utc_time.replace(tzinfo=timezone.utc).astimezone(PH_TZ)
                formatted_date = ph_time.strftime("%m/%d/%Y %I:%M %p")
            except:
                formatted_date = datetime.now(PH_TZ).strftime("%m/%d/%Y %I:%M %p")

            # Get initial likes and reached
            likes, reached = get_post_stats(post_id)

            # Save to testing C2
            sheet.append_row([
                post_id,
                formatted_date,
                message,
                likes,
                reached
            ])
            existing_ids.add(post_id)
            new_count += 1

        return f"Poll done! {new_count} new posts added.", 200

    except Exception as e:
        import traceback
        print(f"Poll error: {e}")
        print(traceback.format_exc())
        return f"Error: {e}", 500


# ============================================
# GET POST STATS FROM FACEBOOK
# ============================================
def get_post_stats(post_id):
    try:
        url    = (
            f"https://graph.facebook.com/{post_id}"
            f"?fields=likes.summary(true),insights.metric(post_impressions_unique)"
            f"&access_token={FB_PAGE_TOKEN}"
        )
        result  = requests.get(url).json()
        likes   = result.get("likes", {}).get("summary", {}).get("total_count", 0)
        reached = 0
        insights = result.get("insights", {}).get("data", [])
        for insight in insights:
            if insight.get("name") == "post_impressions_unique":
                reached = insight.get("values", [{}])[-1].get("value", 0)
        return likes, reached
    except Exception as e:
        print(f"Post stats error: {e}")
        return 0, 0


# ============================================
# DAILY 7AM JOB
# Updates all posts, moves winners to Sheet1,
# saves images to Drive, deletes old losers.
# Notifies admin on Telegram for wins and deletes.
# ============================================
@app.route("/daily-job", methods=["GET"])
def daily_job():
    try:
        gc            = get_sheets_client()
        testing       = gc.open_by_key(SHEET_ID).worksheet(TESTING_SHEET)
        sheet1        = gc.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
        rows          = testing.get_all_values()
        drive_service = build("drive", "v3", credentials=get_google_creds())

        if len(rows) <= 1:
            return "No posts to process", 200

        rows_to_delete = []
        now = datetime.now(PH_TZ)

        for i, row in enumerate(rows[1:], start=2):
            if len(row) < 5:
                continue

            post_id    = row[0].strip()
            created_at = row[1].strip()
            c2_text    = row[2].strip()

            # Update likes and reached
            likes, reached = get_post_stats(post_id)
            testing.update_cell(i, 4, likes)
            testing.update_cell(i, 5, reached)

            # Check post age
            try:
                post_date = datetime.strptime(created_at, "%m/%d/%Y %I:%M %p")
                post_date = post_date.replace(tzinfo=PH_TZ)
                age_days  = (now - post_date).days
            except:
                age_days = 0

            preview = c2_text[:60] + "..." if len(c2_text) > 60 else c2_text

            # Winner — likes >= 10,000
            if likes >= LIKES_THRESHOLD:
                # Save to Sheet1
                sheet1_rows = sheet1.get_all_values()
                if len(sheet1_rows) == 0:
                    sheet1.append_row(["Message ID", "Date Added", "C2 Text", "Likes", "Reached", "Platform"])
                sheet1.append_row([
                    post_id,
                    now.strftime("%m/%d/%Y"),
                    c2_text,
                    likes,
                    reached,
                    "Facebook"
                ])

                # Save image to Google Drive
                save_image_to_drive(post_id, drive_service)

                # Notify admin — winner!
                notify(
                    f"🏆 A-RR Winner!\n\n"
                    f"📝 \"{preview}\"\n"
                    f"👍 Likes: {likes:,}\n"
                    f"👁️ Reached: {reached:,}\n\n"
                    f"✅ Moved to Sheet1 (A-RR database)\n"
                    f"🖼️ Image saved to Google Drive\n"
                    f"🆔 ID: {post_id}"
                )

                rows_to_delete.append(i)

            # Loser — older than 7 days
            elif age_days >= DAYS_BEFORE_DELETE:
                notify(
                    f"🗑️ Content deleted from testing C2\n\n"
                    f"📝 \"{preview}\"\n"
                    f"👍 Only reached {likes:,} likes in {age_days} days\n"
                    f"❌ Did not reach {LIKES_THRESHOLD:,} likes threshold\n"
                    f"🆔 ID: {post_id}"
                )

                rows_to_delete.append(i)

        # Delete rows in reverse order
        for row_num in sorted(rows_to_delete, reverse=True):
            testing.delete_rows(row_num)

        return f"Daily job done! Processed {len(rows) - 1} posts.", 200

    except Exception as e:
        import traceback
        print(f"Daily job error: {e}")
        print(traceback.format_exc())
        return f"Error: {e}", 500


# ============================================
# SAVE IMAGE TO GOOGLE DRIVE
# ============================================
def save_image_to_drive(post_id, drive_service):
    try:
        url    = f"https://graph.facebook.com/{post_id}?fields=full_picture&access_token={FB_PAGE_TOKEN}"
        result = requests.get(url).json()
        image_url = result.get("full_picture")

        if not image_url:
            print(f"No image found for post {post_id}")
            return

        img_response = requests.get(image_url)
        img_data     = img_response.content
        img_stream   = io.BytesIO(img_data)

        file_metadata = {
            "name":    post_id,
            "parents": [DRIVE_FOLDER_ID]
        }
        media = MediaIoBaseUpload(img_stream, mimetype="image/jpeg")
        drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id"
        ).execute()

        print(f"Image saved to Drive for post {post_id}")

    except Exception as e:
        print(f"Drive upload error: {e}")


# ============================================
# NOTIFY ADMIN ON TELEGRAM
# ============================================
def notify(text):
    if not ADMIN_CHAT_ID:
        print(f"No ADMIN_CHAT_ID set. Message: {text}")
        return
    send_message(ADMIN_CHAT_ID, text)


# ============================================
# THREADS SETUP PAGE
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
# THREADS CALLBACK
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
        return f"Error getting token: {data}", 400

    short_token = data["access_token"]
    user_id     = data["user_id"]

    ll_response = requests.get(
        f"https://graph.threads.net/access_token"
        f"?grant_type=th_exchange_token"
        f"&client_secret={APP_SECRET}"
        f"&access_token={short_token}"
    )
    ll_data    = ll_response.json()
    long_token = ll_data.get("access_token", short_token)

    return f"""
    <h2>✅ Threads Connected!</h2>
    <p><strong>User ID:</strong> {user_id}</p>
    <p><strong>Long-lived Token:</strong><br>
    <textarea rows="4" cols="80">{long_token}</textarea></p>
    <p>Add to Render environment variables:<br>
    <strong>THREADS_USER_ID</strong> = {user_id}<br>
    <strong>THREADS_TOKEN</strong> = (the token above)</p>
    """


# ============================================
# TELEGRAM WEBHOOK ENDPOINT
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


# ============================================
# SAVE TO SHEET1 (A-RR DATABASE)
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
# GET THREADS FOLLOWERS
# ============================================
def get_threads_followers():
    try:
        if not THREADS_TOKEN or not THREADS_USER_ID:
            return "coming soon!"
        url    = f"https://graph.threads.net/v1.0/{THREADS_USER_ID}?fields=followers_count&access_token={THREADS_TOKEN}"
        result = requests.get(url).json()
        count  = int(result["followers_count"])
        return f"{count:,}"
    except Exception as e:
        print(f"Threads error: {e}")
        return "unavailable"


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
