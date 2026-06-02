# Reviewer Role + Scoped Access — Implementation Plan

**Status:** PLANNED — **not started.** Written 2026-06-02 after a critical
evaluation (workflow `advise-reviewer-assignment-access`) + design discussion.
Pick this up as its **own sprint, AFTER the cockpit-polish deploy.** Backend-first
(this is a security/access feature, not a UI tweak).

> A restricted **reviewer** (interviewer) signs in and sees only the students
> assigned to them and only the menus they need — and that boundary is **enforced
> on the server**, never just hidden in the browser.

---

## 1. Role taxonomy (settled)

Three roles on `PartnerAdmin` (the model already has `ROLE_CHOICES =
super | reviewer | viewer`):

| Role | Who | Can |
|---|---|---|
| **super** | the owner (currently the sole user — superadmin **and** coordinator in one) | Everything: assign reviewers, invite admins, all menus, all students, verify-&-accept, reject. |
| **reviewer** | a partner interviewer | **Only their assigned students.** Menus: **B40 Applications + Profile only.** Opens the cockpit, runs/records the interview, records the verdict (audits the AI), can request info / raise resolution tickets — **on their assigned students only.** Cannot assign, cannot see Students/Sponsors/Invite/Dashboard, cannot see unassigned or other reviewers' students. |
| **viewer** | read-only observer | Read-only (unchanged). |

- **Coordinator is NOT a separate role yet** — `super` is coordinator+admin
  combined. Split `coordinator` out from `super` later when there is staff.
- **Individual vs organisation** is already modelled (every admin belongs to an
  organisation via the Invite page's "Existing / New Organisation"); an individual
  is a one-person org. No change needed now.

### ⚠️ Semantic change to guard (do this FIRST)
Today the code's **`reviewer` is the powerful workhorse** — every write endpoint
gates on `has_role(admin, 'reviewer')`, so a `reviewer` can currently assign,
verify-&-accept, reject, and act on **every** application. This plan **restricts**
`reviewer`. Before flipping the semantics, **audit existing `PartnerAdmin.role`
values** (esp. the two "Concerned UM Indian Graduates" admins) so nobody who needs
coordinator powers is silently demoted. `super` (the owner) is unaffected.

---

## 2. The non-negotiable: enforce on the server, not the screen

The mapping found the current gap: **the B40 list endpoint returns EVERY
application to every admin; the "assigned to me" filter is frontend-only** (rows are
hidden *after* the server already sent them). So scoping by hiding menus/columns/rows
in React is **not** access control. Every "a reviewer can't see X" below must be a
server `WHERE` clause or a role check, or it is bypassable by hitting the API directly.

---

## 3. Scope

### Backend (the real work — ~1–1.5 days incl. tests)
1. **List scoping** — `AdminApplicationListView.get`: if the caller's effective role
   is `reviewer`, force `qs = qs.filter(assigned_to=admin)` on the server and
   **ignore/override** the `?assigned` param (they can't widen it). super/viewer keep
   the full (org-scoped) view.
2. **Detail + interview scoping** — `AdminApplicationDetailView.get` and the interview
   GETs currently require only `is_admin`. A `reviewer` must get **403/404** on a
   student not assigned to them (else they change the id in the URL and see anyone).
3. **Assign = super-only** — tighten the assign action (`AdminApplicationDetailView.patch`
   `assigned_to`) from `has_role('reviewer')` to **super-only**. (Reviewers never
   assign — decision #5.)
4. **Per-action split on a reviewer's OWN assigned students** (confirm in §5):
   reviewer **keeps** interview capture + `record-verdict` + request-info / resolution
   raise; **verify-&-accept** and **reject** become **super-only** (the final award
   decision is the coordinator's).
5. **Menu endpoints** — the endpoints behind Students / Sponsors / Invite / Dashboard
   must deny `reviewer` (not just hide the nav link).
6. **Tests** — prove a `reviewer` gets an empty/filtered list, a 403/404 on someone
   else's application via a direct API call, and a 403 on assign / verify-accept /
   reject / invite / sponsors. (Security is only real if a test proves the API blocks it.)

### Frontend (small — ~0.5 day)
1. **Nav menu by role** — `reviewer` sees only **B40 Applications + Profile** (gate the
   other links on the role already in `useAdminAuth` / `/admin/role`).
2. **List columns role-conditional** — move **Assigned** to the **rightmost** column;
   `reviewer` sees columns **up to Submitted only** (Name · Qualification · Status ·
   Bucket · Submitted); super sees Assigned too. *(This is the real meaning of the
   earlier "swap Submitted ↔ Assigned".)*
3. **Cockpit Assign box = super-only** — hide the "Assign a reviewer" dropdown from
   reviewers entirely (decision #3); they just open their student and review.
4. The reviewer's list is driven by the **scoped backend** (step B1) — the FE simply
   renders what the server returns.

### Invite page (minor)
- Add a **role selector** (super / reviewer / viewer) when inviting a partner admin
  (today the Invite flow sets org + name + email; role defaults). Individual-vs-org is
  already handled.

---

## 4. Deferred (future — note, don't build)
Flagged by the user as scale-dependent ("very few students now"):
- **Granular permission ticks** — the per-feature checkbox matrix. The right *eventual*
  direction (roles become presets; a custom person gets ticks), but overkill at 3–5
  users. Revisit when named roles stop fitting.
- **Auto-assignment** — round-robin/rotation assignment of unassigned students.
- **Stale-case reassignment** — a case unattended for ~2 weeks auto-reassigns to
  another reviewer to close, with **internal demerit points** to the original reviewer.
- **Assignment audit trail** — who reassigned whom and when (`assigned_changed_by/at`).
  Expected eventually for a PII + money process; not now.

---

## 5. Open decisions (small — settle at sprint start)
1. **Per-action split:** does a `reviewer` do **verify-&-accept** and **reject** on
   their assigned students, or are those **super-only** (reviewer only interviews +
   records the verdict)? *(Lean: super-only — the final award decision is the
   coordinator's; the reviewer's output is the interview + verdict audit.)*
2. **Existing-admin audit:** confirm the current `role` of every `PartnerAdmin` before
   flipping `reviewer` semantics (so nobody is silently demoted).
3. **Viewer scope:** does `viewer` keep seeing *all* applications (read-only), or also
   get scoped? *(Lean: viewer stays org-wide read-only — it's an oversight role.)*

---

## 6. Effort & sequence
- **Backend-first**, ~1–1.5 days + tests; frontend ~0.5 day. The trap to avoid:
  doing only the frontend half and believing the boundary is secured.
- **Sequence:** (1) cockpit polish (issues 1 + 2) ships in the pending 2nd deploy;
  (2) **this** is the next sprint after that. The trivial column-move can ride with
  either, but the **scoping must not be half-shipped**.
- Related queued front-end work (independent): `application-review-and-referee-plan.md`.
