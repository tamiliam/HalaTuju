import type { ApplyFormState } from '@/lib/scholarship'

/**
 * The apply form's two DERIVED answers follow a patch from the picker: every pathway is a public
 * institution, so naming one implies `upu_status = 'public_other'` (none → ''); and the chosen
 * course's field is the field of study (no separate question).
 */
export function applyPlanPatch(form: ApplyFormState, patch: Partial<ApplyFormState>): ApplyFormState {
  const next = { ...form, ...patch }
  if ('chosenPathway' in patch) next.upuStatus = patch.chosenPathway ? 'public_other' : ''
  if ('chosenProgramme' in patch) next.fieldOfStudy = patch.chosenProgramme?.fieldKey ?? ''
  return next
}
