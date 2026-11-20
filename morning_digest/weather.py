"""Thin wrapper around your existing weather script."""
import re
import subprocess

from . import config

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


def fetch() -> str:
    try:
        result = subprocess.run(
            config.WEATHER_CMD, capture_output=True, text=True, timeout=15, check=True
        )
        # Many CLI weather tools colorize output; strip escape codes since
        # they're meaningless (and ugly) once embedded in markdown/HTML.
        return _ANSI_RE.sub("", result.stdout).strip()
    except Exception as exc:
        return f"(weather unavailable: {exc})"


def render_markdown() -> str:
    output = fetch()
    return f"```\n{output}\n```\n"


if __name__ == "__main__":
    print(render_markdown())
