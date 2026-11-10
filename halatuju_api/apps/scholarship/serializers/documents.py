"""Applicant-document serializers: read, sign-upload, create and the Action Centre resolution items."""

from rest_framework import serializers
from ..models import ApplicantDocument, ResolutionItem


# ── Documents / referee / consent (Sprint 5a) ────────────────────────────

class ApplicantDocumentSerializer(serializers.ModelSerializer):
    download_url = serializers.SerializerMethodField()
    # S13: server-computed match verdicts (so client doesn't reimplement matchers).
    vision_nric_verdict = serializers.SerializerMethodField()
    vision_name_verdict = serializers.SerializerMethodField()
    # Genuineness fingerprint (verification-assurance): {status, reason, doc_seen} — soft,
    # flag-gated. status ∈ canonical genuine / suspect / not_<type>. Null if it didn't run.
    authenticity = serializers.SerializerMethodField()
    # Check-1 Academic: the results slip's three clinical checks (name/subjects/results) vs the
    # student's own profile; S3b: the higher-results check (`higher_results`). Null otherwise.
    academic_check = serializers.SerializerMethodField()
    higher_check = serializers.SerializerMethodField()
    # Check-1 Pathway: the offer-letter facts (name + IC + data points) — null unless offer_letter.
    pathway_check = serializers.SerializerMethodField()
    # Check-1 Income: the earner-IC relationship facts (parent_ic); a member-tagged slip / EPF vs the IC.
    income_ic_check = serializers.SerializerMethodField()
    income_proof_check = serializers.SerializerMethodField()
    # Check-1 Income: the STR document — recipient vs the earner IC + currency.
    str_check = serializers.SerializerMethodField()
    # Check-1 Income: a utility bill — address (vs home) + monthly bill + unpaid balance.
    utility_check = serializers.SerializerMethodField()
    # Check-1 Income: relationship proof — birth certificate / guardianship letter.
    bc_check = serializers.SerializerMethodField()
    guardianship_check = serializers.SerializerMethodField()
    # V1: the declared-income supporting doc — whether it READ (officer chip).
    support_doc_check = serializers.SerializerMethodField()
    # Academic: a post-SPM semester-result slip — name/NRIC (vs the student) + CGPA. Null otherwise.
    semester_check = serializers.SerializerMethodField()
    # Academic: a school-leaving cert — school + name/NRIC (vs the student) + kelakuan + activities.
    school_leaving_check = serializers.SerializerMethodField()
    # Officer box: whose income doc this is — its tag, else resolved by the name on it. Display-only.
    resolved_member = serializers.SerializerMethodField()

    class Meta:
        model = ApplicantDocument
        fields = [
            'id', 'doc_type', 'household_member', 'original_filename', 'content_type', 'size',
            'verification_status', 'uploaded_at', 'download_url', 'results_kind',
            # S13: Vision OCR soft-signal fields (IC only); post-S14 vision_address (admin, no matcher).
            'vision_nric', 'vision_name', 'vision_address',
            'vision_run_at', 'vision_error',
            'vision_nric_verdict', 'vision_name_verdict', 'authenticity',
            # Supporting-doc soft checks (name/address presence). Stored at upload.
            'vision_name_match', 'vision_address_match',
            # Document-assist: Gemini-extracted fields + student verdict (stored).
            'vision_fields', 'vision_fields_run_at',
            # Check-1 Academic: results-slip 3-check; third route S3b: the higher-results check.
            'academic_check', 'higher_check',
            # Check-1 Pathway: offer-letter facts (null unless doc_type=offer_letter).
            'pathway_check',
            # Check-1 Income: earner-IC relationship facts (null unless doc_type=parent_ic).
            'income_ic_check',
            # Check-1 Income: salary slip / EPF vs the member's IC (null otherwise).
            'income_proof_check',
            # Check-1 Income: STR recipient vs the earner IC + currency (null otherwise).
            'str_check',
            # Check-1 Income: utility bill — address + monthly bill + unpaid balance.
            'utility_check',
            # Check-1 Income: relationship proof checklists (BC / guardianship letter).
            'bc_check', 'guardianship_check',
            # V1: declared-income supporting doc read-status (null unless income_support_doc).
            'support_doc_check',
            # Academic: semester-result name/NRIC/CGPA (null unless semester_result).
            'semester_check',
            # Academic: school-leaving cert school/name/NRIC/kelakuan/activities (null otherwise).
            'school_leaving_check',
            # Officer box: resolved household member (stored tag or name-resolved). Display-only.
            'resolved_member',
            # Phase 2 version history: when this doc was replaced (null = live) + which
            # doc replaced it. The admin path returns superseded rows to show history;
            # the student GET filters them out.
            'superseded_at', 'superseded_by',
        ]
        read_only_fields = [
            'vision_nric', 'vision_name', 'vision_address',
            'vision_run_at', 'vision_error',
            'vision_name_match', 'vision_address_match',
            'vision_fields', 'vision_fields_run_at',
            'superseded_at', 'superseded_by',
        ]

    def get_download_url(self, obj):
        from ..storage import create_signed_download_url, resolve_org_for_path
        # org-fence (Sprint 4, belt-and-braces): refuse to sign a doc whose key-org
        # disagrees with its application's org. The real fence is upstream (student
        # sees own docs; admin reads are org-scoped) — this catches a mis-keyed blob.
        app = getattr(obj, 'application', None)
        path_org = resolve_org_for_path(obj.storage_path)
        if path_org is not None and app is not None and path_org != app.owning_organisation_id:
            return None
        return create_signed_download_url(obj.storage_path)

    def get_vision_nric_verdict(self, obj):
        """'match' / 'mismatch' / 'unreadable' — soft signal. Empty when Vision hasn't run."""
        if obj.doc_type != 'ic' or obj.vision_run_at is None:
            return ''
        from ..read_errors import ic_second_opinion_deferred
        from ..vision import nric_match
        v = ('unreadable' if obj.vision_error or not obj.vision_nric else 'match'
             if nric_match(obj.vision_nric, getattr(obj.application.profile, 'nric', '') or '') else 'mismatch')
        # TD-390: a read our outage left half-done shows as not-yet-read, never a red chip.
        return '' if v != 'match' and ic_second_opinion_deferred(obj) else v

    def get_vision_name_verdict(self, obj):
        """'match' / 'partial' / 'mismatch' / 'unreadable' — soft signal. Empty when Vision hasn't run."""
        if obj.doc_type != 'ic' or obj.vision_run_at is None:
            return ''
        from ..read_errors import ic_second_opinion_deferred
        from ..vision import name_match
        v = ('unreadable' if obj.vision_error or not obj.vision_name
             else name_match(obj.vision_name, getattr(obj.application.profile, 'name', '') or ''))
        return '' if v in ('unreadable', 'mismatch') and ic_second_opinion_deferred(obj) else v   # TD-390

    def get_authenticity(self, obj):
        """Genuineness fingerprint summary {status, reason, doc_seen} — soft, flag-gated.
        IC/parent_ic (Sprint 1) + the standardised supporting docs (Sprint 2: STR, results
        slip, birth cert, EPF). Null when the check didn't run (flag off / AI outage)."""
        if obj.doc_type not in ('ic', 'parent_ic', 'str', 'results_slip', 'birth_certificate', 'epf',
                                'offer_letter', 'salary_slip', 'electricity_bill', 'water_bill',
                                'school_leaving_cert', 'higher_results'):   # + STPM exact-read S3
            return None
        vf = obj.vision_fields if isinstance(obj.vision_fields, dict) else {}
        auth = vf.get('authenticity')
        if not isinstance(auth, dict) or not auth.get('status'):
            return None
        from ..genuineness.bands import shown_status
        # Expose the CANONICAL outcome (genuine / suspect / not_<type>), folding any legacy
        # stored value, so the FE renders one consistent vocabulary across all document types.
        status = shown_status(auth.get('status'), obj.doc_type, auth.get('doc_seen', ''))   # + M4b final_owed
        # Salary slip (MODEL_VERSION 1.0.0): surface ONLY the WRONG-TYPE reject (not_salary — a MyKad
        # or other document in the salary-slip slot, #47) → the red "wrong document" chip. The informal
        # 'suspect' band (a genuine but weakly-verifiable slip, common for real B40 families) would be
        # amber noise, so a genuine/suspect slip renders normally (no chip). Mirrors how a genuine EPF
        # shows nothing while a not_epf shows the wrong-type chip.
        if obj.doc_type == 'salary_slip' and not status.startswith('not_'):
            return None
        # Electricity bill (MODEL_VERSION 1.0.0): same — surface ONLY the wrong-type reject
        # (not_electricity_bill: a MyKad / water bill / junk in the electricity slot) → the red chip.
        # The 'suspect' band is a thin/cropped-but-genuine bill (common), so hide it as amber noise;
        # a genuine/suspect bill renders normally.
        if obj.doc_type == 'electricity_bill' and not status.startswith('not_'):
            return None
        # Water bill (MODEL_VERSION 1.0.0): same — surface ONLY the wrong-type reject (not_water_bill:
        # a MyKad / an ELECTRICITY bill / junk in the water slot) → the red chip. The 'suspect' band is
        # a thin/cropped-but-genuine bill (common for real B40 families), so hide it as amber noise; a
        # genuine/suspect bill renders normally. Closes the swap symmetrically with electricity_bill.
        if obj.doc_type == 'water_bill' and not status.startswith('not_'):
            return None
        # School-leaving cert (MODEL_VERSION 1.0.0): surface ONLY the wrong-type reject
        # (not_school_leaving_cert: a MyKad / results slip / another document in the slot) → the red
        # chip. A 'suspect' (thin/cropped) OR 'unrecognised' (a free-form testimonial we can't
        # structurally confirm — folded to 'suspect' by canonical_status) is a real B40 leaver doc, so
        # hide it as amber noise; a genuine/suspect cert renders normally (never a false reject).
        if obj.doc_type == 'school_leaving_cert' and not status.startswith('not_'):
            return None
        return None if not status else {'status': status,   # NOT CHECKED (1.8.0) reads as unscored
                                        'reason': auth.get('reason', ''), 'doc_seen': auth.get('doc_seen', '')}

    def get_academic_check(self, obj):
        """{name, subjects, results, candidate_name, missing, mismatched, slip_count} for a results
        slip — the three clinical checks against the student's own profile. Null otherwise."""
        if obj.doc_type != 'results_slip':
            return None
        from ..academic_engine import student_slip_check
        return student_slip_check(obj)

    def get_higher_check(self, obj):
        if obj.doc_type != 'higher_results':          # S3b: `higher_results.student_higher_check`
            return None
        from ..higher_results import student_higher_check
        return student_higher_check(obj)

    def get_pathway_check(self, obj):
        """{name, ic, + data points} for an offer letter — the clinical facts against
        the student's own profile, plus ``switched_from`` on the LIVE offer when it replaced a
        genuinely different prior offer (the course-switch note). Null for every other doc type."""
        if obj.doc_type != 'offer_letter':
            return None
        from ..pathway_engine import student_offer_check, offer_pathway_switch
        chk = student_offer_check(obj)
        sw = offer_pathway_switch(obj.application) if getattr(obj, 'superseded_at', None) is None else None
        chk['switched_from'] = ({'programme': sw['from_programme'], 'institution': sw['from_institution']}
                                if sw else None)
        return chk

    def get_income_ic_check(self, obj):
        """{nric, name, address, member, name_status, readable} for an income earner's
        IC (parent_ic) — the OCR'd values + the RELATIONSHIP verdict (the earner's IC
        links to the student's family via patronymic / birth cert / letter), NOT an
        identity match against the student. Null for every other doc type."""
        if obj.doc_type != 'parent_ic':
            return None
        from ..income_engine import student_income_ic_check, income_cluster_advice
        chk = student_income_ic_check(obj)
        if chk:
            # The CLUSTER verdict (relationship + coherence across this member's income
            # docs) drives the single per-member coach anchored on the IC.
            chk['cluster_status'] = (income_cluster_advice(obj.application, chk['member'])
                                     if chk['member'] else '')
        return chk

    def get_income_proof_check(self, obj):
        """{name, nric, amount, period, member, name_status, nric_status, ic_present}
        for a salary slip / EPF in an income context — the earner facts cross-checked
        against THAT earner's IC (salary route = the member's IC; STR route = the single
        earner's IC). Null for everything else (the check returns None with no context)."""
        if obj.doc_type not in ('salary_slip', 'epf'):
            return None
        from ..income_engine import student_income_proof_check
        return student_income_proof_check(obj)

    def get_str_check(self, obj):
        """{name, nric, status, year, member, name_status, nric_status, current_status,
        ic_present, ic_slots} for an STR document — recipient vs the household ICs, currency, and
        the ICs that would settle whose it is (TD-309). Null for every other doc type."""
        if obj.doc_type != 'str':
            return None
        from ..income_str_ownership import student_str_payload
        return student_str_payload(obj)

    def get_utility_check(self, obj):
        """{name, address, monthly_bill, unpaid_balance, address_status, current_status, bill_month,
        reasonable_status, reasonable_detail, outstanding_status, name_note} for a water /
        electricity bill — address + soft consumption/recency/arrears signals + the standardised
        'MMM YYYY' bill month, never the student's name. Null for every other doc type."""
        if obj.doc_type not in ('water_bill', 'electricity_bill'):
            return None
        from ..income_engine import utility_check
        return utility_check(obj)

    def get_bc_check(self, obj):
        """{child/mother/father names + statuses} for a birth certificate — links the
        student to their mother (the income earner). Null for other doc types."""
        if obj.doc_type != 'birth_certificate':
            return None
        from ..income_engine import student_bc_check
        return student_bc_check(obj)

    def get_guardianship_check(self, obj):
        """{guardian/ward names + statuses + doc_kind} for a guardianship letter — ties the
        guardian to the student. Null for other doc types."""
        if obj.doc_type != 'guardianship_letter':
            return None
        from ..income_engine import student_guardianship_check
        return student_guardianship_check(obj)

    def get_semester_check(self, obj):
        """{name, nric, cgpa, name_status, nric_status} for a semester-result slip — null otherwise."""
        if obj.doc_type != 'semester_result':
            return None
        from ..academic_engine import semester_check
        return semester_check(obj)

    def get_school_leaving_check(self, obj):
        """{school, name, name_status, nric, nric_status, kelakuan, activities} for a school-leaving
        certificate — the officer chips (name/NRIC vs the student) + school/conduct/leadership.
        Null for every other doc type."""
        if obj.doc_type != 'school_leaving_cert':
            return None
        from ..academic_engine import student_school_leaving_check
        return student_school_leaving_check(obj)

    def get_support_doc_check(self, obj):
        """{name/amount/issuer/kind + read_status} for a declared-income supporting doc.
        Null for other doc types. V1: the officer sees whether the declared informal income
        actually has a readable supporting document behind it."""
        if obj.doc_type != 'income_support_doc':
            return None
        from ..income_engine import student_income_support_check
        return student_income_support_check(obj)

    def get_resolved_member(self, obj):
        """The household member this income doc belongs to — stored tag, or name-resolved for a
        blank-tagged doc. '' for non-income docs / when unresolvable. The cockpit box uses it to
        place a doc under the right person even when it was uploaded without a tag."""
        from ..income_engine import resolved_member_for
        return resolved_member_for(obj.application, obj)


