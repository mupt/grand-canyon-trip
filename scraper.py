#!/usr/bin/env python3
"""
Grand Canyon NPS scraper.
Fetches pages from nps.gov/grca and saves them as JSON for the offline viewer.
"""

import json
import time
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Missing deps. Run: pip install requests beautifulsoup4")
    sys.exit(1)

BASE = "https://www.nps.gov/grca/"
ALLOWED_HOST = "www.nps.gov"
ALLOWED_PREFIX = "/grca/"
OUTPUT = Path("data")
OUTPUT.mkdir(exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; GrandCanyonOfflineReader/1.0)"
}

# Seed URLs — main sections of the Grand Canyon NPS site
SEEDS = [
    "https://www.nps.gov/grca/index.htm",
    "https://www.nps.gov/grca/planyourvisit/index.htm",
    "https://www.nps.gov/grca/learn/index.htm",
    "https://www.nps.gov/grca/getinvolved/index.htm",
    "https://www.nps.gov/grca/planyourvisit/hours.htm",
    "https://www.nps.gov/grca/planyourvisit/fees.htm",
    "https://www.nps.gov/grca/planyourvisit/directions.htm",
    "https://www.nps.gov/grca/planyourvisit/lodging.htm",
    "https://www.nps.gov/grca/planyourvisit/camping.htm",
    "https://www.nps.gov/grca/planyourvisit/permits.htm",
    "https://www.nps.gov/grca/planyourvisit/backcountry-permit.htm",
    "https://www.nps.gov/grca/planyourvisit/safety.htm",
    "https://www.nps.gov/grca/planyourvisit/trails.htm",
    "https://www.nps.gov/grca/planyourvisit/south-rim-trail-descriptions.htm",
    "https://www.nps.gov/grca/planyourvisit/north-rim-trail-descriptions.htm",
    "https://www.nps.gov/grca/planyourvisit/inner-canyon-trail-descriptions.htm",
    "https://www.nps.gov/grca/planyourvisit/ranger-programs.htm",
    "https://www.nps.gov/grca/planyourvisit/accessibility.htm",
    "https://www.nps.gov/grca/planyourvisit/weather.htm",
    "https://www.nps.gov/grca/planyourvisit/shuttle-buses.htm",
    "https://www.nps.gov/grca/learn/nature/index.htm",
    "https://www.nps.gov/grca/learn/historyculture/index.htm",
    "https://www.nps.gov/grca/learn/kidsyouth/index.htm",
]


def url_to_key(url):
    parsed = urlparse(url)
    key = parsed.path.rstrip("/") or "/grca/index"
    return key.replace("/", "_").strip("_")


def is_allowed(url):
    p = urlparse(url)
    return p.netloc == ALLOWED_HOST and p.path.startswith(ALLOWED_PREFIX)


def extract_links(soup, base_url):
    links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        full = urljoin(base_url, href)
        full = full.split("#")[0].split("?")[0]
        if full.endswith(".htm") or full.endswith(".html") or full.endswith("/"):
            if is_allowed(full):
                links.add(full)
    return links


def clean_html(soup):
    # Remove nav, footer, scripts, styles, ads
    for tag in soup.find_all(["script", "style", "noscript", "iframe",
                               "header", "footer", "nav", ".global-nav",
                               ".global-footer"]):
        tag.decompose()
    for tag in soup.find_all(class_=re.compile(r"(nav|footer|cookie|banner|skip)", re.I)):
        tag.decompose()
    return soup


def scrape_page(url, session):
    try:
        r = session.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
    except Exception as e:
        print(f"  SKIP {url}: {e}")
        return None, set()

    soup = BeautifulSoup(r.text, "html.parser")
    links = extract_links(soup, url)
    clean_html(soup)

    title = soup.title.get_text(strip=True) if soup.title else url
    main = soup.find("main") or soup.find(id="cs-content") or soup.find("article") or soup.body
    body_html = str(main) if main else str(soup.body)

    # Strip excessive whitespace
    body_html = re.sub(r"\n{3,}", "\n\n", body_html)

    return {
        "url": url,
        "title": title,
        "html": body_html,
        "scraped_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }, links


def main():
    session = requests.Session()
    visited = set()
    queue = list(SEEDS)
    pages = []
    index = []

    print(f"Scraping Grand Canyon NPS pages...")

    while queue:
        url = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)

        print(f"  [{len(visited):3d}] {url}")
        page, links = scrape_page(url, session)

        if page:
            key = url_to_key(url)
            out_file = OUTPUT / f"{key}.json"
            with open(out_file, "w") as f:
                json.dump(page, f, ensure_ascii=False, indent=2)
            pages.append(page)
            index.append({"key": key, "url": url, "title": page["title"], "file": f"data/{key}.json"})

            # Queue newly discovered links (up to depth)
            for link in sorted(links):
                if link not in visited and link not in queue:
                    queue.append(link)

        time.sleep(0.4)  # be polite

    # Write index
    with open(OUTPUT / "index.json", "w") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    print(f"\nDone. {len(pages)} pages saved to {OUTPUT}/")
    print(f"Index written to {OUTPUT}/index.json")


if __name__ == "__main__":
    main()
