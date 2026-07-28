"""PF-2 — reconcile the module flags with what production actually does (2026-07-28).

Migration `0098` (scholarship) seeded BrightPath with `module_payout = False`. The payout stack
shipped AFTERWARDS — payments, Vircle, contracts, the Sprint-14 finance chain — so the flag has
been contradicting production ever since.

**Why this is a sprint of its own, ahead of any enforcement.** The four flags are currently read
by NOTHING (only `module_scholarship` is *written*, by the Add-tenant slice). That makes the
contradiction latent and harmless today — and it is exactly why it is dangerous tomorrow: the
first sprint that starts *enforcing* these flags would take BrightPath's live payout surfaces
dark in production, with real money mid-flight. Reconcile first, enforce later. Never together.

**Reconciled against evidence, not against intent** (prod, 2026-07-28):

    module_scholarship  already True   143 applications
    module_sponsor_pool already True   48 sponsorships, 6 confirmed credits
    module_comms_whatsapp already True 128 WhatsApp messages sent
    module_payout       False -> True  15 payment runs (2 completed), 19 disbursements,
                                       46 students with a Vircle wallet

Only `module_payout` moves. The other three were already correct — worth stating, because a
first reading of "the flags contradict production" invites the assumption that all four are
wrong, and flipping a flag that was already right is how a reconciliation introduces the drift
it set out to remove.

The nine REFERRAL organisations (cumig, ewrf, hyo, mhm, hss, pptm, smc, sathya_sai, tara)
correctly hold all four False. They refer students; they do not run a programme. That is not
drift and must not be "fixed".

Idempotent and targeted: keyed on `code='brightpath'`, and the reverse restores False, so this
is safely re-runnable and revertible.

MIGRATE-FIRST PROD DML (hand-written — never `manage.py sqlmigrate`; local is SQLite, prod is
Postgres):

    UPDATE partner_organisations SET module_payout = true WHERE code = 'brightpath';

    INSERT INTO django_migrations (app, name, applied)
        VALUES ('courses', '0067_reconcile_module_flags', NOW());

POST-CHECK: brightpath reads True on all four flags; the nine referral orgs still read False on
all four; no other row changed.
"""

from django.db import migrations

TENANT_CODE = 'brightpath'


def reconcile(apps, schema_editor):
    Org = apps.get_model('courses', 'PartnerOrganisation')
    # Targeted by code, not by "any org with applications" — a rule that clever would also
    # sweep a future tenant that has applications but genuinely has no payout module.
    Org.objects.filter(code=TENANT_CODE).update(module_payout=True)


def unreconcile(apps, schema_editor):
    Org = apps.get_model('courses', 'PartnerOrganisation')
    Org.objects.filter(code=TENANT_CODE).update(module_payout=False)


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0066_alter_partneradmin_role'),
    ]

    operations = [
        migrations.RunPython(reconcile, unreconcile),
    ]
