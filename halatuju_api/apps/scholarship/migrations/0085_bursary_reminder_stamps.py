# S6: signing-chain reminder stamps on BursaryAgreement. Additive — apply migrate-first.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0084_guarantor_phone_verify'),
    ]

    operations = [
        migrations.AddField(
            model_name='bursaryagreement',
            name='witness_reminded_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='bursaryagreement',
            name='countersign_reminded_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
