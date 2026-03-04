from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import pickle
from email.utils import parseaddr

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from gmail_actions import (
    ensure_label,
    get_label_id_map,
    fetch_message_full,
    fetch_thread_full,
    thread_to_text,
    create_reply_draft,
    extract_core_fields,
    classify_email,
    mark_as_read,
    apply_labels,
)
from job_candidate_filter import is_job_candidate


SCOPES = (
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.compose",
)


@dataclass(frozen=True)
class Labels:
    job_candidate: str = "AI/JobCandidate"
    job_not_fit: str = "AI/JobNotFit"
    ads_read: str = "AI/AdsRead"
    draft_ready: str = "AI/DraftReady"
    needs_review: str = "AI/NeedsReview"

import os

print(os.getcwd())

def authenticate(
    client_secret: Path = Path("client_secret.json"),
    token_path: Path = Path("token.pkl"),
):
    creds = None
    if token_path.exists():
        creds = pickle.loads(token_path.read_bytes())

    if not creds or not creds.valid:
        creds = InstalledAppFlow.from_client_secrets_file(str(client_secret), SCOPES).run_local_server(port=0)
        token_path.write_bytes(pickle.dumps(creds))

    return creds


def list_unread_ids(gmail, max_results: int = 10) -> list[str]:
    resp = gmail.users().messages().list(
        userId="me",
        q="is:unread in:inbox",
        maxResults=max_results,
    ).execute()
    return [m["id"] for m in resp.get("messages", [])]


def ensure_labels(gmail, labels: Labels) -> dict[str, str]:
    for name in labels.__dict__.values():
        ensure_label(gmail, name)
    return get_label_id_map(gmail)


def label_id(label_map: dict[str, str], name: str) -> str:
    try:
        return label_map[name]
    except KeyError as e:
        raise KeyError(f"Missing Gmail label '{name}'. Did ensure_label() run?") from e


def extract_email(from_header: str) -> str:
    """Turn 'Name <email@x.com>' into 'email@x.com'."""
    _, addr = parseaddr(from_header)
    return addr or from_header


def process_message(gmail, msg_id: str, label_map: dict[str, str], labels: Labels) -> None:
    msg_full = fetch_message_full(gmail, msg_id)
    subject, from_addr, thread_id, body_text, headers = extract_core_fields(msg_full)

    bucket = classify_email(subject, from_addr, body_text, headers)

    print("-" * 70)
    print(f"[{bucket}] {subject} — {from_addr}")

    if bucket == "ADVERTISEMENT":
        mark_as_read(gmail, msg_id)
        apply_labels(gmail, msg_id, add_label_ids=[label_id(label_map, labels.ads_read)])
        print(" -> read + AI/AdsRead")
        return

    if bucket == "JOB":
        candidate, score, hits = is_job_candidate(subject, body_text, from_addr)
        print(f" -> candidate={candidate} score={score} hits={hits}")
        target = labels.job_candidate if candidate else labels.job_not_fit
        apply_labels(gmail, msg_id, add_label_ids=[label_id(label_map, target)])
        print(f" -> labeled {target}")
        return

    # HUMAN (or anything else): create a draft reply (no AI yet)
    to_addr = extract_email(from_addr)

    thread_full = fetch_thread_full(gmail, thread_id)
    _ = thread_to_text(thread_full, max_messages=6)  # available if you want to debug/log it

    reply_body = """Hi,

Thanks for your email! I’ve read through the thread and will get back to you shortly.

Best regards,
Samer
"""

    # Keep subject stable (avoid Re: Re: ...)
    reply_subject = subject if subject.lower().startswith("re:") else f"Re: {subject}"

    create_reply_draft(
        gmail,
        thread_id=thread_id,
        to_addr=to_addr,
        subject=reply_subject,
        body_text=reply_body,
    )

    apply_labels(
        gmail,
        msg_id,
        add_label_ids=[label_id(label_map, labels.draft_ready)],
    )
    print(f" -> draft created + labeled {labels.draft_ready}")


def main(max_results: int = 10) -> None:
    labels = Labels()
    gmail = build("gmail", "v1", credentials=authenticate())

    label_map = ensure_labels(gmail, labels)
    unread_ids = list_unread_ids(gmail, max_results=max_results)

    if not unread_ids:
        print("No unread inbox messages.")
        return

    for msg_id in unread_ids:
        process_message(gmail, msg_id, label_map, labels)

    print("\nDone.")


if __name__ == "__main__":
    main(max_results=10)