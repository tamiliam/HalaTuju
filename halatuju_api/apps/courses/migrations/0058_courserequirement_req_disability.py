from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0057_studentprofile_chosen_pathway_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='courserequirement',
            name='req_disability',
            field=models.BooleanField(
                default=False,
                help_text="Student MUST have a declared disability — special-needs (MBPK) "
                          "intake. Gated on the onboarding 'Physical disability' signal.",
            ),
        ),
    ]
