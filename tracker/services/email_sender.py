import logging
from typing import Optional

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)

PUBLIC_WEBMAIL_DOMAINS = {
    "gmail.com",
    "googlemail.com",
    "yahoo.com",
    "ymail.com",
    "rocketmail.com",
    "outlook.com",
    "hotmail.com",
    "live.com",
    "msn.com",
    "aol.com",
    "icloud.com",
    "me.com",
    "mac.com",
}


def _sendgrid_sender_error(message: str) -> str:
    if settings.DEBUG:
        return f"Failed to send email: {message}"
    return "Email service not configured"


def _build_sendgrid_payload(to_email: str, subject: str, body: str):
    recipient_email = (to_email or "").strip()
    sender_email = (settings.DEFAULT_FROM_EMAIL or "").strip()

    if not recipient_email:
        return None, "Recipient email is required"

    if not sender_email:
        logger.error("DEFAULT_FROM_EMAIL is not configured for SendGrid.")
        return None, "Email service not configured"

    sender_domain = sender_email.rsplit("@", 1)[-1].lower() if "@" in sender_email else ""
    if sender_domain in PUBLIC_WEBMAIL_DOMAINS:
        logger.error(
            "DEFAULT_FROM_EMAIL=%s uses a consumer mailbox domain. "
            "SendGrid mail to Gmail requires a verified custom domain sender for DMARC alignment.",
            sender_email,
        )
        return None, (
            "Use a verified custom-domain sender email in DEFAULT_FROM_EMAIL, "
            "not a Gmail/Outlook/Yahoo address"
        )

    return {
        "from": {"email": sender_email},
        "personalizations": [
            {
                "to": [{"email": recipient_email}],
            }
        ],
        "subject": subject or "",
        "content": [
            {
                "type": "text/plain",
                "value": body or "",
            }
        ],
    }, None


def _send_via_sendgrid_api(to_email: str, subject: str, body: str) -> Optional[str]:
    try:
        from sendgrid import SendGridAPIClient
    except Exception:
        logger.exception("SendGrid library not available")
        return "Email service not configured"

    payload, payload_error = _build_sendgrid_payload(to_email, subject, body)
    if payload_error:
        return _sendgrid_sender_error(payload_error)

    try:
        sg = SendGridAPIClient(api_key=settings.SENDGRID_API_KEY)
        response = sg.client.mail.send.post(request_body=payload)
        status = getattr(response, "status_code", None)
        if status and not (200 <= status < 300):
            body_text = getattr(response, "body", b"")
            if isinstance(body_text, bytes):
                body_text = body_text.decode("utf-8", "ignore")
            if settings.DEBUG:
                return f"Failed to send email: SendGrid {status} {body_text}"
            return "Failed to send email. Try again."
    except Exception as exc:
        logger.exception("SendGrid send failed")
        if settings.DEBUG:
            return f"Failed to send email: {exc}"
        return "Failed to send email. Try again."

    return None


def _send_via_smtp(to_email: str, subject: str, body: str) -> Optional[str]:
    try:
        send_mail(
            subject,
            body,
            settings.DEFAULT_FROM_EMAIL,
            [to_email],
            fail_silently=False,
        )
        return None
    except Exception as exc:
        logger.exception("SMTP send failed")
        if settings.DEBUG:
            return f"Failed to send email: {exc}"
        return "Failed to send email. Try again."


def send_app_email(to_email: str, subject: str, body: str) -> Optional[str]:
    if settings.SENDGRID_API_KEY:
        return _send_via_sendgrid_api(to_email, subject, body)

    if getattr(settings, "USE_GMAIL_SMTP", False):
        logger.warning("SENDGRID_API_KEY missing; using explicit Gmail SMTP fallback.")
        return _send_via_smtp(to_email, subject, body)

    logger.error("SENDGRID_API_KEY missing and Gmail SMTP fallback is disabled.")
    if settings.DEBUG:
        return "Failed to send email: Email service not configured"
    return "Email service not configured"
