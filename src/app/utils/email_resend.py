import os

try:
    import resend
    HAS_RESEND = True
except Exception:
    resend = None
    HAS_RESEND = False

if HAS_RESEND:
    # Will raise KeyError if not configured; let caller see that explicit error
    resend.api_key = os.environ.get("RESEND_API_KEY")


def send_email_resend(to, subject, html):
    # Build plain-text fallback by stripping basic tags and collapsing whitespace.
    # This helps mail clients (and spam filters) and can reduce likelihood of clipping.
    import re

    def _html_to_text(h: str) -> str:
        # Remove script/style blocks first
        h = re.sub(r"(?is)<(script|style).*?>.*?</\1>", "", h)
        # Replace <br> and <p> with newlines
        h = re.sub(r"(?i)<br\s*/?>", "\n", h)
        h = re.sub(r"(?i)</p>", "\n\n", h)
        # Remove all remaining tags
        h = re.sub(r"<[^>]+>", "", h)
        # Decode common HTML entities
        h = h.replace("&nbsp;", " ")
        h = h.replace("&amp;", "&")
        h = h.replace("&lt;", "<").replace("&gt;", ">")
        # Collapse multiple whitespace/newlines
        h = re.sub(r"[ \t\r]+", " ", h)
        h = re.sub(r"\n{3,}", "\n\n", h)
        return h.strip()

    text = _html_to_text(html) if html else ""

    params = {
        "from": "Accounts@tigerleads.ai",
        "to": [to],
        "subject": subject,
        "html": html,
        "text": text,
    }

    if not HAS_RESEND:
        raise RuntimeError("Resend SDK is not installed; cannot send email via Resend")

    return resend.Emails.send(params)
