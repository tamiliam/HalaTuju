from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0101_payments_module'),
    ]

    operations = [
        migrations.AddField(
            model_name='paymentrun',
            name='period_month',
            field=models.DateField(blank=True, null=True),
        ),
    ]
