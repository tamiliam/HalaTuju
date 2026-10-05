/**
 * The programme an organisation's own apply link names (PF-1 P2) — the apply form's gift code.
 *
 * `/scholarship/apply?p=<programme-code>` — a PROGRAMME code, never a cohort code: a cohort is
 * year-specific (`b40-2026`), so a link pinned to one would rot every intake, whereas a
 * programme never lapses. The backend refuses to guess when more than one round is open, so
 * this value is what tells it which organisation the student is applying to.
 *
 * Also kept in sessionStorage, so the two round trips out of the form (the My Results →
 * onboarding detour and the sign-in gate) can come back carrying it — see `./applyPagePath`.
 *
 * A LEAF, moved out of `scholarship.ts` (2026-10-05): only the apply form uses these, and
 * `scholarship.ts` rides whole on `/profile` and `/scholarship/application`, both of which sat on
 * their first-load budgets.
 */
import { APPLY_PROGRAMME_KEY, safeSession, type StorageLike } from './applyReturn'

/** Arrive on the apply page: the URL's `?p=` is the gift in force — remembered and returned. A BARE
 *  arrival forgets any earlier code and returns '' (so the chooser asks): reusing the gift of an
 *  earlier visit in the tab skipped the question and filed under a gift this visit never named. */
export function enterApplyPage(search: string | null | undefined, storage?: StorageLike): string {
  const s = storage ?? safeSession()
  const fromUrl = (new URLSearchParams(search ?? '').get('p') ?? '').trim()
  if (fromUrl) s?.setItem(APPLY_PROGRAMME_KEY, fromUrl)
  else s?.removeItem(APPLY_PROGRAMME_KEY)
  return fromUrl
}

/** Remember a code the student CHOSE (or the server resolved), through the same seam as one they
 *  arrived with.
 *
 *  ⚠ SAME KEY ON PURPOSE. A pick from the chooser and a follow of an organisation's own `?p=`
 *  link must be indistinguishable from here on — submit reads one value and neither the payload
 *  nor the backend has any idea which way it was set, so there is exactly one routing path to be
 *  right about.
 */
export function setApplyProgramme(code: string, storage?: StorageLike): void {
  const s = storage ?? safeSession()
  const clean = (code ?? '').trim()
  if (clean) s?.setItem(APPLY_PROGRAMME_KEY, clean)
}

/** Forget it — on submit (a later visit is a fresh decision) and on the form's "Change". */
export function clearApplyProgramme(storage?: StorageLike): void {
  const s = storage ?? safeSession()
  s?.removeItem(APPLY_PROGRAMME_KEY)
}

/** Must this student be ASKED which programme they mean, before they fill anything in?
 *
 *  ⚠ THE WHOLE POINT IS THE TIMING. `resolve_open_cohort` refuses to guess between two open
 *  rounds — correctly; guessing once filed a student under the wrong foundation, funded from the
 *  wrong money, with no error anywhere. But that refusal used to arrive as a 409 AT SUBMIT, after
 *  the entire form was filled in. This is the same refusal, moved to before the first keystroke.
 *
 *  Yes only when BOTH are true: nothing is remembered (no `?p=`, no earlier pick) AND the server
 *  actually offered a choice. One open round, or a link that named a programme, asks nothing —
 *  which is every visitor today and stays the common case.
 */
export function needsProgrammeChoice(
  remembered: string,
  choices: readonly { code: string }[] | undefined,
): boolean {
  return !remembered.trim() && (choices?.length ?? 0) > 1
}
