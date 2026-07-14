# Partner onboarding: replace the expiring Supabase invite with a durable account + temp password

## Context

On 2026-07-10 a new reviewer (Goban Arasu) was invited from `/admin/invite`. The Supabase invite email
landed, he clicked "Accept your invitation", and was dropped on the **student homepage** with no idea
what to do. He emailed twice, was eventually told to go to `/admin/login` and use Google, and only got
in ~7 hours later. Investigating it surfaced three defects that compound:

1. **`redirect_to` never reaches Supabase.** `AdminInviteView` passes it in the JSON *body*
   (`halatuju_api/apps/courses/views_admin.py:412-422`), but GoTrue reads `redirect_to` from the
   **query string**. The key is silently dropped, GoTrue falls back to the project's Site URL, and the
   invitee lands on `https://halatuju.xyz/` instead of `/admin/set-password`. The API still returns 200.
   Confirmed by the raw link in his email (`…&type=invite&redirect_to=https://halatuju.xyz/`) and by the
   expiry bounce (`https://halatuju.xyz/#error=access_denied&error_code=otp_expired`). The Supabase
   Redirect-URLs allowlist (`https://halatuju.xyz/**`) and the invite email template
   (`{{ .ConfirmationURL }}`) were both inspected and are **correct** — ruled out. Broken since the line
   was written (`89fcad5d`, 2026-06-16); Goban is likely the first non-Google invitee to click it.
2. **The invite link expires in 24h** — Supabase's maximum for an email OTP. Miss it and the link is dead.
3. **Nobody can be re-invited.** `views_admin.py:373` 409s on an existing email, so the form can never
   target them again. Even Revoke-then-reinvite sends no email: Supabase returns `422 email_exists` for
   any address that already has an auth user, and the view treats that as the `already_registered` path
   ("access granted, no invite email needed"). So **no one who has ever been invited can be sent another
   invite link, by any route.**

**Intended outcome:** onboarding a partner stops depending on an expiring, single-use token. The account
is created server-side, we send our own email (copy we control, no expiry claim), and the invitee signs
in whenever they like — by temp password, by Google, or by Forgot-password. Re-sending becomes trivial
because the email carries no secret.

**Owner decisions (2026-07-12):** don't assume a Google account → the non-Google path must not depend on
an emailed link, so a **temporary password** is issued and forced-changed on first login; the password is
**delivered in the same automatic email** — no phone number, no WhatsApp, no manual relay step, and it is
never shown in the admin UI or returned to the browser; **English-only** email (matches every existing
reviewer/admin email). Acceptable for the reviewer population. Still Supabase auth throughout — only the
*invite email* is dropped.

## Approach

Swap the Supabase **invite** call for a Supabase **admin-create-user** call, and send our own email.
Nothing expires; no token exists anywhere.

### 1. Backend — `halatuju_api/apps/courses/views_admin.py`

**`AdminInviteView.post`** (lines 352-461). Keep the super-admin gate, the role/org validation, and the
409-on-existing-`PartnerAdmin` guard exactly as they are. Replace only the outbound call and what follows:

- Generate a temp password with `secrets` — 12-14 chars from an unambiguous alphabet (no `0/O/1/l/I`),
  hyphen-grouped so it is dictatable over the phone (e.g. `Kx7m-Pq4t-Rd92`).
- `POST {SUPABASE_URL}/auth/v1/admin/users` (service-role headers, unchanged) with
  `{'email', 'password': temp, 'email_confirm': True, 'user_metadata': {'name': name, 'must_change_password': True}}`.
  **`email_confirm: True` is load-bearing** — `PartnerAdminMixin.get_admin` (`views_admin.py:59-66`) only
  links a `PartnerAdmin` row by email when the JWT's `email_verified` claim is true. Without it they'd
  authenticate but get no role.
- **Store the returned Supabase user `id` on the new `PartnerAdmin` row** (`supabase_user_id`). Today it's
  left null until first login; capturing it now makes login hit the fast path and, more importantly, gives
  Resend a user to PUT against.
