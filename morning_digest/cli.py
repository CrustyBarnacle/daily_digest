"""Entry point: build the morning digest and write/open it. Fully local/standalone --
no Claude session or MCP connectors required.

Usage:
    python3 -m morning_digest.cli [--open-glow] [--serve]
"""
import argparse
import functools
import http.server
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


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Build the morning digest.")
    parser.add_argument("--open-glow", action="store_true", help="open the result with glow")
    parser.add_argument("--serve", action="store_true", help="serve the HTML view on localhost")
    parser.add_argument("--port", type=int, default=8808)
    args = parser.parse_args(argv)

    config.STATE_DIR.mkdir(parents=True, exist_ok=True)
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    sections = build_sections()
    md = render.assemble_markdown(sections)
    config.DIGEST_MD.write_text(md, encoding="utf-8")
    config.DIGEST_HTML.write_text(render.render_html(sections), encoding="utf-8")

    # Only seed the default stylesheet once -- if it's already there, it may
    # have been hand-edited/replaced, and reruns shouldn't clobber that.
    if not config.DIGEST_CSS.exists():
        shutil.copyfile(render.DEFAULT_STYLE_PATH, config.DIGEST_CSS)

    print(f"Wrote {config.DIGEST_MD}")
    print(f"Wrote {config.DIGEST_HTML}")
    print(f"Wrote {config.DIGEST_CSS}")

    if args.open_glow:
        subprocess.run(["glow", str(config.DIGEST_MD)])

    if args.serve:
        handler = functools.partial(
            http.server.SimpleHTTPRequestHandler, directory=str(config.DATA_DIR)
        )
        url = f"http://127.0.0.1:{args.port}/{config.DIGEST_HTML.name}"
        socketserver.TCPServer.allow_reuse_address = True
        httpd = socketserver.TCPServer(("127.0.0.1", args.port), handler)
        server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        server_thread.start()
        print(f"Serving {config.DIGEST_HTML.name} at {url}")
        print("Press Ctrl-C or Ctrl-D to stop.")
        try:
            subprocess.run(["xdg-open", url], check=True)
        except Exception as exc:
            print(f"warning: couldn't auto-open browser: {exc}", file=sys.stderr)
        try:
            sys.stdin.read()  # blocks until EOF (Ctrl-D) or KeyboardInterrupt (Ctrl-C)
        except KeyboardInterrupt:
            pass
        finally:
            print("\nShutting down server...")
            httpd.shutdown()
            httpd.server_close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
