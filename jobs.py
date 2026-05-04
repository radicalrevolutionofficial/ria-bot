from datetime import datetime, timezone
from config import PH_TZ, LIKES_THRESHOLD, DAYS_BEFORE_DELETE
from facebook import fetch_latest_posts, has_photo, get_post_stats, build_post_link
from sheets import (
    get_worksheets, ensure_testing_headers, ensure_sheet1_headers,
    get_all_ids, save_to_testing, save_to_sheet1,
    batch_update_stats, update_post_link, delete_rows_by_ids
)
from telegram import notify


def run_poll():
    sheet, sheet1 = get_worksheets()
    rows          = ensure_testing_headers(sheet)
    rows1         = ensure_sheet1_headers(sheet1)

    testing_ids   = get_all_ids(rows)
    sheet1_ids    = get_all_ids(rows1)
    all_known_ids = testing_ids | sheet1_ids

    # STEP 1 — Fetch new photo posts
    posts = list(reversed(fetch_latest_posts()))

    for post in posts:
        post_id      = post.get("id", "")
        message      = post.get("message", "")
        created_time = post.get("created_time", "")
        attachments  = post.get("attachments", {}).get("data", [])

        if post_id in all_known_ids:
            continue

        if not has_photo(attachments):
            continue

        post_link = build_post_link(post_id)

        try:
            utc_time = datetime.strptime(created_time, "%Y-%m-%dT%H:%M:%S+0000")
            ph_time  = utc_time.replace(tzinfo=timezone.utc).astimezone(PH_TZ)
            formatted_date = ph_time.strftime("%m/%d/%Y %I:%M %p")
        except:
            formatted_date = datetime.now(PH_TZ).strftime("%m/%d/%Y %I:%M %p")

        c2_text                     = message.split("\n")[0].strip()
        reactions, comments, shares = get_post_stats(post_id)

        save_to_testing(
            sheet, post_id, formatted_date, c2_text,
            reactions, comments, shares, post_link
        )
        all_known_ids.add(post_id)
        testing_ids.add(post_id)

    # STEP 2 — Batch update stats in Sheet1
    rows1    = sheet1.get_all_values()
    updates1 = []
    for i, row in enumerate(rows1[1:], start=2):
        if len(row) < 1 or not row[0].strip():
            continue
        post_id                     = row[0].strip()
        reactions, comments, shares = get_post_stats(post_id)
        updates1.append((i, reactions, comments, shares))
        if not (row[6] if len(row) > 6 else ""):
            update_post_link(sheet1, i, build_post_link(post_id))
    batch_update_stats(sheet1, updates1)

    # STEP 3 — Check winners and old losers
    rows          = sheet.get_all_values()
    now           = datetime.now(PH_TZ)
    ids_to_delete = []
    ids_to_sheet1 = []
    updates       = []

    for i, row in enumerate(rows[1:], start=2):
        if len(row) < 4 or not row[0].strip():
            continue

        post_id    = row[0].strip()
        created_at = row[1].strip()
        c2_text    = row[2].strip()
        post_link  = row[6] if len(row) > 6 else build_post_link(post_id)

        reactions, comments, shares = get_post_stats(post_id)
        updates.append((i, reactions, comments, shares))

        try:
            post_date = datetime.strptime(created_at, "%m/%d/%Y %I:%M %p")
            post_date = post_date.replace(tzinfo=PH_TZ)
            age_days  = (now - post_date).days
        except:
            age_days = 0

        preview = c2_text[:60] + "..." if len(c2_text) > 60 else c2_text

        if reactions >= LIKES_THRESHOLD:
            if post_id not in sheet1_ids:
                ids_to_sheet1.append({
                    "post_id":   post_id,
                    "posted_at": created_at,
                    "c2_text":   c2_text,
                    "reactions": reactions,
                    "comments":  comments,
                    "shares":    shares,
                    "post_link": post_link,
                    "preview":   preview
                })
            ids_to_delete.append(post_id)

        elif age_days >= DAYS_BEFORE_DELETE:
            notify(
                f"🗑️ Content deleted from testing C2\n\n"
                f"📝 \"{preview}\"\n"
                f"❤️ Only reached {reactions:,} reactions in {age_days} days\n"
                f"❌ Did not reach {LIKES_THRESHOLD:,} reactions threshold\n"
                f"🔗 {post_link}\n"
                f"🆔 ID: {post_id}"
            )
            ids_to_delete.append(post_id)

    # Batch update testing C2 stats
    batch_update_stats(sheet, updates)

    # Save winners to Sheet1
    for winner in ids_to_sheet1:
        save_to_sheet1(
            sheet1,
            winner["post_id"], winner["posted_at"], winner["c2_text"],
            winner["reactions"], winner["comments"],
            winner["shares"], winner["post_link"]
        )
        sheet1_ids.add(winner["post_id"])
        notify(
            f"🏆 A-RR Winner!\n\n"
            f"📝 \"{winner['preview']}\"\n"
            f"❤️ Reactions: {winner['reactions']:,}\n"
            f"💬 Comments: {winner['comments']:,}\n"
            f"🔁 Shares: {winner['shares']:,}\n\n"
            f"✅ Moved to Sheet1\n"
            f"🔗 {winner['post_link']}\n"
            f"🆔 ID: {winner['post_id']}"
        )

    # Delete losers and winners from testing C2
    delete_rows_by_ids(sheet, ids_to_delete)

    return len(rows) - 1
