/**
 * School search understands the MOE short forms (owner, 2026-10-31): a student who types the
 * long form — "sekolah menengah kebangsaan ...", "kolej tingkatan enam ...", "jalan ..." — finds
 * the school our lists hold under its short name. Checked against the REAL lists, because the
 * point is what a student finds, not what the table says.
 */
import { SECONDARY_SCHOOLS, searchSchools } from '@/data/secondary-schools'
import { STPM_SCHOOLS } from '@/data/stpm-schools'
import { MATRIC_COLLEGES } from '@/data/matric-colleges'
import { matchesSearch, normaliseSearch, schoolSearchText } from '@/lib/schoolSearch'

const names = (q: string) => searchSchools(q, 50).map((s) => s.name)
const stpm = (q: string) => STPM_SCHOOLS.filter((s) => matchesSearch(schoolSearchText(s.name), q)).map((s) => s.name)

describe('normaliseSearch', () => {
  it('lowercases, drops apostrophes, turns other marks into single spaces', () => {
    expect(normaliseSearch("SMK KG. DATO' AHMAD SAID")).toBe('smk kg dato ahmad said')
    expect(normaliseSearch("MA'AHAD AL-IMAM")).toBe('maahad al imam')
    expect(normaliseSearch('SMK (P)  MOHD.')).toBe('smk p mohd')
  })
})

describe('schoolSearchText', () => {
  it('spells out bracketed (P)/(L)/(A), but never a bare P', () => {
    expect(schoolSearchText('SMK (P) AIR PANAS')).toContain('sekolah menengah kebangsaan perempuan air panas')
    expect(schoolSearchText('SMU(A)AL-FALAH')).toContain('sekolah menengah ugama agama agama al falah')
    expect(schoolSearchText('SMK LANGKAWI P.TUBA')).not.toContain('perempuan')
  })
  it('only whole words: "STPM" is not "saint", "SMKA" is not "SMK"', () => {
    expect(schoolSearchText('STPM CENTRE')).toBe('stpm centre')
    expect(schoolSearchText('SMKA X')).toContain('sekolah menengah kebangsaan agama x')
  })
  it('a word that is a property of every object is just a word', () => {
    expect(schoolSearchText('CONSTRUCTOR TOSTRING')).toBe('constructor tostring')
    expect(matchesSearch('x', 'constructor')).toBe(false)
  })
})

describe('the owner\'s long forms find the short names', () => {
  it('"sekolah menengah sains" finds an "SM SAINS ..." row', () => {
    expect(names('sekolah menengah sains').some((n) => n.startsWith('SM SAINS '))).toBe(true)
  })
  it('"kolej tingkatan enam pontian" finds "KTE PONTIAN" (both lists)', () => {
    expect(names('kolej tingkatan enam pontian')).toContain('KTE PONTIAN')
    expect(stpm('kolej tingkatan enam pontian')).toContain('KTE PONTIAN')
    expect(stpm('tingkatan 6 pontian')).toContain('KTE PONTIAN')
  })
  it('"sekolah menengah kebangsaan perempuan" finds an "SMK (P) ..." school', () => {
    expect(names('sekolah menengah kebangsaan perempuan').some((n) => n.startsWith('SMK (P) '))).toBe(true)
  })
  it('"dato" finds "DATO\' ..." and the apostrophe never blocks a longer query', () => {
    expect(names('dato').some((n) => n.includes("DATO'"))).toBe(true)
    expect(names('dato ahmad said')).toContain("SMK KG. DATO' AHMAD SAID")
  })
  it('"kolej matrikulasi perak" finds "KM Perak"', () => {
    const hit = MATRIC_COLLEGES.filter((c) => matchesSearch(schoolSearchText(c.name), 'kolej matrikulasi perak'))
    expect(hit.map((c) => c.name)).toEqual(['KM Perak'])
  })
})

