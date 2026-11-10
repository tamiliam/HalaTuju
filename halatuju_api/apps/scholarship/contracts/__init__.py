"""Contract module service — org-owned, versioned bursary-agreement templates.

Mirrors ``payments.py`` in shape (a ``ContractsError`` carrying a machine code;
module-level service functions over the models). The lifecycle is DEPLOYMENT,
not approval::

    draft → pending_deployment → active → archived

Authoring calls all refuse a non-draft template (``not_draft``) — the
immutability guarantee that lets a signed ``BursaryAgreement`` PROTECT-reference
the exact version it was rendered from, forever. Deploying a new version
atomically archives the previous active version OF THE SAME GIFT (per organisation
until TD-229, 2026-10-03; which template governs an application: ``contract_scope``).

Sprint 1 scope: model + service + seed + tests. The module is INERT — neither
``bursary.py`` nor ``payments.py`` reads it yet (that cutover is Sprint 2). No
live Gemini / Drive / storage calls happen here; the Gemini seam
(``_gemini_generate``) is mocked in tests exactly like the reports tests.

The package (audit A3.8, 2026-11-10). ``contracts.py`` was split, unchanged, into the modules
beside this file; every name it held is re-exported here, so ``from apps.scholarship.contracts
import X`` and ``contracts.X`` resolve as before. Three functions stay in THIS file on purpose:
``_gemini_generate`` (the seam tenancy rule 6 names, patched as
``apps.scholarship.contracts._gemini_generate``) and its two callers ``generate_quiz`` and
``segment_docx``, so every existing patch of ``_gemini_generate``, ``_docx_structure`` and
``_extract_docx_text`` still reaches the name they look up.
"""

from django.conf import settings

from .. import award
from .. import gemini
from .. import staff_activity
from ..models import ContractClause, ContractTemplate, PaymentScheduleRow
from .numbering import (
    HEADING_MAX_LEN, HEADING_TITLE_MAX, LANGUAGES, MAX_CLAUSE_LEVEL, MAX_QUIZ_LEVEL, _CONFIG_FIELDS,
    _ROMAN, _fit_heading, _roman, clause_numbers, normalise_levels,
)
from .variables import (
    CONTRACT_VARS, _BRACKET_RE, _BRACKET_VARS, _COUNTERPARTY_RE, _VAR_RE, _brackets_to_vars,
    _extract_counterparty, substitute_vars,
)
from .errors import ContractsError, ValidationResult, _require_draft
from .authoring import (
    _clone_content, _resolve_quiz_flags, create_template, record_vetting, replace_clauses,
    replace_schedule, update_config,
)
from .quiz import (
    _build_quiz_prompt, _clause_and_descendants, _parse_quiz_json, _quiz_payload_valid,
)
from .docx_import import (
    _build_segment_prompt, _docx_structure, _extract_docx_text, _para_numbering, _parse_segments,
)
from .deployment import (
    _expected_row_total, deploy, revert_to_draft, submit_for_deployment, validate_for_deployment,
)
from .readers import (
    _MONTHS, _row_label, is_paid_month, pick_schedule_row, quiz_checkpoints, resolve_locale,
    schedule_calendar, schedule_row_for, schedule_summary_text, schedule_table,
)
from .render import _bold, render_clauses_html, render_preview_html


# ─────────────────────────────────────────────────────────────────────────────
# Quiz generation (Gemini — draft-only, on-demand, configured model then the Flash cascade)
# ─────────────────────────────────────────────────────────────────────────────
def _gemini_generate(prompt, model, images=None, timeout_ms=None):
    """The single-model Gemini call — the mockable seam (patched in tests, never
    a live call in CI). ONE model per call; it raises on any failure. The fallback is the
    callers': `gemini.generate_with_fallback` calls this seam once per model (the configured
    one, then the Flash cascade). That SUPERSEDES "Owner decision 4: NO downgrade fallback"
    (owner, 2026-11-10, Gemini Phase 1; docs/decisions.md).

    ``images`` is an optional list of ``(bytes, mime_type)`` sent alongside the prompt, added
    2026-07-30 so the requests reviewer can actually SEE the screenshots a submitter attached
    (it was previously told only how many there were). **The default keeps every existing caller
    byte-identical** — contract generation passes no images and takes the same `contents=prompt`
    path it always did, which a test pins, because this seam is shared and mocked everywhere.

    ``timeout_ms`` (optional, default None = the client's own default) is set only by
    ``gemini.generate_with_fallback``'s deadline.

    Note the part ORDER: images first, then the prompt, matching ``vision._call_gemini_json`` —
    the model attends better to instructions that follow the evidence.

    ⚠ THE SEAM STAYS HERE, THREE LINES LONG. Code health H7 moved the body to ``gemini`` (one copy
    instead of three) and kept this name, because this is the boundary tenancy rule 6 names BY
    NAME and the string nineteen ``patch()`` calls in the suite point at. Do not "simplify" it
    into a direct call.
    """
    return gemini.generate_text(prompt, model, images=images, exc=ContractsError,
                                unconfigured='quiz_ai_unconfigured',
                                unavailable='quiz_ai_unavailable', timeout_ms=timeout_ms)


