import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0065_trust_content'),
    ]

    operations = [
        migrations.CreateModel(
            name='StandingGift',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('field_pref', models.CharField(blank=True, default='', max_length=120)),
                ('state_pref', models.CharField(blank=True, default='', max_length=60)),
                ('max_amount', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('active', models.BooleanField(default=True)),
                ('last_allocated_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('sponsor', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE,
                                                 related_name='standing_gift', to='scholarship.sponsor')),
            ],
            options={
                'db_table': 'standing_gifts',
            },
        ),
    ]
