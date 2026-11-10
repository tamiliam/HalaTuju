"""Claiming a MyKad number: the claim and its two challenge doors."""
from rest_framework.response import Response
from rest_framework.views import APIView

from halatuju.middleware.supabase_auth import auth_sub, SupabaseIsAuthenticated


class NricClaimView(APIView):
    """
    POST /api/v1/profile/claim-nric/

    Look an IC up. Outcomes:
    - the IC is new              → it is written to the caller's profile, status='created'
    - the IC is already theirs   → status='linked' (no-op)
    - the IC belongs to somebody → status='exists' + the challenge CHANNELS, never a name

    ⚠ `confirm: true` IS GONE (TD-254). It used to move the profile's primary key in raw SQL —
    an account takeover with no challenge and no record. A client still posting it gets a
    refusal; the claim now runs through the two challenge doors below. All of the logic lives
    in `profile_claim.py`; this view only carries the request in and the answer out.
    """
    permission_classes = [SupabaseIsAuthenticated]

    def post(self, request):
        # ⚠ `auth_sub`, never `request.user_id`: a caller who already holds an alias must act
        # as THEMSELVES here, or a second claim would be filed under the profile they claimed.
        from .. import profile_claim
        payload, code = profile_claim.handle_claim(auth_sub(request), request.user_id, request.data)
        return Response(payload, status=code)


class NricClaimSendCodeView(APIView):
    """
    POST /api/v1/profile/claim-nric/send-code/  {nric, channel, lang}

    Send a one-time code to a contact that is ALREADY ON the target profile and ALREADY
    VERIFIED — the second factor the real owner holds (owner ruling 2026-09-18).
    """
    permission_classes = [SupabaseIsAuthenticated]

    def post(self, request):
        from .. import profile_claim
        payload, code = profile_claim.send_code(auth_sub(request), request.user_id, request.data)
        return Response(payload, status=code)


class NricClaimConfirmCodeView(APIView):
    """
    POST /api/v1/profile/claim-nric/confirm-code/  {nric, code}

    Answer the challenge. On success ONE `ProfileLoginAlias` row is written — a link, not a
    move: nothing is renumbered and nothing is deleted, and deleting that row reverses it.
    """
    permission_classes = [SupabaseIsAuthenticated]

    def post(self, request):
        from .. import profile_claim
        payload, code = profile_claim.confirm_code(auth_sub(request), request.data)
        return Response(payload, status=code)
