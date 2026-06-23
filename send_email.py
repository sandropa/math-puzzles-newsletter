"""Email the day's math puzzle (an inline PNG) via the Gmail API. Run daily by CI.

Which puzzle = days since START into the fixed-shuffled puzzles.json (no state,
no repetition). The puzzle image is cropped on the fly from Dartmouth's public
copy of the book, so nothing copyrighted is stored in this repo. Auth is entirely
from env vars (GitHub secrets); the refresh token is long-lived.
"""

import base64
import json
import os
import sys
import urllib.request
from datetime import date
from email.message import EmailMessage
from io import BytesIO

import fitz  # PyMuPDF
from PIL import Image
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

URL = "https://math.dartmouth.edu/news-resources/electronic/puzzlebook/book/book.pdf"
START = date(2026, 6, 23)  # puzzle #1 goes out on this date
ZOOM = 2.8

puzzles = json.load(open("puzzles.json"))
if len(sys.argv) > 1:  # send_email.py "Puzzle Name" -> send that one (testing)
    name = sys.argv[1].lower()
    index = next((i for i, p in enumerate(puzzles) if p["name"].lower() == name), -1)
    if index < 0:
        sys.exit(f"No puzzle named {sys.argv[1]!r}.")
else:
    index = (date.today() - START).days
    if not 0 <= index < len(puzzles):
        print(f"No puzzle for index {index} (have {len(puzzles)}).")
        sys.exit(0)
puzzle = puzzles[index]


doc = fitz.open(stream=urllib.request.urlopen(URL).read(), filetype="pdf")


def render(strips):
    """Crop the given strips from the PDF and stack them into one PNG."""
    imgs = []
    for page, top, bottom, x0, x1 in strips:
        pix = doc[page].get_pixmap(
            matrix=fitz.Matrix(ZOOM, ZOOM), clip=fitz.Rect(x0, top, x1, bottom)
        )
        imgs.append(Image.frombytes("RGB", (pix.width, pix.height), pix.samples))
    if len(imgs) > 1:
        canvas = Image.new("RGB", (max(i.width for i in imgs), sum(i.height for i in imgs)), "white")
        y = 0
        for im in imgs:
            canvas.paste(im, (0, y))
            y += im.height
        imgs = [canvas]
    buf = BytesIO()
    imgs[0].save(buf, "PNG")
    return buf.getvalue()


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
msg["Subject"] = f"Daily Puzzle #{index + 1}: {puzzle['name']}"
msg.set_content(f"Today's puzzle: {puzzle['name']} — view with images enabled.")

# Problem first, then a screenful of empty space, then the solution (scroll to reveal).
msg.add_alternative(
    '<div style="font-family:Georgia,serif;padding:40px;box-sizing:border-box">'
    '<img src="cid:puzzle" style="max-width:100%;display:block">'
    + "<br>" * 40  # HEY strips big margins; blank lines make the scroll gap
    + '<img src="cid:solution" style="max-width:100%;display:block">'
    + "</div>",
    subtype="html",
)
html_part = msg.get_payload()[1]
html_part.add_related(render(puzzle["strips"]), "image", "png", cid="puzzle")
html_part.add_related(render(puzzle["solution"]), "image", "png", cid="solution")
# Force inline disposition or HEY (and some others) file the images as attachments.
for img_part in html_part.get_payload()[1:]:
    cid = img_part["Content-ID"].strip("<>")
    if img_part.get("Content-Disposition"):
        img_part.replace_header("Content-Disposition", "inline")
    else:
        img_part.add_header("Content-Disposition", "inline")
    img_part.add_header("X-Attachment-Id", cid)

raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
build("gmail", "v1", credentials=creds).users().messages().send(
    userId="me", body={"raw": raw}
).execute()
print(f"sent #{index + 1}: {puzzle['name']}")
