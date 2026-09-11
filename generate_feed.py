import re
from urllib.request import Request, urlopen
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

LINKEDIN_URL = "https://www.linkedin.com/company/kycnow/"
USER_AGENT = "Mozilla/5.0"
STATE_FILE = Path("last_seen.txt")

req = Request(LINKEDIN_URL, headers={"User-Agent": USER_AGENT})
html = urlopen(req).read().decode("utf-8", errors="ignore")

matches = re.findall(
    r'data-activity-urn="urn:li:activity:(\d+)"',
    html
)

activity_ids = []
seen = set()

for activity_id in matches:
    if activity_id not in seen:
        seen.add(activity_id)
        activity_ids.append(activity_id)

if not activity_ids:
    raise RuntimeError("Keine LinkedIn-Posts gefunden.")

latest_id = activity_ids[0]

# Beim ersten Lauf: aktuellen Stand nur merken.
# Nichts erneut an Slack schicken.
if not STATE_FILE.exists():
    STATE_FILE.write_text(latest_id, encoding="utf-8")
    new_ids = []
else:
    last_seen = STATE_FILE.read_text(encoding="utf-8").strip()

    new_ids = []

    for activity_id in activity_ids:
        if activity_id == last_seen:
            break
        new_ids.append(activity_id)

    STATE_FILE.write_text(latest_id, encoding="utf-8")

now = datetime.now(timezone.utc)
pub_date = now.strftime("%a, %d %b %Y %H:%M:%S GMT")

items = []

for activity_id in reversed(new_ids):
    post_url = (
        f"https://www.linkedin.com/feed/update/"
        f"urn:li:activity:{activity_id}/"
    )

    items.append(f"""
    <item>
      <title>KYCnow LinkedIn Post</title>
      <link>{escape(post_url)}</link>
      <guid isPermaLink="true">{escape(post_url)}</guid>
      <pubDate>{pub_date}</pubDate>
      <description>{escape(post_url)}</description>
    </item>
    """)

rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>KYCnow LinkedIn Posts</title>
    <link>{escape(LINKEDIN_URL)}</link>
    <description>Neue LinkedIn-Posts von KYCnow</description>
    <lastBuildDate>{pub_date}</lastBuildDate>
    {''.join(items)}
  </channel>
</rss>
"""

Path("feed.xml").write_text(rss, encoding="utf-8")

print(f"{len(new_ids)} neue Posts gefunden.")
print(f"Aktueller Stand: {latest_id}")
