"""Entry point: build the morning digest and write/open it. Fully local/standalone --
no Claude session or MCP connectors required.

Usage:
    python3 -m morning_digest.cli [--open-glow] [--serve]
"""
import argparse
import concurrent.futures
import functools
import hashlib
import http.server
import mimetypes
import random
import shutil
import socketserver
import subprocess
import sys
import threading

from . import calendar_client, config, email_section, gmail_client, news, podcasts, render, schedule, weather


def build_sections() -> dict:
    emails = _safe(gmail_client.fetch_urgent_emails, "email", default=[])
    events = _safe(calendar_client.fetch_today_events, "calendar", default=[])
    headlines = news.fetch_all()
    episodes = podcasts.find_recent_episodes()

    schedule_md = schedule.render_markdown(events).rstrip() + "\n\n" + weather.render_markdown()
    forecast_days = weather.fetch_forecast()

    sections = {
        "schedule": schedule_md,
        "email": email_section.render_markdown(emails),
        "news": news.render_markdown(headlines),
        "podcasts": podcasts.render_markdown(episodes),
    }
    if forecast_days:
        sections["schedule_forecast"] = "\n".join(f"- {line}" for line in forecast_days) + "\n"

    if config.ENABLE_LLM_NEWS_SUMMARY:
        briefing = news.llm_briefing(headlines)
        if briefing:
            sections["briefing"] = briefing + "\n"

    return sections


def _safe(fn, label, default):
    try:
        return fn()
    except Exception as exc:
        print(f"warning: {label} fetch failed: {exc}", file=sys.stderr)
        return default


def _sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sync_tracked_file(default_path, deployed_path, stamp_file, label: str) -> None:
    """Keep a deployed, user-editable file (digest.css, briefing_prompt.txt)
    in sync with its shipped default, without ever clobbering a hand-edited
    copy:

    - doesn't exist yet -> seed it, stamp its hash.
    - matches the stamp (untouched since we last wrote it) and the shipped
      default has since changed (e.g. new loader styles, a reworded prompt)
      -> refresh it, update the stamp.
    - anything else -- no stamp yet (predates this tracking) or it doesn't
      match -- assume it's been hand-edited and leave it alone.
    """
    default_hash = _sha256(default_path)

    if not deployed_path.exists():
        shutil.copyfile(default_path, deployed_path)
        stamp_file.write_text(default_hash)
        return

    current_hash = _sha256(deployed_path)
    if current_hash == default_hash:
        if not stamp_file.exists():
            stamp_file.write_text(default_hash)
        return

    if stamp_file.exists() and stamp_file.read_text().strip() == current_hash:
        shutil.copyfile(default_path, deployed_path)
        stamp_file.write_text(default_hash)
        return

    if not stamp_file.exists():
        print(
            f"note: {deployed_path} predates {label} update-tracking and "
            "differs from the shipped default -- if you haven't hand-edited it, "
            f"delete it (or re-copy it from {default_path}) once "
            "to pick up changes; future updates will then apply automatically.",
            file=sys.stderr,
        )


def _sync_default_css() -> None:
    _sync_tracked_file(render.DEFAULT_STYLE_PATH, config.DIGEST_CSS, config.DIGEST_CSS_SEED_HASH, "digest.css")


def _sync_briefing_prompt() -> None:
    _sync_tracked_file(news.DEFAULT_PROMPT_PATH, config.BRIEFING_PROMPT, config.BRIEFING_PROMPT_SEED_HASH, "briefing_prompt.txt")


def _write_digest_html(sections: dict, pending: set, briefing_loader: str) -> None:
    # Written via a temp file + atomic rename, not a direct write_text() --
    # --serve's HTTP server runs in its own thread with no coordination with
    # this one, and write_text() truncates-then-writes, so a GET landing
    # mid-write could otherwise be served a torn/partial file.
    html = render.render_html(sections, pending=pending, briefing_loader=briefing_loader)
    tmp = config.DIGEST_HTML.with_suffix(".html.tmp")
    tmp.write_text(html, encoding="utf-8")
    tmp.replace(config.DIGEST_HTML)