class SignUploadSerializer(serializers.Serializer):
    doc_type = serializers.ChoiceField(choices=[c[0] for c in ApplicantDocument.DOC_TYPES])
    filename = serializers.CharField(max_length=255, required=False, allow_blank=True)


class DocumentCreateSerializer(serializers.Serializer):
    doc_type = serializers.ChoiceField(choices=[c[0] for c in ApplicantDocument.DOC_TYPES])
    # Salary-route income docs tag the household member they belong to (so father's
    # and mother's payslips don't overwrite each other). Blank for everything else.
    household_member = serializers.ChoiceField(
        choices=[c[0] for c in ApplicantDocument.HOUSEHOLD_MEMBER_CHOICES],
        required=False, allow_blank=True, default='')
    # Set ONLY for an Action-Centre reviewer-requested upload (the officer ResolutionItem
    # code, e.g. 'officer_3') — gives each request its own document slot. Blank otherwise.
    request_code = serializers.CharField(max_length=20, required=False, allow_blank=True, default='')
    storage_path = serializers.CharField(max_length=500)
    original_filename = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')
    content_type = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    size = serializers.IntegerField(required=False, default=0)


class ResolutionItemSerializer(serializers.ModelSerializer):
    """A resolution ticket (S3). Read-only to the client; the `code` resolves to
    `admin.scholarship.verdict.item.<code>` copy on the frontend (officer items
    carry their own `prompt`)."""
    vircle_expected = serializers.SerializerMethodField()

    class Meta:
        model = ResolutionItem
        fields = [
            'id', 'fact', 'code', 'params', 'prompt', 'kind', 'doc_type',
            'status', 'source', 'resolution_text', 'created_at', 'resolved_at',
            'vircle_expected',
        ]
        read_only_fields = fields

    def get_vircle_expected(self, obj):
        """Vircle setup task only: the account type Vircle's own birth-year rule expects —
        'principal' (born 2008 or earlier) or 'child'. SERVED, not derived in the browser,
        because the rule lives in vircle.can_register (owner-confirmed against Vircle's
        1-January counting: born 31/12/2008 is 18, born 1/1/2009 is not). None elsewhere."""
        from ..resolution import VIRCLE_CODE
        if obj.code != VIRCLE_CODE:
            return None
        from ..vircle import can_register
        return 'principal' if can_register(obj.application) else 'child'
