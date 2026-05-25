export interface SecondarySchool {
  code: string
  name: string
  state: string
  type: string
}

import schoolsData from './secondary-schools.json'
// All 2,480 Malaysian secondary schools (PERINGKAT = Menengah) from the MOE
// directory SenaraiSekolahWeb (April 2026). Used by the B40 apply form's
// searchable School field. Source workbook lives in /docs.
export const SECONDARY_SCHOOLS: SecondarySchool[] = schoolsData as SecondarySchool[]

/**
 * Search secondary schools by name (case-insensitive). Prefix matches rank above
 * mid-string matches; otherwise data order (alphabetical by name). Returns up to
 * `limit`. Queries under 2 chars return nothing, so we never dump the full list.
 */
export function searchSchools(query: string, limit = 8): SecondarySchool[] {
  const q = query.trim().toLowerCase()
  if (q.length < 2) return []
  const prefix: SecondarySchool[] = []
  const mid: SecondarySchool[] = []
  for (const s of SECONDARY_SCHOOLS) {
    const i = s.name.toLowerCase().indexOf(q)
    if (i === 0) prefix.push(s)
    else if (i > 0) mid.push(s)
    if (prefix.length >= limit) break
  }
  return [...prefix, ...mid].slice(0, limit)
}
