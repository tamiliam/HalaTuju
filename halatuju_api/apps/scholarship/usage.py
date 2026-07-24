"""Per-tenant usage meter (Billing & usage v1 — Sprint 13a).

The meter is a thin, ABSOLUTELY best-effort logger wrapped around the sanctioned
billable seams (Gemini / Cloud Vision / OpenAI / Brevo email / Twilio WhatsApp).
Two hard promises:

1. **Unconditional** — metering runs from deploy with NO flag. Rows are cheap; the
   data accrues immediately for reconciliation. The ``BILLING_USAGE_ENABLED`` flag
   gates ONLY the read endpoint/UI, never this logger.
2. **Best-effort** — a metering failure can NEVER break the user-facing call. Every
   public entry point here swallows *all* exceptions (``record_usage`` is the fault
   boundary; a failing DB write is logged and dropped). A fault-injection test proves
   it.

Call sites thread a lightweight context (organisation / application / source tag) via
``usage_context``; the seam reads it when it logs, so the seams' public return shapes
never change. Token counts (AI only) are read from each provider response's own usage
metadata inside the seam.

NO prices anywhere in v1 (units/tokens only) — there is no price table yet.
"""
import contextvars
import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# ── Service tags (mirror UsageEvent.SERVICE_CHOICES) ───────────────────────────
GEMINI = 'gemini'
VISION_OCR = 'vision_ocr'
OPENAI = 'openai'
EMAIL = 'email'
WHATSAPP = 'whatsapp'

# ── Call-path context (thread/async-safe) ──────────────────────────────────────
# A frame holds {source, org_id, app_id}. A nested usage_context inherits any value
# it does not itself supply, so a low-level seam (e.g. the IC Gemini second opinion)
# can re-tag ONLY the source while keeping the org/application the outer doc set.
_ctx: 'contextvars.ContextVar[dict]' = contextvars.ContextVar('usage_ctx', default={})


@contextmanager
def usage_context(*, source='', application=None, organisation_id=None, application_id=None):
    """Set the billing attribution context for any billable seam called within the block.

    Pass ``application`` to resolve BOTH the owning organisation (the denormalised
    ``owning_organisation``) and the application id in one go; or pass the ids directly.
    Anything not supplied is inherited from the enclosing context (so a nested block can
    override just ``source``). Never raises — attribution is best-effort scaffolding."""
    cur = _ctx.get() or {}
    try:
        org_id = organisation_id
        app_id = application_id
        if application is not None:
            if app_id is None:
                app_id = getattr(application, 'id', None)
            if org_id is None:
                org_id = getattr(application, 'owning_organisation_id', None)
        frame = {
            'source': source or cur.get('source', ''),
            'org_id': org_id if org_id is not None else cur.get('org_id'),
            'app_id': app_id if app_id is not None else cur.get('app_id'),
        }
    except Exception:  # noqa: BLE001 — context must never break the wrapped call
        frame = dict(cur)
    token = _ctx.set(frame)
    try:
        yield
    finally:
        _ctx.reset(token)


def current_context() -> dict:
    return _ctx.get() or {}


# ── The logger (the fault boundary) ────────────────────────────────────────────
def _int_or_none(v):
    """Only genuine ints survive — a Mock/float/str token value becomes None, so a
    test that mocks the provider client can't leak a Mock into the DB."""
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def record_usage(service, *, model='', source=None, quantity=1,
                 input_tokens=None, output_tokens=None,
                 organisation_id=None, application_id=None):
    """Log ONE billable event. ABSOLUTELY best-effort: any exception (including a DB
    write failure) is caught and dropped so the surrounding user-facing call is never
    broken. Reads org/application/source from the current usage_context when not given.
    """
    try:
        ctx = _ctx.get() or {}
        if source is None:
            source = ctx.get('source', '') or ''
        if organisation_id is None:
            organisation_id = ctx.get('org_id')
        if application_id is None:
            application_id = ctx.get('app_id')
        from .models import UsageEvent
        UsageEvent.objects.create(
            organisation_id=organisation_id,
            application_id=application_id,
            service=service,
            model=(model or '')[:80],
            source=(source or '')[:40],
            quantity=quantity if isinstance(quantity, int) and quantity > 0 else 1,
            input_tokens=_int_or_none(input_tokens),
            output_tokens=_int_or_none(output_tokens),
        )
    except Exception:  # noqa: BLE001 — a metering failure must NEVER surface
        logger.warning('usage metering failed (service=%s)', service, exc_info=True)


def gemini_tokens(resp):
    """(input, output) token counts from a genai response's usage_metadata, or
    (None, None). Never raises; a mocked response yields (None, None)."""
    try:
        md = getattr(resp, 'usage_metadata', None)
        if md is None:
            return (None, None)
        return (_int_or_none(getattr(md, 'prompt_token_count', None)),
                _int_or_none(getattr(md, 'candidates_token_count', None)))
    except Exception:  # noqa: BLE001
        return (None, None)


def openai_tokens(completion):
    """(input, output) token counts from an OpenAI completion's usage, or (None, None)."""
    try:
        u = getattr(completion, 'usage', None)
        if u is None:
            return (None, None)
        return (_int_or_none(getattr(u, 'prompt_tokens', None)),
                _int_or_none(getattr(u, 'completion_tokens', None)))
    except Exception:  # noqa: BLE001
        return (None, None)


# ── Aggregation for the super-only usage screen ────────────────────────────────
# Plain allowlist dicts (NO model passthrough, NO prices). The endpoint's exact-key
# snapshot test pins these shapes.
_ZERO = {'events': 0, 'quantity': 0, 'input_tokens': 0, 'output_tokens': 0}


