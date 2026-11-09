"""The public intake door: the WhatsApp opt-out webhook and "are applications open"."""
from django.http import HttpResponse
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .. import apply_copy, gift_sources, whatsapp
from ..services import AmbiguousOpenCohort, resolve_open_cohort, resolve_programme_by_code


class WhatsAppInboundView(APIView):
    """Twilio inbound-WhatsApp webhook — honours STOP/START to keep `whatsapp_opt_in` in sync
    (roadmap S5, TD-135). Anonymous (Twilio calls it) but authenticated by the Twilio signature."""
    permission_classes = [AllowAny]
    authentication_classes = []   # no Bearer/session → no CSRF; the Twilio signature is the auth
    # Twilio POSTs application/x-www-form-urlencoded — accept form bodies (the API defaults to JSON).
    parser_classes = [FormParser, MultiPartParser]

    _STOP = {'stop', 'stopall', 'unsubscribe', 'cancel', 'end', 'quit'}
    _START = {'start', 'unstop', 'yes', 'resume'}

    def post(self, request):
        ok = whatsapp.verify_twilio_signature(
            request.build_absolute_uri(), request.data,
            request.META.get('HTTP_X_TWILIO_SIGNATURE', ''))
        if not ok:
            return HttpResponse(status=status.HTTP_403_FORBIDDEN)
        body = (request.data.get('Body') or '').strip().lower()
        from_number = request.data.get('From') or ''
        if body in self._STOP:
            whatsapp.apply_opt_out(from_number, opted_in=False)
        elif body in self._START:
            whatsapp.apply_opt_out(from_number, opted_in=True)
        # Always 200 with no auto-reply (a TwiML body would send a WhatsApp back).
        return HttpResponse(status=status.HTTP_200_OK)


def _open_round_choices():
    """Every open round, as the least a student needs to choose between them.

    ⚠ THE `code` IS THE **PROGRAMME** CODE, not the cohort's. That is what `?p=` carries and what
    `resolve_open_cohort` narrows on — a cohort code is year-specific (`b40-2026`) and a link
    pinned to one would rot every intake, which is the whole reason the apply link names the
    programme (PF-1 P2). A round whose programme is somehow missing is skipped rather than offered
    with a code that would resolve to nothing.

    ⚠ The NAME shown is the ROUND's (`ScholarshipCohort.name`, e.g. "BrightPath Bursary Programme
    2026") — it is what the student's own screens already call the thing they are applying to.
    """
    from ..models import ScholarshipCohort
    rows = (ScholarshipCohort.objects
            .filter(is_active=True, is_open=True, programme__is_active=True)
            .select_related('programme')
            .order_by('-year', 'code'))
    return [{'code': c.programme.code, 'name': c.name}
            for c in rows if c.programme_id and c.programme.code]


class ScholarshipIntakeView(APIView):
    """
    GET /api/v1/scholarship/intake/  — PUBLIC. Whether NEW applications are open right
    now (drives the landing 'Apply' button + the apply page). Open iff an active, open
    cohort exists. Existing applicants continue via their own application regardless of
    this flag — it only governs starting a fresh application.

    ⚠ PF-1, second half. This ran its OWN copy of the platform-wide query, so fixing only the
    apply path would have moved the bug rather than closed it: with two tenants open, this told
    every visitor about whichever round sorted first — organisation A's programme name on
    organisation B's landing page.

    It now shares `resolve_open_cohort`, so there is ONE rule about what "the open round" means.
    Ambiguity is not an error here: applications genuinely ARE open, and this endpoint is public
    with no scope to narrow by. What it must not do is NAME a programme it cannot identify — so
    the name goes blank and the caller falls back to generic copy.

    Takes an optional `?programme=<code>` — the organisation's own apply link (PF-1 P2). It
    answers for THAT programme only, so a tenant's landing page never reports on another's round.
    An unknown or inactive programme reads closed rather than 404: this endpoint is public and
    unauthenticated, and distinguishing "no such programme" from "not open" would let anyone
    enumerate which tenants exist on the platform.

    ── `choices` (2026-09-06) ──────────────────────────────────────────────────────────────────
    ⚠ ON AMBIGUITY IT NOW LISTS THE OPEN ROUNDS, because it already knew them and threw them away.

    Before the owner's per-gift ruling, two rounds could not be open at once, so ambiguity here was
    a two-tenant edge case and a blank name was enough. Now an organisation may legitimately run
    two intakes, and a student on a bare `/scholarship/apply` hits `AmbiguousOpenCohort` **at
    submit** — after filling in the entire form. The refusal is right; its TIMING was not.

    So the caller gets what it needs to ASK, before the form: `{code, name}` per open round, the
    programme code being exactly what `?p=` carries. PF-1's rule is unchanged — nothing here picks;
    it offers.

    ⚠ WHAT IT DELIBERATELY DOES NOT LEAK: no organisation, no counts, no ids — only what a student
    must read to choose. The list appears ONLY when the caller named no programme and there is
    genuine ambiguity; a normal single-round visitor sees `choices: []` exactly as before.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        programme_code = (request.query_params.get('programme') or '').strip()

        # ⚠ THE COPY IS RESOLVED FROM THE CODE, NOT FROM THE COHORT — and that is the whole
        # point. `resolve_open_cohort` returns None for a CLOSED round, so reading the gift off
        # it would serve the platform default on every closed gift: Sabah's page would advertise
        # BrightPath's criteria, which is the defect this feature exists to remove. A closed gift
        # must stay identifiable so the page can answer "closed" ABOUT THE RIGHT GIFT.
        #
        # ⚠ AN UNKNOWN CODE STAYS SILENT, NEVER 404. This endpoint is public and unauthenticated;
        # distinguishing "no such gift" from "not open" would let anyone enumerate the platform's
        # tenants. It reads exactly like a closed gift with no copy — see the docstring.
        copy = {}
        if programme_code:
            p = resolve_programme_by_code(programme_code)
            if p is not None:
                copy = apply_copy.for_wire(p)

        try:
            cohort = resolve_open_cohort(programme_code=programme_code)
        except AmbiguousOpenCohort:
            # Applications ARE open but nothing says which round: name none, offer the choice.
            # ⚠ NO COPY/CODE ON PURPOSE — no gift is chosen yet; the page re-reads once picked.
            return Response({'open': True, 'cohort_name': '', 'programme_code': '',
                             'choices': _open_round_choices(), 'apply_copy': {}, 'sources': []})

        # No code + exactly one open round → that round's gift owns the page the student is on.
        if not copy and cohort is not None and cohort.programme_id:
            copy = apply_copy.for_wire(cohort.programme)

        # ⚠ `programme_code` is the CANONICAL code of the round `cohort_name` names (an alias or a
        # bare visit resolves to it), so the form submits the gift it showed — a round that closes
        # mid-form is then refused at submit, never silently re-routed. ('' if it could not route.)
        p = cohort.programme if cohort and cohort.programme_id else None
        p = p if p and p.is_active else None
        return Response({
            'open': cohort is not None,
            'cohort_name': cohort.name if cohort else '',
            'programme_code': p.code if p else '',
            'choices': [],
            'apply_copy': copy,
            # Who-referred-you choices of THAT gift ([] when none can be named) — `gift_sources`.
            'sources': gift_sources.public_sources(p),
            'fixed_sources': gift_sources.offered_fixed_codes(p),   # request #44; all three when no gift
        })
