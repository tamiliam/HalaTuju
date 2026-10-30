"""What the source console SHOWS — the payload builders (source sign-in S3, 2026-10-30).

Roadmap: `docs/plans/2026-10-30-source-sign-in-roadmap.md` (S3, conflicts C11, C12, C14). The views
(`views_admin/source_console.py`) decide WHO may ask and WHICH rows; this module only turns rows the
view has already scoped through `source_access` into dicts, so nothing here can widen what a source
reaches.

⚠ AN ALLOWLIST BY CONSTRUCTION, like the sponsor serializers (`serializers.SponsorPoolCardSerializer`).
Every key below is written out by hand; nothing is passed through from the application or the
profile, so a new model field can never reach a source by accident. `tests/test_source_console.py`
walks every response and fails on any key from the never-list (NRIC, address, income, family,
essays, documents, scores, verdicts, reviewers, notes, money, results …).

⚠ THE CEILING IS WHAT A SOURCE ALREADY RECEIVES BY EMAIL (`partner_comms`): the folded stage lines
and the chase list. Three things go a step past it, each by ruling:
  * the student's phone and email (owner ruling 2026-10-30);
  * on ONE shortlisted application's page, the NAMES of the checklist parts still open (lead decision
    2026-10-30, for the owner to review): the coarse part keys of
    `services.completeness.application_completeness` (`PARTS`), never a document type or an income
    route;
  * to the WITNESS source only, on the witness step and after, the full signed contract as a PDF
    link (`agreement_dict`, S4; owner ruling 2026-10-30) — the document it attests, which it also
    receives by email once executed (`distribute_executed_agreement`). It is the ONE payload here
    that carries a `pdf` key, and its test names that exception.

⚠ A SOURCE NEVER LEARNS AN OUTCOME BEFORE THE STUDENT (C12). The stage is the STUDENT'S OWN masked
status (`student_status.student_facing_status`: an embargoed decline reads as the stage it was
declined from, `recommended` as `interviewed`), folded through the partner emails' own
`partner_comms.STAGE_LINES` (`recommended` → under review). Both are reused, never re-derived.
"""
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q

from .partner_comms import STAGE_LINES, chase_entries
from .student_status import student_facing_status

#: Status → stage line, from the partner emails' own table.
_LINE_OF = {status: line for line, statuses in STAGE_LINES for status in statuses}

#: The stage keys, in email order — the console's whole vocabulary.
STAGES = tuple(line for line, _ in STAGE_LINES)

#: The stages that are an OUTCOME the student is told of; only these carry a `told_at`.
OUTCOME_STAGES = ('shortlisted', 'awarded', 'rejected', 'closed')

#: `application_completeness` key → the part name a source may see. Coarse on purpose: these are
#: the student's own checklist sections, never a document type or an income route.
PARTS = (
    ('quiz_done', 'quiz'), ('details_done', 'story'), ('funding_done', 'funding'),
    ('documents_done', 'documents'), ('consent_done', 'consent'), ('address_done', 'address'),
    ('guardian_docs_done', 'guardian_documents'), ('family_done', 'family'),
)


def in_gift(qs, gift):
    """Narrow to one gift, through the cohort as well as the column (`programme_student_queryset`'s
    rule: a cohort moved between gifts leaves `programme` on the old one). None = every gift."""
    if gift is None:
        return qs
    return qs.filter(Q(programme_id=gift.pk) | Q(cohort__programme_id=gift.pk))


def stage_of(app):
    """The folded stage the source sees — what the STUDENT sees, on the partner emails' lines."""
    return _LINE_OF.get(student_facing_status(app), 'under_review')


def told_at(app, stage):
    """When the student was told of an OUTCOME stage, or None (a stage that is not an outcome)."""
    if stage == 'shortlisted':
        return app.decision_released_at or app.shortlisted_at
    if stage == 'awarded':
        return app.awarded_at
    if stage == 'rejected':
        return (app.decline_email_sent_at or app.decision_email_sent_at
                or app.decision_released_at or app.rejected_at)
    if stage == 'closed':
        return app.closed_at or app.expired_at
    return None


def stage_counts(apps):
    """`{stage: n}` + `total` over already-fetched applications; every stage sums to `total`."""
    counts = dict.fromkeys(STAGES, 0)
    for app in apps:
        counts[stage_of(app)] += 1
    counts['total'] = len(apps)
    return counts


def gift_dict(gift):
    return {'code': gift.code, 'name': gift.name_en} if gift is not None else None


def _name(app):
    return (getattr(app.profile, 'name', '') or '').strip() or f'Applicant #{app.id}'


