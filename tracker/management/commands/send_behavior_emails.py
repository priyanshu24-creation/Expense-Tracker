from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from django.conf import settings

from tracker.services.prediction_service import build_prediction_summary
from tracker.services.email_service import build_email_content, send_behavior_email


class Command(BaseCommand):
    help = "Send predictive spending behavior emails."

    def handle(self, *args, **options):
        today = timezone.localdate()
        first_week_days = int(getattr(settings, "PREDICTION_FIRST_WEEK_DAYS", 7))

        sent = 0
        skipped = 0

        for user in User.objects.filter(is_active=True):
            if not user.email:
                skipped += 1
                continue

            prediction = build_prediction_summary(user, today)
            if prediction.risk_level == "insufficient":
                skipped += 1
                continue

            if prediction.risk_level in ("high", "under"):
                content = build_email_content(user, prediction, prediction.risk_level, today)
                if send_behavior_email(user, content):
                    sent += 1
                else:
                    skipped += 1
                continue

            if today.day <= first_week_days:
                content = build_email_content(user, prediction, "healthy", today, force_type="prediction")
                if send_behavior_email(user, content):
                    sent += 1
                else:
                    skipped += 1
            else:
                skipped += 1

        self.stdout.write(self.style.SUCCESS(f"Behavior emails sent: {sent}, skipped: {skipped}"))
