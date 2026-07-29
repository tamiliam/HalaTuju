"""Seed the Layer 0 catalogue, and give each existing programme the configuration it ALREADY HAS.

⚠ **THE ONLY CORRECT OUTPUT OF THIS COMMAND IS "NOTHING CHANGES."** Every row it writes is a
statement about what the code already does, made explicit so that a later sprint can move the
decision here without altering behaviour. If running this changes what BrightPath asks a student
for, the seed is wrong — not the code.

Idempotent: safe to re-run. Items are matched on (kind, code) and updated in place, so correcting
a label or a default is a re-run rather than a migration.

    python manage.py seed_application_catalogue            # apply
    python manage.py seed_application_catalogue --dry-run  # show what would change
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from ...models import ApplicationItem, Programme, ProgrammeApplicationItem

# ─────────────────────────────────────────────────────────────────────────────
# The catalogue. Each row is (code, label_key, is_core, default_state).
#
# ⚠ `label_key` POINTS AT A KEY THAT ALREADY EXISTS WHEREVER ONE DOES. Sprint 2 invented an
# `apply.docs.*` / `apply.questions.*` namespace and nothing was ever created behind it — 19 keys
# with no messages, invisible to `check-i18n.js` because it cannot see a string held in a database
# row (TD-197). Correcting it in Layer 0 Sprint 5 showed the fix was smaller AND better than
# creating them: EIGHT of the nine document labels already existed as `scholarship.docs.type.<code>`,
# translated into all three languages, and minting a parallel set would have been the same document
# named twice — the drift this whole layer exists to remove. Only `income_proof` needed a new one
# (it is the income ROUTE, not a document, so it never had a student-facing card).
#
# Questions genuinely had no coherent set, so they get `admin.programme.question.<code>` — named
# for the screen that renders them, which is the honest home for an admin-facing label.
#
# The two prefixes differ on purpose. A document label is genuinely shared with the student UI (the
# same noun); a question label is an admin's summary of a form field. `test_requirements.py` no
# longer checks the PREFIX — it asserts the key EXISTS in `en.json`, which is what was wanted all
# along and what a shape-check was standing in for.
#
# `is_core` is a POLICY floor set by the owner on 2026-07-28 — identity card, results slip,
# offer letter, consent, and the family/income block — NOT an engineering judgement. An
# organisation may never switch a core item off.
#
# `default_state` reproduces TODAY'S behaviour for a not-yet-submitted application, read from
# `services.application_completeness` and `services.consent_blockers`.
# ─────────────────────────────────────────────────────────────────────────────

DOCUMENTS = [
    # code,                  label_key,                                  core,  default
    ('ic',                   'scholarship.docs.type.ic',                      True,  'required'),
    ('results_slip',         'scholarship.docs.type.results_slip',            True,  'required'),
    # Compulsory for every route since the 2026-06-05 gate v2. A Form-Six student has no
    # university offer letter and uploads a school enrolment letter instead — that is handled
    # per-STUDENT inside `_offer_blocks`, and is NOT a per-organisation setting. Core here means
    # the ORGANISATION cannot remove it; it does not flatten the route logic.
    ('offer_letter',         'scholarship.docs.type.offer_letter',            True,  'required'),
    # ONE switch over the whole income route engine — see DOCUMENT_AGGREGATES in requirements.py.
    ('income_proof',         'scholarship.docs.type.income_proof',            True,  'required'),
    # Offered, never blocking. These are why `default_state` had to stop being a boolean.
    ('water_bill',           'scholarship.docs.type.water_bill',              False, 'optional'),
    ('electricity_bill',     'scholarship.docs.type.electricity_bill',        False, 'optional'),
    ('statement_of_intent',  'scholarship.docs.type.statement_of_intent',     False, 'optional'),
    ('photo',                'scholarship.docs.type.photo',                   False, 'optional'),
    # Added in Sprint 3b, and the reason is worth recording: the student Documents tab has been
    # rendering a `school_leaving_cert` card all along, but the Sprint 2 catalogue never listed it
    # and neither did the front end's own `OTHER_OPTIONAL_DOC_TYPES` — three descriptions of "what
    # we offer", all different, none of them complete. It went unnoticed because nothing consumed
    # the catalogue for RENDERING until now. From 3b the catalogue decides which cards appear, so
    # an omission here would have silently withdrawn a document students can upload today.
    ('school_leaving_cert',  'scholarship.docs.type.school_leaving_cert',     False, 'optional'),
]

QUESTIONS = [
    # The four "your story" fields — `details_done` requires all four today.
    ('aspirations',          'admin.programme.question.aspirations',        False, 'required'),
    ('plans',                'admin.programme.question.plans',              False, 'required'),
    ('daily_life',           'admin.programme.question.daily_life',         False, 'required'),
    ('fears',                'admin.programme.question.fears',              False, 'required'),
    # `_family_done` — the structured roster. Core: the family/income block, per the owner.
    ('family_roster',        'admin.programme.question.family_roster',      True,  'required'),
    # `funding_done` — categories + programme_months.
    ('funding',              'admin.programme.question.funding',            False, 'required'),
    # `address_done` — resolved from the profile, asked on the apply form.
    ('address',             'admin.programme.question.address',             False, 'required'),
    # `consent_done`. Core, and it is worth saying why plainly: consent is a legal requirement,
    # not a programme preference. It appears in the catalogue so an org admin can SEE that the
    # application asks for it and that they cannot remove it — a locked row is information, a
    # missing row is a mystery.
    ('consent',              'admin.programme.question.consent',            True,  'required'),
    # Never blocked anything.
    ('justification',        'admin.programme.question.justification',      False, 'optional'),
    ('anything_else',        'admin.programme.question.anything_else',      False, 'optional'),
]


class Command(BaseCommand):
    help = 'Seed the application-item catalogue and each programme\'s current configuration.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Report what would change without writing anything.')

    @transaction.atomic
    def handle(self, *args, **opts):
        dry = opts['dry_run']
        created, updated = 0, 0

        for kind, rows in (('document', DOCUMENTS), ('question', QUESTIONS)):
            for code, label_key, is_core, default_state in rows:
                desired = dict(label_key=label_key, is_core=is_core,
                               default_state=default_state, is_active=True)
                existing = ApplicationItem.objects.filter(kind=kind, code=code).first()
                if existing is None:
                    created += 1
                    self.stdout.write(f'  + {kind}:{code} ({default_state}'
                                      f'{", core" if is_core else ""})')
                    if not dry:
                        ApplicationItem.objects.create(kind=kind, code=code, **desired)
                elif any(getattr(existing, f) != v for f, v in desired.items()):
                    updated += 1
                    self.stdout.write(f'  ~ {kind}:{code}')
                    if not dry:
                        for f, v in desired.items():
                            setattr(existing, f, v)
                        existing.save(update_fields=list(desired))

        self.stdout.write(self.style.SUCCESS(
            f'catalogue: {created} created, {updated} updated'))

        # ── Existing programmes ──────────────────────────────────────────────
        #
        # ⚠ We write NO ProgrammeApplicationItem rows. That is deliberate, and it is the safer
        # choice of the two available.
        #
        # With no explicit row, `requirements.resolve()` falls through to the item's own
        # `default_state` (and to 'required' for a core item) — which IS today's behaviour, by
        # construction. Seeding an explicit row per programme would say the same thing twice, and
        # the copy would then be free to drift: correcting a default in the catalogue would
        # silently fail to reach a programme that already had a row overriding it with the old
        # value. An organisation's row should mean "we deliberately chose this", not "somebody
        # ran a seed once".
        programmes = Programme.objects.filter(is_active=True).count()
        self.stdout.write(
            f'{programmes} active programme(s) left with NO explicit selections — they resolve '
            f'to the catalogue defaults, which reproduce current behaviour exactly.')

        if ProgrammeApplicationItem.objects.exists():
            self.stdout.write(self.style.WARNING(
                'NOTE: explicit programme selections already exist; this command did not touch '
                'them. They override the defaults above.'))

        if dry:
            self.stdout.write(self.style.WARNING('dry run — nothing written'))
            transaction.set_rollback(True)
