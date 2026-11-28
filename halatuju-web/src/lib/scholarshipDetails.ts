/**
 * The deeper-info (Step 2) form: its state, the application-to-form reader and the payload builder.
 *
 * A LEAF, moved out of `scholarship.ts` VERBATIM: that module rides whole on /scholarship/apply,
 * which never touches this block; only the next-steps surface (ScholarshipNextSteps) does.
 * Keep it off `scholarship.ts` so its `familyRoster` edge does not ship to the apply page.
 */
import type { ScholarshipApplication } from '@/lib/api'
import { cleanOtherMembers, type OtherMember } from '@/lib/familyRoster'

export interface DetailsFormState {
  // Card A — About your family (redesign 2026-06): structured roster. first_in_family
  // + parents_occupation are DERIVED on the backend from this, so the form no longer
  // holds/sends them. occupation_other only matters when occupation === 'other'.
  fatherName: string
  fatherOccupation: string          // a PROFESSION_CODE, '' = not yet chosen
  fatherOccupationOther: string
  motherName: string
  motherOccupation: string
  motherOccupationOther: string
  otherFamilyMembers: OtherMember[]
  // Phase 2B: unemployment detail per 'unemployed' roster member — {member: {reason, since}}.
  nonEarning: Record<string, { reason?: string; since?: string }>
  // Sibling steppers — default 0 (a real "none" answer; no confusing "not set" state).
  siblingsInSchool: number
  siblingsInTertiary: number
  familyContext: string
  // Card B — About you (S2; aspirations/plans/fears pre-existing, daily_life new)
  aspirations: string
  plans: string
  fears: string
  dailyLife: string
  // Legacy field (kept for backward compatibility; no longer part of completeness)
  justification: string
  // "How you'd use the support" — the S3 reframe
  fundingCategories: string[]
  fundingNote: string
  programmeMonths: string  // string for the <select>; converted to int|null in buildDetailsPayload
  // Address (S14) — under "About your family" in the Story tab. Round-trips
  // through the profile (the save endpoint writes it to profile.address/etc).
  // State is sourced from /apply (profile.preferred_state) and not editable here.
  address: string
  postalCode: string
  city: string
}

export function emptyDetailsForm(): DetailsFormState {
  return {
    // Card A — About your family (structured roster)
    fatherName: '',
    fatherOccupation: '',
    fatherOccupationOther: '',
    motherName: '',
    motherOccupation: '',
    motherOccupationOther: '',
    otherFamilyMembers: [],
    nonEarning: {},
    siblingsInSchool: 0,
    siblingsInTertiary: 0,
    familyContext: '',
    // Card B — About you
    aspirations: '',
    plans: '',
    fears: '',
    dailyLife: '',
    justification: '',
    // Funding
    fundingCategories: [],
    fundingNote: '',
    programmeMonths: '',
    // Address
    address: '',
    postalCode: '',
    city: '',
  }
}

export function applicationToDetailsForm(app: ScholarshipApplication): DetailsFormState {
  const fn = app.funding_need
  return {
    // Card A — About your family (structured roster)
    fatherName: app.father_name || '',
    fatherOccupation: app.father_occupation || '',
    fatherOccupationOther: app.father_occupation_other || '',
    motherName: app.mother_name || '',
    motherOccupation: app.mother_occupation || '',
    motherOccupationOther: app.mother_occupation_other || '',
    otherFamilyMembers: Array.isArray(app.other_family_members) ? app.other_family_members : [],
    nonEarning: (app.income_nonearning && typeof app.income_nonearning === 'object'
      ? app.income_nonearning : {}) as Record<string, { reason?: string; since?: string }>,
    siblingsInSchool: app.siblings_in_school ?? 0,
    siblingsInTertiary: app.siblings_in_tertiary ?? 0,
    familyContext: app.family_context || '',
    // Card B — About you
    aspirations: app.aspirations || '',
    plans: app.plans || '',
    fears: app.fears || '',
    dailyLife: app.daily_life || '',
    justification: app.justification || '',
    // Funding
    fundingCategories: fn?.categories ?? [],
    fundingNote: fn?.funding_note ?? '',
    programmeMonths: fn?.programme_months != null ? String(fn.programme_months) : '',
    // Address — pre-fill from the profile fields the read serializer exposes.
    address: app.address || '',
    postalCode: app.postal_code || '',
    city: app.city || '',
  }
}

/** Keep unemployment detail ONLY for members who are currently 'unemployed' in the roster,
 *  so a member who changed occupation doesn't leave stale reason/since data behind. */
function pruneNonEarning(f: DetailsFormState): Record<string, { reason?: string; since?: string }> {
  const unemployed = new Set<string>()
  if (f.fatherOccupation === 'unemployed') unemployed.add('father')
  if (f.motherOccupation === 'unemployed') unemployed.add('mother')
  for (const m of f.otherFamilyMembers) {
    if (m.occupation === 'unemployed' && m.role) unemployed.add(m.role)
  }
  const out: Record<string, { reason?: string; since?: string }> = {}
  for (const [member, detail] of Object.entries(f.nonEarning || {})) {
    if (!unemployed.has(member) || !detail) continue
    const reason = (detail.reason || '').trim()
    const since = (detail.since || '').trim()
    if (reason || since) out[member] = { ...(reason ? { reason } : {}), ...(since ? { since } : {}) }
  }
  return out
}

export function buildDetailsPayload(f: DetailsFormState): Record<string, unknown> {
  // Convert programmeMonths string to int or null
  const pm = f.programmeMonths.trim()
  const programmeMonthsInt = pm !== '' ? (parseInt(pm, 10) || null) : null

  return {
    // Card A — About your family (structured roster). first_in_family +
    // parents_occupation are DERIVED on the backend from these — not sent here.
    father_name: f.fatherName.trim(),
    father_occupation: f.fatherOccupation,
    father_occupation_other: f.fatherOccupation === 'other' ? f.fatherOccupationOther.trim() : '',
    mother_name: f.motherName.trim(),
    mother_occupation: f.motherOccupation,
    mother_occupation_other: f.motherOccupation === 'other' ? f.motherOccupationOther.trim() : '',
    other_family_members: cleanOtherMembers(f.otherFamilyMembers),
    income_nonearning: pruneNonEarning(f),
    siblings_in_school: f.siblingsInSchool,
    siblings_in_tertiary: f.siblingsInTertiary,
    family_context: f.familyContext.trim(),
    // Card B — About you
    aspirations: f.aspirations.trim(),
    plans: f.plans.trim(),
    fears: f.fears.trim(),
    daily_life: f.dailyLife.trim(),
    justification: f.justification.trim(),
    funding_need: {
      categories: f.fundingCategories,
      funding_note: f.fundingNote.trim(),
      programme_months: programmeMonthsInt,
    },
    // Address — backend save_application_details writes these to the profile.
    address: f.address.trim(),
    postal_code: f.postalCode.trim(),
    city: f.city.trim(),
  }
}
