import os
from datetime import timezone, timedelta

# ============================================
# TELEGRAM
# ============================================
BOT_TOKEN     = os.environ.get("BOT_TOKEN")
BOT_ID        = int(os.environ.get("BOT_ID", "8726579895"))
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID")

# ============================================
# GOOGLE SHEETS
# ============================================
SHEET_ID      = os.environ.get("SHEET_ID")
SHEET_NAME    = os.environ.get("SHEET_NAME", "Sheet1")
TESTING_SHEET = "testing C2"

# ============================================
# FACEBOOK
# ============================================
FB_PAGE_TOKEN = os.environ.get("FB_PAGE_TOKEN")
FB_PAGE_ID    = os.environ.get("FB_PAGE_ID")

# ============================================
# INSTAGRAM
# ============================================
IG_ACCOUNT_ID = os.environ.get("IG_ACCOUNT_ID")

# ============================================
# YOUTUBE
# ============================================
YT_API_KEY = os.environ.get("YT_API_KEY")
YT_CHANNEL = os.environ.get("YT_CHANNEL")

# ============================================
# THREADS
# ============================================
THREADS_TOKEN   = os.environ.get("THREADS_TOKEN")
THREADS_USER_ID = os.environ.get("THREADS_USER_ID")

# ============================================
# META APP (for Threads OAuth)
# ============================================
APP_ID       = "1619028032581015"
APP_SECRET   = "9d84a34bc4cbbfaebc7c07ea1d977114"
REDIRECT_URI = "https://ria-bot-16zn.onrender.com/threads-callback"

# ============================================
# JOB SETTINGS
# ============================================
LIKES_THRESHOLD    = 10000
DAYS_BEFORE_DELETE = 7

# ============================================
# TIMEZONE
# ============================================
PH_TZ = timezone(timedelta(hours=8))