import requests
from config import YT_API_KEY, YT_CHANNEL, FB_PAGE_TOKEN, IG_ACCOUNT_ID, THREADS_TOKEN, THREADS_USER_ID
from facebook import get_facebook_followers

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

def get_youtube_subscribers():
    try:
        url = f"https://www.googleapis.com/youtube/v3/channels?part=statistics&id={YT_CHANNEL}&key={YT_API_KEY}"
        result = requests.get(url).json()
        return f"{int(result['items'][0]['statistics']['subscriberCount']):,}"
    except:
        return "unavailable"

from facebook import get_facebook_followers

def get_instagram_followers():
    try:
        url = f"https://graph.facebook.com/{IG_ACCOUNT_ID}?fields=followers_count&access_token={FB_PAGE_TOKEN}"
        result = requests.get(url).json()
        return f"{int(result['followers_count']):,}"
    except:
        return "unavailable"

def get_threads_followers():
    try:
        if not THREADS_TOKEN or not THREADS_USER_ID:
            return "coming soon!"
        url = f"https://graph.threads.net/v1.0/{THREADS_USER_ID}?fields=followers_count&access_token={THREADS_TOKEN}"
        result = requests.get(url).json()
        return f"{int(result['followers_count']):,}"
    except:
        return "unavailable"