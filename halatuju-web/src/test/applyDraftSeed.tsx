/**
 * Test helpers for the apply form's DRAFT (Mobile M4). Before M4 the page tests landed on a filled
 * form by writing the whole-form "stash" and clicking the bottom tab bar; both are gone. Now a test
 * seeds HER draft (her user id, the programme, the step to land on) and, on the last step, gives the
 * two answers a draft never holds — the consent switch and the typed signature — exactly as a student
 * returning after a tab kill has to.
 */
import { act, fireEvent, screen } from '@testing-library/react'
import { writeApplyDraft } from '@/lib/applyDraft'
import type { ApplyFormState } from '@/lib/scholarship'

export const TEST_UID = 'stu-apply-test'
/** What `useAuth().session` carries for the seeded student. */
export const testSession = { user: { id: TEST_UID } }

export function seedApplyDraft(form: ApplyFormState, step: string, programme: string, uid = TEST_UID): void {
  writeApplyDraft(form, { uid, programme }, step)
}

/** On the last step: switch consent on and sign with `name` (never restored from a draft). WAITS for the
 *  step: the draft is laid over the form in an effect AFTER the first render that shows the gift line. */
export async function consentAndSign(name: string): Promise<void> {
  const consent = await screen.findByRole('switch', { name: 'scholarship.apply.consentLabel' })
  if (consent.getAttribute('aria-checked') !== 'true') fireEvent.click(consent)
  fireEvent.change(screen.getByPlaceholderText('scholarship.apply.declaration.signPlaceholder'),
    { target: { value: name } })
}

/** Consent, sign, and press Submit. */
export async function signAndSubmit(name: string): Promise<void> {
  await consentAndSign(name)
  await act(async () => {
    fireEvent.click(screen.getByRole('button', { name: 'scholarship.apply.submit' }))
  })
}
