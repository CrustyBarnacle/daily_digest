"""Fetch today's events directly from the Google Calendar API (no MCP)."""
import datetime

from googleapiclient.discovery import build

from . import config, google_auth, state


def _format_time(value: str) -> str:
    # Calendar API gives either a dateTime (timed event) or a date (all-day).
    if "T" in value:
        dt = datetime.datetime.fromisoformat(value)
        return dt.astimezone().strftime("%H:%M")
    return "All day"


def fetch_today_events() -> list:
    creds = google_auth.get_credentials()
    service = build("calendar", "v3", credentials=creds)

    now = datetime.datetime.now().astimezone()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + datetime.timedelta(days=1)

    result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=start.isoformat(),
            timeMax=end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    events = []
    for ev in result.get("items", []):
        start_info = ev["start"].get("dateTime", ev["start"].get("date"))
        events.append(
            {
                "time": _format_time(start_info),
                "title": ev.get("summary", "(untitled)"),
                "location": ev.get("location", ""),
            }
        )

    state.save(config.CALENDAR_JSON, events)
    return events


if __name__ == "__main__":
    import json

    print(json.dumps(fetch_today_events(), indent=2))
