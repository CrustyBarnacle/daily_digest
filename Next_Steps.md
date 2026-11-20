# Next Steps — Setting Up & Running Morning Digest

Run these on your actual machine (this project's sandbox doesn't have your
Gmail, Lemonade, or weather script) — not through Claude in an isolated
sandbox session.

## 1. Install dependencies
```
cd /path/to/this/project
pip install -r requirements.txt
```

## 2. Set up Google OAuth (Gmail + Calendar)
- Go to [Google Cloud Console](https://console.cloud.google.com/) → create/select a project → **APIs & Services → Library** → enable **Gmail API** and **Google Calendar API**.
- **APIs & Services → Credentials → Create Credentials → OAuth client ID** → Application type **Desktop app**.
- Download the resulting JSON and save it as:
  ```
  mkdir -p ~/.local/state/morning-digest
  mv ~/Downloads/client_secret_*.json ~/.local/state/morning-digest/credentials.json
  ```
- You'll also need an OAuth consent screen configured (test user = your own email is fine if the app is in "Testing" mode).

## 3. Check Lemonade is running
```
curl http://localhost:8000/v1/models
```
If that doesn't return something sane, start Lemonade with Llama3 loaded first (adjust to however you normally launch it on the sky-ai box). If the host/port differs from `localhost:8000`, edit `LEMONADE_BASE_URL`/`LEMONADE_MODEL` in `morning_digest/config.py`.

## 4. Edit `morning_digest/config.py`
- `WEATHER_CMD` → path/args to your real weather script.
- `NEWS_FEEDS` → adjust if you want different sources.
- `GMAIL_QUERY` → defaults to `is:unread`, tweak if needed.
- `PODCAST_OPML` auto-detects `podcasts.opml` if it's sitting next to the project — confirm yours is there or in `~/.local/state/morning-digest/podcasts.opml`.

## 5. First run (one-time browser auth)
```
python3 -m morning_digest.cli --open-glow
```
This will pop a browser window for Google consent the first time (Gmail + Calendar read-only scopes), then cache a refresh token in `~/.local/state/morning-digest/token.json` — no browser prompt on subsequent runs.

## 6. Subsequent runs
```
python3 -m morning_digest.cli --open-glow      # Markdown view via glow
python3 -m morning_digest.cli --serve          # or browser view at http://127.0.0.1:8808/digest.html
```

## 7. (Optional) Run it via Claude Code instead
Just ask for "my morning digest" or type `/morning-digest` — the skill runs the same command and reports any warnings (dead feed, Lemonade down, etc.) printed to stderr.

If anything errors on first run (missing `credentials.json`, OAuth consent screen not configured, Lemonade unreachable), share the error for debugging.
