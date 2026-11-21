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
    is_new: bool = False


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
        # Some feeds (e.g. Megaphone) omit <link> and only put the episode
        # URL in <guid isPermaLink="true">; fall back to it when it's a URL.
        if not link and guid.startswith(("http://", "https://")):
            link = guid
        items.append((title, link, guid))
    return items


def find_recent_episodes(opml_path=None, seen_path=None, per_feed=None, timeout=None) -> list:
    """Latest `per_feed` episodes from every subscribed show, every run --
    always something to show, with `is_new` marking ones not seen last run."""
    opml_path = opml_path or config.PODCAST_OPML
    seen_path = seen_path or config.PODCAST_SEEN_FILE
    per_feed = per_feed or config.PODCAST_NEW_EPISODES_PER_FEED
    timeout = timeout or config.FETCH_TIMEOUT

    seen = state.load(seen_path, default={})
    episodes = []

    for title, url in parse_opml(opml_path):
        seen_guids = set(seen.get(url, []))
        latest = _latest_items(url, per_feed, timeout)
        fresh_guids = []
        for ep_title, link, guid in latest:
            episodes.append(Episode(title, ep_title, link, guid, is_new=guid not in seen_guids))
            fresh_guids.append(guid)
        # Remember the guids we've now surfaced so next run can mark them seen.
        seen[url] = fresh_guids

    state.save(seen_path, seen)
    return episodes


def render_markdown(episodes) -> str:
    if not episodes:
        return "_No episodes found._\n"
    lines = []
    for ep in episodes:
        marker = " 🆕" if ep.is_new else ""
        if ep.link:
            lines.append(f"- **{ep.podcast}**: [{ep.title}]({ep.link}){marker}")
        else:
            lines.append(f"- **{ep.podcast}**: {ep.title}{marker}")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    print(render_markdown(find_recent_episodes()))
