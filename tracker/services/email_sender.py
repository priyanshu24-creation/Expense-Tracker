import logging
from typing import Optional

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def _build_sendgrid_payload(to_email: str, subject: str, body: str):
    recipient_email = (to_email or "").strip()
    sender_email = (settings.DEFAULT_FROM_EMAIL or "").strip()

    if not recipient_email:
        return None, "Recipient email is required"

    if not sender_email:
        logger.error("DEFAULT_FROM_EMAIL is not configured for SendGrid.")
        return None, "Email service not configured"

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
        if settings.DEBUG:
            return f"Failed to send email: {payload_error}"
        return "Failed to send email. Try again."

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

    if not settings.DEBUG:
        logger.error("SENDGRID_API_KEY not configured in production.")
        return "Email service not configured"

    return _send_via_smtp(to_email, subject, body)
