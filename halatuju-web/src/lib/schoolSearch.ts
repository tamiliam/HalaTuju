/**
 * School-name search that understands the MOE short forms (owner, 2026-10-31).
 *
 * Our lists carry the Ministry's short names — "SMK (P) TEMENGGONG IBRAHIM", "KTE PONTIAN",
 * "KM Perak", "SMK JLN MENGKIBOL" — and a student who types the long form ("sekolah menengah
 * kebangsaan ...", "kolej tingkatan enam ...", "jalan ...") used to find nothing. Two tables fix it:
 *
 * - `LONG` — a school-type short form and what it stands for. Added to the NAME only, so
 *   "kolej tingkatan enam pontian" finds "KTE PONTIAN". It is never applied to the query: "smk"
 *   typed by a student must not widen to every name holding "sekolah".
 * - `SAME` — one word, two spellings ("JLN" / "JALAN", "SRI" / "SERI"). Both the name and the
 *   query are mapped to ONE form, so either spelling finds the other.
 *
 * "(P)", "(L)" and "(A)" mean perempuan, lelaki and agama only inside brackets; a bare "P" is a
 * place ("P.TUBA" is Pulau Tuba) and is left alone.
 *
 * Every query word must appear somewhere in the text (word-AND). A query that matched as one
 * substring before still matches, so nothing that was found is lost.
 *
 * ⚠ PURE MODULE. Object literals only at the top level — no `new Map()`, no computed table:
 * the bundler keeps anything that looks like a side effect, and one top-level Map once put 3 kB
 * on every route. Callers that search a long list cache the text themselves (see
 * `data/secondary-schools.ts`).
 */

const LONG: Record<string, string> = {
  smk: 'sekolah menengah kebangsaan',
  sm: 'sekolah menengah',
  sma: 'sekolah menengah agama',
  smka: 'sekolah menengah kebangsaan agama',
  smu: 'sekolah menengah ugama agama',
  sam: 'sekolah agama menengah',
  samt: 'sekolah agama menengah tinggi',
  smt: 'sekolah menengah teknik',
  sabk: 'sekolah agama bantuan kerajaan',
  sbp: 'sekolah berasrama penuh',
  kv: 'kolej vokasional',
  kte: 'kolej tingkatan enam tingkatan 6 form 6 form six',
  km: 'kolej matrikulasi',
  kmk: 'kolej matrikulasi kejuruteraan',
  pj: 'petaling jaya',
  // "TG" is Tanjung in "LA SALLE TG ARU" but Tengku in "TG PANGLIMA PERANG TG MUHAMMAD": both.
  tg: 'tanjung tengku',
}

const SAME: Record<string, string> = {
  jln: 'jalan',
  sg: 'sungai', sgai: 'sungai', sungei: 'sungai',
  kg: 'kampung', kpg: 'kampung', kampong: 'kampung',
  // Old Malay spellings that sit beside the new ones in the MOE list (review, 2026-10-31).
  // BAHRU and BHARU are NOT joined: they name different places.
  ayer: 'air', telok: 'teluk', lubok: 'lubuk', tasek: 'tasik', ulu: 'hulu', krian: 'kerian',
  datoh: 'datuk',
  tmn: 'taman',
  bdr: 'bandar',
  bt: 'batu',
  bkt: 'bukit',
  pdg: 'padang',
  tg: 'tanjung', tjg: 'tanjung', tj: 'tanjung', tanjong: 'tanjung',
  pt: 'parit',
  pengkalan: 'pangkalan',
  sri: 'seri',
  hj: 'haji',
  hjh: 'hajah',
  abd: 'abdul',
  mohd: 'muhammad', muhd: 'muhammad', mohamad: 'muhammad', mohammad: 'muhammad',
  mohammed: 'muhammad', mohamed: 'muhammad', muhamad: 'muhammad',
  st: 'saint',
  sek: 'sekolah',
  keb: 'kebangsaan',
}

const BRACKET: Record<string, string> = { p: 'perempuan', l: 'lelaki', a: 'agama' }

// Own keys only: a word such as "constructor" must not read Object.prototype.
const own = (t: Record<string, string>, w: string) =>
  Object.prototype.hasOwnProperty.call(t, w) ? t[w] : undefined

/** Lowercase; apostrophes dropped ("MA'AHAD" → "maahad"); anything else not a letter or digit is a space. */
export function normaliseSearch(s: string): string {
  return s.toLowerCase().replace(/['’`]/g, '').replace(/[^a-z0-9]+/g, ' ').trim()
}

/** The name as written, normalised, and the same name with every short form spelt out. */
export function schoolSearchForms(name: string): [string, string] {
  const plain = normaliseSearch(name)
  const long = normaliseSearch(name.replace(/\(\s*([pla])\s*\)/gi, (_, c: string) => ` ${BRACKET[c.toLowerCase()]} `))
    .split(' ')
    .map((w) => own(LONG, w) ?? own(SAME, w) ?? w)
    .join(' ')
  return [plain, long]
}

/** One searchable string: the normalised name, then its spelt-out form when that differs. */
export function schoolSearchText(name: string): string {
  const [plain, long] = schoolSearchForms(name)
  return long === plain ? plain : `${plain} ${long}`
}

/** The query's words, each with its one-form spelling where it has one. */
export function searchWords(query: string): [string, string | undefined][] {
  const q = normaliseSearch(query)
  return q ? q.split(' ').map((w) => [w, own(SAME, w)]) : []
}

/** True when EVERY word (or its one-form spelling) appears in the text. For a loop: split once. */
export function matchesWords(text: string, words: [string, string | undefined][]): boolean {
  return words.every(([w, c]) => text.includes(w) || (c !== undefined && text.includes(c)))
}

/** True when EVERY query word (or its one-form spelling) appears in the text. */
export function matchesSearch(text: string, query: string): boolean {
  return matchesWords(text, searchWords(query))
}
