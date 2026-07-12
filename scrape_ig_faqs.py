#!/usr/bin/env python3
"""
Instagram Help Center FAQ scraper.

Scrapes an Instagram Help Center section (e.g. Chats:
https://help.instagram.com/561062241952036/) and every linked
FAQ/article page within that section, outputting clean Markdown.

Instagram's Help Center is JavaScript-rendered, so this uses Playwright
(a real headless browser) rather than requests/BeautifulSoup.

Install:
    pip install playwright beautifulsoup4
    playwright install chromium

Usage:
    python scrape_ig_faqs.py https://help.instagram.com/561062241952036/
    python scrape_ig_faqs.py https://help.instagram.com/561062241952036/ -o output.md
"""

import argparse
import re
import sys
import time
from collections import deque
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

HELP_HOST = "help.instagram.com"


def normalize_url(url: str) -> str:
    """Strip query/fragment, ensure consistent form for dedup."""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    return f"https://{HELP_HOST}{path}"


def is_help_article_link(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.netloc and parsed.netloc != HELP_HOST:
        return False
    # Instagram help articles are numeric IDs under /help.instagram.com/<id>/
    return bool(re.search(r"/\d{6,}/?$", parsed.path))


def fetch_rendered_html(page, url: str, wait_ms: int = 2500) -> str:
    page.goto(url, wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(wait_ms)  # let any lazy content settle
    return page.content()


def extract_content(html: str, url: str):
    """Return (title, markdown_body, list_of_linked_article_urls)."""
    soup = BeautifulSoup(html, "html.parser")

    title_tag = soup.find("h1")
    title = title_tag.get_text(strip=True) if title_tag else (soup.title.get_text(strip=True) if soup.title else url)

    main = soup.find("main") or soup.find("div", {"role": "main"}) or soup.body

    lines = []
    seen_text = set()

    if main:
        for el in main.find_all(["h1", "h2", "h3", "h4", "p", "li"]):
            text = el.get_text(" ", strip=True)
            if not text or text in seen_text:
                continue
            seen_text.add(text)
            if el.name == "h1":
                continue  # already used as title
            elif el.name == "h2":
                lines.append(f"\n## {text}\n")
            elif el.name in ("h3", "h4"):
                lines.append(f"\n### {text}\n")
            elif el.name == "li":
                lines.append(f"- {text}")
            else:
                lines.append(text)

    body_md = "\n".join(lines).strip()

    linked = set()
    for a in soup.find_all("a", href=True):
        full = urljoin(url, a["href"])
        if is_help_article_link(full):
            linked.add(normalize_url(full))

    return title, body_md, linked


def crawl(start_url: str, max_pages: int = 200, delay: float = 1.0):
    start_url = normalize_url(start_url)
    visited = set()
    queue = deque([start_url])
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()

        while queue and len(visited) < max_pages:
            url = queue.popleft()
            if url in visited:
                continue
            visited.add(url)

            print(f"[{len(visited)}] Fetching: {url}", file=sys.stderr)
            try:
                html = fetch_rendered_html(page, url)
            except Exception as e:
                print(f"  !! failed: {e}", file=sys.stderr)
                continue

            title, body_md, linked_urls = extract_content(html, url)
            if body_md:
                results.append({"url": url, "title": title, "body": body_md})

            for link in linked_urls:
                if link not in visited:
                    queue.append(link)

            time.sleep(delay)  # be polite / avoid rate limiting

        browser.close()

    return results


def to_markdown(results, section_url: str) -> str:
    out = [f"# Instagram Help Center FAQs\n", f"Source: {section_url}\n", "---\n"]
    for r in results:
        out.append(f"# {r['title']}\n")
        out.append(f"*Source: {r['url']}*\n")
        out.append(r["body"])
        out.append("\n---\n")
    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser(description="Scrape Instagram Help Center FAQs into Markdown.")
    parser.add_argument("url", help="Starting Help Center section/article URL")
    parser.add_argument("-o", "--output", default="instagram_faqs.md", help="Output Markdown file path")
    parser.add_argument("--max-pages", type=int, default=200, help="Safety cap on number of pages to crawl")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay in seconds between page fetches")
    args = parser.parse_args()

    results = crawl(args.url, max_pages=args.max_pages, delay=args.delay)

    if not results:
        print("No content extracted. Instagram may have changed their page structure "
              "or blocked the request.", file=sys.stderr)
        sys.exit(1)

    markdown = to_markdown(results, args.url)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(markdown)

    print(f"\nDone. {len(results)} pages written to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