def available_months():
    """Descending list of 'YYYY-MM' strings that have at least one usage event."""
    from .models import UsageEvent
    return [d.strftime('%Y-%m')
            for d in UsageEvent.objects.dates('created_at', 'month', order='DESC')]


def _service_row(service, agg):
    return {
        'service': service,
        'events': int(agg.get('events') or 0),
        'quantity': int(agg.get('quantity') or 0),
        'input_tokens': int(agg.get('input_tokens') or 0),
        'output_tokens': int(agg.get('output_tokens') or 0),
    }


def org_storage_bytes(org_id):
    """Live Supabase-storage snapshot for ONE organisation: the sum of the document
    bytes we hold for that org — applicant documents (via the application's
    owning_organisation) + request screenshot attachments. Computed at request time
    from our own metadata (NO usage_events row, NO meter change). Best-effort → 0."""
    try:
        from django.db.models import Sum
        from .models import ApplicantDocument, OrgRequestAttachment
        docs = (ApplicantDocument.objects
                .filter(application__owning_organisation_id=org_id)
                .aggregate(b=Sum('size'))['b'] or 0)
        atts = (OrgRequestAttachment.objects
                .filter(org_request__organisation_id=org_id)
                .aggregate(b=Sum('size'))['b'] or 0)
        return int(docs) + int(atts)
    except Exception:  # noqa: BLE001
        return 0


def bucket_storage_bytes():
    """Whole-bucket storage snapshot (all orgs) — the platform reconciliation figure.
    Best-effort → 0."""
    try:
        from django.db.models import Sum
        from .models import ApplicantDocument, OrgRequestAttachment
        docs = ApplicantDocument.objects.aggregate(b=Sum('size'))['b'] or 0
        atts = OrgRequestAttachment.objects.aggregate(b=Sum('size'))['b'] or 0
        return int(docs) + int(atts)
    except Exception:  # noqa: BLE001
        return 0


def monthly_usage(month, *, restrict_org_id=None, include_platform=False):
    """Per-organisation metered usage + a live document-storage snapshot for ``month``
    ('YYYY-MM'). Units and token sums ONLY — no prices. Returns a plain allowlist dict.

    Dual audience, enforced HERE by construction:
      * org_admin — pass ``restrict_org_id`` = the caller's own organisation. The query
        filters ``organisation_id=<that org>`` so NO other org and NO platform (NULL-org)
        row can ever be built. ``include_platform`` is ignored.
      * super — pass ``restrict_org_id=None`` + ``include_platform=True`` for every
        organisation PLUS the platform (NULL-org) row. The platform block is SUPER-ONLY.
    """
    from django.db.models import Count, Sum
    from apps.courses.models import PartnerOrganisation
    from .models import UsageEvent

    try:
        year, mon = (int(x) for x in str(month).split('-'))
    except Exception:  # noqa: BLE001 — a malformed month yields an empty (but valid) payload
        year, mon = 0, 0

    qs = UsageEvent.objects.filter(created_at__year=year, created_at__month=mon)
    if restrict_org_id is not None:
        # org_admin fence: only this org's rows survive — platform (NULL) drops out here.
        qs = qs.filter(organisation_id=restrict_org_id)
    rows = (qs.values('organisation_id', 'service')
            .annotate(events=Count('id'), quantity=Sum('quantity'),
                      input_tokens=Sum('input_tokens'), output_tokens=Sum('output_tokens'))
            .order_by('organisation_id', 'service'))

    by_org = {}
    for r in rows:
        by_org.setdefault(r['organisation_id'], []).append(r)

    names = {}
    ids = [oid for oid in by_org if oid is not None]
    if restrict_org_id is not None and restrict_org_id not in ids:
        ids.append(restrict_org_id)   # always render the caller's own org, even at zero usage
    if ids:
        names = dict(PartnerOrganisation.objects.filter(pk__in=ids).values_list('id', 'name'))

    def org_block(org_id, service_rows):
        services = [_service_row(r['service'], r) for r in service_rows]
        totals = {
            'events': sum(s['events'] for s in services),
            'quantity': sum(s['quantity'] for s in services),
            'input_tokens': sum(s['input_tokens'] for s in services),
            'output_tokens': sum(s['output_tokens'] for s in services),
        }
        is_platform = org_id is None
        return {
            'organisation_id': org_id,
            'organisation': (names.get(org_id, 'Organisation') if not is_platform else 'Platform'),
            'is_platform': is_platform,
            'services': services,
            'totals': totals,
            # Live snapshot (not metered): document bytes we hold for this org; the platform
            # block carries the whole-bucket total for reconciliation (super-only).
            'storage_bytes': (bucket_storage_bytes() if is_platform else org_storage_bytes(org_id)),
        }

    organisations = []
    # Platform (NULL org) first — SUPER-ONLY, and only when asked for.
    if include_platform and restrict_org_id is None:
        organisations.append(org_block(None, by_org.pop(None, [])))
    elif None in by_org:
        # Defensive: never let a NULL-org block into an org-scoped payload.
        by_org.pop(None, None)

    if restrict_org_id is not None:
        organisations.append(org_block(restrict_org_id, by_org.get(restrict_org_id, [])))
    else:
        for org_id in sorted((i for i in by_org if i is not None),
                             key=lambda i: (names.get(i, '') or '').lower()):
            organisations.append(org_block(org_id, by_org[org_id]))

    return {
        'month': str(month),
        'months': available_months(),
        'can_see_platform': bool(include_platform and restrict_org_id is None),
        'organisations': organisations,
    }
