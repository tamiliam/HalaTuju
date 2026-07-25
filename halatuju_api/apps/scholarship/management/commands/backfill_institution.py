"""Backfill + audit ``chosen_programme.institution`` — the must-fill field (owner 2026-07-25).

Why its own command rather than a flag on ``backfill_offer_pathways``: that command walks only
applications that HAVE an offer letter, because settling a PATHWAY needs one. The institution does
not — a course offered at a single campus resolves from the catalogue alone, which is exactly the
student who has uploaded nothing yet. Scanning only offer-holders would miss them.

READ-ONLY by default. Reports every application whose institution is blank, grouped by CAUSE, so
what cannot be filled automatically is visible rather than silently absent:

    filled            → the writer resolves it (this is what --apply persists)
    stpm              → pre-U STPM: deliberately not resolved (see sync_institution_from_catalogue)
    clash             → the offer names an institution that is NOT a campus of the declared course
    catalogue_gap     → the course has ZERO course_institutions rows — fix the CATALOGUE
    multi_campus      → 2+ campuses and no usable offer to disambiguate
    unresolvable      → no course_id and no pre-U route

Never re-OCRs anything: it reads ALREADY-STORED ``vision_fields`` via ``student_offer_check``, so it
is safe to run from a local checkout against the pooler (``docs/lessons.md`` — a local re-extraction
destroys ``vision_fields``).

    python manage.py backfill_institution            # report only
    python manage.py backfill_institution --apply    # persist the resolvable ones
"""
from collections import Counter, defaultdict

from django.core.management.base import BaseCommand
from django.db import connection

from apps.courses.models import CourseInstitution
from apps.scholarship.models import ApplicantDocument, ScholarshipApplication
from apps.scholarship.pathway_engine import student_offer_check
from apps.scholarship.services import sync_institution_from_catalogue


class Command(BaseCommand):
    help = "Fill (or audit) chosen_programme.institution across applications."

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true',
                            help='Persist the resolvable ones. Without it, report only.')
        parser.add_argument('--status', default='',
                            help='Limit to one application status (e.g. shortlisted).')

    def handle(self, *args, **options):
        db = connection.settings_dict
        self.stdout.write(f"DB: {db.get('ENGINE')} -> {db.get('HOST') or db.get('NAME')}")
        apply = options['apply']

        qs = ScholarshipApplication.objects.select_related('profile').order_by('id')
        if options['status']:
            qs = qs.filter(status=options['status'])

        counts = Counter()
        by_cause = defaultdict(list)
        for app in qs:
            cp = app.chosen_programme if isinstance(app.chosen_programme, dict) else {}
            if (cp.get('institution') or '').strip():
                counts['already_filled'] += 1
                continue
            cause, detail = self._classify(app, cp)
            if cause == 'filled':
                if apply and sync_institution_from_catalogue(app):
                    app.refresh_from_db()
                    detail = (app.chosen_programme or {}).get('institution', '')
                counts['filled'] += 1
            else:
                counts[cause] += 1
            by_cause[cause].append(f"#{app.pk} [{app.status}] {detail}")

        for cause in ('filled', 'stpm', 'clash', 'catalogue_gap', 'multi_campus', 'unresolvable'):
            rows = by_cause.get(cause) or []
            if not rows:
                continue
            self.stdout.write(f"\n{cause.upper()} ({len(rows)}):")
            for r in rows:
                self.stdout.write(f"  {r}")

        verb = 'filled' if apply else 'fillable'
        self.stdout.write(self.style.SUCCESS(
            f"\nInstitution backfill: {counts['filled']} {verb}, "
            f"{counts['already_filled']} already on file, "
            f"{sum(v for k, v in counts.items() if k not in ('filled', 'already_filled'))} "
            f"need a human"))

    # ── classification (pure reporting; mirrors the writer's own order) ──────────
    def _classify(self, app, cp):
        from apps.scholarship import offer_pathway as op
        cid = (cp.get('course_id') or '').strip()
        pathway = (app.chosen_pathway or '').strip().lower()

        if cid:
            campuses = CourseInstitution.objects.filter(course_id=cid).count()
            if campuses == 0:
                return 'catalogue_gap', f"course {cid} has no catalogue institution"
            offer_inst, wrong_person = self._offer_institution(app)
            if campuses == 1:
                if op.offer_contradicts_course_institution(cid, offer_inst):
                    return 'clash', (f"offer says '{offer_inst}', course {cid} is at "
                                     f"'{op.sole_catalogue_institution(cid)}'")
                return 'filled', op.sole_catalogue_institution(cid)
            if not offer_inst:
                return 'multi_campus', (
                    f"course {cid} has {campuses} campuses; "
                    + ('offer is a wrong-person letter' if wrong_person else 'no offer institution'))
            if op.catalogue_institution(cid, offer_inst):
                return 'filled', op.catalogue_institution(cid, offer_inst)
            return 'clash', f"offer says '{offer_inst}', not a campus of {cid}"

        if pathway == 'matric':
            vc = op.preu_course_id('matric', (app.pre_u_track or '').strip().lower())
            offer_inst, _ = self._offer_institution(app)
            hint = offer_inst or (app.pre_u_institution or '').strip()
            canon = op.catalogue_institution(vc, hint) if (vc and hint) else ''
            if canon:
                return 'filled', canon
            return 'unresolvable', f"matric track='{app.pre_u_track}' hint='{hint}'"
        if pathway == 'stpm':
            return 'stpm', f"declared school '{app.pre_u_institution or '-'}' — needs a human"
        return 'unresolvable', f"pathway='{pathway or '-'}' no course_id"

    def _offer_institution(self, app):
        """(institution, wrong_person) off the LIVE offer, reading stored fields only."""
        offer = (ApplicantDocument.objects
                 .filter(application=app, doc_type='offer_letter', superseded_at__isnull=True)
                 .order_by('-uploaded_at').first())
        if offer is None:
            return '', False
        chk = student_offer_check(offer)
        wrong = chk.get('name') == 'mismatch' or chk.get('ic') == 'mismatch'
        return ('' if wrong else (chk.get('institution') or '').strip()), wrong
