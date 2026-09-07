"""One-off: file the income documents that were left with a blank household tag.

BrightPath #20. A blank ``household_member`` is not "no slot" — it is a SLOT OF ITS OWN, and that
slot is permanently empty, so any document landing in it wins by default and stays live for ever.
Application 73 carried the same payslip twice: one copy tagged ``father`` and correctly replaced,
and one copy uploaded fifty seconds later with no tag, which sat beside the good one in the live
documents for a fortnight. The upload guard now fills the tag at source (``views.py``, the
last-resort ``implied_single_member`` branch); this repairs what accumulated before it.

The member is resolved exactly as the upload guard resolves it — the NAME read off the document
first, then the STR route's single declared earner — so the two can never disagree. A document
whose owner is genuinely undecidable is LEFT ALONE and reported, never guessed at.

Which copy keeps the live slot is decided by the SAME pair of rules an upload goes through, and by
the same functions — ``income_engine.dedupe_income_proof`` for the income proofs (STR, salary, EPF)
and ``promotion.should_promote`` for the rest. This command invents no rule of its own: a
non-genuine copy cannot displace a genuine one here either. See the note at ``DEDUPED`` for why
running only the first of those two rules gave the wrong answer on application 73.

    python manage.py backfill_untagged_income_docs            # report only
    python manage.py backfill_untagged_income_docs --apply

⚠ IT MUST RUN ON THE LIVE SERVICE, not from a checkout — the only place the production database
is reachable. It is registered as cron job ``backfill-untagged-income-docs``; the endpoint calls a
command with NO arguments, so the write is switched on there by ``INCOME_DOC_TAG_APPLY=1``
(set it, run the job, UNSET it — the ``backfill_requirements_snapshots`` pattern). Locally the
flag is the honest way. It reads STORED fields only: no Vision, no Gemini, no re-extraction.
"""
from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.utils import timezone

from apps.scholarship import promotion
from apps.scholarship.income_engine import (
    _DEDUP_DOC_TYPES, _HOUSEHOLD_WIDE_DEDUP, dedupe_income_proof, implied_single_member,
    income_dedup_rank, resolved_member_for,
)
from apps.scholarship.models import ApplicantDocument
from apps.scholarship.resolution import doc_match_verdict

INCOME_DOC_TYPES = ('parent_ic', 'salary_slip', 'epf', 'str')
# ⚠ THE INCOME PROOFS SETTLE THEIR SLOT BY THE DE-DUP'S RULE, NOT BY `promotion.should_promote`.
# At upload both run — promote, then de-dup — so the promote proxy never has the last word on
# these types; this sweep had only copied the first half. On application 73 that inverted the
# answer: `doc_quality` leads with `usable`, and a genuine payslip whose OCR misread one digit of
# the earner's IC reads NOT usable while a `not_salary` photo that read no identity at all reads
# usable, so the photo would have taken the slot from the real payslip. `parent_ic` is not a
# de-duped type and keeps the promote decision.
DEDUPED = _DEDUP_DOC_TYPES
HOUSEHOLD_WIDE = _HOUSEHOLD_WIDE_DEDUP


