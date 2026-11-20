"""Parse an OPML podcast-subscription export and report new episodes since last run."""
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from . import config, state


@dataclass
class Episode:
    podcast: str
    title: str
    link: str
    guid: str


def _fetch(url: str, timeout: int) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "morning-digest/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def parse_opml(path) -> list:
    """Return [(title, feed_url), ...] from an OPML file exported by a podcast app."""
    if not path.exists():
        return []
    root = ET.parse(path).getroot()
    feeds = []
    for outline in root.findall(".//outline"):
        url = outline.get("xmlUrl")
        if not url:
            continue
        title = outline.get("title") or outline.get("text") or url
        feeds.append((title, url))
    return feeds


def _latest_items(url: str, limit: int, timeout: int) -> list:
    try:
        raw = _fetch(url, timeout)
        root = ET.fromstring(raw)
    except Exception:
        return []
    items = []
    for item in root.findall(".//item")[:limit]:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        guid = (item.findtext("guid") or link or title).strip()
        items.append((title, link, guid))
    return items


def find_new_episodes(opml_path=None, seen_path=None, per_feed=None, timeout=None) -> list:
    opml_path = opml_path or config.PODCAST_OPML
    seen_path = seen_path or config.PODCAST_SEEN_FILE
    per_feed = per_feed or config.PODCAST_NEW_EPISODES_PER_FEED
    timeout = timeout or config.FETCH_TIMEOUT

    seen = state.load(seen_path, default={})
    new_episodes = []

    for title, url in parse_opml(opml_path):
        seen_guids = set(seen.get(url, []))
        latest = _latest_items(url, per_feed, timeout)
        fresh_guids = []
        for ep_title, link, guid in latest:
            if guid not in seen_guids:
                new_episodes.append(Episode(title, ep_title, link, guid))
            fresh_guids.append(guid)
        # Remember the guids we've now surfaced so next run doesn't repeat them.
        seen[url] = fresh_guids

    state.save(seen_path, seen)
    return new_episodes


def render_markdown(episodes) -> str:
    if not episodes:
        return "_No new episodes._\n"
    lines = []
    for ep in episodes:
        if ep.link:
            lines.append(f"- **{ep.podcast}**: [{ep.title}]({ep.link})")
        else:
            lines.append(f"- **{ep.podcast}**: {ep.title}")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    print(render_markdown(find_new_episodes()))
