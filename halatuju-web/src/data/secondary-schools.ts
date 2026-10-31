export interface SecondarySchool {
  code: string
  name: string
  state: string
  type: string
}

import schoolsData from './secondary-schools.json'
import { matchesWords, schoolSearchForms, searchWords } from '@/lib/schoolSearch'
// All 2,480 Malaysian secondary schools (PERINGKAT = Menengah) from the MOE
// directory SenaraiSekolahWeb (April 2026). Used by the B40 apply form's
// searchable School field. Source workbook lives in /docs.
export const SECONDARY_SCHOOLS: SecondarySchool[] = schoolsData as SecondarySchool[]

// Each school's [plain, spelt-out, joined] search text, built by the FIRST search and kept — never
// at import time (lib/schoolSearch's pure-module rule).
let forms: [string, string, string][] | null = null

/**
 * Search secondary schools by name (case-insensitive), understanding the MOE short forms
 * (lib/schoolSearch): "sekolah menengah kebangsaan perempuan" finds "SMK (P) ...", "jln ipoh"
 * finds "JALAN IPOH". Rows whose name — as written or spelt out — STARTS with the query rank
 * first; then every other row holding all the query's words; data order (alphabetical) within
 * each. Returns up to `limit`. Queries under 2 chars return nothing, so we never dump the list.
 */
export function searchSchools(query: string, limit = 8): SecondarySchool[] {
  const q = query.trim().toLowerCase()
  if (q.length < 2) return []
  const words = searchWords(q)
  if (words.length === 0) return []
  const nq = words.map(([w]) => w).join(' ')
  const cq = words.map(([w, c]) => c ?? w).join(' ')
  if (!forms) forms = SECONDARY_SCHOOLS.map((s) => {
    const [plain, long] = schoolSearchForms(s.name)
    return [plain, long, long === plain ? plain : `${plain} ${long}`]
  })
  const prefix: SecondarySchool[] = []
  const mid: SecondarySchool[] = []
  for (let i = 0; i < SECONDARY_SCHOOLS.length; i++) {
    const [plain, long, text] = forms[i]
    if (plain.startsWith(nq) || long.startsWith(nq) || long.startsWith(cq)) prefix.push(SECONDARY_SCHOOLS[i])
    else if (mid.length < limit && matchesWords(text, words)) mid.push(SECONDARY_SCHOOLS[i])
    if (prefix.length >= limit) break
  }
  return [...prefix, ...mid].slice(0, limit)
}
