"""Assemble section markdown into one digest, and render a card-based dashboard HTML view.

Styling itself lives entirely in static/digest.css (shipped as the default,
copied into the state dir on first run only) -- this module only emits the
.dashboard/.card/.card-body/h1/h2 markup those rules target, so a hand-written
stylesheet can be dropped in without touching any Python.
"""
import html
import re
from datetime import datetime
from pathlib import Path

SECTION_ORDER = ["schedule", "briefing", "news", "podcasts", "email"]
SECTION_TITLES = {
    "schedule": "Today's Schedule & Weather",
    "email": "Urgent / Unread Email",
    "briefing": "Today's Briefing",
    "news": "IT & Cybersec News",
    "podcasts": "Recent Podcast Episodes",
}
# Sections whose content can grow long enough to need their own scrollbar
# rather than stretching the whole dashboard row to match their height.
SECTION_SCROLLABLE = {"email"}
# Cards that should span the full dashboard width instead of sitting in the grid.
SECTION_FULL_WIDTH = {"email"}

STYLE_FILENAME = "digest.css"
DEFAULT_STYLE_PATH = Path(__file__).resolve().parent / "static" / STYLE_FILENAME


def assemble_markdown(sections: dict) -> str:
    today = datetime.now().strftime("%A, %B %d %Y")
    parts = [f"# Morning Digest — {today}\n"]
    for key in SECTION_ORDER:
        if key not in sections:
            continue
        parts.append(f"## {SECTION_TITLES.get(key, key.title())}\n")
        parts.append(sections[key].rstrip() + "\n")
        if key == "schedule" and "schedule_forecast" in sections:
            parts.append("**Upcoming forecast**\n")
            parts.append(sections["schedule_forecast"].rstrip() + "\n")
    return "\n".join(parts) + "\n"


# Minimal stdlib-only Markdown -> HTML for the handful of constructs we
# actually emit (bullets, bold, italics, links, code fences). Not a
# general-purpose parser; good enough for this digest's own output.
def _inline(text: str) -> str:
    text = html.escape(text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"_([^_]+)_", r"<i>\1</i>", text)
    return text


def _section_fragment(md_text: str) -> str:
    """Convert one section's markdown body (no heading line) to an HTML fragment."""
    lines = md_text.splitlines()
    out = []
    in_code = False
    in_list = False
    for line in lines:
        if line.strip().startswith("```"):
            out.append("</pre>" if in_code else "<pre>")
            in_code = not in_code
            continue
        if in_code:
            out.append(html.escape(line))
            continue
        if line.startswith("- "):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{_inline(line[2:])}</li>")
            continue
        if in_list:
            out.append("</ul>")
            in_list = False
        if line.strip():
            out.append(f"<p>{_inline(line)}</p>")
    if in_list:
        out.append("</ul>")
    return "\n".join(out)


def render_html(sections: dict) -> str:
    today = datetime.now().strftime("%A, %B %d %Y")
    cards = []
    for key in SECTION_ORDER:
        if key not in sections:
            continue
        title = html.escape(SECTION_TITLES.get(key, key.title()))
        body = _section_fragment(sections[key])
        if key == "schedule" and "schedule_forecast" in sections:
            forecast_body = _section_fragment(sections["schedule_forecast"])
            body += (
                '\n<details class="forecast"><summary>Upcoming forecast</summary>\n'
                f'{forecast_body}\n</details>'
            )
        classes = ["card"]
        if key in SECTION_SCROLLABLE:
            classes.append("scroll")
        if key in SECTION_FULL_WIDTH:
            classes.append("full-width")
        cards.append(
            f'<div class="{" ".join(classes)}" id="{key}">\n<h2>{title}</h2>\n'
            f'<div class="card-body">\n{body}\n</div>\n</div>'
        )
    dashboard = "\n".join(cards)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Morning Digest</title>
<link rel="stylesheet" href="{STYLE_FILENAME}">
</head>
<body>
<h1>Morning Digest — {today}</h1>
<div class="dashboard">
{dashboard}
</div>
</body>
</html>
"""
