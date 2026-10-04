"""Seed a LOCAL SQLite database so the officer console can be reviewed on a developer's machine.

TD-194 (2026-10-05). The console signs in through Supabase and then asks the API who you are
(`/api/v1/admin/role/`); locally that API is `manage.py runserver` on SQLite, which knows nobody.
This makes you a super admin of a made-up organisation and gives the console a handful of
made-up applications to draw — one at each main stage of the funnel, built by the test factory
(`apps.scholarship.tests.factories`), which makes only states the product can reach.

    python manage.py migrate
    python manage.py seed_local_console --email you@example.com
    python manage.py runserver              # with SUPABASE_URL set, see halatuju_api/CLAUDE.md

Sign in to http://localhost:3000/admin with that address: the API links your Supabase account to
the seeded admin on your first VERIFIED sign-in (`PartnerAdminMixin.get_admin`'s email fallback).
`--uid` links it up front instead.

⛔ **SQLite ONLY — it refuses any other database.** Everything it writes is fictional (fake
NRICs, "Test Student" names, an organisation called "Local Review"), and it must never reach a
real one: with `DATABASE_URL` or `DB_HOST` set the database is not SQLite and it stops before
writing a row. No production data is read either. Re-running is safe: the demo set is made once.
"""
from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

ORG_CODE = 'local-review'
GIFT_CODE = 'local-review-gift'

#: One application per stage the console's lists and cockpit draw. `(stage, outcome)`.
DEMO_STAGES = (
    ('submitted', None), ('shortlisted', None), ('profile_complete', None), ('assigned', None),
    ('interviewing', None), ('verdict_recorded', 'recommend'), ('awaiting_qc', 'recommend'),
    ('awaiting_qc', 'decline'), ('recommended', None), ('awarded', None),
)


class Command(BaseCommand):
    help = 'Seed a local SQLite database with a super admin and made-up applications (TD-194).'

    def add_arguments(self, parser):
        parser.add_argument('--email', required=True,
                            help='The address you sign in to the console with.')
        parser.add_argument('--uid', default='',
                            help='Your Supabase user id (optional; the first sign-in links it).')
        parser.add_argument('--name', default='Local Reviewer')

    def handle(self, *args, **opts):
        if connection.vendor != 'sqlite':
            raise CommandError(
                f'seed_local_console writes made-up data and runs on a local SQLite database '
                f'only; this one is {connection.vendor!r}. Unset DATABASE_URL / DB_HOST.')
        self.stdout.write(f"DB: sqlite -> {connection.settings_dict.get('NAME')}")
        with transaction.atomic():
            org, made = self._demo_set()
            admin = self._super_admin(org, opts['email'].strip().lower(), opts['uid'].strip(),
                                      opts['name'])
        self.stdout.write(self.style.SUCCESS(
            f"{'Seeded' if made else 'Already seeded'}: organisation {org.code!r}, gift "
            f"{GIFT_CODE!r}; super admin {admin.email} "
            f"({'linked' if admin.supabase_user_id else 'links on first sign-in'})."))

    def _demo_set(self):
        from apps.scholarship.tests import factories as f
        Org = apps.get_model('courses', 'PartnerOrganisation')
        org = Org.objects.filter(code=ORG_CODE).first()
        if org is not None:
            return org, False
        org = f.make_org(code=ORG_CODE, name='Local Review Organisation')
        gift = f.make_programme(organisation=org, code=GIFT_CODE, name_en='Local Review Bursary',
                                is_active=True)
        cohort = f.make_cohort(programme=gift, code='local-review-2026', is_open=True,
                               name='Local Review Bursary 2026')
        reviewer = f.make_admin('reviewer', owning_org=org, name='Local Demo Reviewer',
                                email='reviewer@local-review.invalid')
        for stage, outcome in DEMO_STAGES:
            needs_reviewer = f.stage_reaches(stage, 'assigned')
            f.make_application(stage, outcome=outcome, cohort=cohort,
                               reviewer=reviewer if needs_reviewer else None)
        return org, True

    def _super_admin(self, org, email, uid, name):
        Admin = apps.get_model('courses', 'PartnerAdmin')
        admin = Admin.objects.filter(email=email).first()
        if admin is None:
            admin = Admin(email=email)
        admin.name = admin.name or name
        admin.role, admin.is_super_admin, admin.is_active = 'super', True, True
        admin.owning_organisation = org
        if uid:
            admin.supabase_user_id = uid
        admin.save()
        return admin
