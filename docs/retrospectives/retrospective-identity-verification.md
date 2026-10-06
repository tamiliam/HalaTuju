# Retrospective — Identity Verification + UI Polish Sprint (2026-03-17)

## What Was Built

1. **NRIC Identity System**: NRIC as unique identity anchor. Claim/reclaim model with raw SQL PK transfer for existing profiles. Contact email/phone fields separate from auth credentials.
2. **Email Verification**: EmailVerification model, Gmail SMTP send/verify endpoints, verify-email landing page.
3. **Profile Page Redesign**: 5-section layout with per-section edit, verification badges on contact fields.
4. **Onboarding IC Claim Flow**: IC page claims NRIC on backend, handles existing profile transfer gracefully.
5. **Referral Link Sharing**: Admin dashboard card with copy button, WhatsApp share, QR code.
6. **Course Compare**: Side-by-side comparison of 2-3 saved courses, desktop only.
7. **State Sync**: Bidirectional sync between onboarding and profile pages.
8. **Outcomes → Saved Merge**: Deleted redundant `/outcomes` page.
9. **Admin UI Polish**: Student list and detail pages updated to match Stitch designs (pagination, icons, grade pills, danger zone redesign).

## What Went Well

- Identity verification system designed cleanly — NRIC as PK anchor with raw SQL transfer avoids CASCADE issues.
- Course compare reuses existing `getCourse()` and `getStpmCourseDetail()` APIs — no new backend endpoints needed.
- State sync implemented with minimal, targeted edits (3 files) rather than a large refactor.
- 30 new backend tests added (645 total), maintaining zero failures.

## What Went Wrong

1. **State sync was fixed, then re-investigated unnecessarily.**
   - Symptom: Claude re-examined and attempted to re-fix the state sync after it was already working.
   - Root cause: Context loss during a long conversation — didn't track what was already completed.
   - Fix: Mark completed items explicitly before moving on. Don't revisit code unless the user reports a regression.

2. **Wrong screenshots referenced for Saved/Outcomes investigation.**
   - Symptom: Looked at older screenshots instead of the latest two showing the disconnect.
   - Root cause: Multiple screenshots in folder, didn't sort by date.
   - Fix: Always sort screenshots by modification time and confirm with user which ones are current.

3. **Stitch preview URLs returned 404.**
   - Symptom: Playwright couldn't access Stitch design previews.
   - Root cause: Stitch preview URLs aren't publicly shared by default.
   - Fix: Use Stitch MCP `get_screen` to retrieve screenshots directly instead of trying to navigate to preview URLs.

## Design Decisions

- **NRIC as identity anchor**: Chose NRIC over email/phone because Malaysian students may share devices. NRIC is permanent and unique. Conditional unique constraint allows null (not all students enter NRIC).
- **Raw SQL PK transfer**: Used raw SQL for claim/reclaim rather than Django ORM to handle the complex FK cascade correctly. Trade-off: less portable, but correct.
- **Desktop-only compare**: Mobile screens too narrow for meaningful side-by-side comparison. Hidden entirely on mobile rather than a degraded experience.
- **Outcomes merged into Saved**: Two tracking systems were confusing. `interest_status` field on saved_courses handles "I Applied" and "I Got an Offer" inline.

## Numbers

- Backend tests: 615 → 645 (+30)
- Frontend tests: 17 (unchanged)
- Golden masters: SPM 5319, STPM 1994
- New migrations: 3 (0039, 0040, 0041)
- Files created: ~8 (verify-email page, test files, etc.)
- Files modified: ~15
- Files deleted: 1 (outcomes page)