def level_of(profile):
    """The qualification we hold results for: `spm` / `stpm` / `matric` / `asasi` / `diploma` / ''."""
    from apps.courses.exam_questions import results_held
    return results_held(profile)


def missing_items(applications):
    """The chase list for these applications — EXACTLY the partner email's (`chase_entries`):
    shortlisted students whose application is not complete, oldest first, with dates only."""
    return [{'application_id': app.id, 'student_name': name, 'applied': applied,
             'last_activity': activity}
            for app, name, applied, activity in chase_entries(applications)]


def missing_parts(app):
    """The checklist parts still open on ONE shortlisted application (names only), else []."""
    if stage_of(app) != 'shortlisted':
        return []
    from .services.completeness import application_completeness
    done = application_completeness(app)
    return [name for key, name in PARTS if not done.get(key, True)]


def agreement_of(app):
    try:
        return app.bursary_agreement
    except ObjectDoesNotExist:
        return None


def witness_is(app, source):
    """Is ``source`` this application's resolved witness (`bursary._resolve_witness_org`)?"""
    from .bursary import _resolve_witness_org
    org = _resolve_witness_org(app)
    return org is not None and org.pk == source.pk


# ── What the STUDENT sees decides the scholar set and the witness step (review H1) ───────────────
#: A decline still inside its cool-off: `rejected` with the pending marker set — the student has NOT
#: been told, and `student_status.student_facing_status` still shows her the stage she was declined
#: FROM. Read the raw status and the console would change (a scholar gone, a contract no longer
#: witnessable) before the student is told — the C12 leak by another road.
def held_decline_q():
    return Q(status='rejected') & ~Q(pending_rejection_category='')


def scholar_q():
    """The source's SCHOLARS as the student sees her own status: `maintenance_scope.has_file_q`,
    plus a held decline whose pre-decline status had a file (in maintenance: `active` /
    `maintenance`, or `awarded` with a live wallet — `maintenance_scope.in_maintenance_q` applied to
    `pre_decline_status`). `cancel_pending_decline` puts the status back, so the case simply stays."""
    from .closure import FUNDED_STATUSES
    from .maintenance_scope import has_file_q
    pre_in_file = (Q(pre_decline_status='awarded', vircle_activated_at__isnull=False)
                   | Q(pre_decline_status__in=FUNDED_STATUSES))
    return has_file_q() | (held_decline_q() & pre_in_file)


# ── The witness step (source sign-in S4) ─────────────────────────────────────────────────────────
#: The application states in which the contract is LIVE, so its witness may still be recorded: being
#: signed (`awarded`), or already executed by the organisation's countersignature (`active`, then
#: `maintenance`) — the witness is non-blocking and `bursary.record_witness` handles one that comes
#: last. A declined, withdrawn, closed or expired application's contract is never witnessed. Read on
#: the STUDENT-FACING status (review H1): a decline in its cool-off is still its pre-decline stage.
WITNESS_STATUSES = ('awarded', 'active', 'maintenance')


def agreements_on():
    """`BURSARY_AGREEMENT_ENABLED` — with it off there is no witness step to reach (the student's own
    `BursaryAgreementView` is a 404 then too)."""
    from django.conf import settings
    return bool(getattr(settings, 'BURSARY_AGREEMENT_ENABLED', False))


def contract_live(app):
    """The contract is live as the STUDENT sees it (`WITNESS_STATUSES` on `student_facing_status`)."""
    return student_facing_status(app) in WITNESS_STATUSES


def is_the_witness(app, source):
    """Is ``source`` THIS contract's witness? Once a witness is recorded, the one that RECORDED it
    (`agreement.witness_org`) — an override moved afterwards never hands its signed contract to a
    source that did not sign it (review M1). Before, the live resolution (`witness_is`)."""
    agreement = agreement_of(app)
    if agreement is not None and agreement.witness_signed_at is not None:
        return agreement.witness_org_id == source.pk
    return witness_is(app, source)


def witness_case_open(app, source):
    """A case this source only WITNESSES may be shown to it (review L6b): the agreement exists, the
    guarantor has signed, and ``source`` is the witness (`is_the_witness`). Before that, a source
    named only by the override learns nothing — not even the student's name."""
    agreement = agreement_of(app)
    return bool(agreement is not None and agreement.guarantor_signed_at
                and is_the_witness(app, source))


def witness_step_reached(app, source):
    """Agreements are on and `witness_case_open`."""
    return agreements_on() and witness_case_open(app, source)


def can_witness(app, source):
    """THE one predicate for "this contract waits for this source's witness": the Overview's
    `witness_waiting`, the contract block's and the agreement's `can_witness`, and the witness POST
    all read it, so they cannot disagree."""
    agreement = agreement_of(app)
    return bool(witness_step_reached(app, source) and agreement.witness_signed_at is None
                and contract_live(app))


