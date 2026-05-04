import requests
from config import (
    FB_PAGE_TOKEN, FB_PAGE_ID,
    IG_ACCOUNT_ID,
    YT_API_KEY, YT_CHANNEL,
    THREADS_TOKEN, THREADS_USER_ID
)


# ============================================
# FACEBOOK PAGE FOLLOWERS
# ============================================
def get_facebook_followers():
    try:
        url    = f"https://graph.facebook.com/{FB_PAGE_ID}?fields=followers_count&access_token={FB_PAGE_TOKEN}"
        result = requests.get(url).json()
        return f"{int(result['followers_count']):,}"
    except:
        return "unavailable"


# ============================================
# INSTAGRAM FOLLOWERS
# ============================================
def get_instagram_followers():
    try:
        url    = f"https://graph.facebook.com/{IG_ACCOUNT_ID}?fields=followers_count&access_token={FB_PAGE_TOKEN}"
        result = requests.get(url).json()
        return f"{int(result['followers_count']):,}"
    except:
        return "unavailable"


# ============================================
# YOUTUBE SUBSCRIBERS
# ============================================
def get_youtube_subscribers():
    try:
        url    = f"https://www.googleapis.com/youtube/v3/channels?part=statistics&id={YT_CHANNEL}&key={YT_API_KEY}"
        result = requests.get(url).json()
        count  = int(result["items"][0]["statistics"]["subscriberCount"])
        return f"{count:,}"
    except:
        return "unavailable"


# ============================================
# THREADS FOLLOWERS
# ============================================
def get_threads_followers():
    try:
        if not THREADS_TOKEN or not THREADS_USER_ID:
            return "coming soon!"
        url    = f"https://graph.threads.net/v1.0/{THREADS_USER_ID}?fields=followers_count&access_token={THREADS_TOKEN}"
        result = requests.get(url).json()
        return f"{int(result['followers_count']):,}"
    except:
        return "unavailable"


# ============================================
# GET ALL FOLLOWERS SUMMARY
# Returns formatted string with all platforms.
# ============================================
def get_all_followers():
    fb = get_facebook_followers()
    ig = get_instagram_followers()
    yt = get_youtube_subscribers()
    th = get_threads_followers()

    return (
        f"📊 Radical Revolution Followers\n\n"
        f"👍 Facebook: {fb}\n"
        f"📸 Instagram: {ig}\n"
        f"🧵 Threads: {th}\n"
        f"▶️ YouTube: {yt}\n\n"
        f"🎵 TikTok — coming soon!"
    )