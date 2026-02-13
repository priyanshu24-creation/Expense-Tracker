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

    def __str__(self):
        return f"{self.user.username} - {self.category} - {self.amount}"

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
