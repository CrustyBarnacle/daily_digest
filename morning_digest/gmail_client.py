"""Fetch unread/urgent email directly from the Gmail API (no MCP)."""
from googleapiclient.discovery import build

from . import config, google_auth, llm_client, state


def _is_urgent(label_ids: list) -> bool:
    return "IMPORTANT" in label_ids or "STARRED" in label_ids


def _llm_urgency(subject: str, snippet: str) -> bool:
    answer = llm_client.chat(
        f"Subject: {subject}\nPreview: {snippet}",
        system="Reply with exactly one word, YES or NO: does this email need action today?",
        max_tokens=5,
    )
    return answer.strip().upper().startswith("Y")


def fetch_urgent_emails(max_results=None) -> list:
    max_results = max_results or config.GMAIL_MAX_RESULTS
    creds = google_auth.get_credentials()
    service = build("gmail", "v1", credentials=creds)

    results = (
        service.users()
        .messages()
        .list(userId="me", q=config.GMAIL_QUERY, maxResults=max_results)
        .execute()
    )

    emails = []
    for m in results.get("messages", []):
        msg = (
            service.users()
            .messages()
            .get(userId="me", id=m["id"], format="metadata", metadataHeaders=["From", "Subject", "Date"])
            .execute()
        )
        headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
        snippet = msg.get("snippet", "")
        subject = headers.get("Subject", "(no subject)")
        label_ids = msg.get("labelIds", [])

        urgent = _is_urgent(label_ids)
        if config.ENABLE_LLM_EMAIL_URGENCY and not urgent:
            urgent = _llm_urgency(subject, snippet)

        emails.append(
            {
                "from": headers.get("From", "unknown"),
                "subject": subject,
                "snippet": snippet,
                "date": headers.get("Date", ""),
                "urgent": urgent,
            }
        )

    state.save(config.EMAIL_JSON, emails)
    return emails


if __name__ == "__main__":
    import json

    print(json.dumps(fetch_urgent_emails(), indent=2))