describe('one word, two spellings: either finds the other', () => {
  const anyName = (re: RegExp) => SECONDARY_SCHOOLS.some((s) => re.test(s.name))
  it('the data holds both spellings, so the pairs below are live', () => {
    expect(anyName(/\bSRI\b/)).toBe(true)
    expect(anyName(/\bSERI\b/)).toBe(true)
  })
  it('"seri" finds a "SRI ..." school and "sri" finds a "SERI ..." one', () => {
    expect(names('seri').some((n) => /\bSRI\b/.test(n))).toBe(true)
    expect(names('sri').some((n) => /\bSERI\b/.test(n))).toBe(true)
  })
  it('"jalan ipoh" and "jln ipoh" both find "SMK (P) JALAN IPOH"', () => {
    expect(names('jalan ipoh')).toContain('SMK (P) JALAN IPOH')
    expect(names('jln ipoh')).toContain('SMK (P) JALAN IPOH')
    expect(names('jalan mengkibol')).toContain('SMK JLN MENGKIBOL')
  })
  it('"kampung" finds a "KG ..." row', () => {
    expect(names('kampung').some((n) => /\bKG\b/.test(n))).toBe(true)
  })
  it('"tanjung aru" finds "TG ARU"; "mohamad" finds "MOHD"', () => {
    expect(names('tanjung aru')).toContain('SMK LA SALLE TG ARU')
    expect(names('muhammad').some((n) => /\bMOHD\b/.test(n))).toBe(true)
    expect(names('mohd').some((n) => /\bMUHAMMAD\b/.test(n))).toBe(true)
  })
})

describe('old Malay spellings beside the new ones (review, 2026-10-31)', () => {
  const both = (a: RegExp, q: string) => names(q).some((n) => a.test(n))
  it('KAMPONG joins KG / KAMPUNG; AYER and AIR; TELOK and TELUK', () => {
    expect(both(/\bKAMPONG\b/, 'kampung')).toBe(true)
    expect(both(/\bKG\b/, 'kampong')).toBe(true)
    expect(both(/\bAIR\b/, 'ayer')).toBe(true)
    expect(both(/\bAYER\b/, 'air')).toBe(true)
    expect(both(/\bTELUK\b/, 'telok')).toBe(true)
    expect(both(/\bTELOK\b/, 'teluk')).toBe(true)
  })
  it('LUBOK / LUBUK, TASEK / TASIK, ULU / HULU, KRIAN / KERIAN, SUNGEI, DATOH', () => {
    expect(both(/\bLUBUK\b/, 'lubok')).toBe(true)
    expect(both(/\bTASIK\b/, 'tasek')).toBe(true)
    expect(both(/\bULU\b/, 'hulu')).toBe(true)
    expect(both(/\bKERIAN\b/, 'krian')).toBe(true)
    expect(both(/\bSUNGAI\b/, 'sungei')).toBe(true)
    expect(both(/\bBAGAN DATOH\b/, 'bagan datuk')).toBe(true)
  })
  it('BAHRU and BHARU stay apart: they are different places', () => {
    expect(names('bahru').some((n) => /\bBHARU\b/.test(n))).toBe(false)
    expect(names('bharu').some((n) => /\bBAHRU\b/.test(n))).toBe(false)
  })
})

describe('nothing found before is lost', () => {
  it('a bare query that matched as one substring still matches, prefix first', () => {
    const res = names('smk bandar')
    expect(res.length).toBeGreaterThan(0)
    expect(res[0].startsWith('SMK BANDAR')).toBe(true)
  })
  it('every row the old substring search found, word-AND still finds', () => {
    for (const q of ['smk bandar', 'taman', 'sains', "dato'", 'jalan', 'kte']) {
      const nq = q.toLowerCase()
      const old = SECONDARY_SCHOOLS.filter((s) => s.name.toLowerCase().includes(nq))
      expect(old.every((s) => matchesSearch(schoolSearchText(s.name), q))).toBe(true)
    }
  })
  it('a word that appears nowhere returns nothing', () => {
    expect(names('zzqxv')).toEqual([])
    expect(stpm('kolej zzqxv')).toEqual([])
  })
})
