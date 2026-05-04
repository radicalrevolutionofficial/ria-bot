import requests
from datetime import datetime, timedelta
from config import FB_PAGE_TOKEN, FB_PAGE_ID, PH_TZ
from telegram import notify


# ============================================
# CHECK SCHEDULED POSTS FOR NEXT 3 DAYS
# Fetches scheduled posts from Facebook Page
# and notifies admin if less than 4 found.
# ============================================
def check_scheduled_posts():
    try:
        now        = datetime.now(PH_TZ)
        three_days = now + timedelta(days=3)

        # Fetch scheduled posts from Facebook
        url = (
            f"https://graph.facebook.com/{FB_PAGE_ID}/scheduled_posts"
            f"?fields=id,message,scheduled_publish_time"
            f"&access_token={FB_PAGE_TOKEN}"
        )
        result = requests.get(url).json()
        posts  = result.get("data", [])

        # Filter posts scheduled in the next 3 days
        upcoming = []
        for post in posts:
            scheduled_time = post.get("scheduled_publish_time")
            if not scheduled_time:
                continue
            try:
                from datetime import timezone
                post_time = datetime.fromtimestamp(scheduled_time, tz=PH_TZ)
                if now <= post_time <= three_days:
                    upcoming.append(post)
            except:
                continue

        count = len(upcoming)

        if count < 4:
            notify(
                f"⚠️ Content Schedule Alert!\n\n"
                f"📅 Next 3 days: {now.strftime('%m/%d/%Y')} — {three_days.strftime('%m/%d/%Y')}\n\n"
                f"You only have {count} content scheduled on Facebook.\n"
                f"Please schedule at least 4 posts to stay consistent! 🙏\n\n"
                f"📌 Go to Meta Business Suite to schedule more."
            )
        else:
            notify(
                f"✅ Content Schedule OK!\n\n"
                f"📅 Next 3 days: {now.strftime('%m/%d/%Y')} — {three_days.strftime('%m/%d/%Y')}\n\n"
                f"You have {count} content scheduled on Facebook. Keep it up! 💪"
            )

        return count

    except Exception as e:
        import traceback
        print(f"Scheduler error: {e}")
        print(traceback.format_exc())
        notify(f"❌ Error checking scheduled posts: {e}")
        return 0
