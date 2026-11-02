import datetime
import json
import os
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

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


def cohere_chat(prompt):
    req = urllib.request.Request(
        "https://api.cohere.com/v2/chat",
        data=json.dumps(
            {
                "model": MODEL,
                "max_tokens": 1500,
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
    listing = "\n".join(
        f"- {i['title']} ({i['source']}) {i['link']}" for i in items
    )
    prompt = (
        "Below are today's Google News headlines about 3D printing.\n"
        "Pick the 3-5 most positive, uplifting stories (breakthroughs, launches, "
        "helpful applications). Ignore negative or controversial ones. Write an "
        "engaging blog post in Markdown with a title (H1), a short intro, a section "
        "per story, and a link to each source article. Use only facts present in the "
        "headlines; do not invent details.\n\n" + listing
    )
    post = cohere_chat(prompt)

    os.makedirs("blogs", exist_ok=True)
    path = f"blogs/{today}.md"
    with open(path, "w") as f:
        f.write(post.strip() + "\n")

    with open("issue_body.md", "w") as f:
        f.write(f"Daily 3D printing blog for {today}: `{path}`\n\n---\n\n{post.strip()}\n")
    print(path)


if __name__ == "__main__":
    main()
