import re
from urllib.request import Request, build_opener, HTTPCookieProcessor
from urllib.error import HTTPError, URLError
from http.cookiejar import CookieJar
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

LINKEDIN_URL = "https://www.linkedin.com/company/kycnow/"
LINKEDIN_URLS = [
    "https://www.linkedin.com/company/kycnow/",
    "https://de.linkedin.com/company/kycnow/",
    "https://www.linkedin.com/company/kycnow/posts/",
]
STATE_FILE = Path("last_seen.txt")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/141.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}

ACTIVITY_PATTERN = re.compile(
    r'data-activity-urn="urn:li:activity:(\d+)"'
)


def fetch_linkedin_html():
    opener = build_opener(HTTPCookieProcessor(CookieJar()))

    # Eine normale LinkedIn-Startseite zuerst aufrufen, damit öffentliche
    # Gast-Cookies gesetzt werden können.
    try:
        opener.open(
            Request("https://www.linkedin.com/", headers=HEADERS),
            timeout=20,
        ).read(1024)
    except Exception as exc:
        print(f"LinkedIn Startseite nicht nutzbar: {exc}")

    errors = []

    for url in LINKEDIN_URLS:
        try:
            request_headers = dict(HEADERS)
            request_headers["Referer"] = "https://www.linkedin.com/"
            response = opener.open(
                Request(url, headers=request_headers),
                timeout=30,
            )
            html = response.read().decode("utf-8", errors="ignore")

            found = ACTIVITY_PATTERN.findall(html)
            print(
                f"Abruf erfolgreich: {url} "
                f"(HTTP {response.status}, {len(html)} Zeichen, "
                f"{len(found)} Post-Marker)"
            )

            if found:
                return html

            errors.append(f"{url}: Seite geladen, aber keine Post-Marker gefunden")

        except HTTPError as exc:
            errors.append(f"{url}: HTTP {exc.code} {exc.reason}")
        except URLError as exc:
            errors.append(f"{url}: Netzwerkfehler {exc.reason}")
        except Exception as exc:
            errors.append(f"{url}: {type(exc).__name__}: {exc}")

    raise RuntimeError(
        "LinkedIn konnte nicht ausgelesen werden. "
        + " | ".join(errors)
    )


html = fetch_linkedin_html()
matches = ACTIVITY_PATTERN.findall(html)

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
if not STATE_FILE.exists():
    STATE_FILE.write_text(latest_id, encoding="utf-8")
    new_ids = []
else:
    last_seen = STATE_FILE.read_text(encoding="utf-8").strip()

    if last_seen in activity_ids:
        new_ids = []
        for activity_id in activity_ids:
            if activity_id == last_seen:
                break
            new_ids.append(activity_id)
    elif latest_id != last_seen:
        # Nach einer längeren Störung nicht alle alten Beiträge nach Slack
        # schicken. Nur den aktuellsten noch unbekannten Beitrag übernehmen.
        print(
            "Der zuletzt bekannte Post ist nicht mehr in der öffentlichen "
            "LinkedIn-Liste. Es wird nur der aktuellste Post übernommen."
        )
        new_ids = [latest_id]
    else:
        new_ids = []

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
