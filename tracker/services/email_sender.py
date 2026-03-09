import logging
from typing import Optional

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def _send_via_sendgrid_api(to_email: str, subject: str, body: str) -> Optional[str]:
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Content, Email, Mail
    except Exception:
        logger.exception("SendGrid library not available")
        return "Email service not configured"

    try:
        message = Mail(
            Email(settings.DEFAULT_FROM_EMAIL),
            subject,
            Email(to_email),
            Content("text/plain", body),
        )
        sg = SendGridAPIClient(api_key=settings.SENDGRID_API_KEY)
        response = sg.client.mail.send.post(request_body=message.get())
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
