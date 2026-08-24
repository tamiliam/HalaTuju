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

Which copy keeps the live slot is decided by ``promotion.should_promote``, the same judgement every
upload goes through. This command does not invent a rule: an unreadable copy cannot displace a good
one here either.

    python manage.py backfill_untagged_income_docs            # report only
    python manage.py backfill_untagged_income_docs --apply
"""
from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.utils import timezone

from apps.scholarship import promotion
from apps.scholarship.income_engine import implied_single_member, resolved_member_for
from apps.scholarship.models import ApplicantDocument
from apps.scholarship.resolution import doc_match_verdict

INCOME_DOC_TYPES = ('parent_ic', 'salary_slip', 'epf', 'str')


class Command(BaseCommand):
    help = "Tag live income documents left with a blank household_member, and settle their slot."

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true',
                            help='Write the tags and slot decisions. Without it, report only.')

    def handle(self, *args, **options):
        apply = options['apply']
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

            existing = (ApplicantDocument.objects
                        .filter(application=app, doc_type=doc.doc_type, household_member=member,
                                request_code=doc.request_code, superseded_at__isnull=True)
                        .exclude(id=doc.id)
                        .order_by('-uploaded_at').first())
            if existing is None:
                verdict = 'takes the empty slot'
            else:
                usable = doc_match_verdict(doc) not in ('mismatch', 'unreadable')
                verdict = ('replaces the live copy' if promotion.should_promote(doc, existing, usable=usable)
                           else f'goes to Replaced behind #{existing.id}')

            self.stdout.write(
                f"  {'' if apply else '[report] '}doc #{doc.id} (app {app.id}, {doc.doc_type}, "
                f"{doc.original_filename or 'no filename'}) -> {member}; {verdict}")

            if apply:
                with transaction.atomic():
                    doc.household_member = member
                    doc.save(update_fields=['household_member'])
                    if existing is not None:
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
