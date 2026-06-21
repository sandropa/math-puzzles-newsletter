"""
Send email from sandro.paradzik+math-puzzles@gmail.com via the Gmail API.

One-time setup (see the chat steps):
  1. Enable the Gmail API in your Google Cloud project.
  2. Configure the consent screen (Google Auth Platform), add yourself as a test user.
  3. Add the scope https://www.googleapis.com/auth/gmail.send
  4. Create an OAuth client of type "Desktop app", download the JSON,
     and save it next to this script as  credentials.json
  5. After confirming it works, publish the app to production so the
     refresh token doesn't expire after 7 days.

Install dependencies:
  pip install google-auth google-auth-oauthlib google-api-python-client

First run opens a browser for you to grant permission once, then writes
token.json. Every run after that is fully automatic.
"""

import base64
import os
from email.message import EmailMessage

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

# Must exactly match the verified "Send mail as" alias in your Gmail settings.
SENDER = "sandro.paradzik+math-puzzles@gmail.com"


def get_service():
    """Authenticate and return a Gmail API service object."""
    creds = None

    # Reuse the saved token if we have one.
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    # If there's no valid token, refresh it or run the consent flow.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            # Opens a browser window for the one-time consent.
            creds = flow.run_local_server(port=0)
        # Persist the (refreshed) credentials for next time.
        with open("token.json", "w") as token_file:
            token_file.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def send_email(to, subject, body):
    """Send a plain-text email from the configured alias."""
    service = get_service()

    message = EmailMessage()
    message["From"] = SENDER
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    encoded = base64.urlsafe_b64encode(message.as_bytes()).decode()
    sent = (
        service.users()
        .messages()
        .send(userId="me", body={"raw": encoded})
        .execute()
    )
    print(f"Sent! Message id: {sent['id']}")
    return sent


if __name__ == "__main__":
    # Edit these for your test, then run:  python send_email.py
    send_email(
        to="sandropa@hey.com",
        subject="This week's math puzzle",
        body="What's the next number in the sequence 2, 3, 5, 7, 11, ... ?",
    )
