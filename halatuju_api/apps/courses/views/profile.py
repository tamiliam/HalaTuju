"""The student profile: read, update and the login-time sync."""
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from halatuju.middleware.supabase_auth import SupabaseIsAuthenticated
from ..bumiputera import foreign_never_bumi, nationality_payload
from ..exam_questions import results_held, third_route_payload
from ..models import StudentProfile
from ..serializers import ProfileUpdateSerializer
from ..stpm_pngk import stpm_cgpa_payload


class ProfileView(APIView):
    """
    GET/PUT /api/v1/profile/

    Requires authentication.
    """
    permission_classes = [SupabaseIsAuthenticated]

    def get(self, request):
        profile, created = StudentProfile.objects.get_or_create(
            supabase_user_id=request.user_id
        )

        # Email comes from Supabase Auth JWT, not the profile model
        email = getattr(request, 'supabase_user', {}).get('email', '')

        contact_email, contact_email_verified = self._contact_email_state(profile, email)
        merit_score = self._merit_score(profile)
        application_open = self._application_open(profile)
        identity_verified, nric_locked, ic_flags, ic_card_nric, ic_card_name = self._identity_state(profile)

        return Response(self._payload(
            profile, email, contact_email, contact_email_verified, merit_score, application_open,
            identity_verified, nric_locked, ic_flags, ic_card_nric, ic_card_name,
        ))

    @staticmethod
    def _contact_email_state(profile, email):
        """The contact email and whether it counts as verified."""
        # Contact email auto-defaults to the auth email when blank — the auth
        # email is already verified (Google/Supabase). It is ALSO considered verified
        # when the student's saved contact email IS that same Google identity (the
        # common case — they logged in with the address they want contacted on), so
        # it no longer shows a false "Not verified". An explicitly DIFFERENT contact
        # email still needs the verify-email flow.
        contact_email = profile.contact_email or email
        contact_email_verified = bool(
            profile.contact_email_verified
            or (email and contact_email.strip().lower() == email.strip().lower())
        )
        return contact_email, contact_email_verified

    @staticmethod
    def _merit_score(profile):
        """SPM academic merit, computed from the stored grades; None if there are none or it fails."""
        # Shown on the /profile Application Tracking card; tapping it routes to the grades editor.
        merit_score = None
        if profile.grades:
            try:
                from ..eligibility_service import compute_student_merit
                merit_score = round(compute_student_merit({
                    'grades': profile.grades,
                    'coq_score': profile.coq_score if profile.coq_score is not None else 5.0,
                    'stream_subjects': profile.stream_subjects,
                }), 1)
            except Exception:
                merit_score = None
        return merit_score

    @staticmethod
    def _application_open(profile):
        """Is the student's latest B40 application still OPEN (undecided)?"""
        # Tells the FE whether the family/pathway link is live (a small note). Pathway itself now
        # lives on the profile (the durable home), so it's read from the profile columns.
        application_open = False
        try:
            # Read through the reverse relation rather than importing the model: one fewer
            # `courses -> scholarship` edge for an identical queryset (app-boundary standard).
            from apps.scholarship.public import DECIDED_STATUSES
            latest_app = profile.scholarship_applications.order_by('-id').first()
            if latest_app is not None:
                application_open = latest_app.status not in DECIDED_STATUSES
        except Exception:
            application_open = False
        return application_open

    @staticmethod
    def _identity_state(profile):
        """(identity_verified, nric_locked, ic_flags, ic_card_nric, ic_card_name) for the badges."""
        # Identity verified — drives the Name + IC "Verified" badges on /profile. True when
        # the student's uploaded MyKad SCAN confirms both name and IC No against the profile
        # (the "verified with an IC" sense), OR an admin has locked the NRIC at verify-&-accept.
        # The IC lock, and what the card disagrees with (2026-07-29).
        #
        # `nric_locked` is the STORED lock and the only thing the padlock may key on. The
        # separate `identity_verified` below is a DISPLAY badge and deliberately broader — it
        # also greens for a card that matches but has not (yet) locked, e.g. one that was never
        # scored for genuineness. **These are not interchangeable.** Wiring the padlock to the
        # badge would lock students the moment they upload a matching card, with no genuineness
        # check and no admin — and worse, it would UNLOCK again if they deleted the document,
        # because the badge is derived on every read and the lock is not.
        #
        # `ic_flags` is what makes a wrong number fixable at all: until now a student whose
        # typed IC disagreed with their card was told nothing here, and found out only when
        # consent refused them. Codes, not sentences — the screen owns the wording, and must
        # not assert which side is wrong (our OCR mangles names too; see #27 and #118).
        identity_verified = bool(profile.nric_verified)
        # TD-377: an IC held by a "Born in" rule is locked to her too (see `profile_claim`).
        from .. import profile_claim
        nric_locked = (bool(profile.nric_verified)
                       or profile_claim.ic_held_by_birth_state_rule(profile))
        ic_flags, ic_card_nric, ic_card_name = [], '', ''
        try:
            from apps.scholarship.public import ApplicantDocument, identity as identity_rules
            ic = (ApplicantDocument.objects
                  .filter(application__profile=profile, doc_type='ic',
                          superseded_at__isnull=True)     # a REPLACED card decides nothing
                  .exclude(vision_name='').order_by('-id').first())
            if ic is not None and profile.name and profile.nric:
                cmp_ = identity_rules.compare(ic, profile)
                ic_flags = identity_rules.flags(cmp_)
                ic_card_nric, ic_card_name = cmp_['card_nric'], cmp_['card_name']
                if not identity_verified:
                    identity_verified = (cmp_['name'] == 'match' and cmp_['nric'] == 'match')
        except Exception:
            pass
        return identity_verified, nric_locked, ic_flags, ic_card_nric, ic_card_name

    @staticmethod
    def _payload(profile, email, contact_email, contact_email_verified, merit_score, application_open,
                 identity_verified, nric_locked, ic_flags, ic_card_nric, ic_card_name):
        """The profile response body (key order is part of the contract the pins freeze)."""
        from django.conf import settings
        return {
            'grades': profile.grades,
            'gender': profile.gender,
            **nationality_payload(profile),     # + the Bumiputera answer (Sprint B), hers only
            'colorblind': profile.colorblind,
            'disability': profile.disability,
            'student_signals': profile.student_signals,
            'preferred_state': profile.preferred_state,
            'preferred_call_language': profile.preferred_call_language,
            'referral_source': profile.referral_source,
            'guardians': profile.guardians,
            'name': profile.name,
            'school': profile.school,
            'nric': profile.nric,
            'nric_verified': profile.nric_verified,
            'identity_verified': identity_verified,
            # The padlock keys on THIS, never on identity_verified above.
            'nric_locked': nric_locked,
            'ic_flags': ic_flags,
            'ic_card_nric': ic_card_nric,
            'ic_card_name': ic_card_name,
            'angka_giliran': profile.angka_giliran,
            'address': profile.address,
            'postal_code': profile.postal_code,
            'city': profile.city,
            'email': email,
            'contact_email': contact_email,
            'contact_email_verified': contact_email_verified,
            'contact_phone': profile.contact_phone,
            'contact_phone_verified': profile.contact_phone_verified,
            # Whether the student phone-verify control is live (paused by default — see
            # settings.PHONE_VERIFY_ENABLED). The badge still shows for already-verified numbers.
            'phone_verify_enabled': getattr(settings, 'PHONE_VERIFY_ENABLED', False),
            'whatsapp_opt_in': profile.whatsapp_opt_in,
            # TD-061: canonical financial fields (replace legacy family_income/
            # siblings/phone). The /profile family card reads these.
            'household_income': profile.household_income,
            'household_size': profile.household_size,
            # Structured family roster (profile-level home; two-way synced with an open application)
            'father_name': profile.father_name,
            'father_occupation': profile.father_occupation,
            'father_occupation_other': profile.father_occupation_other,
            'mother_name': profile.mother_name,
            'mother_occupation': profile.mother_occupation,
            'mother_occupation_other': profile.mother_occupation_other,
            'other_family_members': profile.other_family_members,
            'siblings_in_school': profile.siblings_in_school,
            'siblings_in_tertiary': profile.siblings_in_tertiary,
            # Pathway / "Your Plans" (profile-level home; two-way synced with an open application)
            'pathway_certainty': profile.pathway_certainty,
            'chosen_pathway': profile.chosen_pathway,
            'pre_u_track': profile.pre_u_track,
            'pre_u_institution': profile.pre_u_institution,
            'chosen_programme': profile.chosen_programme,
            'pathways_considered': profile.pathways_considered,
            'uncertainty_reasons': profile.uncertainty_reasons,
            'uncertainty_note': profile.uncertainty_note,
            # Application Tracking surfaces: merit (computed) + a back-compat `pathway` alias
            'merit_score': merit_score,
            'pathway': profile.chosen_pathway,
            'application_open': application_open,
            'exam_type': profile.exam_type,
            # TD-218 (2026-10-02): served at last — the web's results-held reader and its login
            # hydrate were written against this key, and it was never on the payload.
            'results_exam_type': profile.results_exam_type,
            'results_held': results_held(profile),       # TD-218 review F1: the ONE rule, served
            'stpm_grades': profile.stpm_grades,
            **stpm_cgpa_payload(profile),       # CGPA sprint C2: stpm_cgpa (from the grades) + _calculated
            'muet_band': profile.muet_band,
            'coq_score': profile.coq_score,
            'spm_prereq_grades': profile.spm_prereq_grades,
            'stream_subjects': profile.stream_subjects,
            'elective_subjects': profile.elective_subjects,
            'spm_elective_subjects': profile.spm_elective_subjects,     # TD-069
            'spm_stream': profile.spm_stream,
            **third_route_payload(profile),      # S2a: higher_*, completed list, overall_cgpa
        }

    def put(self, request):
        profile = StudentProfile.objects.get(
            supabase_user_id=request.user_id
        )

        serializer = ProfileUpdateSerializer(profile, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Capture old contact values before save
        old_contact_email = profile.contact_email
        old_contact_phone = profile.contact_phone

        # Sprint B: a foreign student is never Bumiputera (`bumiputera.foreign_never_bumi`).
        profile = serializer.save(**foreign_never_bumi(profile, serializer.validated_data))

        # Reset verification when contact details actually change
        if 'contact_email' in serializer.validated_data and profile.contact_email != old_contact_email:
            profile.contact_email_verified = False
            profile.save(update_fields=['contact_email_verified'])
        if 'contact_phone' in serializer.validated_data and profile.contact_phone != old_contact_phone:
            profile.contact_phone_verified = False
            profile.save(update_fields=['contact_phone_verified'])

        # A client-supplied `referral_source` is IGNORED here (two columns, 2026-10-09): it is not on
        # the serializer, so it sets neither the chip, `source` nor `referred_by_org`. No web caller
        # sends it, and a 400 would cost a stale bundle its whole save.

        # The family roster + pathway are two-way linked to an OPEN application: a /profile
        # edit flows into the student's latest undecided application so the two stay
        # identical. Once the application is decided its copy FREEZES (excluded here), and
        # a /profile edit no longer touches it.
        from apps.scholarship.public import (
            PROFILE_FAMILY_FIELDS, PROFILE_PATHWAY_FIELDS, DECIDED_STATUSES,
            copy_family_roster, copy_pathway,
        )
        vd = serializer.validated_data
        family_changed = any(f in vd for f in PROFILE_FAMILY_FIELDS)
        pathway_changed = any(f in vd for f in PROFILE_PATHWAY_FIELDS)
        if family_changed or pathway_changed:
            # Reverse relation, not an import: one fewer `courses -> scholarship` edge for an
            # identical queryset (app-boundary standard).
            open_app = (profile.scholarship_applications
                        .exclude(status__in=DECIDED_STATUSES)
                        .order_by('-id').first())
            if open_app is not None:
                fields = []
                if family_changed:
                    copy_family_roster(profile, open_app); fields += list(PROFILE_FAMILY_FIELDS)
                if pathway_changed:
                    copy_pathway(profile, open_app); fields += list(PROFILE_PATHWAY_FIELDS)
                open_app.save(update_fields=fields)

        return Response({'message': 'Profile updated'})


class ProfileSyncView(APIView):
    """
    POST /api/v1/profile/sync/

    Sync localStorage data to backend profile after first login.
    Accepts grades, demographics, quiz signals, name, and school in one call.
    Creates the profile if it doesn't exist.
    """
    permission_classes = [SupabaseIsAuthenticated]

    def post(self, request):
        # Reject anonymous users — they must claim NRIC first
        supabase_user = getattr(request, 'supabase_user', None) or {}
        if supabase_user.get('is_anonymous', False):
            return Response(
                {'error': 'Anonymous users cannot sync profiles. Please sign in first.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        profile, created = StudentProfile.objects.get_or_create(
            supabase_user_id=request.user_id
        )

        # Seed-only name. This browser sync pre-fills the name from the Google sign-in
        # display name (which can be a handle like "Sharmila 1204"). It may SEED a blank
        # profile, but must never OVERWRITE a name already on file — the real legal name
        # is set deliberately at apply submit (the declaration signature), and a later
        # re-sign-in through the auth gate must not clobber it back to the Google handle.
        # Explicit edits still go through PUT /profile/, which is unaffected.
        data = request.data.copy()
        if (profile.name or '').strip():
            data.pop('name', None)

        serializer = ProfileUpdateSerializer(profile, data=data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        profile = serializer.save(**foreign_never_bumi(profile, serializer.validated_data))  # Sprint B

        # A `?ref=` code the browser resends on EVERY sign-in: the REFERRAL PARTNER column only,
        # first touch, partner rows only — never the bursary's source (two columns, 2026-10-09).
        from .. import referral_links
        referral_links.apply_ref_code(profile, request.data.get('referral_source'))

        return Response({
            'message': 'Profile synced',
            'created': created,
        })
