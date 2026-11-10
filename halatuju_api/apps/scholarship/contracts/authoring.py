"""Contract module: draft authoring (create, clone, config, clauses, schedule, vetting).

Moved unchanged out of ``contracts.py`` when audit A3.8 (2026-11-10) made it a package.
"""
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .. import staff_activity
from ..models import ContractClause, ContractTemplate, PaymentScheduleRow
from .errors import ContractsError, _require_draft
from .numbering import LANGUAGES, MAX_QUIZ_LEVEL, _CONFIG_FIELDS, _fit_heading, normalise_levels


# ─────────────────────────────────────────────────────────────────────────────
# Authoring (draft-only)
# ─────────────────────────────────────────────────────────────────────────────
@transaction.atomic
def create_template(organisation, version, *, programme=None, created_by_email='', copy_from=None,
                    actor=None):
    """Create a new DRAFT template for ``organisation``, written for the gift ``programme``
    (REQUIRED since TD-229 — `programme_required` without one; a gift of another organisation
    is refused the same way). With ``copy_from`` (a ContractTemplate), clone its config +
    clauses + schedule — but never its lifecycle/attestation stamps (a new version starts
    unvetted, undeployed)."""
    if programme is None or programme.organisation_id != organisation.id:
        raise ContractsError('programme_required')
    version = (version or '').strip()
    if not version:
        raise ContractsError('version_required')
    # Guard the column length here so an over-long version returns a clean 400 (version_too_long)
    # instead of hitting Postgres and surfacing as a raw 500 (.create() doesn't run full_clean()).
    max_len = ContractTemplate._meta.get_field('version').max_length
    if len(version) > max_len:
        raise ContractsError('version_too_long')
    if ContractTemplate.objects.filter(organisation=organisation, version=version).exists():
        raise ContractsError('version_exists')
    template = ContractTemplate.objects.create(
        organisation=organisation, programme=programme, version=version, status='draft',
        created_by_email=created_by_email or '',
    )
    if copy_from is not None:
        _clone_content(copy_from, template)
    # Common profile S4: the person who pressed the button gets the row on their own activity list
    # (best-effort; never raises). A management command passes no actor and writes nothing.
    staff_activity.record(actor, staff_activity.CONTRACT_TEMPLATE_CREATED, template)
    return template


def _clone_content(source, target):
    for field in _CONFIG_FIELDS:
        setattr(target, field, getattr(source, field))
    target.save()
    clauses = [
        {
            'level': c.level,
            'heading_en': c.heading_en, 'heading_ms': c.heading_ms, 'heading_ta': c.heading_ta,
            'body_en': c.body_en, 'body_ms': c.body_ms, 'body_ta': c.body_ta,
            'is_quiz_candidate': c.is_quiz_candidate,
            'quiz_en': c.quiz_en, 'quiz_ms': c.quiz_ms, 'quiz_ta': c.quiz_ta,
            'quiz_generated_model': c.quiz_generated_model,
        }
        for c in source.clauses.all().order_by('order')
    ]
    replace_clauses(target, clauses)
    rows = [
        {
            'pathway': r.pathway, 'variant': r.variant,
            'label_en': r.label_en, 'label_ms': r.label_ms, 'label_ta': r.label_ta,
            'monthly_amount': r.monthly_amount, 'start_month': r.start_month,
            'paid_offsets': r.paid_offsets, 'sort_order': r.sort_order,
        }
        for r in source.schedule_rows.all()
    ]
    replace_schedule(target, rows)


def update_config(template, **fields):
    """Set whitelisted config fields on a draft. Unknown keys raise."""
    _require_draft(template)
    changed = []
    for key, value in fields.items():
        if key not in _CONFIG_FIELDS:
            raise ContractsError('unknown_config_field', key)
        setattr(template, key, value)
        changed.append(key)
    if changed:
        template.save(update_fields=changed + ['updated_at'])
    return template


def _resolve_quiz_flags(clauses, levels):
    """Which clauses keep the comprehension-quiz flag: an ELIGIBLE level (0 clause or 1 sub-clause)
    that is flagged AND has NO flagged ancestor. A clause and its own descendants are mutually
    exclusive — the ancestor's quiz already covers the subtree, so a flagged descendant under a
    flagged ancestor is dropped (ancestor wins). Level-2 (sub-sub-clause) is never eligible.
    Returns a list[bool] aligned to ``clauses`` (walks the normalised (order, level) run)."""
    keep = []
    open_flagged_levels = []   # levels of the currently-open flagged ancestors, shallow → deep
    for item, level in zip(clauses, levels):
        # Drop any open flagged clause that is not a strict ancestor of this position (a
        # same-or-shallower level means we've left its subtree).
        while open_flagged_levels and open_flagged_levels[-1] >= level:
            open_flagged_levels.pop()
        flagged = bool(item.get('is_quiz_candidate')) and level <= MAX_QUIZ_LEVEL
        if flagged and open_flagged_levels:
            flagged = False   # covered by a flagged ancestor's quiz → drop
        keep.append(flagged)
        if flagged:
            open_flagged_levels.append(level)
    return keep


