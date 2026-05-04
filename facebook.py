import requests
from config import FB_PAGE_TOKEN, FB_PAGE_ID

def build_post_link(post_id):
    # post_id format is "PAGE_ID_POST_ID"
    # Extract just the post part after the underscore
    try:
        parts = post_id.split("_")
        post_part = parts[-1]
        return f"https://www.facebook.com/{FB_PAGE_ID}/posts/{post_part}"
    except:
        return f"https://www.facebook.com/{FB_PAGE_ID}"

def get_post_stats(post_id):
    try:
        url = (
            f"https://graph.facebook.com/{post_id}"
            f"?fields=reactions.summary(true),comments.summary(true),shares"
            f"&access_token={FB_PAGE_TOKEN}"
        )
        result = requests.get(url).json()
        reactions = result.get("reactions", {}).get("summary", {}).get("total_count", 0)
        comments = result.get("comments", {}).get("summary", {}).get("total_count", 0)
        shares = result.get("shares", {}).get("count", 0)
        return reactions, comments, shares
    except:
        return 0, 0, 0

def get_facebook_followers():
    try:
        url = f"https://graph.facebook.com/{FB_PAGE_ID}?fields=followers_count&access_token={FB_PAGE_TOKEN}"
        result = requests.get(url).json()
        return f"{int(result['followers_count']):,}"
    except:
        return "unavailable"