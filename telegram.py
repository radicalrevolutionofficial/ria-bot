import requests
from config import BOT_TOKEN, ADMIN_CHAT_ID

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

def send_message(chat_id, text):
    requests.post(f"{TELEGRAM_API}/sendMessage", json={"chat_id": chat_id, "text": text})

def send_menu(chat_id):
    requests.post(f"{TELEGRAM_API}/sendMessage", json={
        "chat_id": chat_id,
        "text": "👋 Welcome to Ria Bot!\n\nWhat do you want to do?",
        "reply_markup": {
            "inline_keyboard": [[
                {"text": "📊 Followers", "callback_data": "followers"},
                {"text": "✍️ Input C2", "callback_data": "input_c2"}
            ]]
        }
    })

def answer_callback(callback_id):
    requests.post(f"{TELEGRAM_API}/answerCallbackQuery", json={"callback_query_id": callback_id})

def notify(text):
    ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID")
    if not ADMIN_CHAT_ID:
        return
    send_message(ADMIN_CHAT_ID, text)