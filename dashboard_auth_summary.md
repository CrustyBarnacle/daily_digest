# Google API Access Summary — Morning Digest

Explanation of what access is granted, to what, and to whom via the Google
OAuth scopes used by `morning_digest/gmail_client.py` and
`morning_digest/calendar_client.py`.

## What access is requested

The two OAuth scopes defined in `morning_digest/config.py`:

- **`gmail.readonly`** — read-only access to the *entire* Gmail mailbox: all
  messages, threads, labels, attachments, and settings — not just unread
  mail. The code only calls `messages.list(q="is:unread")`, but that's just
  how *our script* chooses to filter; the scope itself grants Google
  permission to let this app read anything in the mailbox if the code asked.
  It cannot send, delete, or modify anything — `readonly` is enforced by
  Google, not just convention.
- **`calendar.readonly`** — read-only access to all calendars visible to the
  account (not just "primary"), including events, attendees, and free/busy
  info. Code only queries the `primary` calendar, but again, the scope is
  broader than what's currently used.

## Who the access is granted to

The OAuth **client** — identified by the `client_id`/`client_secret` in the
`credentials.json` downloaded from Google Cloud Console. That's a
Desktop-app credential you create and own in your own Google Cloud project.
It's not a third-party service, not Anthropic, not Claude — it's a
credential belonging to you, used by code running on your machine.

## Who approves it, and where the result lives

You do, via the browser consent screen that pops up on first run (signing
into your own Google account and clicking "Allow"). The resulting refresh
token is written to `~/.local/state/morning-digest/token.json` **on your
machine only**. From then on, `gmail_client.py`/`calendar_client.py` talk
directly from your machine to Google's API servers — that traffic never
passes through Claude; the token/data aren't visible outside your machine.

## Revocation

Anytime, at `myaccount.google.com/permissions` → find the app by the name
given in Cloud Console → Remove access. That invalidates the refresh token
immediately; the script would then need re-consent on next run.

## Scope granularity

The code only ever needs unread mail and the primary calendar, but Google
doesn't offer anything narrower than `gmail.readonly`/`calendar.readonly` for
this use case (no "unread-only" scope exists) — so this is already the
minimum granularity available.
