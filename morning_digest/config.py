"""User-editable settings for the morning digest."""
from pathlib import Path

STATE_DIR = Path.home() / ".local" / "state" / "morning-digest"

# --- Google OAuth (Gmail + Calendar) ---
# Create an OAuth client ID (type "Desktop app") in Google Cloud Console,
# download it, and point this at the file. First run opens a browser for
# one-time consent; after that the refresh token in GOOGLE_TOKEN_FILE is reused.
GOOGLE_CREDENTIALS_FILE = STATE_DIR / "credentials.json"
GOOGLE_TOKEN_FILE = STATE_DIR / "token.json"
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
]
GMAIL_MAX_RESULTS = 10
GMAIL_QUERY = "is:unread"  # Gmail search syntax; e.g. "is:unread -category:promotions"

# Cached copies of the last fetch, mostly useful for debugging/offline reruns.
EMAIL_JSON = STATE_DIR / "email.json"
CALENDAR_JSON = STATE_DIR / "calendar.json"

# --- Local LLM (Lemonade serving Llama3, OpenAI-compatible endpoint) ---
LEMONADE_BASE_URL = "http://localhost:13305"
LEMONADE_MODEL = "llama3"
LLM_TIMEOUT = 30
# If the LLM enrichment steps below fail/time out, sections fall back to the
# plain non-LLM rendering, so turning this off (or Lemonade being down) is safe.
ENABLE_LLM_NEWS_SUMMARY = True
ENABLE_LLM_EMAIL_URGENCY = False  # Gmail label heuristic is used unless this is on.

# --- IT/cybersec RSS feeds ---
NEWS_FEEDS = [
    ("Krebs on Security", "https://krebsonsecurity.com/feed/"),
    ("The Hacker News", "https://feeds.feedburner.com/TheHackersNews"),
    ("SANS ISC", "https://isc.sans.edu/rssfeed_full.xml"),
    ("Ars Technica - Security", "https://feeds.arstechnica.com/arstechnica/security"),
]
NEWS_ITEMS_PER_FEED = 3

# --- Podcasts ---
# OPML export from your podcast app (most apps have an "export subscriptions" option).
# `cybersec_example.opml` ships as a sample; drop your own `podcasts.opml` in
# the project root or in the state dir and it takes priority over the sample.
_PROJECT_OPML = Path(__file__).resolve().parent.parent / "podcasts.opml"
_SAMPLE_OPML = Path(__file__).resolve().parent.parent / "cybersec_example.opml"
PODCAST_OPML = (
    _PROJECT_OPML if _PROJECT_OPML.exists()
    else STATE_DIR / "podcasts.opml" if (STATE_DIR / "podcasts.opml").exists()
    else _SAMPLE_OPML
)
PODCAST_SEEN_FILE = STATE_DIR / "podcasts_seen.json"
PODCAST_NEW_EPISODES_PER_FEED = 2

# --- Weather ---
# Uses CrustyBarnacle/Utility_Scripts' `weather` (zsh; needs curl/jq/bc on PATH):
# https://github.com/CrustyBarnacle/Utility_Scripts/blob/main/weather
# Install it somewhere on PATH (or point WEATHER_CMD at its full path), then
# set your location with -l/--lat, --lon, -n/--name (defaults to LA if unset).
# Base invocation only -- weather.py appends "-f <mode>" per call
# ("notification" for the current-conditions line, "json" for the raw NWS
# forecast periods used to build the multi-day popover).
WEATHER_CMD = ["weather"]
# How many upcoming daytime periods to show in the forecast popover (3-5).
WEATHER_FORECAST_DAYS = 3

FETCH_TIMEOUT = 10

# --- Output ---
DIGEST_MD = STATE_DIR / "digest.md"
DIGEST_HTML = STATE_DIR / "digest.html"
DIGEST_CSS = STATE_DIR / "digest.css"