- Keep the `422 email_exists` branch (someone who already has an account — e.g. an existing student). In
  that case there is no temp password and no UID; the row is created as today and the email tells them to
  sign in with their existing credentials. Any other non-2xx stays a 502.
- **The temp password is emailed and nothing else.** It is not returned in the API response, not logged,
  not stored on `PartnerAdmin`, and never reaches the browser. The response keeps its current shape plus
  a boolean `emailed`, so the UI can say "invite email sent" or warn if the send failed.

**New `AdminResendView`** — `POST /api/v1/admin/admins/<id>/resend/`, super-admin only, registered in
`apps/courses/urls.py` beside the existing `admins/<id>/revoke/` route:
- Target has a `supabase_user_id` → rotate: `PUT {SUPABASE_URL}/auth/v1/admin/users/<uid>` with a fresh
  temp password + `user_metadata.must_change_password = True`, and re-send the same email. The new password
  goes only to the invitee; the response says whether the email went out.
- Target has no `supabase_user_id` (the `already_registered` case) → send the "use your existing login"
  email, no password.
- This is what makes the original complaint impossible to hit again: the owner presses one button, the
  person gets a fresh working password, and nothing has to be relayed by hand.

Because the send is now the only delivery channel, `send_partner_welcome_email` returning `False` matters:
surface it (`emailed: false` → a red banner telling the owner to press Resend), rather than the current
silent best-effort swallow.

### 2. Backend — `halatuju_api/apps/scholarship/emails.py`

New `send_partner_welcome_email(to_email, name, role, temp_password=None)`, English-only, following the
existing best-effort shape (`try / send_mail / return True` … `except Exception: logger.warning(exc_info=True);
return False`). Reuse `_reviewer_dashboard_cta()` (line ~1291) which already builds `{FRONTEND_URL}/admin/login`,
and sit beside `send_reviewer_assigned_email` (line 1302) — the closest precedent (English, admin-facing).

