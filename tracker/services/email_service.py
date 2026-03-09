from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from django.db.models import Sum

from tracker.models import EmailLog, Transaction
from tracker.services.prediction_service import _month_start
from tracker.models import Transaction as TransactionModel


@dataclass
class EmailContent:
    subject: str
    body: str
    email_type: str
    related_month: date


def _from_email() -> str:
    return getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@example.com")


def _format_currency(amount: float) -> str:
    return f"₹{amount:,.2f}"


def _top_category(user, month: date) -> str:
    top = (
        Transaction.objects.filter(
            user=user,
            type="expense",
            date__year=month.year,
            date__month=month.month,
        )
        .values("category")
        .order_by()
        .annotate(total=Sum("amount"))
        .order_by("-total")
        .first()
    )
    if not top:
        return "your top category"
    label_map = dict(TransactionModel.CATEGORY_CHOICES)
    return label_map.get(top["category"], top["category"].title())


def build_email_content(user, prediction, risk_level: str, today: date, force_type: Optional[str] = None) -> EmailContent:
    current_month = _month_start(today)
    related_month = prediction.month if force_type == "prediction" else current_month
    projected = _format_currency(prediction.predicted_expense)
    top_category = _top_category(user, current_month)

    if risk_level == "high":
        subject = "Bro… your wallet needs CPR 💸🚨"
        body = (
            f"At this rate, your money is leaving faster than your ex.\n"
            f"Projected next month expense: {projected} 😵\n"
            f"Biggest spender: {top_category}.\n"
            "Maybe slow down on the ‘just one more order’ habit?\n\n"
            "Open app → Check your spending."
        )
        return EmailContent(subject=subject, body=body, email_type=force_type or "overspend", related_month=related_month)

    if risk_level == "under":
        subject = "Whoa! Who are you and what have you done with your wallet? 👀"
        body = (
            "You’re spending way less than usual.\n"
            "Savings mode activated? Nice. But don’t forget to treat yourself responsibly 😉\n\n"
            "Open app → Check your spending."
        )
        return EmailContent(subject=subject, body=body, email_type=force_type or "underspend", related_month=related_month)

    subject = "Balanced. Disciplined. Financially attractive. 💼✨"
    body = (
        "You’re managing money like a pro.\n"
        f"Prediction for next month: {projected}\n"
        "Keep it steady."
    )
    return EmailContent(subject=subject, body=body, email_type=force_type or "healthy", related_month=related_month)


def should_send_email(user, email_type: str, related_month: date) -> bool:
    week_start = timezone.localdate() - timedelta(days=timezone.localdate().weekday())
    return not EmailLog.objects.filter(
        user=user,
        email_type=email_type,
        related_month=related_month,
        sent_at__date__gte=week_start,
    ).exists()


def send_behavior_email(user, email_content: EmailContent) -> bool:
    if not user.email:
        return False

    if not should_send_email(user, email_content.email_type, email_content.related_month):
        return False

    send_mail(
        subject=email_content.subject,
        message=email_content.body,
        from_email=_from_email(),
        recipient_list=[user.email],
        fail_silently=True,
    )

    EmailLog.objects.create(
        user=user,
        email_type=email_content.email_type,
        related_month=email_content.related_month,
    )
    return True
