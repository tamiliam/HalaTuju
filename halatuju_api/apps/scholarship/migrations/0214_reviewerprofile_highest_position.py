"""Request #69 (2026-11-17): `reviewer_profiles.highest_position`, the highest position a staff member
has held. ADDITIVE: one ADD COLUMN with a DATABASE default '' so the old image's inserts (which do not
name the column) still pass between migrate and deploy. Blank = not given.

(0211's note said its DROP COLUMN step would be 0212; that step now takes the next free number.)
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0213_document_replace_count'),
    ]

    operations = [
        migrations.AddField(
            model_name='reviewerprofile',
            name='highest_position',
            field=models.CharField(blank=True, choices=[('c_level', 'C-level, founder or business owner'), ('head', 'Head of department or senior manager'), ('manager', 'Manager'), ('individual', 'Individual contributor (academic, doctor, etc.)')], db_default='', default='', max_length=20),
        ),
    ]
