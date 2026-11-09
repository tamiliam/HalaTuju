"""The Action Centre: the student's resolution items, list and resolve."""
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from halatuju.middleware.supabase_auth import SupabaseIsAuthenticated
from .common import _current_application, SET_ASIDE_STATES


class ResolutionItemListView(APIView):
    """GET the caller's resolution queue — the IBKR-style Action Centre (S3).
    Syncs against the live verdict first, then returns the open items + the most
    recently resolved, so the student sees what's left and what just cleared."""
    permission_classes = [SupabaseIsAuthenticated]

    def get(self, request):
        from ..resolution import sync_resolution_items
        from ..check2_queries import sync_check2_queries
        from ..serializers import ResolutionItemSerializer
        app = _current_application(request.user_id)
        # Check-2 gate: NO student queries until the /application is submitted
        # (consent = profile_completed_at). Before that the student works through the
        # Step-4 tabs normally. This also hides any tickets generated prematurely
        # under the old behaviour. (Apply → Shortlist → Consent → Check 2 → Query.)
        if app is None or app.profile_completed_at is None:
            return Response({'open': [], 'resolved': []})
        from django.conf import settings as _settings
        sync_resolution_items(app)
        # Post-award: surface (or clear) the bank-details task for an awarded/active student.
        # Independent of the Check-2 flag — it's a payout step, not a verification query.
        from ..resolution import sync_bank_details_item, sync_vircle_item
        sync_bank_details_item(app)
        # Post-award: the Vircle eWallet setup task (install the app → confirm here). Same
        # nature as the bank task — a payout step, not a verification query — so it is likewise
        # independent of the Check-2 flag, and gated by its own VIRCLE_SETUP_ENABLED.
        sync_vircle_item(app)
        # Check 2 STEP 2: the AI clarify queries are held behind a flag until the
        # questions have been reviewed — while OFF, students are asked nothing new
        # (officers still review them in the cockpit).
        queries_live = getattr(_settings, 'CHECK2_STUDENT_QUERIES_ENABLED', False)
        if queries_live:
            sync_check2_queries(app)
        # The student's Action Centre shows: a reviewer's (officer) query/doc-request, the
        # Check-2 student queries (clarify + pathway confirm, source='check2'), AND the
        # "review assistant" (Check 2) asking for any MISSING compulsory document (a `doc`
        # system gap — birth cert / offer letter / earner IC / …). All flag-gated.
        # The uploaded-but-bad system tickets (*_unreadable / *_name_mismatch /
        # str_not_current) stay HIDDEN — those are reviewer-raised re-uploads, coached inline
        # by Gopal (the 2026-06-10 duplicate-noise fix). 'human' = reviewer-only.
        from ..resolution import STUDENT_DOC_REQUEST_CODES, BANK_DETAILS_CODE, VIRCLE_CODE

        # From RECOMMENDED onward, the AUTO review-phase items — verification gaps
        # (source='system') + Check-2 clarify queries (source='check2') — are SET ASIDE, not
        # deleted: they were the review's to-do list, and the review is over. The still-OPEN ones
        # are peeled out of the actionable queue and shown struck-through (amber) — NOT a to-do,
        # NOT "done"/green — so the student sees they no longer need answering. The post-award
        # tasks (bank details, Vircle setup) stay actionable. (Owner 2026-06-29; moved from
        # `awarded` to `recommended` 2026-07-13 — nobody may ask a recommended student anything,
        # so leaving their old queries live was asking for an answer we no longer want.)
        set_aside_stage = app.status in SET_ASIDE_STATES

        def _student_visible(i):
            if i.kind == 'human':
                return False
            # The post-award bank-details task (a payout step, not a Check-2 query) shows for an
            # awarded/active student ONLY while the capture feature is enabled. It is being
            # deprecated (an alternative monthly arrangement replaces it), so default OFF →
            # never shown (sync_bank_details_item also sweeps any existing one to resolved).
            if i.code == BANK_DETAILS_CODE:
                return getattr(_settings, 'BANK_DETAILS_CAPTURE_ENABLED', False)
            # The Vircle setup task, likewise: a post-award step, shown to an awarded/active
            # student whenever the feature is on, whatever the Check-2 flag says.
            if i.code == VIRCLE_CODE:
                return getattr(_settings, 'VIRCLE_SETUP_ENABLED', False)
            if i.source == 'system':
                return queries_live and i.code in STUDENT_DOC_REQUEST_CODES
            if i.source == 'check2':
                return queries_live
            return True   # officer items always show

        # A review-phase AUTO item (not the post-award operational tasks): set aside for funded
        # students. The bank + Vircle tasks are EXCLUDED — they only exist once funded, so
        # setting them aside would strike through the one thing we're actually asking for.
        def _is_review_auto(i):
            return (i.source in ('system', 'check2')
                    and i.code not in (BANK_DETAILS_CODE, VIRCLE_CODE))

        items = [i for i in app.resolution_items.all() if _student_visible(i)]
        openq = [i for i in items if i.status == 'open']
        resolved = [i for i in items if i.status == 'resolved'][:10]
        # Recommended onward: lift the OPEN review-phase items out of the actionable queue into a
        # SET-ASIDE bucket (the FE renders them struck-through amber). Resolved items stay as they
        # are. An OFFICER-raised item is never set aside — but by this stage none can be raised.
        set_aside = []
        if set_aside_stage:
            set_aside = [i for i in openq if _is_review_auto(i)]
            openq = [i for i in openq if not _is_review_auto(i)]
        return Response({
            'open': ResolutionItemSerializer(openq, many=True).data,
            'resolved': ResolutionItemSerializer(resolved, many=True).data,
            'set_aside': ResolutionItemSerializer(set_aside, many=True).data,
        })


