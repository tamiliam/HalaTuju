// The 20 Malaysian public universities (IPTA / "Universiti Awam"). Canonical name
// is the official Bahasa Malaysia name — that is what we store. `acronym` and
// `aliases` (common English renderings + variants) are searchable only, to absorb
// the University↔Universiti / Technology↔Teknologi / IIUM↔UIAM mix-ups. Private,
// foreign or unknown universities are accepted as free text (the picker allows it).
export interface PublicUniversity {
  name: string       // canonical BM name (stored)
  acronym: string
  aliases?: string[] // EN renderings / common variants (searchable, not stored)
}

export const PUBLIC_UNIVERSITIES: PublicUniversity[] = [
  { name: 'Universiti Malaya', acronym: 'UM', aliases: ['University of Malaya', 'University Malaya'] },
  { name: 'Universiti Sains Malaysia', acronym: 'USM', aliases: ['University of Science Malaysia', 'Science University of Malaysia'] },
  { name: 'Universiti Kebangsaan Malaysia', acronym: 'UKM', aliases: ['National University of Malaysia'] },
  { name: 'Universiti Putra Malaysia', acronym: 'UPM', aliases: ['Putra University Malaysia', 'University Putra Malaysia'] },
  { name: 'Universiti Teknologi Malaysia', acronym: 'UTM', aliases: ['University of Technology Malaysia', 'University Technology Malaysia'] },
  { name: 'Universiti Teknologi MARA', acronym: 'UiTM', aliases: ['MARA University of Technology', 'University Technology MARA'] },
  { name: 'Universiti Islam Antarabangsa Malaysia', acronym: 'UIAM', aliases: ['International Islamic University Malaysia', 'IIUM'] },
  { name: 'Universiti Utara Malaysia', acronym: 'UUM', aliases: ['Northern University of Malaysia'] },
  { name: 'Universiti Malaysia Sarawak', acronym: 'UNIMAS', aliases: ['University of Malaysia Sarawak', 'University Malaysia Sarawak'] },
  { name: 'Universiti Malaysia Sabah', acronym: 'UMS', aliases: ['University of Malaysia Sabah', 'University Malaysia Sabah'] },
  { name: 'Universiti Pendidikan Sultan Idris', acronym: 'UPSI', aliases: ['Sultan Idris Education University'] },
  { name: 'Universiti Sains Islam Malaysia', acronym: 'USIM', aliases: ['Islamic Science University of Malaysia'] },
  { name: 'Universiti Teknikal Malaysia Melaka', acronym: 'UTeM', aliases: ['Technical University of Malaysia Malacca', 'University Technical Malaysia Melaka'] },
  { name: 'Universiti Malaysia Pahang Al-Sultan Abdullah', acronym: 'UMPSA', aliases: ['University Malaysia Pahang', 'UMP'] },
  { name: 'Universiti Malaysia Perlis', acronym: 'UniMAP', aliases: ['University Malaysia Perlis'] },
  { name: 'Universiti Tun Hussein Onn Malaysia', acronym: 'UTHM', aliases: ['University Tun Hussein Onn Malaysia'] },
  { name: 'Universiti Malaysia Terengganu', acronym: 'UMT', aliases: ['University Malaysia Terengganu'] },
  { name: 'Universiti Malaysia Kelantan', acronym: 'UMK', aliases: ['University Malaysia Kelantan'] },
  { name: 'Universiti Pertahanan Nasional Malaysia', acronym: 'UPNM', aliases: ['National Defence University of Malaysia'] },
  { name: 'Universiti Sultan Zainal Abidin', acronym: 'UniSZA', aliases: ['Sultan Zainal Abidin University'] },
]
