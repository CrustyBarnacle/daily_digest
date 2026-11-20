"""Render today's schedule section. Data comes from calendar_client.fetch_today_events(),
cached as JSON in config.CALENDAR_JSON for debugging/offline reruns.
"""
from . import config, state


def load_events(path=None):
    path = path or config.CALENDAR_JSON
    return state.load(path, default=[])


def render_markdown(events=None) -> str:
    events = events if events is not None else load_events()
    if not events:
        return "_Your day is clear._\n"
    lines = []
    for ev in sorted(events, key=lambda e: e.get("time", "")):
        loc = f" @ {ev['location']}" if ev.get("location") else ""
        lines.append(f"- **{ev.get('time', '?')}** — {ev.get('title', '(untitled)')}{loc}")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    print(render_markdown())
