export interface StpmSchool {
  code: string
  name: string
  state: string
  ppd: string
  streams: string[]
  subjects: string
  phone: string
}

import schoolsData from './stpm-schools.json'
export const STPM_SCHOOLS: StpmSchool[] = schoolsData as StpmSchool[]

// Stream keys (matching STPM_STREAMS in lib/scholarship) → the labels used in the data.
const STREAM_LABEL: Record<string, string> = { sains: 'Sains', sains_sosial: 'Sains Sosial' }

/**
 * The Form 6 centres offering a given stream. "not_sure" (or an unknown key) returns
 * every centre — an undecided student still names where they'll study. Used by the
 * B40 apply form's STPM stream → school sub-flow (P4).
 */
export function stpmSchoolsForStream(streamKey: string): StpmSchool[] {
  const label = STREAM_LABEL[streamKey]
  if (!label) return STPM_SCHOOLS
  return STPM_SCHOOLS.filter((s) => s.streams.includes(label))
}
