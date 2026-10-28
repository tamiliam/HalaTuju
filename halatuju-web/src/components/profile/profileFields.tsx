/**
 * The small, shared pieces of the /profile page (`src/app/profile/page.tsx`): the state list, the
 * empty forms, the "how many fields are blank" count, and the read-only label/value pair. MOVED
 * here verbatim from the page (2026-10-28) to bring it under its size budget — no behaviour change.
 */
import type { FamilyRosterForm } from '@/components/FamilyRosterFields'
import type { PathwayForm } from '@/components/PathwayPicker'

export const MALAYSIAN_STATES = [
  'Johor', 'Kedah', 'Kelantan', 'Melaka', 'Negeri Sembilan',
  'Pahang', 'Perak', 'Perlis', 'Pulau Pinang', 'Sabah',
  'Sarawak', 'Selangor', 'Terengganu',
  'W.P. Kuala Lumpur', 'W.P. Putrajaya', 'W.P. Labuan',
]

export const EMPTY_FAMILY: FamilyRosterForm = {
  fatherName: '', fatherOccupation: '', fatherOccupationOther: '',
  motherName: '', motherOccupation: '', motherOccupationOther: '',
  otherFamilyMembers: [], siblingsInSchool: 0, siblingsInTertiary: 0,
}

export const EMPTY_PATHWAY: PathwayForm = {
  pathwayCertainty: '', chosenPathway: '', chosenProgramme: null,
  preUTrack: '', preUInstitution: '', pathwaysConsidered: [],
  uncertaintyReasons: [], uncertaintyNote: '',
}

export function countIncomplete(fields: (string | boolean | number | null | undefined)[]): number {
  return fields.filter(f => f === '' || f === null || f === undefined).length
}

export function FieldValue({ value, t }: { value: string; t: (key: string) => string }) {
  if (!value) {
    return <span className="text-sm text-caution-700 italic">{t('profile.notSet')}</span>
  }
  return <span className="text-sm text-ground-900">{value}</span>
}

export function FieldLabel({ label, empty }: { label: string; empty: boolean }) {
  return (
    <span className="text-sm text-ground-500 flex items-center gap-1.5">
      {empty && <span className="w-1.5 h-1.5 rounded-full bg-caution-400 inline-block" />}
      {label}
    </span>
  )
}
