"""Shared OAuth handling for Gmail + Calendar.

Requires: google-auth, google-auth-oauthlib, google-api-python-client
(see requirements.txt). These are the standard Google client libraries --
not stdlib, but this is the supported way to talk to Gmail/Calendar
without hand-rolling OAuth2 token refresh/signing.
"""
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from . import config


def get_credentials() -> Credentials:
    token_path = config.GOOGLE_TOKEN_FILE
    creds = None

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), config.GOOGLE_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not config.GOOGLE_CREDENTIALS_FILE.exists():
                raise FileNotFoundError(
                    f"Missing OAuth client file: {config.GOOGLE_CREDENTIALS_FILE}\n"
                    "Create a Desktop-app OAuth client in Google Cloud Console, "
                    "download its JSON, and save it there."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(config.GOOGLE_CREDENTIALS_FILE), config.GOOGLE_SCOPES
            )
            creds = flow.run_local_server(port=0)
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")

    return creds
