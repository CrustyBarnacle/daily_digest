---
name: morning-digest
description: Build Mario's unified morning digest (urgent email, today's calendar, IT/cybersec news, new podcast episodes, weather). Use when the user asks for their morning digest, daily briefing, or runs /morning-digest.
---

# Morning Digest

Fully local/standalone now — email and calendar go through the Gmail/Calendar
APIs directly (OAuth), news/podcasts/weather are fetched in-process, and
summarization uses a local Lemonade/Llama3 server. No Claude session or MCP
connector is required to run it.

## Steps

1. First run only: confirm `~/.local/state/morning-digest/credentials.json`
   exists (a Desktop-app OAuth client JSON downloaded from Google Cloud
   Console — see README.md). The first `fetch_urgent_emails()`/
   `fetch_today_events()` call will open a browser for one-time consent and
   cache a refresh token in `token.json`.
2. Confirm `morning_digest/config.py` points `WEATHER_CMD` at the real
   weather script and `PODCAST_OPML` at an exported subscription list.
3. Run:
   ```
   python3 -m morning_digest.cli --open-glow
   ```
   (or `--serve` for the browser view).
4. Report where the files landed and surface any fetch warnings printed to
   stderr (dead feed, Lemonade unreachable, weather command missing, etc.).

## Roadmap (v2.1)

MCP-based Gmail/Calendar (using Claude's connectors instead of direct OAuth)
is a planned alternate backend, not yet implemented — current priority is
staying local-first.