def generate_quiz(clause, *, model=None):
    """Generate the clause's en/ms/ta quiz via Gemini, validate the structure,
    and save it to the (draft) clause. Billable → call on demand only. A CLAUSE (0) or SUB-CLAUSE
    (1) may carry a quiz; it covers that clause's whole subtree. A sub-sub-clause (2) may not."""
    _require_draft(clause.template)
    if clause.level > MAX_QUIZ_LEVEL:
        raise ContractsError('quiz_not_top_level')
    model = model or getattr(settings, 'CONTRACT_QUIZ_MODEL', 'gemini-3.8-flash')
    from .. import usage
    with usage.usage_context(organisation_id=getattr(clause.template, 'organisation_id', None),
                             source='contract_quiz'):
        raw, model = gemini.generate_with_fallback(_gemini_generate, _build_quiz_prompt(clause),
                                                   model, fatal=ContractsError)
    data = _parse_quiz_json(raw)
    payloads = {}
    for lang in LANGUAGES:
        payload = data.get(lang) or {}
        if payload and not _quiz_payload_valid(payload):
            raise ContractsError('quiz_invalid', lang)
        payloads[lang] = payload
    if not payloads.get('en'):
        raise ContractsError('quiz_invalid', 'en missing')
    clause.quiz_en = payloads['en']
    clause.quiz_ms = payloads['ms']
    clause.quiz_ta = payloads['ta']
    clause.quiz_generated_model = model
    clause.is_quiz_candidate = True
    clause.save(update_fields=[
        'quiz_en', 'quiz_ms', 'quiz_ta', 'quiz_generated_model', 'is_quiz_candidate',
    ])
    return clause


def segment_docx(data, *, model=None):
    """Propose a draft's structure from an author's ``.docx``. Tries the DETERMINISTIC
    parse of the document's own heading/list numbering first (:func:`_docx_structure`) —
    which reads the real ``1.`` / ``1.1`` / ``i)`` hierarchy Word generates — and only an
    unstyled document falls back to Gemini segmentation of its flat text.

    Returns ``{'title': str, 'preamble': str, 'clauses': [{heading, body, level}]}`` — the
    PROPOSAL only; nothing is saved and the upload is not retained (the caller reviews it
    and, on confirm, calls replace_clauses / update_config). Hand-typed bracket placeholders
    are converted to ``{{tokens}}``. Raises ContractsError (docx_unreadable / docx_empty /
    segmentation_failed / …) so the FE can degrade to hand-editing."""
    structured = _docx_structure(data)
    if structured is None:
        text = _extract_docx_text(data)
        model = model or getattr(settings, 'CONTRACT_QUIZ_MODEL', 'gemini-3.8-flash')
        from .. import usage  # import proposal: no template yet → org NULL, source docx_segment
        with usage.usage_context(source='docx_segment'):
            raw, _answered = gemini.generate_with_fallback(
                _gemini_generate, _build_segment_prompt(text), model, fatal=ContractsError)
        structured = {'title': '', 'preamble': '', 'clauses': _parse_segments(raw)}
    # Pull the counterparty from the ORIGINAL recital (before rewriting), then tokenise: the
    # author's brackets → {{tokens}}, AND the donor's literal name / NRIC / address →
    # {{donor_name}} / {{donor_nric}} / {{donor_address}} so each is defined ONCE in Config and
    # referenced as a variable everywhere (edit in one place, updates the whole document).
    cp = _extract_counterparty(structured.get('preamble', ''))
    structured['counterparty'] = cp
    # Address first (longest, contains the name-free street text) so it swaps before any substring.
    donor_subs = [(v, tok) for v, tok in (
        ((cp.get('address') or '').strip(), '{{donor_address}}'),
        ((cp.get('name') or '').strip(), '{{donor_name}}'),
        ((cp.get('nric') or '').strip(), '{{donor_nric}}'),
    ) if len(v) >= 3]

    def _tokenise(text):
        text = _brackets_to_vars(text)
        for value, token in donor_subs:
            text = text.replace(value, token)
        return text

    structured['preamble'] = _tokenise(structured.get('preamble', ''))
    for c in structured['clauses']:
        c['heading'] = _tokenise(c['heading'])
        c['body'] = _tokenise(c['body'])
    return structured
