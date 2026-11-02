import datetime
import json
import os
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

FEED = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
    {"q": "3D printing when:1d", "hl": "en-US", "gl": "US", "ceid": "US:en"}
)
MODEL = os.environ.get("COHERE_MODEL", "command-r-plus-08-2024")


def fetch_headlines(limit=25):
    with urllib.request.urlopen(FEED, timeout=30) as r:
        root = ET.fromstring(r.read())
    items = []
    for item in root.iter("item"):
        items.append(
            {
                "title": item.findtext("title", ""),
                "link": item.findtext("link", ""),
                "source": item.findtext("source", ""),
            }
        )
        if len(items) >= limit:
            break
    return items


class ParagraphParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_p = False
        self.skip = 0
        self.paras = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "nav", "footer"):
            self.skip += 1
        elif tag == "p" and not self.skip:
            self.in_p = True
            self.paras.append("")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "nav", "footer"):
            self.skip = max(0, self.skip - 1)
        elif tag == "p":
            self.in_p = False

    def handle_data(self, data):
        if self.in_p:
            self.paras[-1] += data


def fetch_article(google_link, max_chars=6000):
    """Return (real_url, text); text is empty if the page can't be read."""
    try:
        from googlenewsdecoder import gnewsdecoder

        decoded = gnewsdecoder(google_link, interval=1)
        url = decoded.get("decoded_url") if decoded.get("status") else google_link
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            html = r.read().decode("utf-8", errors="ignore")
        parser = ParagraphParser()
        parser.feed(html)
        text = "\n\n".join(p.strip() for p in parser.paras if len(p.strip()) > 60)
        return url, text[:max_chars]
    except Exception as e:
        print(f"Article fetch failed: {e}")
        return google_link, ""


def cohere_chat(prompt):
    req = urllib.request.Request(
        "https://api.cohere.com/v2/chat",
        data=json.dumps(
            {
                "model": MODEL,
                "max_tokens": 2000,
                "messages": [{"role": "user", "content": prompt}],
            }
        ).encode(),
        headers={
            "Authorization": f"Bearer {os.environ['COHERE_API_KEY']}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=300) as r:
        data = json.load(r)
    return data["message"]["content"][0]["text"]


def main():
    today = datetime.date.today().isoformat()
    items = fetch_headlines()
    if not items:
        raise SystemExit("No headlines found")
    listing = "\n".join(f"{n}. {i['title']}" for n, i in enumerate(items, 1))
    pick = cohere_chat(
        "Below are numbered Google News headlines about 3D printing. Choose the "
        "single most positive, uplifting one (breakthrough, launch, helpful "
        "application). Reply with only its number.\n\n" + listing
    )
    digits = "".join(c for c in pick if c.isdigit())
    idx = int(digits) - 1 if digits else 0
    item = items[idx] if 0 <= idx < len(items) else items[0]

    url, article = fetch_article(item["link"])
    post = cohere_chat(
        "Write an engaging, positive blog post of 400-600 words in Markdown about "
        "this one news story only, with a title (H1), a short intro, and a few "
        "sections. Do not mention other stories. Use only facts from the headline "
        "and article text below; do not invent quotes or numbers. End with a link "
        "to the source.\n\n"
        f"Headline: {item['title']}\nSource: {item['source']}\nLink: {url}\n\n"
        f"Article text:\n{article or '(unavailable; rely on the headline only)'}"
    )

    os.makedirs("blogs", exist_ok=True)
    path = f"blogs/{today}.md"
    with open(path, "w") as f:
        f.write(post.strip() + "\n")

    with open("issue_body.md", "w") as f:
        f.write(f"Daily 3D printing blog for {today}: `{path}`\n\n---\n\n{post.strip()}\n")
    print(path)


if __name__ == "__main__":
    main()
