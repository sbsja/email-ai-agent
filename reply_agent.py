import os
from openai import OpenAI

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

SYSTEM = """You draft email replies for Samer.
Be concise, professional, friendly.
Use the thread context. If any key detail is missing, ask 1-2 clarifying questions.
Never promise actions Samer didn't confirm.
Output ONLY the email body text (no subject, no greeting header like 'Subject:').
"""

def draft_reply(thread_text: str, latest_subject: str) -> str:
    resp = client.responses.create(
        model="gpt-5-mini",
        input=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"Subject: {latest_subject}\n\nThread:\n{thread_text}"},
        ],
    )
    return resp.output_text.strip()