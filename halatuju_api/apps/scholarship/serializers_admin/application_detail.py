"""The officer cockpit payload: the declared fields and Meta of AdminApplicationDetailSerializer. Its computed fields live in detail_people and detail_blocks."""

from rest_framework import serializers
from ..models import ScholarshipApplication
from .. import (
    results_route as _notes,
    serializers_admin_family as _family,
    serializers_admin_gift as _gift,
    stpm_marks as _stpm,
)
from .. import serializers_admin_decision_mail as _dmail
from ..sgd_conversion import AdminApplicantDocumentSerializer
from ..serializers import ConsentSerializer, RefereeSerializer
from .detail_blocks import ServesTheDetailBlocks
from .detail_people import ServesTheDetailPeople


class AdminApplicationDetailSerializer(ServesTheDetailBlocks, ServesTheDetailPeople, _gift.ServesTheGift, _dmail.ServesTheDecisionMail, _family.ServesTheFamilyAnswers, _stpm.ServesTheStpmMarks, _notes.ServesTheStudentsResultsNotes, serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    school = serializers.SerializerMethodField()
    # NRIC shown in full so the admin can compare it to the uploaded MyKad at verify time.
    nric = serializers.CharField(source='profile.nric', read_only=True)
    nric_verified = serializers.BooleanField(source='profile.nric_verified', read_only=True)
    # Request #31: the place of birth the IC states, re-checked against the intake's CURRENT rule
    # on every load (`birth_state.for_cockpit`). Admin-only.
    birth_state = serializers.SerializerMethodField()
    has_file = serializers.SerializerMethodField()   # maintenance S2: the cockpit's "Open scholar file"
    maintenance_controls = serializers.SerializerMethodField()   # S3 review M1 — see the getter
    # Academic + financial data is read live from the canonical profile.
    # The qualification we hold RESULTS for, not the one declared at sign-up — see
    # `held_qualification`. A Form Six student holds SPM results and reads SPM.
    qualification = serializers.SerializerMethodField()
    stpm_pngk = serializers.FloatField(source='profile.stpm_pngk', read_only=True)   # CGPA sprint C2
    overall_cgpa = serializers.SerializerMethodField()    # S2a: tertiary CGPA; None for SPM
    household_income = serializers.IntegerField(source='profile.household_income', read_only=True)
    household_size = serializers.IntegerField(source='profile.household_size', read_only=True)
    receives_str = serializers.BooleanField(source='profile.receives_str', read_only=True)
    receives_jkm = serializers.BooleanField(source='profile.receives_jkm', read_only=True)
    # Profile-stored address (S14) — surfaced so the admin Vision card can show
    # it alongside `vision_address` (the MyKad-read address) for eyeball compare.
    address = serializers.CharField(source='profile.address', read_only=True, allow_blank=True)
    # Complete-profile view — the remaining profile-sourced fields the student
    # entered at /apply (contact, family, academic detail). All read-only mirrors.
    postal_code = serializers.CharField(source='profile.postal_code', read_only=True, allow_blank=True)
    city = serializers.CharField(source='profile.city', read_only=True, allow_blank=True)
    preferred_state = serializers.CharField(source='profile.preferred_state', read_only=True, allow_blank=True)
    contact_phone = serializers.CharField(source='profile.contact_phone', read_only=True, allow_blank=True)
    contact_email = serializers.CharField(source='profile.contact_email', read_only=True, allow_blank=True)
    preferred_call_language = serializers.CharField(source='profile.preferred_call_language', read_only=True, allow_blank=True)
    referral_source = serializers.CharField(source='referral_code', read_only=True)   # this application's
    guardians = serializers.JSONField(source='profile.guardians', read_only=True)
    # Request #26: the parent phone is the student's own, and no consenting call has cleared THIS
    # number (`parent_call.needs_parent_call` — derived live, never stored). The cockpit asks for a call.
    guardian_needs_call = serializers.SerializerMethodField()
    # Academic detail (rendered SPM/STPM-aware on the admin page).
    muet_band = serializers.IntegerField(source='profile.muet_band', read_only=True)
    coq_score = serializers.FloatField(source='profile.coq_score', read_only=True)
    grades = serializers.JSONField(source='profile.grades', read_only=True)
    stpm_grades = serializers.JSONField(source='profile.stpm_grades', read_only=True)
    higher_cgpa = serializers.FloatField(source='profile.higher_cgpa', read_only=True)
    higher_koko = serializers.FloatField(source='profile.higher_koko', read_only=True)
    higher_institution_type = serializers.CharField(source='profile.higher_institution_type',
                                                    read_only=True)
    spm_prereq_grades = serializers.JSONField(source='profile.spm_prereq_grades', read_only=True)
    spm_a_count = serializers.SerializerMethodField()
    merit_score = serializers.SerializerMethodField()
    verified_email = serializers.SerializerMethodField()
    funding_need = serializers.SerializerMethodField()
    sponsor_profile = serializers.SerializerMethodField()
    # Pre-interview deterministic flag list (S16 Phase A). Each entry is
    # {code, params}; the frontend resolves human copy from its i18n bundle.
    anomalies = serializers.SerializerMethodField()
    interview_agenda = serializers.SerializerMethodField()   # V3 (#9): folded Check-3 agenda
    verdict = serializers.SerializerMethodField()
    submission_review = serializers.SerializerMethodField()
    query_sla = serializers.SerializerMethodField()
    funding_estimate = serializers.SerializerMethodField()
    resolution_items = serializers.SerializerMethodField()
    # Request #40: may a reviewer raise a query / request a document right now? 'open' |
    # 'documents_step' | 'closed' — served from the endpoint's own predicate so the cockpit does
    # not offer a form the server will refuse (see services.officer_requests_state).
    officer_requests = serializers.SerializerMethodField()
    completeness = serializers.SerializerMethodField()
    consent_blockers = serializers.SerializerMethodField()
    # The "you haven't submitted yet" nudge state (drives the Blockers-box reminder button):
    # applicable / sent_at / available / available_at. Server-computed — the FE only renders it.
    nudge = serializers.SerializerMethodField()
    interview_session = serializers.SerializerMethodField()
    # Phase B: Gemini interview gaps — a PLAIN read-only field (the GET never calls
    # Gemini; gaps are produced + stored by the admin-on-demand suggest-gaps endpoint).
    interview_gaps = serializers.JSONField(read_only=True)
    interview_gaps_run_at = serializers.DateTimeField(read_only=True)
    # Interview scheduling: booking state + proposed slots (dark behind the flag).
    interview_schedule = serializers.SerializerMethodField()
    # The reviewer's full NAME for the audit lines (verified_by / verdict_decided_by /
    # rejected_by store an email; the cockpit shows the name, falling back to email).
    verified_by_name = serializers.SerializerMethodField()
    verdict_decided_by_name = serializers.SerializerMethodField()
    recommended_by_name = serializers.SerializerMethodField()
    # The QC floor override. Written since the V5 gate shipped and, until now, exposed NOWHERE —
    # not on this payload, not in the web app. The endpoint's own comment says "the override
    # leaves a trail", and it left one in the table rather than on any trail a person walks.
    # A reason nobody can read provides no accountability, which is the entire point of
    # demanding one before a red fact can be accepted.
    qc_override_by_name = serializers.SerializerMethodField()
    rejected_by_name = serializers.SerializerMethodField()
    assigned_to_id = serializers.IntegerField(source='assigned_to.id', read_only=True, default=None)
    assigned_to_name = serializers.CharField(source='assigned_to.name', read_only=True, default=None)
    # Internal-only correction tally for the assigned reviewer (reopened decisions that
    # led to a real change). Shown in the assign panel; never on a sponsor/student surface.
    assigned_to_corrections = serializers.SerializerMethodField()
    # Decision-reopen state: when set, the decision panel is editable + the reviewer
    # dropdown unlocks + a "held from sponsors" banner shows. The open reason drives the banner.
    decision_reopen_reason = serializers.SerializerMethodField()
    # The most recent reopen (open OR closed) as a compact record for the decision-history
    # trail on a decided case: who reopened, the reviewer it's attributed to (the original
    # recommender), the reason, and when. None when the case was never reopened. This is what
    # lets a rejected card read "recommended by X → reopened by Y (reason) → declined by Z"
    # instead of hiding the reviewer's recommendation behind a lone "Declined by …" line.
    last_decision_reopen = serializers.SerializerMethodField()
    # Whether the (dark-by-default) Conditional Bursary Agreement feature is live — the cockpit
    # only renders the agreement panel when this is on (otherwise its signing flow doesn't exist).
    bursary_agreement_enabled = serializers.SerializerMethodField()
    # TD-144: the real loaded agreement (signature timestamps + derived status + signed PDF
    # URL) so the cockpit panel shows ACCURATE four-party ticks instead of an optimistic
    # default. None when the flag is off or no agreement exists yet. No donor field.
    bursary_agreement = serializers.SerializerMethodField()
    # Post-award S4: the money-out tranche ledger (admin-facing; no sponsor identity).
    disbursements = serializers.SerializerMethodField()
    # Payments module (P2): the Vircle account ID (display; edited via the detail PATCH,
    # gated to super/org_admin), the paid-to-date (SUM of released disbursements), and the
    # paid-ahead credit — all read-only here.
    vircle_id = serializers.CharField(read_only=True)
    payment_credit = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    paid_to_date = serializers.SerializerMethodField()
    # Standardised bursary (2026-06-29; by-type-only 2026-07-04): the pathway-derived amount the
    # cockpit shows + auto-applies on approve — always the STANDARD figure for the pathway type
    # (RM2k/3k/1k), never null now. award_amount is the persisted value. award_disqualifier still
    # names any confident marker (offer_not_official / income_above_b40_line) so the cockpit can
    # show it as a red fact — it no longer zeroes the amount (see award.py).
    proposed_award_amount = serializers.SerializerMethodField()
    award_disqualifier = serializers.SerializerMethodField()
    # Cockpit "verified value" reconciliation (2026-07-15) for the field-level ticks: does the
    # DOCUMENT-derived household income / itemised roster corroborate the student's stated income
    # and size? Non-mutating — a mismatch is flagged for the reviewer, never auto-applied.
    household_check = serializers.SerializerMethodField()
    # TD-262 chunks 2+3: the per-earner "has this earner's income been SHOWN?" answer, one entry
    # per roster member code. SERVED, NOT MIRRORED — the cockpit's income panel used to decide
    # evidence from document PRESENCE and so disagreed with the submission gate about the same
    # household (W2/W3/W4). Additive: a build that predates it falls back to that old reading.
    income_shown = serializers.SerializerMethodField()
    # Read-time institution fill for a multi-campus POLY diploma (see get_chosen_programme).
    chosen_programme = serializers.SerializerMethodField()
    # The display split {title, stream}: a degree+specialisation pathway (PISMP) shows the CONSTANT
    # degree as the programme + the bidang on its own Stream/Bidang row; STPM/Matric carry the track;
    # else stream is ''. One backend home (card_display.programme_split) so the cockpit just renders.
    chosen_programme_display = serializers.SerializerMethodField()
    # TD-280: the Malay pre-U track label the cockpit renders, SERVED rather than computed in the
    # browser out of a whole Malay catalogue. The model property holds the reasoning.
    pre_u_track_label = serializers.ReadOnlyField()
    documents = AdminApplicantDocumentSerializer(many=True, read_only=True)
    referees = RefereeSerializer(many=True, read_only=True)
    consents = ConsentSerializer(many=True, read_only=True)
    # Go-live transition (T2): THIS application's source (sources Sprint C — never the referral
    # partner) and the witness-org OVERRIDE. The cockpit shows the witness dropdown for a
    # SOURCELESS application so an org_admin can assign one. Each is {id, code, name} or null.
    # (The old `referred_by_org` key for the same value was served one release; Sprint D removed it.)
    source = serializers.SerializerMethodField()
    witness_org = serializers.SerializerMethodField()

    class Meta:
        model = ScholarshipApplication
        fields = [
            'id', 'name', 'school', 'nric', 'nric_verified', 'profile_id', 'qualification',
            'spm_a_count', 'merit_score', 'stpm_pngk', 'overall_cgpa', 'household_income',
            'household_size',
            'receives_str', 'receives_jkm', 'intended_pathway', 'intends_tertiary_2026',
            'aspirations', 'plans', 'fears', 'justification',
            'address', 'postal_code', 'city', 'preferred_state', 'birth_state',
            'contact_phone', 'contact_email', 'notify_email', 'verified_email', 'preferred_call_language', 'referral_source', 'guardians', 'guardian_needs_call',
            'source', 'witness_org',
            # Academic detail (FE renders SPM vs STPM by qualification)
            'muet_band', 'coq_score', 'grades', 'stpm_grades', 'spm_prereq_grades',
            # Third results route S2a: the raw CGPA / co-curriculum as entered + D5's answer
            'higher_cgpa', 'higher_koko', 'higher_institution_type',
            # "Your story" narrative (S2) + support + declaration
            'first_in_family', 'parents_occupation', 'siblings_studying_count',
            # P2 (Check 2): the school/tertiary split (cockpit shows the burden breakdown)
            'siblings_in_school', 'siblings_in_tertiary',
            # Structured family roster (redesign 2026-06) — the cockpit Family card
            # shows father/mother name + profession + the member pool.
            'father_name', 'father_occupation', 'father_occupation_other',
            'mother_name', 'mother_occupation', 'mother_occupation_other',
            'other_family_members',
            'family_context', 'daily_life', 'consent_to_contact',
            'declaration_name', 'declared_at',
            'status', 'bucket', 'shortlist_reason', 'submitted_at',
            # Phase E3: admin-set award amount (gates fundability; shown on the pool card)
            'award_amount',
            # Standardised assistance (2026-06-29): pathway-derived proposed amount + the
            # confident-disqualifier code (null = none; drives the cockpit "no amount" reason).
            'proposed_award_amount', 'award_disqualifier',
            # Rejection bucket (merit/need/ineligible/interview/contractual/incomplete) + stamps.
            # rejection_comments = the org-admin's verbatim reason ('incomplete' only). ADMIN
            # SERIALIZER ONLY — it must never reach the student-facing ApplicationReadSerializer.
            'rejection_category', 'rejected_at', 'rejected_by', 'rejected_by_name',
            'rejection_comments',
            # Closure bucket (post-award lifecycle): graduated/completed/withdrawn/lapsed/terminated
            'closure_reason', 'closed_at', 'closed_by',
            # Lifecycle transition stamps — the DATE first reached each milestone; drive the
            # cockpit header timeline (Submitted·Recommended·Awarded → Awarded·Active·Maintenance).
            'recommended_at', 'recommended_by', 'recommended_by_name',
            'awarded_at', 'active_at', 'maintenance_at',
            # The QC floor override — who accepted a case over a RED fact, when, and why.
            'qc_override_by', 'qc_override_by_name', 'qc_override_at', 'qc_override_reason',
            # S5: operational maintenance sub-state (on_track/probation/on_hold/ready_to_close)
            'maintenance_substate', 'has_file', 'maintenance_controls',
            # Cool-off (#13/#14): a scheduled-but-unrevealed decline / award confirmation +
            # its reveal date — drives the cockpit "scheduled — cancel/hold" banners.
            'pending_rejection_category', 'decline_due_at', 'award_due_at',
            # Phase C handoff + interview funnel
            'profile_completed_at', 'completeness', 'consent_blockers', 'nudge', 'interview_session',
            'interview_gaps', 'interview_gaps_run_at', 'interview_schedule',
            'assigned_to_id', 'assigned_to_name', 'assigned_at',
            'info_request_note', 'info_requested_at',
            # S11a verify-&-accept + mentoring
            'mentoring_candidate', 'verified_at', 'verified_by', 'verified_by_name', 'verify_checklist',
            # S10 plans/support intake (surface for the admin review)
            'pathways_considered', 'top_choices', 'upu_status', 'field_of_study',
            'other_scholarships', 'other_scholarships_text', 'help_university',
            'help_scholarship', 'anything_else',
            # Plans redesign — surface the structured pathway plan for admin/coordinator
            'pathway_certainty', 'chosen_pathway', 'pre_u_track', 'pre_u_track_label',
            'pre_u_institution',
            'chosen_programme', 'chosen_programme_display', 'uncertainty_reasons', 'uncertainty_note',
            # NB chosen_programme is a SerializerMethodField (get_chosen_programme) — fills a
            # blank POLY-diploma institution live from the offer (see the method).
            # S3: normalised (sortable) offer reporting date.
            'reporting_date',
            # Income wizard answers — drive the cockpit's route-aware income document panel.
            'income_route', 'income_earner', 'income_working_members',
            'household_check', 'income_shown',
            'funding_need', 'documents', 'referees', 'consents', 'sponsor_profile',
            'anomalies',
            'interview_agenda',
            'verdict', 'results_change_notes',   # S3b: results changed after submit (D13)
            'submission_review',
            'query_sla',
            'funding_estimate',
            'resolution_items',
            'officer_requests',
            'intake_snapshot',
            # S5 verdict audit / override capture (read-only; written via record-verdict).
            'ai_verdict_snapshot', 'officer_verdict', 'verdict_reason',
            'verdict_decided_by', 'verdict_decided_at', 'verdict_decided_by_name',
            # Decision-reopen (reverse a recorded decision) state + assigned-reviewer corrections.
            'decision_reopened_at', 'decision_reopen_reason', 'last_decision_reopen',
            'assigned_to_corrections', 'bursary_agreement_enabled', 'bursary_agreement',
            # Post-award S4: the disbursement/tranche ledger (cockpit money-out panel).
            'disbursements',
            # Payments module (P2): Vircle account ID + paid-to-date + paid-ahead credit.
            'vircle_id', 'payment_credit', 'paid_to_date',
            # S-ASSIGN: WHICH GIFT this case belongs to. The assignee picker needs it to grey a
            # reviewer scoped to a different gift. `programme` is denormalised on the model and
            # SET ONCE at save, so this is a plain column read, not a derivation.
            #
            # ⚠ IT IS NOT A FENCE and adding it does not make one. The org fence is
            # `_org_scoped`; this narrows an OFFER in a dropdown. A blank on either side falls
            # open (see `officerCockpit.assignOptions`).
            'programme_id',
        ]

    #: Cockpit consolidation: anomalies that already have an authoritative home
    #: elsewhere (the verdict tile + the identity caveat) are NOT also surfaced as
    #: pre-interview flags, so the merged "Outstanding" panel never double-asks.
    _DEDUPED_ANOMALIES = frozenset({'vision_nric_mismatch', 'vision_name_mismatch'})
