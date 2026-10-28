import os
import json
import time
import requests
import feedparser

# 1. Pull the secret from GitHub Actions Environment Variables
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

# 2. Feeds to monitor
FEEDS = [
    {
        "name": "r/Sweepstakes",
        "url": "https://www.reddit.com/r/sweepstakes/new/.rss"
    }
]

# 3. Optional keywords (leave empty [] for all contests)
KEYWORDS = ["cash", "gift card", "trip", "concert", "radio", "tech"]

SEEN_FILE = "seen_contests.json"

HEADERS = {
    # Custom User-Agent so feeds do not block GitHub's cloud IP addresses
    "User-Agent": "ContestAlertCloudBot/1.0 (GitHubActions-Runner)"
}

def load_seen():
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()

def save_seen(seen_set):
    # Keep only the last 1,000 entries so the file doesn't grow indefinitely
    limited_list = list(seen_set)[-1000:]
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(limited_list, f, indent=2)

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
                "description": f"New match found on **{source_name}**.",
                "color": 3447003,
                "fields": [
                    {"name": "Direct Link", "value": f"[Click here to enter]({link})", "inline": False}
                ],
                "footer": {"text": "Cloud Sweepstakes Notifier"}
            }
        ]
    }
    try:
        res = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        res.raise_for_status()
        print(f"[SENT] {title}")
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

                if entry_id not in seen:
                    seen.add(entry_id)
                    new_found = True

                    if matches_keywords(entry.title):
                        send_alert(entry.title, entry.link, name)
                        time.sleep(1) # Prevent Discord rate limits

        except Exception as e:
            print(f"[ERROR] Failed checking {name}: {e}")

    if new_found:
        save_seen(seen)
        print("Updated seen_contests.json successfully.")
    else:
        print("No new contests found.")

if __name__ == "__main__":
    main()