@transaction.atomic
def replace_clauses(template, clauses):
    """Atomic PUT of the clause list. Order is assigned by position (contiguous
    1..N by construction). Each item is a flat dict of model fields; a supplied
    quiz payload must be a dict."""
    _require_draft(template)
    template.clauses.all().delete()
    # Levels are normalised across the whole list (clamp 0..MAX, no skipping) — the tree is the
    # (order, level) run. A quiz may live on a CLAUSE (0) or SUB-CLAUSE (1), never a sub-sub-clause
    # (2). A clause and any of its own descendants are MUTUALLY EXCLUSIVE: a flagged clause's quiz
    # already covers its subtree, so a descendant flagged under a flagged ancestor is dropped here
    # (the ancestor wins — a safety net; the editor prevents overlap in the first place). A dropped
    # or ineligible clause also loses any quiz payload (a question can't outlive its flag).
    levels = normalise_levels([item.get('level', 0) for item in clauses])
    keep_quiz = _resolve_quiz_flags(clauses, levels)
    created = []
    for index, (item, level) in enumerate(zip(clauses, levels), start=1):
        for lang in LANGUAGES:
            payload = item.get(f'quiz_{lang}') or {}
            if payload and not isinstance(payload, dict):
                raise ContractsError('bad_quiz_payload', f'clause {index} quiz_{lang}')
        keep = keep_quiz[index - 1]
        # An over-long heading (any language) folds into its body so the save can never
        # overflow heading_*'s varchar(255) — the guard for every write path (2026-07-21).
        h_en, b_en = _fit_heading(item.get('heading_en', ''), item.get('body_en', ''))
        h_ms, b_ms = _fit_heading(item.get('heading_ms', ''), item.get('body_ms', ''))
        h_ta, b_ta = _fit_heading(item.get('heading_ta', ''), item.get('body_ta', ''))
        created.append(ContractClause(
            template=template, order=index, level=level,
            heading_en=h_en, heading_ms=h_ms, heading_ta=h_ta,
            body_en=b_en, body_ms=b_ms, body_ta=b_ta,
            is_quiz_candidate=keep,
            quiz_en=(item.get('quiz_en') or {}) if keep else {},
            quiz_ms=(item.get('quiz_ms') or {}) if keep else {},
            quiz_ta=(item.get('quiz_ta') or {}) if keep else {},
            quiz_generated_model=(item.get('quiz_generated_model', '') or '') if keep else '',
        ))
    ContractClause.objects.bulk_create(created)
    return template.clauses.all()


@transaction.atomic
def replace_schedule(template, rows):
    """Atomic PUT of the schedule rows. Rejects a duplicate (pathway, variant)
    in the input before the DB constraint would."""
    _require_draft(template)
    seen = set()
    template.schedule_rows.all().delete()
    created = []
    for index, item in enumerate(rows):
        pathway = (item.get('pathway', '') or '').strip().lower()
        variant = (item.get('variant', '') or '').strip().lower()
        if not pathway:
            raise ContractsError('bad_schedule_row', f'row {index}: missing pathway')
        key = (pathway, variant)
        if key in seen:
            raise ContractsError('duplicate_schedule_row', f'{pathway}/{variant}')
        seen.add(key)
        created.append(PaymentScheduleRow(
            template=template, pathway=pathway, variant=variant,
            label_en=item.get('label_en', '') or '',
            label_ms=item.get('label_ms', '') or '',
            label_ta=item.get('label_ta', '') or '',
            monthly_amount=Decimal(str(item.get('monthly_amount', '0'))),
            start_month=int(item.get('start_month', 0)),
            paid_offsets=list(item.get('paid_offsets') or []),
            sort_order=int(item.get('sort_order', index)),
        ))
    PaymentScheduleRow.objects.bulk_create(created)
    return template.schedule_rows.all()


def record_vetting(template, *, vetted_by_name, vetted_on, attested_by_email, actor=None):
    """Record the lawyer-vetting attestation (who + date) — the T2 gate."""
    _require_draft(template)
    if not (vetted_by_name and vetted_on and attested_by_email):
        raise ContractsError('incomplete_vetting')
    template.vetted_by_name = vetted_by_name
    template.vetted_on = vetted_on
    template.vetting_attested_by_email = attested_by_email
    template.vetting_attested_at = timezone.now()
    template.save(update_fields=[
        'vetted_by_name', 'vetted_on', 'vetting_attested_by_email',
        'vetting_attested_at', 'updated_at',
    ])
    staff_activity.record(actor, staff_activity.CONTRACT_TEMPLATE_VETTED, template)
    return template
