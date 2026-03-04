import base64
import re
from email.message import EmailMessage
from email.utils import parseaddr

# ---------- Helpers to read message content ----------

def extract_email_address(from_header: str) -> str:
    _, addr = parseaddr(from_header)
    return addr or from_header

def _get_header(msg, name: str):
    for h in msg.get("payload", {}).get("headers", []):
        if h.get("name", "").lower() == name.lower():
            return h.get("value")
    return None

def _html_to_text(html: str) -> str:
    # Remove script/style
    html = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
    # Replace <br> and </p> with newlines
    html = re.sub(r"(?i)<br\s*/?>", "\n", html)
    html = re.sub(r"(?i)</p\s*>", "\n", html)
    # Strip tags
    text = re.sub(r"(?s)<.*?>", " ", html)
    # Unescape common entities (minimal)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
    # Collapse whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()

def _get_text_from_payload(payload) -> str:
    """Extract plaintext from Gmail message payload (handles text/plain and text/html)."""
    if not payload:
        return ""

    mime_type = payload.get("mimeType", "")
    body = payload.get("body", {}) or {}

    if body.get("data"):
        raw = base64.urlsafe_b64decode(body["data"]).decode("utf-8", errors="ignore")
        if mime_type == "text/plain":
            return raw
        if mime_type == "text/html":
            return _html_to_text(raw)

    # Multipart: recurse
    for part in payload.get("parts", []) or []:
        text = _get_text_from_payload(part)
        if text.strip():
            return text

    return ""

def fetch_message_full(gmail, msg_id: str):
    return gmail.users().messages().get(
        userId="me",
        id=msg_id,
        format="full"
    ).execute()

def fetch_thread_full(gmail, thread_id: str):
    return gmail.users().threads().get(
        userId="me",
        id=thread_id,
        format="full"
    ).execute()

# ---------- Label management ----------

def list_labels(gmail):
    resp = gmail.users().labels().list(userId="me").execute()
    return resp.get("labels", [])

def get_label_id_map(gmail):
    """Return dict: label_name -> label_id"""
    labels = list_labels(gmail)
    return {l["name"]: l["id"] for l in labels}

def ensure_label(gmail, name: str):
    """Create label if missing. Return labelId."""
    label_map = get_label_id_map(gmail)
    if name in label_map:
        return label_map[name]

    created = gmail.users().labels().create(
        userId="me",
        body={
            "name": name,
            "labelListVisibility": "labelShow",
            "messageListVisibility": "show",
        }
    ).execute()
    return created["id"]

# ---------- Actions ----------

def mark_as_read(gmail, msg_id: str):
    gmail.users().messages().modify(
        userId="me",
        id=msg_id,
        body={"removeLabelIds": ["UNREAD"]}
    ).execute()

def apply_labels(gmail, msg_id: str, add_label_ids=None, remove_label_ids=None):
    add_label_ids = add_label_ids or []
    remove_label_ids = remove_label_ids or []
    gmail.users().messages().modify(
        userId="me",
        id=msg_id,
        body={"addLabelIds": add_label_ids, "removeLabelIds": remove_label_ids}
    ).execute()

# ---------- Simple classifier (no AI yet) ----------

AD_KEYWORDS = [
    "unsubscribe", "newsletter", "sale", "discount", "offer", "deal",
    "limited time", "buy now", "promo", "promotion", "marketing"
]

JOB_KEYWORDS = [
    "job", "role", "position", "vacancy", "opportunity", "recruiter",
    "interview", "apply", "application", "hiring", "talent", "candidate"
]

def classify_email(subject: str, from_addr: str, body: str, headers: dict) -> str:
    """
    Returns one of: 'ADVERTISEMENT', 'JOB', 'HUMAN'
    Rule: JOB wins over ADVERTISEMENT even if List-Unsubscribe is present.
    """
    text = f"{subject}\n{from_addr}\n{body}".lower()

    # Strong job patterns (job newsletters still count as job-related!)
    job_hit = any(k in text for k in JOB_KEYWORDS) or any(
        k in text for k in [
            "new jobs", "job alert", "job alerts", "vacancies", "career", "careers",
            "application", "recruitment", "talent acquisition", "we found jobs",
            "recommended jobs", "jobs for you"
        ]
    )

    # Strong ad patterns
    ad_hit = any(k in text for k in AD_KEYWORDS)

    # If it looks like a job email, classify as JOB regardless of unsubscribe header
    if job_hit:
        return "JOB"

    # Otherwise, treat newsletters/marketing as ads
    if headers.get("List-Unsubscribe") or ad_hit:
        return "ADVERTISEMENT"

    return "HUMAN"


def extract_core_fields(msg_full: dict):
    payload = msg_full.get("payload", {}) or {}
    headers_list = payload.get("headers", []) or []
    headers = {h.get("name"): h.get("value") for h in headers_list}

    subject = headers.get("Subject", "") or ""
    from_addr = headers.get("From", "") or ""
    thread_id = msg_full.get("threadId")
    body_text = _get_text_from_payload(payload)

    return subject, from_addr, thread_id, body_text, headers

def create_reply_draft(gmail, thread_id: str, to_addr: str, subject: str, body_text: str):
    """
    Creates a reply draft in Gmail for an existing thread.
    Gmail will thread it if threadId is provided and subject matches.
    """
    msg = EmailMessage()
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.set_content(body_text)

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")

    return gmail.users().drafts().create(
        userId="me",
        body={
            "message": {
                "raw": raw,
                "threadId": thread_id,
            }
        }
    ).execute()
    
def thread_to_text(thread_full: dict, max_messages: int = 6) -> str:
    """
    Convert the last N messages in a thread into a readable text transcript.
    """
    messages = (thread_full.get("messages") or [])[-max_messages:]
    chunks = []
    for m in messages:
        payload = m.get("payload", {}) or {}
        headers_list = payload.get("headers", []) or []
        headers = {h.get("name"): h.get("value") for h in headers_list}
        frm = headers.get("From", "(unknown)")
        subj = headers.get("Subject", "")
        body = _get_text_from_payload(payload)  # uses your improved html/plain extraction
        body = body.strip()
        if len(body) > 1500:
            body = body[:1500] + "…"
        chunks.append(f"FROM: {frm}\nSUBJECT: {subj}\nBODY:\n{body}\n")
    return "\n---\n".join(chunks)