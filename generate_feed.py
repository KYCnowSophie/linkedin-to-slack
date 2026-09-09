import re
from urllib.request import Request, urlopen
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

LINKEDIN_URL = "https://www.linkedin.com/company/kycnow/"
USER_AGENT = "Mozilla/5.0"

req = Request(LINKEDIN_URL, headers={"User-Agent": USER_AGENT})
html = urlopen(req).read().decode("utf-8", errors="ignore")

matches = re.findall(r'data-activity-urn="urn:li:activity:(\d+)"', html)

activity_ids = []
seen = set()
for item in matches:
    if item not in seen:
        seen.add(item)
        activity_ids.append(item)

activity_ids = activity_ids[:10]

now = datetime.now(timezone.utc)
pub_date = now.strftime("%a, %d %b %Y %H:%M:%S GMT")

items = []
for activity_id in activity_ids:
    post_url = f"https://www.linkedin.com/feed/update/urn:li:activity:{activity_id}/"
    items.append(f"""
    <item>
      <title>{escape("KYCnow LinkedIn Post")}</title>
      <link>{escape(post_url)}</link>
      <guid>{escape(post_url)}</guid>
      <pubDate>{pub_date}</pubDate>
      <description>{escape(post_url)}</description>
    </item>""")

rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>KYCnow LinkedIn Posts</title>
    <link>{escape(LINKEDIN_URL)}</link>
    <description>Aktuelle LinkedIn-Posts von KYCnow</description>
    <lastBuildDate>{pub_date}</lastBuildDate>
    {''.join(items)}
  </channel>
</rss>
"""

Path("feed.xml").write_text(rss, encoding="utf-8")

print(f"feed.xml erstellt mit {len(activity_ids)} Einträgen.")
for activity_id in activity_ids:
    print(f"https://www.linkedin.com/feed/update/urn:li:activity:{activity_id}/")
