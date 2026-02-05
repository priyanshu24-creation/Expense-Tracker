from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tracker", "0005_transaction_payment_mode"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="last_username_change_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
