import os

from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from django.contrib.staticfiles.storage import staticfiles_storage

class Transaction(models.Model):
    TYPE_CHOICES = (
        ('income', 'Income'),
        ('expense', 'Expense'),
    )

    CATEGORY_CHOICES = (
        ('food', 'Food'),
        ('transport', 'Transport'),
        ('rent', 'Rent'),
        ('shopping', 'Shopping'),
        ('salary', 'Salary'),
        ('other', 'Other'),
    )
    PAYMENT_CHOICES = (
        ('online', 'Online Money'),
        ('cash', 'Cash Money'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE)

    type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    amount = models.FloatField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    payment_mode = models.CharField(max_length=10, choices=PAYMENT_CHOICES, default='online')
    date = models.DateField()
    description = models.CharField(max_length=255, blank=True)
    recurring_source = models.ForeignKey(
        "RecurringTransaction",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="generated_transactions",
    )

    def __str__(self):
        return f"{self.user.username} - {self.category} - {self.amount}"


class MonthlyBudget(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    month = models.DateField()
    total_amount = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "month")

    def __str__(self):
        return f"{self.user.username} - {self.month:%Y-%m} - {self.total_amount}"


class CategoryBudget(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    month = models.DateField()
    category = models.CharField(max_length=20, choices=Transaction.CATEGORY_CHOICES)
    amount = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "month", "category")

    def __str__(self):
        return f"{self.user.username} - {self.month:%Y-%m} - {self.category}"


class RecurringTransaction(models.Model):
    REPEAT_CHOICES = (
        ("daily", "Daily"),
        ("weekly", "Weekly"),
        ("monthly", "Monthly"),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    type = models.CharField(max_length=10, choices=Transaction.TYPE_CHOICES)
    amount = models.FloatField()
    category = models.CharField(max_length=20, choices=Transaction.CATEGORY_CHOICES)
    payment_mode = models.CharField(max_length=10, choices=Transaction.PAYMENT_CHOICES, default="online")
    description = models.CharField(max_length=255, blank=True)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    repeat = models.CharField(max_length=10, choices=REPEAT_CHOICES)
    weekdays = models.CharField(max_length=20, blank=True)
    active = models.BooleanField(default=True)
    last_generated_on = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.repeat} - {self.category}"


class SavingsGoal(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=120)
    target_amount = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.name}"


class SpendingPrediction(models.Model):
    RISK_CHOICES = (
        ("high", "High Risk"),
        ("under", "Under-utilizing"),
        ("healthy", "Healthy"),
        ("insufficient", "Insufficient Data"),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    month = models.DateField()
    predicted_expense = models.FloatField()
    risk_level = models.CharField(max_length=20, choices=RISK_CHOICES, default="insufficient")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "month")

    def __str__(self):
        return f"{self.user.username} - {self.month:%Y-%m} - {self.risk_level}"


class EmailLog(models.Model):
    EMAIL_TYPES = (
        ("overspend", "Overspending"),
        ("underspend", "Underspending"),
        ("healthy", "Healthy"),
        ("prediction", "Prediction"),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    email_type = models.CharField(max_length=20, choices=EMAIL_TYPES)
    sent_at = models.DateTimeField(auto_now_add=True)
    related_month = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} - {self.email_type} - {self.sent_at:%Y-%m-%d}"

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=100)
    image = models.ImageField(upload_to="profiles/", default="profiles/default.png")
    last_username_change_at = models.DateTimeField(null=True, blank=True)

    def _default_avatar_url(self):
        try:
            return staticfiles_storage.url("tracker/default-avatar.png")
        except Exception:
            return f"{settings.MEDIA_URL}profiles/default.png"

    @property
    def profile_image_url(self):
        name = getattr(self.image, "name", "")
        if not name or name == "profiles/default.png":
            return self._default_avatar_url()

        try:
            if hasattr(self.image, "path"):
                try:
                    path = self.image.path
                except Exception:
                    path = None
                if path and not os.path.exists(path):
                    return self._default_avatar_url()

            return self.image.url
        except Exception:
            return self._default_avatar_url()
    def __str__(self):
        return self.user.username
    
@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

class EmailOTP(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
