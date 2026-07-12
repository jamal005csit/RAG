# Step 1: Data Collection by Instagram FAQ Scraper 

Scrapes Instagram Help Center FAQs into clean Markdown, to be used as the
knowledge base for a RAG pipeline.

## What it does

- Starts from a Help Center section URL (e.g. Chats FAQ).
- Renders each page with a headless browser (Instagram's Help Center is JS-rendered,
  so plain `requests` won't see the content).
- Extracts headings, paragraphs, and list items as Markdown.
- Follows every linked article on the page (same `/help.instagram.com/<id>/` pattern)
  and crawls the whole section, not just the single starting page.
- Writes all articles into one Markdown file, each separated with source URL.

## Setup

```bash
pip install playwright beautifulsoup4
playwright install chromium
```

## Usage

```bash
python scrape_ig_faqs.py https://help.instagram.com/561062241952036/
```

Options:

| Flag | Default | Description |
|---|---|---|
| `-o / --output` | `instagram_faqs.md` | Output file path |
| `--max-pages` | `200` | Safety cap on number of pages crawled |
| `--delay` | `1.0` | Seconds to wait between page fetches |

## Output

A single Markdown file structured like:

```markdown
# <Article Title>
*Source: https://help.instagram.com/<id>/*

<article content...>

---
```

This is the raw corpus. Chunking, embedding, and indexing are separate,
later steps in the pipeline.

## Known limitations

- DOM structure may vary slightly across article types — sparse output on
  some pages may need selector tweaks in `extract_content`.
- No CAPTCHA/bot-check handling. If blocked, try `headless=False` for a
  manual pass or add proxy/UA rotation.
- Only crawls within `help.instagram.com`.

## Next steps (pipeline)

1. **Scrape** (this script) → raw Markdown per article
2. Chunk articles into passages
3. Embed chunks
4. Store in a vector DB
5. Build retrieval + generation on top