class Command(BaseCommand):
    help = "Tag live income documents left with a blank household_member, and settle their slot."

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true',
                            help='Write the tags and slot decisions. Without it, report only.')

    def _dedup_outcome(self, app, doc, member):
        """Who keeps the slot once ``doc`` carries ``member`` — the de-dup's OWN answer, so the
        report cannot promise something the write then contradicts. Returns (winner, existing),
        ``existing`` None when nothing is competing.

        Scope is copied from ``dedupe_income_proof``: salary/EPF are per-member, STR and the
        utility bills are household-wide (one recipient, inconsistent tags), so a member filter
        there would miss the very copy that wins.
        """
        q = app.documents.filter(doc_type=doc.doc_type, superseded_at__isnull=True).exclude(id=doc.id)
        if doc.doc_type not in HOUSEHOLD_WIDE:
            q = q.filter(household_member=member)
        others = list(q)
        if not others:
            return doc, None
        doc.household_member = member          # in memory only — rank as it WILL be tagged
        winner = max(others + [doc], key=income_dedup_rank)
        doc.household_member = ''              # ...and put it back; the write is the caller's
        return winner, max(others, key=income_dedup_rank)

    def handle(self, *args, **options):
        # The cron endpoint passes no arguments, so on the live service the env var IS the flag.
        # Report-only stays the default in both places: an unset var can only under-write.
        import os
        apply = options['apply'] or os.environ.get('INCOME_DOC_TAG_APPLY') == '1'
        db = connection.settings_dict
        self.stdout.write(f"DB: {db.get('ENGINE')} -> {db.get('HOST') or db.get('NAME')}")

        blanks = (ApplicantDocument.objects
                  .filter(doc_type__in=INCOME_DOC_TYPES, household_member='',
                          superseded_at__isnull=True)
                  .select_related('application')
                  .order_by('application_id', 'doc_type', 'uploaded_at'))

        tagged = kept = replaced = unresolved = 0
        for doc in blanks:
            app = doc.application
            member = resolved_member_for(app, doc) or implied_single_member(app)
            if not member:
                # Undecidable: a salary-route household where several members may hold documents,
                # or an STR route with no declared earner. The blank stands — it shows in the
                # cockpit's unassigned catch-all, which is honest, and a guess here would file one
                # earner's payslip under another.
                unresolved += 1
                self.stdout.write(
                    f"  skip doc #{doc.id} (app {app.id}, {doc.doc_type}) — owner not determinable "
                    f"(route={getattr(app, 'income_route', '') or 'unset'})")
                continue

            if doc.doc_type in DEDUPED:
                winner, existing = self._dedup_outcome(app, doc, member)
                verdict = ('takes the empty slot' if existing is None else
                           'replaces the live copy' if winner is doc else
                           f'goes to Replaced behind #{winner.id}')
            else:
                existing = (ApplicantDocument.objects
                            .filter(application=app, doc_type=doc.doc_type, household_member=member,
                                    request_code=doc.request_code, superseded_at__isnull=True)
                            .exclude(id=doc.id)
                            .order_by('-uploaded_at').first())
                if existing is None:
                    verdict = 'takes the empty slot'
                else:
                    usable = doc_match_verdict(doc) not in ('mismatch', 'unreadable')
                    verdict = ('replaces the live copy'
                               if promotion.should_promote(doc, existing, usable=usable)
                               else f'goes to Replaced behind #{existing.id}')

            self.stdout.write(
                f"  {'' if apply else '[report] '}doc #{doc.id} (app {app.id}, {doc.doc_type}, "
                f"{doc.original_filename or 'no filename'}) -> {member}; {verdict}")

            if apply:
                with transaction.atomic():
                    doc.household_member = member
                    doc.save(update_fields=['household_member'])
                    if doc.doc_type in DEDUPED:
                        # ⚠ The de-dup is the WRITER for these types — never a second copy of the
                        # decision here. It re-reads the live set with the tag now written, so the
                        # report above and this write ask `income_dedup_rank` the same question.
                        dedupe_income_proof(app, member, doc.doc_type)
                    elif existing is not None:
                        now = timezone.now()
                        if verdict == 'replaces the live copy':
                            ApplicantDocument.objects.filter(id=existing.id).update(
                                superseded_at=now, superseded_by=doc)
                        else:
                            ApplicantDocument.objects.filter(id=doc.id).update(
                                superseded_at=now, superseded_by=existing)
            tagged += 1
            if existing is None:
                pass
            elif verdict == 'replaces the live copy':
                replaced += 1
            else:
                kept += 1

        self.stdout.write(self.style.SUCCESS(
            f"{tagged} document(s) {'tagged' if apply else 'would be tagged'} "
            f"({replaced} replacing a live copy, {kept} filed as Replaced); "
            f"{unresolved} left blank as undecidable."))
        if tagged and not apply:
            self.stdout.write("Re-run with --apply to write them.")
