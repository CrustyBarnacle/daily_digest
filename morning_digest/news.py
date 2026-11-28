"""Fetch and summarize IT/cybersec RSS headlines using only the standard library."""
import re
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from pathlib import Path

from . import config

ATOM_NS = "{http://www.w3.org/2005/Atom}"
_TAG_RE = re.compile(r"<[^>]+>")

# Shipped default for config.BRIEFING_PROMPT, deployed/kept-in-sync by
# cli.py's _sync_briefing_prompt() the same way render.DEFAULT_STYLE_PATH is
# for digest.css -- lets the briefing's instructions be viewed/edited without
# touching this module.
DEFAULT_PROMPT_PATH = Path(__file__).resolve().parent / "static" / "briefing_prompt.txt"


def _clean_description(raw: str, limit: int = 300) -> str:
    """Strip HTML and collapse whitespace from a feed's description/summary,
    truncated to keep the LLM prompt small."""
    text = " ".join(_TAG_RE.sub(" ", raw or "").split())
    return text[:limit]


@dataclass
class Headline:
    feed: str
    title: str
    link: str
    published: str  # best-effort human string, already-formatted
    description: str = ""  # short plain-text snippet, used to ground the LLM briefing


def _fetch(url: str, timeout: int) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "morning-digest/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _parse_rss2(root) -> list:
    items = []
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        desc = _clean_description(item.findtext("description"))
        items.append((title, link, pub, desc))
    return items


def _parse_atom(root) -> list:
    items = []
    for entry in root.findall(f"{ATOM_NS}entry"):
        title = (entry.findtext(f"{ATOM_NS}title") or "").strip()
        link_el = entry.find(f"{ATOM_NS}link")
        link = link_el.get("href") if link_el is not None else ""
        pub = (entry.findtext(f"{ATOM_NS}updated") or entry.findtext(f"{ATOM_NS}published") or "").strip()
        desc = _clean_description(entry.findtext(f"{ATOM_NS}summary") or entry.findtext(f"{ATOM_NS}content"))
        items.append((title, link, pub, desc))
    return items


def _sort_key(pub: str):
    try:
        return parsedate_to_datetime(pub)
    except Exception:
        return None


def fetch_feed(name: str, url: str, limit: int, timeout: int) -> list:
    try:
        raw = _fetch(url, timeout)
        root = ET.fromstring(raw)
    except Exception as exc:
        return [Headline(name, f"(failed to fetch: {exc})", "", "")]

    items = _parse_rss2(root) if root.tag != f"{ATOM_NS}feed" else _parse_atom(root)
    items.sort(key=lambda t: _sort_key(t[2]) or "", reverse=True)
    return [Headline(name, title, link, pub, desc) for title, link, pub, desc in items[:limit] if title]


def fetch_all(feeds=None, limit=None, timeout=None) -> list:
    feeds = feeds or config.NEWS_FEEDS
    limit = limit or config.NEWS_ITEMS_PER_FEED
    timeout = timeout or config.FETCH_TIMEOUT
    headlines = []
    for name, url in feeds:
        headlines.extend(fetch_feed(name, url, limit, timeout))
    return headlines


def llm_briefing(headlines) -> str:
    """'What matters today' summary via the local LLM, built from the
    user-editable template at config.BRIEFING_PROMPT (falls back to the
    shipped default if it isn't deployed yet). Best-effort: falls back to no
    briefing if Lemonade is unreachable."""
    from . import llm_client

    if not headlines:
        return ""
    entries = "\n".join(
        f"- {h.title}" + (f" :: {h.description}" if h.description else "")
        for h in headlines if h.title and "(failed to fetch" not in h.title
    )
    if not entries:
        return ""

    template_path = config.BRIEFING_PROMPT if config.BRIEFING_PROMPT.exists() else DEFAULT_PROMPT_PATH
    template = template_path.read_text(encoding="utf-8")
    prompt = template.format(text=entries)

    result = llm_client.chat(prompt, max_tokens=280)
    if result.startswith("(local LLM unavailable"):
        return ""
    return result


def render_markdown(headlines) -> str:
    if not headlines:
        return "_No news fetched._\n"
    lines = []
    by_feed = {}
    for h in headlines:
        by_feed.setdefault(h.feed, []).append(h)
    for feed, items in by_feed.items():
        lines.append(f"**{feed}**")
        for h in items:
            if h.link:
                lines.append(f"- [{h.title}]({h.link})")
            else:
                lines.append(f"- {h.title}")
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    print(render_markdown(fetch_all()))
