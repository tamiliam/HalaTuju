"""Contract module: the deploy checks and the lifecycle (submit, revert, deploy).

Moved unchanged out of ``contracts.py`` when audit A3.8 (2026-11-10) made it a package.
"""
import re

from django.db import transaction
from django.utils import timezone

from .. import award
from .. import staff_activity
from ..models import ContractTemplate
from .errors import ContractsError, ValidationResult
from .quiz import _quiz_payload_valid


# ─────────────────────────────────────────────────────────────────────────────
# Deploy validation (T / C / Q / S / P rules + W warnings)
# ─────────────────────────────────────────────────────────────────────────────
def _expected_row_total(pathway, variant):
    """Mirror award.py: what the award (and therefore the schedule total) must be
    for a pathway/variant. STPM fresh 3000, STPM continuing 1000, else 2000."""
    if pathway == 'stpm':
        return award._STPM_CONTINUING_AMOUNT if variant == 'continuing' else award._STPM_AMOUNT
    return award._DEFAULT_AMOUNT


def validate_for_deployment(template):
    """Return a ValidationResult of error + warning codes. Errors block
    deployment; warnings are advisory (surfaced on the deploy panel)."""
    errors = []
    warnings = []
    clauses = list(template.clauses.all().order_by('order'))
    rows = list(template.schedule_rows.all())

    # ── T: template-level ─────────────────────────────────────────────────────
    if not (template.version and template.counterparty_name
            and template.counterparty_title and template.counterparty_nric):
        errors.append('T1')
    if not (template.vetted_by_name and template.vetted_on
            and template.vetting_attested_by_email):
        errors.append('T2')

    # ── C: clauses ────────────────────────────────────────────────────────────
    orders = [c.order for c in clauses]
    if not clauses or orders != list(range(1, len(clauses) + 1)):
        errors.append('C1')
    english_complete = bool(
        template.title_en and template.preamble_en and template.progress_standard_en
    ) and all(c.heading_en and c.body_en for c in clauses)
    if not clauses or not english_complete:
        errors.append('C2')

    # ── Q: quiz ───────────────────────────────────────────────────────────────
    candidates = [c for c in clauses if c.is_quiz_candidate]
    if not candidates:
        errors.append('Q1')
    for c in candidates:
        if not _quiz_payload_valid(c.quiz_en):
            errors.append('Q2')
    for c in clauses:
        if not c.is_quiz_candidate and (c.quiz_en or c.quiz_ms or c.quiz_ta):
            errors.append('Q3')  # a question can't outlive its clause
    for c in candidates:
        base = c.quiz_en.get('correct') if isinstance(c.quiz_en, dict) else None
        for lang in ('ms', 'ta'):
            payload = getattr(c, f'quiz_{lang}')
            if payload:
                if not _quiz_payload_valid(payload) or payload.get('correct') != base:
                    errors.append('Q4')

    # ── S: schedule ───────────────────────────────────────────────────────────
    by_key = {(r.pathway, r.variant): r for r in rows}
    if ('default', '') not in by_key:
        errors.append('S1')
    seen = set()
    for r in rows:
        key = (r.pathway, r.variant)
        shape_ok = (
            r.monthly_amount and r.monthly_amount > 0
            and 1 <= r.start_month <= 12
            and isinstance(r.paid_offsets, list) and r.paid_offsets
            and all(isinstance(o, int) and o >= 0 for o in r.paid_offsets)
            and len(set(r.paid_offsets)) == len(r.paid_offsets)
        )
        if not shape_ok or key in seen:
            errors.append('S2')
        seen.add(key)
        if r.total not in award.ALLOWED_AMOUNTS:
            errors.append('S3')
        if r.total != _expected_row_total(r.pathway, r.variant):
            errors.append('S4')

    # ── P: v1 fence ───────────────────────────────────────────────────────────
    if template.parent_role == 'minor_only' or template.witness_policy == 'required':
        errors.append('P1')

    # ── W: warnings (advisory) ────────────────────────────────────────────────
    if template.parent_role == 'co_signer_all':
        blob = ' '.join([template.preamble_en] + [c.body_en for c in clauses]).lower()
        if 'guarantor' in blob or 'surety' in blob:
            warnings.append('W1')
    if 'ms' not in template.languages_available:
        warnings.append('W2')
    if 'ta' not in template.languages_available:
        warnings.append('W2')
    rm_literal = re.compile(r'RM\s?\d')
    if any(rm_literal.search(c.body_en or '') for c in clauses):
        warnings.append('W3')

    return ValidationResult(errors, warnings)


# ─────────────────────────────────────────────────────────────────────────────
# Lifecycle
# ─────────────────────────────────────────────────────────────────────────────
def submit_for_deployment(template, *, submitted_by_email='', actor=None):
    """draft → pending_deployment. Refuses unless validation passes."""
    if template.status != 'draft':
        raise ContractsError('not_draft')
    result = validate_for_deployment(template)
    if not result.ok:
        err = ContractsError('not_deployable')
        err.errors = result.errors
        raise err
    template.status = 'pending_deployment'
    template.submitted_by_email = submitted_by_email or ''
    template.submitted_by_at = timezone.now()
    template.save(update_fields=[
        'status', 'submitted_by_email', 'submitted_by_at', 'updated_at',
    ])
    staff_activity.record(actor, staff_activity.CONTRACT_TEMPLATE_SUBMITTED, template)
    return template


def revert_to_draft(template):
    """pending_deployment → draft (to edit further before deploying)."""
    if template.status != 'pending_deployment':
        raise ContractsError('not_pending')
    template.status = 'draft'
    template.submitted_by_email = ''
    template.submitted_by_at = None
    template.save(update_fields=[
        'status', 'submitted_by_email', 'submitted_by_at', 'updated_at',
    ])
    return template


@transaction.atomic
def deploy(template, *, deployed_by_email='', is_super=False, actor=None):
    """pending_deployment → active (SUPER only). Atomically archives THE SAME GIFT's
    previous active version — exactly one active template per GIFT (TD-229; the
    `uniq_contract_template_active_per_programme` index backs it). A template with no gift
    governs nobody, so it is refused (`programme_required`)."""
    if not is_super:
        raise ContractsError('deploy_forbidden')
    if template.status != 'pending_deployment':
        raise ContractsError('not_pending')
    if template.programme_id is None:
        raise ContractsError('programme_required')
    result = validate_for_deployment(template)
    if not result.ok:
        err = ContractsError('not_deployable')
        err.errors = result.errors
        raise err
    now = timezone.now()
    previous = (ContractTemplate.objects
                .select_for_update()
                .filter(programme_id=template.programme_id, status='active')
                .exclude(pk=template.pk))
    for old in previous:
        old.status = 'archived'
        old.archived_at = now
        old.save(update_fields=['status', 'archived_at', 'updated_at'])
    template.status = 'active'
    template.deployed_by_email = deployed_by_email or ''
    template.deployed_by_at = now
    template.save(update_fields=[
        'status', 'deployed_by_email', 'deployed_by_at', 'updated_at',
    ])
    staff_activity.record(actor, staff_activity.CONTRACT_TEMPLATE_DEPLOYED, template)
    return template
