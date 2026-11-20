"""Render the urgent-email section. Data comes from gmail_client.fetch_urgent_emails(),
cached as JSON in config.EMAIL_JSON for debugging/offline reruns.
"""
from . import config, state


def load_emails(path=None):
    path = path or config.EMAIL_JSON
    return state.load(path, default=[])


def render_markdown(emails=None) -> str:
    emails = emails if emails is not None else load_emails()
    if not emails:
        return "_No urgent/unread email._\n"
    lines = []
    for e in emails:
        flag = "\U0001f6a8 " if e.get("urgent") else ""
        lines.append(f"- {flag}**{e.get('from', 'unknown')}** — {e.get('subject', '(no subject)')}")
        if e.get("snippet"):
            lines.append(f"  _{e['snippet']}_")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    print(render_markdown())