def may_read_agreement(app, source):
    """The agreement GET (owner ruling 2026-10-30: the full contract, on the witness step and after).
    Before the witness: only while `can_witness` — a live contract (review L1). After: only the source
    that RECORDED the witness, for as long as agreements are on (review M1)."""
    agreement = agreement_of(app)
    if agreement is not None and agreement.witness_signed_at is not None:
        return agreements_on() and agreement.witness_org_id == source.pk
    return can_witness(app, source)


def contract_dict(app, source):
    """The signing chain — dates only, never a name, an NRIC, an amount or the document."""
    agreement = agreement_of(app)
    if agreement is None:
        return None
    return {
        'status': agreement.status,
        'student_signed_at': agreement.student_signed_at,
        'guarantor_signed_at': agreement.guarantor_signed_at,
        'witness_signed_at': agreement.witness_signed_at,
        'foundation_signed_at': agreement.foundation_signed_at,
        'witness_is_you': is_the_witness(app, source),
        'can_witness': can_witness(app, source),
    }


def agreement_dict(app, source, *, with_link=False):
    """The witness source's view of the contract (S4) — the caller has checked
    `may_read_agreement`. The signing dates, and the signed PDF itself as a short-lived link,
    minted only `with_link` (a click — the Scholars contract tab's rule, `scholar_money.pdf_url`,
    300 seconds, and only for this application's own file). The rendered HTML is never served
    (`rendered: false`): the PDF is the document."""
    from .scholar_money import PDF_URL_SECONDS, pdf_url
    agreement = agreement_of(app)
    return {
        **contract_dict(app, source),
        'application_id': app.id,
        'student_name': _name(app),
        'pdf_url': pdf_url(agreement, app) if with_link else None,
        'pdf_expires_in': PDF_URL_SECONDS,
        'rendered': False,
    }


def witness_waiting(apps, source):
    return [{'application_id': app.id, 'student_name': _name(app)}
            for app in apps if can_witness(app, source)]


def application_row(app):
    """One Applications-list row."""
    profile = app.profile
    return {
        'id': app.id,
        'student_name': _name(app),
        'school': (getattr(profile, 'school', '') or ''),
        'state': (getattr(profile, 'preferred_state', '') or ''),
        'level': level_of(profile),
        'programme': gift_dict(app.programme),
        'submitted_at': app.submitted_at,
        'stage': stage_of(app),
    }


def _contact(app):
    profile = app.profile
    return {'phone': (getattr(profile, 'contact_phone', '') or ''),
            'email': (getattr(profile, 'contact_email', '') or '') or (app.notify_email or '')}


def application_detail(app, source):
    """One LISTED application (its source is the caller's)."""
    stage = stage_of(app)
    return {
        **application_row(app),
        'kind': 'listed',
        **_contact(app),
        'told_at': told_at(app, stage),
        'missing_items': missing_parts(app),
        'contract': contract_dict(app, source),
    }


def witness_only_detail(app, source):
    """A case this source only WITNESSES (`witness_org`, another source's student — C14): the
    contract task and nothing else."""
    return {
        'id': app.id,
        'kind': 'witness_only',
        'student_name': _name(app),
        'programme': gift_dict(app.programme),
        'contract': contract_dict(app, source),
    }


def scholar_row(app, names=None):
    """One Scholars-list row. `status` is what the student sees (awarded / active / maintenance /
    closed); the officer's sub-state (on track, probation, on hold …) is never served."""
    from . import card_display
    agreement = agreement_of(app)
    return {
        'id': app.id,
        'student_name': _name(app),
        'programme': gift_dict(app.programme),
        'institution': card_display.resolve_institution(app),
        'course': card_display.resolve_course(app, names=names),
        'status': student_facing_status(app),
        'contract_stage': agreement.status if agreement is not None else None,
    }


def scholar_detail(app, source):
    return {**scholar_row(app), **_contact(app), 'contract': contract_dict(app, source)}


def course_names(apps):
    """The page's catalogue course names in two queries (the officer Scholars list's rule)."""
    from . import card_display
    return card_display.catalogue_course_names(
        (a.chosen_programme or {}).get('course_id') if isinstance(a.chosen_programme, dict) else ''
        for a in apps)


def profile_dict(admin, source):
    """The source user's own page: their account, and the source they sign in for."""
    return {
        'user': {'name': admin.name or '', 'email': admin.email or ''},
        'source': {
            'name': source.name or '', 'code': source.code,
            'contact_person': source.contact_person or '',
            'contact_email': source.contact_email or '', 'phone': source.phone or '',
            'organisation': source.organisation.name,
        },
    }
