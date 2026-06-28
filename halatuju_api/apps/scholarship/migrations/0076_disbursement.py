# Post-award lifecycle S4 — Disbursement/tranche ledger (money-OUT).
# The stray `AlterField` on scholarshipcohort.name that makemigrations keeps
# re-proposing (a foreign help_text drift, not ours) is deliberately omitted.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0075_alter_scholarshipapplication_status_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='Disbursement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('status', models.CharField(choices=[('scheduled', 'Scheduled'), ('due', 'Due'), ('released', 'Released'), ('withheld', 'Withheld'), ('returned', 'Returned')], default='scheduled', max_length=20)),
                ('sequence', models.PositiveSmallIntegerField(default=1)),
                ('label', models.CharField(blank=True, default='', max_length=100)),
                ('scheduled_for', models.DateField(blank=True, null=True)),
                ('released_at', models.DateTimeField(blank=True, null=True)),
                ('actioned_by', models.CharField(blank=True, default='', max_length=254)),
                ('reference', models.CharField(blank=True, default='mock', max_length=100)),
                ('note', models.CharField(blank=True, default='', max_length=500)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('application', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='disbursements', to='scholarship.scholarshipapplication')),
                ('sponsorship', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='disbursements', to='scholarship.sponsorship')),
            ],
            options={
                'db_table': 'disbursements',
                'ordering': ['sequence', 'id'],
            },
        ),
    ]
