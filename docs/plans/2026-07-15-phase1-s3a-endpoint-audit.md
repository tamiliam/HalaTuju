# Platform Sprint 3a — `_AdminBase` endpoint fence audit

**The review artefact for the #1-risk sprint.** Every class inheriting `_AdminBase`
(incl. `_BursaryAdminBase`) in `apps/scholarship/views_admin.py`, and how each is
org-fenced. The fence keys off `PartnerAdmin.owning_organisation` (never the referral
`org`). Super is global. A second reviewer should sign this off.

## The fence, in one place
- `_org_scoped(qs, admin, field=…)` — filters a queryset to the caller's org (super unchanged; `None` → `IS NULL`).
- `_org_allows(admin, app)` — row-level allow (super `True`; else `app.owning_organisation_id == admin.owning_organisation_id`).
- Wired into the shared gates: `_scoped_application` (cross-org → 404), `_can_review_app` (cross-org → deny), `_require_qc` (cross-org → 404), and the main list query.
- Cross-org reads/writes surface as **404, not 403**, so existence isn't leaked.

## Classification key
- **GATE** — routes through a now-fenced shared gate (`_scoped_application` / `_require_app_write` / `_require_qc`), or a secondary-pk fetch *after* one of those (parent already fenced).
- **LIST-FENCED** — a list/aggregate query with `_org_scoped` applied explicitly.
- **CAN-REVIEW** — fetches a secondary object then re-gates via `_can_review_app(admin, obj.application)` (now org-aware).
- **SUPER-ONLY** — global by role; no org fence needed.
- **CROSS-ORG BY DESIGN** — platform-level (sponsor/staff), documented (D-1); not applicant data.
- **GRANDFATHERED** — referral-org authorisation, orthogonal to ownership (documented).

## The 44 (+ base) endpoints

