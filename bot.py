import os
import json
import time
import calendar
from datetime import datetime, timezone, timedelta
import requests
import feedparser

# =================CONFIGURATION=================
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

# Only alert on contests published within the last 7 days
MAX_AGE_DAYS = 7

# Multiple contest sources (Blogs, Aggregators, and Subreddits)
FEEDS = [
    {
        "name": "Sweepstakes Alerts",
        "url": "https://www.google.com/alerts/feeds/12307665313365322185/3885515929942935714"
    }
]

# Optional keyword filter (Leave empty [] to receive all contests)
KEYWORDS = ["cash", "gift card", "trip", "concert", "radio", "car", "tech"]

SEEN_FILE = "seen_contests.json"

HEADERS = {
    "User-Agent": "ContestAlertCloudBot/2.0 (GitHubActions-Runner)"
}
# ===============================================


def load_seen():
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()


def save_seen(seen_set):
    # Keep the last 1,500 entries so the file stays small
    limited_list = list(seen_set)[-1500:]
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(limited_list, f, indent=2)


def is_within_past_days(entry, max_days=7):
    """Verify that the entry was published within the past `max_days`."""
    parsed_time = entry.get("published_parsed") or entry.get("updated_parsed")
    
    if not parsed_time:
        # If no date metadata exists at all, skip it to prevent old announcements
        return False

    # Convert struct_time (UTC) to a timezone-aware datetime
    entry_epoch = calendar.timegm(parsed_time)
    entry_datetime = datetime.fromtimestamp(entry_epoch, tz=timezone.utc)
    
    cutoff_datetime = datetime.now(timezone.utc) - timedelta(days=max_days)
    return entry_datetime >= cutoff_datetime


def matches_keywords(text):
    if not KEYWORDS:
        return True
    text_lower = text.lower()
    return any(keyword.lower() in text_lower for keyword in KEYWORDS)


def send_alert(title, link, source_name):
    payload = {
        "username": "Contest Radar",
        "avatar_url": "https://cdn-icons-png.flaticon.com/512/3112/3112946.png",
        "embeds": [
            {
                "title": title[:250],
                "url": link,
                "description": f"New contest found on **{source_name}**.",
                "color": 3447003,
                "fields": [
                    {"name": "Direct Link", "value": f"[Click here to enter]({link})", "inline": False}
                ],
                "footer": {"text": "Cloud Sweepstakes Notifier (Past 7 Days)"}
            }
        ]
    }
    try:
        res = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        res.raise_for_status()
        print(f"[SENT] ({source_name}) {title}")
    except Exception as e:
        print(f"[ERROR] Discord post failed: {e}")


def main():
    if not DISCORD_WEBHOOK_URL:
        print("[ERROR] DISCORD_WEBHOOK_URL environment variable is missing!")
        exit(1)

    seen = load_seen()
    new_found = False

    for feed_info in FEEDS:
        name = feed_info["name"]
        url = feed_info["url"]
        print(f"Checking {name}...")

        try:
            res = requests.get(url, headers=HEADERS, timeout=15)
            feed = feedparser.parse(res.content)

            for entry in feed.entries:
                entry_id = getattr(entry, "id", entry.link)

                # 1. Skip if already alerted
                if entry_id in seen:
                    continue

                # 2. Skip if older than MAX_AGE_DAYS (filters out 2025/sticky posts)
                if not is_within_past_days(entry, max_days=MAX_AGE_DAYS):
                    continue

                # Record that we have processed this entry
                seen.add(entry_id)
                new_found = True

                # 3. Check keywords
                if matches_keywords(entry.title):
                    send_alert(entry.title, entry.link, name)
                    time.sleep(1)  # Discord rate limit spacing

        except Exception as e:
            print(f"[ERROR] Failed checking {name}: {e}")

    if new_found:
        save_seen(seen)
        print("Updated seen_contests.json.")
    else:
        print("No new contests matching criteria.")


if __name__ == "__main__":
    main()