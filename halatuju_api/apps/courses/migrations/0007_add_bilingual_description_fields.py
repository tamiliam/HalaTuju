# Generated manually for Sprint 16 — bilingual descriptions

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0006_add_headline_field'),
    ]

    operations = [
        migrations.AddField(
            model_name='course',
            name='headline_en',
            field=models.TextField(blank=True, default='', help_text='English headline'),
        ),
        migrations.AddField(
            model_name='course',
            name='description_en',
            field=models.TextField(blank=True, default='', help_text='English description/synopsis'),
        ),
    ]