def _fetch_sections_progressive(pending: set, briefing_loader: str) -> dict:
    """Same fetches as build_sections(), but run concurrently and written to
    disk (via _write_digest_html) in actual completion order -- not a fixed
    sequence -- as each one resolves. This matters because Gmail/Calendar can
    genuinely hang (OAuth/token-refresh, not just a slow request), and a fixed
    order would let one hung fetch wedge every card behind it forever, even
    though their own fetches already finished."""
    pending = set(pending)
    sections = {}
    schedule_parts = {}
    headlines = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        futures = {
            ex.submit(_safe, gmail_client.fetch_urgent_emails, "email", []): "email",
            ex.submit(_safe, calendar_client.fetch_today_events, "calendar", []): "events",
            ex.submit(weather.render_markdown): "weather_md",
            ex.submit(weather.fetch_forecast): "forecast",
            ex.submit(news.fetch_all): "headlines",
            ex.submit(podcasts.find_recent_episodes): "episodes",
        }

        for fut in concurrent.futures.as_completed(futures):
            kind = futures[fut]
            result = fut.result()

            if kind == "email":
                sections["email"] = email_section.render_markdown(result)
                pending.discard("email")
                _write_digest_html(sections, pending, briefing_loader)
            elif kind == "events":
                schedule_parts["events"] = result
            elif kind == "weather_md":
                schedule_parts["weather_md"] = result
            elif kind == "forecast":
                schedule_parts["forecast"] = result
            elif kind == "headlines":
                headlines = result
                sections["news"] = news.render_markdown(result)
                pending.discard("news")
                _write_digest_html(sections, pending, briefing_loader)
            elif kind == "episodes":
                sections["podcasts"] = podcasts.render_markdown(result)
                pending.discard("podcasts")
                _write_digest_html(sections, pending, briefing_loader)

            # "schedule" needs both halves -- finalize as soon as whichever
            # of events/weather_md was still missing just arrived.
            if "events" in schedule_parts and "weather_md" in schedule_parts and "schedule" in pending:
                sections["schedule"] = (
                    schedule.render_markdown(schedule_parts["events"]).rstrip()
                    + "\n\n" + schedule_parts["weather_md"]
                )
                forecast_days = schedule_parts.get("forecast")
                if forecast_days:
                    sections["schedule_forecast"] = "\n".join(f"- {line}" for line in forecast_days) + "\n"
                pending.discard("schedule")
                _write_digest_html(sections, pending, briefing_loader)

        # The LLM briefing needs headlines first, so it can't join the
        # as_completed() batch above -- fetched last, same as build_sections().
        if "briefing" in pending:
            briefing = news.llm_briefing(headlines)
            if briefing:
                sections["briefing"] = briefing + "\n"
            pending.discard("briefing")
            _write_digest_html(sections, pending, briefing_loader)

    return sections


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Build the morning digest.")
    parser.add_argument("--open-glow", action="store_true", help="open the result with glow")
    parser.add_argument("--serve", action="store_true", help="serve the HTML view on localhost")
    parser.add_argument("--port", type=int, default=8808)
    args = parser.parse_args(argv)

    config.STATE_DIR.mkdir(parents=True, exist_ok=True)
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    _sync_default_css()
    _sync_briefing_prompt()
    briefing_loader = random.choice(render.LLM_WAIT_LOADERS)

    if args.serve:
        # http.server guesses Content-Type from the system's mimetypes
        # database (/etc/mime.types), which minimal installs (e.g. a base
        # Arch system without the `mailcap` package) often don't have --
        # digest.css would then get served as application/octet-stream,
        # which browsers refuse to apply as a stylesheet, breaking every
        # bit of the dashboard's styling (not just the loaders). Force the
        # mapping explicitly so this doesn't depend on the host's setup.
        mimetypes.add_type("text/css", ".css")
        mimetypes.add_type("text/html", ".html")
        handler = functools.partial(
            http.server.SimpleHTTPRequestHandler, directory=str(config.DATA_DIR)
        )
        url = f"http://127.0.0.1:{args.port}/{config.DIGEST_HTML.name}"
        socketserver.TCPServer.allow_reuse_address = True
        httpd = socketserver.TCPServer(("127.0.0.1", args.port), handler)
        server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        server_thread.start()

        # Write the all-pending page (and start serving it) before fetching
        # anything, then open the browser on it -- each card fills in live as
        # _fetch_sections_progressive's background fetches resolve.
        pending = {"schedule", "email", "news", "podcasts"}
        if config.ENABLE_LLM_NEWS_SUMMARY:
            pending.add("briefing")
        _write_digest_html({}, pending, briefing_loader)

        print(f"Serving {config.DIGEST_HTML.name} at {url}")
        print("Press Ctrl-C or Ctrl-D to stop.")
        try:
            # Popen, not run() -- xdg-open is supposed to fork and return
            # immediately, but isn't guaranteed to (e.g. if it ends up
            # launching a brand-new browser process it doesn't cleanly
            # detach from); run()/wait() would then block here until the
            # entire browser session closes, and the fetches below -- which
            # is what's actually supposed to fill the page in -- would never
            # even start.
            subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as exc:
            print(f"warning: couldn't auto-open browser: {exc}", file=sys.stderr)

        sections = _fetch_sections_progressive(pending, briefing_loader)
        config.DIGEST_MD.write_text(render.assemble_markdown(sections), encoding="utf-8")
        _write_digest_html(sections, set(), briefing_loader)
        print(f"Wrote {config.DIGEST_MD}")
        print(f"Wrote {config.DIGEST_HTML}")
        print(f"Wrote {config.DIGEST_CSS}")

        try:
            sys.stdin.read()  # blocks until EOF (Ctrl-D) or KeyboardInterrupt (Ctrl-C)
        except KeyboardInterrupt:
            pass
        finally:
            print("\nShutting down server...")
            httpd.shutdown()
            httpd.server_close()

        return 0

    sections = build_sections()
    config.DIGEST_MD.write_text(render.assemble_markdown(sections), encoding="utf-8")
    _write_digest_html(sections, set(), briefing_loader)

    print(f"Wrote {config.DIGEST_MD}")
    print(f"Wrote {config.DIGEST_HTML}")
    print(f"Wrote {config.DIGEST_CSS}")

    if args.open_glow:
        subprocess.run(["glow", str(config.DIGEST_MD)])

    return 0


if __name__ == "__main__":
    sys.exit(main())
