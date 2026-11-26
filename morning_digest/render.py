"""Assemble section markdown into one digest, and render a card-based dashboard HTML view.

Styling itself lives entirely in static/digest.css (shipped as the default,
copied into the state dir on first run only) -- this module only emits the
.dashboard/.card/.card-body/h1/h2 markup those rules target, so a hand-written
stylesheet can be dropped in without touching any Python.
"""
import html
import math
import random
import re
from datetime import datetime
from pathlib import Path

SECTION_ORDER = ["schedule", "news", "podcasts", "email", "briefing"]
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
# Cards that should span two grid columns instead of sitting in a single one.
SECTION_WIDE = {"email"}

STYLE_FILENAME = "digest.css"
DEFAULT_STYLE_PATH = Path(__file__).resolve().parent / "static" / STYLE_FILENAME

# While a card's data is still being fetched/generated (see cli.py's
# progressive --serve build), its body is replaced with one of these
# pure-CSS pixel loaders instead of real content. "skeleton" is the generic
# placeholder used for any lagging/failed section; the LLM briefing card
# gets a randomly-chosen one of the other three instead, picked once per
# build so it stays the same animation across refreshes.
LLM_WAIT_LOADERS = ("bitbot", "dissolve", "chase")

_BITBOT_ROWS = [
    ".....aa.....",
    ".....oo.....",
    ".oooooooooo.",
    ".obbbbbbbbo.",
    ".obssssssbo.",
    ".obsessesbo.",
    ".obssssssbo.",
    ".obssmmssbo.",
    ".obbbbbbbbo.",
    ".oooooooooo.",
    "..oo....oo..",
    ".ooo....ooo.",
]
_BITBOT_CLASS = {".": "", "o": "k-o", "b": "k-b", "s": "k-s", "e": "k-e", "m": "k-m", "a": "k-a"}


def _bitbot_cells() -> str:
    cells = []
    for row in _BITBOT_ROWS:
        for ch in row:
            cls = ("c " + _BITBOT_CLASS.get(ch, "")).strip()
            cells.append(f'<div class="{cls}"></div>')
    return "".join(cells)


def _dissolve_cells() -> str:
    # Same "ripple outward from center, with a little positional jitter so it
    # doesn't look like a perfect ring" math as the original design -- ported
    # from JS to Python since there's no client-side script to compute it.
    cols, rows, cx, cy = 24, 12, 11.5, 5.5
    cells = []
    for y in range(rows):
        for x in range(cols):
            dist = math.sqrt((x - cx) ** 2 + (y - cy) ** 2 * 2.2)
            jitter = ((x * 73856093) ^ (y * 19349663)) & 3
            d = (round(dist * 1.1) + jitter) % 16
            cells.append(f'<div class="t d{d}"></div>')
    return "".join(cells)


def _chase_segments() -> str:
    return "".join(f'<div class="seg d{i}"></div>' for i in range(16))


def _loader_markup(kind: str) -> str:
    if kind == "bitbot":
        inner = (
            f'<div class="loader-bb-grid">{_bitbot_cells()}</div>'
            '<div class="loader-caption">Thinking'
            '<span class="loader-dot"></span><span class="loader-dot loader-dot2"></span>'
            '<span class="loader-dot loader-dot3"></span></div>'
        )
        dur = "0.9s"
    elif kind == "dissolve":
        inner = (
            f'<div class="loader-dz">{_dissolve_cells()}</div>'
            '<div class="loader-caption">Generating</div>'
        )
        dur = "2.4s"
    elif kind == "chase":
        inner = (
            '<div class="loader-ch-label">&gt; Generating<span class="loader-caret"></span></div>'
            f'<div class="loader-ch-bar">{_chase_segments()}</div>'
            '<div class="loader-caption">querying local Llama3 via Lemonade&hellip;</div>'
        )
        dur = "1.4s"
    else:  # "skeleton" -- generic placeholder for any other pending/lagging card
        inner = (
            '<div class="loader-sk" style="height:14px;width:70%"></div>'
            '<div class="loader-sk" style="height:14px;width:92%"></div>'
            '<div class="loader-sk" style="height:14px;width:55%"></div>'
        )
        dur = "1.6s"
    return f'<div class="loader" style="--dur: {dur}"><div class="loader-inner">{inner}</div></div>'


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


def render_html(sections: dict, pending: set = None, briefing_loader: str = None) -> str:
    """`pending` is the set of section keys not yet fetched/generated -- each
    renders a pixel-loader placeholder instead of pulling from `sections`.
    `briefing_loader` picks which LLM-wait animation the briefing card uses;
    pass the same value on every call within one build so it doesn't change
    out from under the auto-refreshing page mid-run."""
    pending = pending or set()
    briefing_loader = briefing_loader or random.choice(LLM_WAIT_LOADERS)
    today = datetime.now().strftime("%A, %B %d %Y")
    cards = []
    for key in SECTION_ORDER:
        if key in pending:
            title = html.escape(SECTION_TITLES.get(key, key.title()))
            kind = briefing_loader if key == "briefing" else "skeleton"
            classes = ["card", "pending"]
            if key in SECTION_WIDE:
                classes.append("wide")
            cards.append(
                f'<div class="{" ".join(classes)}" id="{key}">\n<h2>{title}</h2>\n'
                f'<div class="card-body">\n{_loader_markup(kind)}\n</div>\n</div>'
            )
            continue
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
        if key in SECTION_WIDE:
            classes.append("wide")
        cards.append(
            f'<div class="{" ".join(classes)}" id="{key}">\n<h2>{title}</h2>\n'
            f'<div class="card-body">\n{body}\n</div>\n</div>'
        )
    dashboard = "\n".join(cards)
    # While anything's still pending, the page refreshes itself every couple
    # seconds so --serve's already-open tab fills in live without any JS.
    refresh_tag = '<meta http-equiv="refresh" content="2">\n' if pending else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
{refresh_tag}<title>Morning Digest</title>
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
