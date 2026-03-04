import os
import base64
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
import pickle

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.compose",
]

def authenticate():
    creds = None

    if os.path.exists("token.pkl"):
        with open("token.pkl", "rb") as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(
            "client_secret.json", SCOPES
        )
        creds = flow.run_local_server(port=0)

        with open("token.pkl", "wb") as token:
            pickle.dump(creds, token)

    return creds

def list_unread_messages(service):
    results = service.users().messages().list(
        userId="me",
        q="is:unread",
        maxResults=5
    ).execute()

    messages = results.get("messages", [])

    if not messages:
        print("No unread messages found.")
        return

    for msg in messages:
        msg_data = service.users().messages().get(
            userId="me",
            id=msg["id"],
            format="metadata",
            metadataHeaders=["Subject"]
        ).execute()

        headers = msg_data["payload"]["headers"]
        subject = next(
            (h["value"] for h in headers if h["name"] == "Subject"),
            "(No Subject)"
        )

        print(f"Message ID: {msg['id']}")
        print(f"Subject: {subject}")
        print("-" * 40)

def main():
    creds = authenticate()
    service = build("gmail", "v1", credentials=creds)

    list_unread_messages(service)

if __name__ == "__main__":
    main()