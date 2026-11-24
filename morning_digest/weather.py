"""Thin wrapper around your existing weather script."""
import json
import re
import subprocess

from . import config

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


def _run(*format_args) -> str:
    try:
        result = subprocess.run(
            config.WEATHER_CMD + list(format_args),
            capture_output=True, text=True, timeout=15, check=True,
        )
        # Many CLI weather tools colorize output; strip escape codes since
        # they're meaningless (and ugly) once embedded in markdown/HTML.
        return _ANSI_RE.sub("", result.stdout).strip()
    except Exception as exc:
        return f"(weather unavailable: {exc})"


def fetch() -> str:
    return _run("-f", "notification")


def fetch_forecast(days: int = None) -> list:
    """Return up to `days` upcoming daytime forecast periods as short strings
    (e.g. "Tuesday: 68F Partly Sunny, 20% rain"), parsed from the script's
    raw NWS `-f json` output. Best-effort: one-item list with an explanation
    on failure, same as the rest of this module.
    """
    days = days or config.WEATHER_FORECAST_DAYS
    raw = _run("-f", "json")
    if raw.startswith("(weather unavailable"):
        return [raw]
    try:
        periods = json.loads(raw)["properties"]["periods"]
    except Exception as exc:
        return [f"(forecast unavailable: {exc})"]

    lines = []
    for period in (p for p in periods if p.get("isDaytime")):
        if len(lines) >= days:
            break
        pop = (period.get("probabilityOfPrecipitation") or {}).get("value")
        rain = f", {pop}% rain" if pop else ""
        lines.append(
            f"{period.get('name', '?')}: {period.get('temperature', '?')}"
            f"{period.get('temperatureUnit', 'F')} {period.get('shortForecast', '')}{rain}"
        )
    return lines


def render_markdown() -> str:
    output = fetch()
    return f"```\n{output}\n```\n"


if __name__ == "__main__":
    print(render_markdown())
    print("\n".join(fetch_forecast()))