| # | Class | line | Auth path | Class |
|---|---|---|---|---|
| 1 | AdminApplicationListView | 211 | main list query + `_org_scoped` | LIST-FENCED |
| 2 | AdminApplicationDetailView | 286 | `_scoped_application` | GATE |
| 3 | AdminVerdictSummaryView | 319 | `_scoped_application` | GATE |
| 4 | AdminVerifyAcceptView | 331 | `_require_app_write` | GATE |
| 5 | AdminRejectView | 407 | `_require_app_write` | GATE |
| 6 | AdminCancelDeclineView | 432 | `_require_app_write` | GATE |
| 7 | AdminHoldAwardView | 443 | `_require_app_write` | GATE |
| 8 | AdminApplicationRefereeView | 455 | `_scoped_application` (+ Referee by application) | GATE |
| 9 | AdminRefereeDetailView | 480 | `_require_app_write` (+ Referee by application_id=pk) | GATE |
| 10 | AdminRunVisionView | 493 | `_require_app_write` (+ doc by application_id=pk) | GATE |
| 11 | AdminGenerateProfileView | 520 | `_require_app_write` | GATE |
| 12 | AdminFinaliseProfileView | 534 | `_require_app_write` | GATE |
| 13 | AdminPublishAnonProfileView | 563 | `_require_app_write` | GATE |
| 14 | AdminSuggestGapsView | 595 | `_require_app_write` | GATE |
| 15 | AdminProfileEditView | 619 | `_require_app_write` | GATE |
| 16 | AdminPublishProfileView | 635 | `_require_app_write` | GATE |
| 17 | AdminInterviewView | 720 | `_scoped_application` / `_require_app_write` | GATE |
| 18 | AdminInterviewSubmitView | 775 | `_require_app_write` | GATE |
| 19 | AdminInterviewReopenView | 797 | `_require_app_write` | GATE |
| 20 | AdminSponsorListView | 833 | Sponsor.objects.all (platform account) | CROSS-ORG BY DESIGN |
| 21 | AdminSponsorReviewView | 849 | `_require_reviewer` + Sponsor by pk (platform) | CROSS-ORG BY DESIGN |
| 22 | AdminSetAwardAmountView | 871 | `_scoped_application` | GATE |
| 23 | AdminSponsorshipListView | 916 | `_org_scoped(field='application__owning_organisation_id')` | LIST-FENCED |
| 24 | AdminDisbursementScheduleView | 933 | `_require_app_write` | GATE |
| 25 | AdminDisbursementActionView | 959 | Disbursement by pk → `_can_review_app(disb.application)` | CAN-REVIEW |
| 26 | AdminCloseApplicationView | 987 | `_require_app_write` | GATE |
| 27 | AdminMaintenanceSubstateView | 1003 | `_require_app_write` | GATE |
| 28 | AdminAssignableAdminsView | 1019 | PartnerAdmin list (staff) | CROSS-ORG BY DESIGN |
| 29 | AdminRequestInfoView | 1057 | `_require_app_write` | GATE |
| 30 | AdminResolutionItemView | 1078 | `_require_app_write` | GATE |
| 31 | AdminResolutionItemActionView | 1123 | ResolutionItem by pk → `_can_review_app(item.application)` | CAN-REVIEW |
| 32 | AdminRecordVerdictView | 1163 | `_require_app_write` | GATE |
| 33 | AdminReopenDecisionView | 1302 | `_scoped_application` (super-gated) | GATE |
| 34 | AdminQcDecisionView | 1325 | `_require_qc` | GATE |
| 35 | AdminCancelReopenView | 1404 | `_scoped_application` (super-gated) | GATE |
| 36 | AdminVerdictMetricsView | 1424 | `_org_scoped` on the aggregate query | LIST-FENCED |
| 37 | AdminAssignReviewerView | 1444 | super-only + `_scoped_application` | GATE + SUPER-ONLY |
| 38 | AdminInterviewSlotsView | 1496 | `_scoped_application` / `_require_app_write` | GATE |
| 39 | AdminInterviewSlotDetailView | 1538 | `_require_app_write` (+ slot by application=app) | GATE |
| 40 | ReviewerProfileView | 1558 | `_require_reviewer` — caller's OWN profile (self-scoped, no app) | N/A |
| 41 | AdminGraduationMessageListView | 1584 | `_org_scoped(field='application__owning_organisation_id')` | LIST-FENCED |
| 42 | AdminGraduationMessageReviewView | 1608 | GraduationMessage by pk → `_org_allows(message.application)` (**closed a role-only hole**) | CAN-REVIEW |
| 43 | _BursaryAdminBase | 1649 | shared `_agreement(pk)` lookup (base) | (base) |
| 44 | AdminBursaryCountersignView | 1658 | SUPER-ONLY (Foundation counterparty) | SUPER-ONLY |
| 45 | AdminBursaryWitnessView | 1678 | referral-org (`admin.org == referred_by_org`) — non-blocking, dark | GRANDFATHERED |

## Findings
- **All applicant-data surfaces are fenced.** Every endpoint that reads or writes an application (or a child object reachable from one) now passes through a gate that checks `owning_organisation`, is a `_org_scoped` list, or is super-only.
- **One hole closed beyond the plan's three:** `AdminGraduationMessageReviewView` (write) fetched by pk with only a role check → a cross-org reviewer could review another org's message. Now `_org_allows`-gated (404). The plan's three bypass *list* surfaces (Sponsorship, VerdictMetrics, Graduation list) are fenced as specified.
- **Deliberately unfenced (documented):** `AdminSponsorListView`, `AdminSponsorReviewView` (platform-level sponsor accounts, D-1), `AdminAssignableAdminsView` (staff list, Sprint-10 concern). None carry student identity.
- **Grandfathered:** `AdminBursaryWitnessView` uses referral-org semantics (orthogonal to ownership), dark behind `BURSARY_AGREEMENT_ENABLED`.
- **Invisible today:** BrightPath is the only org; every staff/application pair is same-org, so every fenced query returns exactly today's rows. The full suite passes with no test edits to existing tests.

## Durable protection (Sprint 3b)
The fence-proof suite + the `__subclasses__` coverage-completeness check + the `views_admin.py` static source guard run in CI, so a new endpoint that skips the fence — or a raw `ScholarshipApplication.objects` query outside the helpers — fails the build.
