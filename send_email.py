"""Send a 'Hello' email via the Gmail API. Run by GitHub Actions daily.

Auth comes entirely from env vars (GitHub secrets) — no token.json file,
no browser. The refresh token is long-lived because the OAuth app is
published to production.
"""

import base64
import os
from email.message import EmailMessage

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

creds = Credentials.from_authorized_user_info(
    {
        "client_id": os.environ["GMAIL_CLIENT_ID"],
        "client_secret": os.environ["GMAIL_CLIENT_SECRET"],
        "refresh_token": os.environ["GMAIL_REFRESH_TOKEN"],
        "token_uri": "https://oauth2.googleapis.com/token",
    },
    ["https://www.googleapis.com/auth/gmail.send"],
)
creds.refresh(Request())

msg = EmailMessage()
msg["From"] = os.environ["SENDER_EMAIL"]
msg["To"] = os.environ["RECIPIENT_EMAIL"]
msg["Subject"] = "Hello"
msg.set_content("Hello")
raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

build("gmail", "v1", credentials=creds).users().messages().send(
    userId="me", body={"raw": raw}
).execute()
print("sent")
