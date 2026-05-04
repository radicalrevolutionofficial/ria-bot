import requests
from config import BOT_TOKEN, ADMIN_CHAT_ID

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"


# ============================================
# SEND MESSAGE
# Sends a plain text message to a chat.
# ============================================
def send_message(chat_id, text):
    requests.post(f"{TELEGRAM_API}/sendMessage", json={
        "chat_id": chat_id,
        "text":    text
    })


# ============================================
# SEND MENU
# Sends the main menu with inline buttons.
# ============================================
def send_menu(chat_id):
    requests.post(f"{TELEGRAM_API}/sendMessage", json={
        "chat_id": chat_id,
        "text":    "👋 Welcome to Ria Bot!\n\nWhat do you want to do?",
        "reply_markup": {
            "inline_keyboard": [[
                {"text": "📊 Followers", "callback_data": "followers"},
                {"text": "✍️ Input C2",  "callback_data": "input_c2"}
            ]]
        }
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
# NOTIFY ADMIN
# Sends a message to the admin chat only.
# ============================================
def notify(text):
    if not ADMIN_CHAT_ID:
        print(f"No ADMIN_CHAT_ID set. Message: {text}")
        return
    send_message(ADMIN_CHAT_ID, text)


# ============================================
# SEND INPUT C2 INSTRUCTIONS
# ============================================
def send_input_c2_instructions(chat_id):
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