Body says plainly: you've been added to HalaTuju as a **{role}**; sign in at `{link}` with **{email}**;
either use the temporary password below (you'll be asked to change it), or "Sign in with Google", or
"Forgot password". **No expiry sentence** — there is nothing to expire. The `already_registered` variant
omits the password paragraph.

### 3. Frontend — `halatuju-web`

- **`src/lib/admin-api.ts`**: `inviteAdmin` return type gains `emailed: boolean`; new
  `resendAdminInvite(adminId, { token })` → `POST /api/v1/admin/admins/${id}/resend/` (same inline-Bearer
  shape as `revokeAdmin`, lines 183-196).
- **`src/app/admin/invite/page.tsx`**: success banner says the invite email was sent to `<email>` (and warns
  if it wasn't); **no password is ever displayed**. Admin List Action column (lines 197-214) gains a
  **Resend** button next to Revoke/Restore, which re-emails a fresh password and confirms with a toast.
- **`src/app/admin/login/page.tsx`**: in `handleLogin` (the email+password path only), if
  `data.session.user.user_metadata?.must_change_password` → `router.push('/admin/set-password')` instead of
  the role redirect at lines 70-71. Deliberately **not** applied to the Google callback
  (`admin/auth/callback/page.tsx`) — a Google signer never typed the temp password and shouldn't be forced
  to invent one.
- **`src/app/admin/set-password/page.tsx`**: after `adminUpdatePassword` succeeds, clear the flag with
  `updateUser({ data: { must_change_password: false } })`. The page already handles a normal signed-in
  session, so no other change is needed. It stays in place for the Forgot-password flow regardless.
- **i18n**: new `admin.*` keys (resend / resending / temp-password label / copy / change-password notice)
  added to all three of `src/messages/{en,ms,ta}.json`. Parity is enforced by
  `node scripts/check-i18n.js` (run from `halatuju-web`; it is not wired into `package.json`).

### What this deletes

The `redirect_to` body-vs-query bug disappears with the invite call — no separate fix needed. The Supabase
**Invite user** email template becomes unused (leave it in place; harmless). `adminResetPassword` already
sends `redirectTo` correctly via `supabase-js`, so **Forgot-password was never broken** and is untouched.

## Risks

- **Credential in an email.** The known cost of this design, accepted by the owner for the reviewer
  population. Mitigated by the forced change on first login, by the account being useless without its
  `PartnerAdmin` role row, by Resend being able to rotate the password at any moment, and by the fact that
  today's invite email already carries a login-granting token — so this is not a step down from where we are.
  The password exists in exactly one place (that email) and nowhere else in the system.
- **Google identity linking.** We create the auth user; the partner may then sign in with Google on the same
  address. Supabase auto-links on a verified email, and we have live proof: Goban's invite-created user is
  exactly what his later Google sign-in landed on. Re-verify once on a throwaway address anyway.
- **`SUPABASE_SERVICE_ROLE_KEY`** must be present on Cloud Run (it is — invites work today) but is
  **missing from the documented env list** in `halatuju_api/CLAUDE.md`. Add it while here.

## Verification

**Environment prerequisite (blocker on this machine):** the backend needs Python ≥3.10 (Django 5; prod runs
3.11 per the Dockerfile). This box has only 3.9.6 and 3.14, and 3.14 can't `ensurepip`. Install e.g.
`brew install python@3.12`, then `python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt`.
Without it, nothing below can run locally.

1. **Backend tests** — extend `apps/courses/tests/test_admin_auth.py` (patch target
   `apps.courses.views_admin.http_requests.post`, `MagicMock(status_code=200, json=lambda: {...})`, super-admin
   JWT via the existing `_token('super-uid')` helper). Assert: the call goes to `/auth/v1/admin/users`; the body
   carries `email_confirm: True`, `user_metadata.name`, and a non-empty password; `supabase_user_id` is stored
   from the response; `mail.outbox` has one email to the invitee containing the temp password and
   `/admin/login`, and **no expiry wording**; the temp password is **absent from the API response body**;
   the `email_exists` path sends an email with no password; Resend rotates (PUTs) and re-emails; non-super
   gets 403.
2. **Full suites** — `python -m pytest apps/courses/tests/ apps/reports/tests/ apps/scholarship/tests/ -v`
   (golden masters must stay SPM 5319 / STPM 2026 — this change touches neither), plus `npx jest`,
   `node scripts/check-i18n.js`, and `next build` in `halatuju-web`.
3. **No migration** — `must_change_password` lives in Supabase `user_metadata`, not on `PartnerAdmin`. Nothing
   to migrate-first.
4. **Live end-to-end after deploy** (both services): invite `tamiliam+t1@gmail.com` as a reviewer → the email
   arrives by itself, carrying the temp password and no expiry claim → sign in at `/admin/login` → forced to
   `/admin/set-password` → set a password → land on `/admin/scholarship` with the reviewer workspace visible.
   Then invite `tamiliam+t2@gmail.com` → ignore the password, "Sign in with Google" → same workspace. Press
   **Resend** on one of them and confirm a new email arrives, the old password stops working and the new one
   works. Delete both rows afterwards. At no point should the owner have to copy, relay, or type a password.
5. **Goban's loose end** — independent of this change: confirm he actually holds the reviewer role and can see
   his assigned applicants, not just that he can log in.

## Sprint close (repo convention)

Branch `feat/partner-onboarding-durable`, commits in the house style (`feat:` / `fix:`), then the usual close:
retro in `docs/retrospective-2026-07-XX-partner-onboarding.md`, an entry each in `docs/decisions.md`
(why a temp password rather than a magic link — the PKCE/cross-device trap) and `docs/lessons.md` (the general
form: *a provider API that ignores an unknown field will 200 and silently drop your intent — assert the
side-effect, not the status code*), plus `CHANGELOG.md` and the `## Next Sprint` block in `halatuju_api/CLAUDE.md`.
