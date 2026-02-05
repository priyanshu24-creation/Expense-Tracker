from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tracker", "0004_alter_profile_full_name"),
    ]

    operations = [
        migrations.AddField(
            model_name="transaction",
            name="payment_mode",
            field=models.CharField(
                choices=[("online", "Online Money"), ("cash", "Cash Money")],
                default="online",
                max_length=10,
            ),
        ),
    ]
