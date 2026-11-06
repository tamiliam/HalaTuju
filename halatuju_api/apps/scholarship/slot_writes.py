"""The upload door's two slot writes, in the order the slot's unique index needs (TD-115, A1.8).

`applicant_documents` admits ONE live row per slot (application, doc_type, household_member,
request_code; in-programme slips aside) — migration 0203's partial unique index. So nothing may go
live while the copy it replaces is still live: the old copy is superseded FIRST, in the same
transaction, so a failed write still leaves the old live doc untouched.

Two uploads into one slot at once: the second write meets the index as an IntegrityError instead
of leaving a silent duplicate. These answer it cleanly — never a 500, never two live rows. The
decisions (what is staged, what is replaced, whether to promote) stay with the caller
(`views.DocumentListCreateView.post`, `promotion.should_promote`); only the order of writes is here.
"""
import logging

from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import ApplicantDocument

logger = logging.getLogger(__name__)


def create_in_slot(app, data, *, staged, existing_live, stale_ids, slot_filter):
    """Write the uploaded row. Returns it, or None when the slot stayed contested (the caller answers
    409 `upload_conflict`).

    * ``staged`` (a KEY NAMED type): the row is CREATED staged (superseded by the live copy it is
      judged against), so the existing proof keeps its slot until the promote decision.
    * otherwise (replace-first types): the slot's live copies in ``stale_ids`` are superseded, then the
      row is created live and they are pointed at it.

    A clash means another upload took the slot in between: it re-reads the slot, replaces that copy
    once as a re-upload would, and gives up only on a second clash. ``stale_ids`` is extended IN PLACE
    with what it re-read, so the caller's later reads see the same set."""
    for attempt in (1, 2):
        try:
            with transaction.atomic():
                if staged:
                    return ApplicantDocument.objects.create(
                        application=app, superseded_at=timezone.now(), superseded_by=existing_live, **data)
                live_stale = list(ApplicantDocument.objects.filter(
                    id__in=stale_ids, superseded_at__isnull=True).values_list('id', flat=True))
                if live_stale:
                    ApplicantDocument.objects.filter(id__in=live_stale).update(superseded_at=timezone.now())
                doc = ApplicantDocument.objects.create(application=app, **data)
                if live_stale:
                    ApplicantDocument.objects.filter(id__in=live_stale).update(superseded_by=doc)
                return doc
        except IntegrityError:
            if attempt == 2:
                logger.warning('AUDIT upload_slot_conflict app=%s doc_type=%s request_code=%r',
                               app.id, data.get('doc_type'), data.get('request_code', ''))
                return None
            stale_ids += [i for i in ApplicantDocument.objects.filter(**slot_filter)
                          .values_list('id', flat=True) if i not in stale_ids]


def promote_into_slot(app, doc, stale_ids):
    """Unstage ``doc`` into its slot: supersede everything this upload replaces — the staged-against
    set (the slot sweep, incl. any blank-tagged legacy copy) PLUS any other live copy in ``doc``'s
    exact slot — then clear its own stamp, in ONE transaction. Returns True when promoted.

    False when an upload that went live in this slot meanwhile meets the index: the transaction rolls
    back whole, that copy keeps the slot, and ``doc`` stays in Old / Replaced (``kept_previous``)."""
    now = timezone.now()
    try:
        with transaction.atomic():
            ApplicantDocument.objects.filter(
                id__in=stale_ids, superseded_at__isnull=True).exclude(id=doc.id).update(
                superseded_at=now, superseded_by=doc)
            ApplicantDocument.objects.filter(
                application=app, doc_type=doc.doc_type, household_member=doc.household_member,
                request_code=doc.request_code, superseded_at__isnull=True).exclude(id=doc.id).update(
                superseded_at=now, superseded_by=doc)
            ApplicantDocument.objects.filter(id=doc.id).update(superseded_at=None, superseded_by=None)
        return True
    except IntegrityError:
        logger.warning('AUDIT upload_promote_conflict app=%s doc=%s doc_type=%s',
                       app.id, doc.id, doc.doc_type)
        return False
