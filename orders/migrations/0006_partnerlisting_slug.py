# orders/migrations/0006_partnerlisting_slug.py
from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0005_orderitem_partner_partnerlisting"),
    ]

    operations = [
        migrations.AddField(
            model_name="partnerlisting",
            name="slug",
            field=models.SlugField(max_length=120, null=True, blank=True, unique=False),
        ),
    ]
