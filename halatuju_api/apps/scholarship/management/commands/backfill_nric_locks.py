"""
One-off: take the IC lock on records whose card ALREADY confirms the typed number.

From 2026-07-29 an IC locks when the uploaded MyKad is genuine, its number matches what the
student typed, and the name matches too. That lock is taken at the end of an IC READ — first
upload, cockpit Re-run, bulk re-extract — because that is the one moment every route passes
through.

Which means shipping the rule locks nobody. A student who uploaded a matching card in June is
never re-read, so they would sit open indefinitely while a student uploading the same card
tomorrow locks immediately. Same evidence, different answer, decided by the accident of when
they happened to press a button — not a rule anyone could explain. This closes that gap once.

**No API calls and no re-extraction.** It reads the genuineness verdict and the name/number
ALREADY STORED on the document and re-applies the same predicate the live path uses
(``identity.locks_now``), so the sweep and the live rule cannot diverge. Nothing is re-read, so
nothing is billable and no stored extraction is overwritten — which matters, because
re-extraction rewrites the card's name and number and can legitimately come back different.

A card that was never scored for genuineness is NOT locked here — it is not evidence we have,
and the lock is one-way. Those need a Re-run first (which does cost a multimodal call).

    python manage.py backfill_nric_locks              # report only
    python manage.py backfill_nric_locks --apply
"""
from collections import Counter

from django.core.management.base import BaseCommand
from django.db import connection

from apps.courses.models import StudentProfile
from apps.scholarship import identity
from apps.scholarship.models import ApplicantDocument


class Command(BaseCommand):
    help = 'Lock ICs whose already-stored card read confirms the typed number. Report by default.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true',
                            help='Take the locks. Without it, report only.')

    def handle(self, *args, **options):
        apply = options['apply']
        db = connection.settings_dict
        self.stdout.write(f"DB: {db.get('ENGINE')} -> {db.get('HOST') or db.get('NAME')}")

        # The LIVE card only — a superseded one has been replaced and decides nothing. Newest
        # first so `seen` keeps the current card when a student has several on record.
        docs = (ApplicantDocument.objects
                .filter(doc_type='ic', superseded_at__isnull=True)
                .select_related('application__profile')
                .order_by('-id'))

        reasons = Counter()
        to_lock = []
        seen = set()
        for doc in docs.iterator():
            profile = getattr(getattr(doc, 'application', None), 'profile', None)
            if profile is None or profile.supabase_user_id in seen:
                continue
            seen.add(profile.supabase_user_id)
            if profile.nric_verified:
                reasons['already locked'] += 1
                continue
            cmp_ = identity.compare(doc, profile)
            if identity.locks_now(cmp_):
                to_lock.append((doc.application_id, profile))
                continue
            # Say WHY, in the order that makes it actionable: a card nobody scored is a
            # Re-run away, a mismatch is the student's to correct.
            if not cmp_['genuine']:
                reasons['card not scored / not genuine — needs a Re-run'] += 1
            elif cmp_['nric'] != 'match':
                reasons['number disagrees with the card — student must correct it'] += 1
            else:
                reasons['name disagrees with the card'] += 1

        for label, n in sorted(reasons.items()):
            self.stdout.write(f'  skipped — {label}: {n}')
        self.stdout.write(f'  WOULD LOCK: {len(to_lock)}')
        for app_id, _ in sorted(to_lock)[:60]:
            self.stdout.write(f'    app {app_id}')

        if not apply:
            self.stdout.write('\nReport only — re-run with --apply to take these locks.')
            return

        locked = clashed = 0
        for app_id, profile in to_lock:
            # Same guard as the live path: locking arms the partial unique index, and another
            # verified holder of this number would make the save raise. Leave it for
            # verify-&-accept to surface as `nric_conflict` rather than failing the sweep.
            if (StudentProfile.objects.filter(nric=profile.nric, nric_verified=True)
                    .exclude(pk=profile.pk).exists()):
                self.stdout.write(f'    app {app_id}: SKIPPED — number already verified elsewhere')
                clashed += 1
                continue
            profile.nric_verified = True
            profile.save(update_fields=['nric_verified'])
            locked += 1
        self.stdout.write(f'\nLocked {locked}; skipped {clashed} on a duplicate number.')