class ResolutionItemResolveView(APIView):
    """POST {text} to resolve a confirm/explanation ticket the caller owns. Doc
    tickets resolve implicitly when the document is uploaded (the upload re-syncs
    the queue), so this serves the confirm/explanation kinds only."""
    permission_classes = [SupabaseIsAuthenticated]

    def post(self, request, pk):
        from ..models import ResolutionItem
        from ..resolution import VIRCLE_CODE, resolve_item
        from ..serializers import ResolutionItemSerializer
        item = ResolutionItem.objects.filter(
            pk=pk, application__profile_id=request.user_id, status='open',
        ).select_related('application').first()
        if item is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        from ..services import querying_locked
        from ..stpm_asks import CODES as STPM_ASKS   # C4: answered on the STPM page, closed by the gap
        # Querying is LOCKED from the interview onward — and an awarded student is well past
        # that. The Vircle task is a post-award operational step, not a Check-2 query, so it
        # must be exempt or the student could never confirm. (The bank task sidesteps this by
        # being a 'doc' kind, resolved by upload; this one is a 'confirm', so it comes through
        # here.)
        if item.code != VIRCLE_CODE and querying_locked(item.application):
            return Response({'error': 'querying_closed'}, status=status.HTTP_400_BAD_REQUEST)
        if item.kind == 'doc' or item.code in STPM_ASKS:
            return Response({'error': 'upload_doc_instead' if item.kind == 'doc' else 'answer_on_page',
                             'doc_type': item.doc_type}, status=status.HTTP_400_BAD_REQUEST)
        if item.kind == 'human':   # reviewer-only — not the student's to answer
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        text = (request.data.get('text') or '').strip()
        if item.kind in ('explanation', 'clarify') and not text:
            return Response({'error': 'text_required'}, status=status.HTTP_400_BAD_REQUEST)
        # The Vircle confirmation carries the MOBILE NUMBER the student registered with Vircle.
        # It is the ONLY join key we will ever have between our record and their Vircle account
        # (Vircle tells us nothing back), so a typo here silently relays the wrong account — or
        # none. Validate + store E.164 via the shared normaliser.
        if item.code == VIRCLE_CODE:
            from ..whatsapp import normalise_msisdn
            mobile = normalise_msisdn(text)
            if not mobile:
                return Response({'error': 'bad_mobile'}, status=status.HTTP_400_BAD_REQUEST)
            text = mobile
            # V2a (2026-09-09): `vircle_id` is OPTIONAL. The eWallet ID now arrives via
            # Vircle's Airtable callback (VircleAirtableUpdateView) after the confirm —
            # the student no longer types it. A value is still accepted (an old cached
            # bundle may send one) and still validated: supplied-but-bad stays a 400,
            # because storing a bad id silently is worse than refusing it.
            from .. import payments
            vircle_id = ''.join(ch for ch in (request.data.get('vircle_id') or '') if ch.isdigit())
            if vircle_id:
                if not payments.valid_vircle_id(vircle_id):
                    # `reason` lets the client name the actual mistake. A student who read the
                    # Top Up screen instead of Settings typed a DuitNow Transfer number —
                    # telling them to "check the number" would be wrong, the number is fine,
                    # the FIELD was.
                    return Response({'error': 'bad_vircle_id',
                                     'reason': payments.vircle_id_error(vircle_id)},
                                    status=status.HTTP_400_BAD_REQUEST)
                item.application.vircle_id = vircle_id
                item.application.save(update_fields=['vircle_id'])
        # Phase 2 (D2): on a typed answer, Cikgu Gopal nudges ONLY when it is TOTALLY
        # off-topic — keep the task open and return his one-sentence steer, don't resolve.
        # Flag-gated + AI-off-safe (judge defaults to accept). 'pathway_confirm' /
        # 'pathway_type_switch' are one-tap Yes confirms (their 'confirmed' text isn't a free
        # answer, so it's never judged); the Vircle confirmation is a phone number, likewise not a
        # free-text answer to judge.
        if text and item.code not in ('pathway_confirm', 'pathway_type_switch', VIRCLE_CODE):
            from django.conf import settings as _settings
            if getattr(_settings, 'CHECK2_ANSWER_RELEVANCE_ENABLED', False):
                from ..help_engine import judge_answer_relevance
                from .. import usage as _usage
                question = (request.data.get('question') or item.prompt or '').strip()
                # Bill the relevance judge to the tenant. The judge stays firewalled to Q+A
                # text only — attribution rides the ambient context, not its signature.
                with _usage.usage_context(application=item.application):
                    verdict = judge_answer_relevance(question, text)
                if not verdict['on_topic']:
                    return Response({'resolved': False, 'nudge': verdict['nudge']})
        resolve_item(item, text=text, by='student')
        # Vircle Airtable push (2026-09-09): the student just said "installed, and this is my
        # mobile" — that is the agreed moment Vircle is told WHO to expect (never earlier: the
        # student may register with a different phone than the application's). Best-effort by
        # contract — push_recipient never raises, so it cannot fail the confirmation it rides on.
        if item.code == VIRCLE_CODE:
            from .. import vircle_airtable
            vircle_airtable.push_recipient(item)
            # The student's own claim of WHICH account type they registered (owner, 2026-09-09):
            # a self-check the card coaches on before sending. Stored for the human reconciling
            # a `no_match` callback row — NEVER trusted over the birth-year derivation
            # (push_recipient keeps deriving Type from vircle.can_register). Junk is dropped.
            claimed = str(request.data.get('account_type') or '').strip().lower()
            extra = {}
            if claimed in ('principal', 'child'):
                extra['account_type'] = claimed
            # The explicit installed-and-registered tick (owner, 2026-09-10, off a real student
            # who confirmed without ever registering — Vircle: "could not find his IC"). The
            # CARD refuses to submit unticked; the server only RECORDS the claim, never
            # requires it, so an old cached bundle (which sends nothing) still resolves.
            if request.data.get('installed_confirmed') is True:
                extra['installed_confirmed'] = True
            if extra:
                item.params = {**(item.params or {}), **extra}
                item.save(update_fields=['params'])
        # The ask-first informal clarify: READ the answer once, here, and store what it claims
        # (#126, owner 2026-07-13). If the student says the earner does have a payslip/EPF, the
        # suppressed document request re-opens (income_engine.informal_payslip_claimed) and the
        # chain resumes — the payslip arrives, and the EPF request follows it automatically.
        # Classifying at ANSWER time (not in the gap engine) keeps the sync loop free of both the
        # cost and the non-determinism of re-reading free text on every reload.
        if item.code == 'informal_income_detail':
            from ..income_engine import payslip_claim
            item.params = {**(item.params or {}), 'payslip_claim': payslip_claim(text)}
            item.save(update_fields=['params'])
        # The twin, #117: a retired/unable parent's pension answer, classified once here. An explicit
        # "yes, he draws a pension" opens the *_pension_proof_missing statement request
        # (check2_queries via income_engine.pension_claimed); "no"/"unclear" ask for nothing.
        if item.code == 'pension_amount_unknown':
            from ..income_engine import pension_claim
            item.params = {**(item.params or {}), 'pension_claim': pension_claim(text)}
            item.save(update_fields=['params'])
        # The pathway confirmations are the 'confirm' items that also WRITE state: the
        # student saying Yes settles their final chosen pathway (no human officer).
        # pathway_type_switch (TD-161) shares the handler — confirm_pathway also adopts the
        # offer's TYPE when it differs from the declaration (STPM → PISMP, #43).
        if item.code in ('pathway_confirm', 'pathway_type_switch'):
            from ..services import confirm_pathway
            confirm_pathway(item.application)
        return Response(ResolutionItemSerializer(item).data)
