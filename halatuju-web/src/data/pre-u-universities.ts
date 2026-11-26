/**
 * The 20 public universities (Universiti Awam) offered by the "Pre-U institution" picker's
 * "Public universities" chip — where an Asasi or Diploma student COMPLETED that study (pre-U
 * sprint, 2026-11-26). Exactly these 20, by the owner's list; names are the canonical BM names
 * the reviewer list (`COMMON_UNIVERSITIES`, `./publicUniversities`) already spells, which this
 * list does NOT change or replace. `keywords` are searchable only, never stored.
 */
export interface PreUUniversity {
  name: string
  hint: string
  keywords?: string
}

export const PRE_U_UNIVERSITIES: PreUUniversity[] = [
  { name: 'Universiti Malaya', hint: 'UM', keywords: 'University of Malaya' },
  { name: 'Universiti Sains Malaysia', hint: 'USM' },
  { name: 'Universiti Kebangsaan Malaysia', hint: 'UKM' },
  { name: 'Universiti Putra Malaysia', hint: 'UPM' },
  { name: 'Universiti Teknologi Malaysia', hint: 'UTM' },
  { name: 'Universiti Islam Antarabangsa Malaysia', hint: 'UIAM', keywords: 'IIUM International Islamic University' },
  { name: 'Universiti Utara Malaysia', hint: 'UUM' },
  { name: 'Universiti Malaysia Sarawak', hint: 'UNIMAS' },
  { name: 'Universiti Malaysia Sabah', hint: 'UMS' },
  { name: 'Universiti Pendidikan Sultan Idris', hint: 'UPSI' },
  { name: 'Universiti Teknologi MARA', hint: 'UiTM' },
  { name: 'Universiti Sains Islam Malaysia', hint: 'USIM' },
  { name: 'Universiti Malaysia Terengganu', hint: 'UMT' },
  { name: 'Universiti Tun Hussein Onn Malaysia', hint: 'UTHM' },
  { name: 'Universiti Teknikal Malaysia Melaka', hint: 'UTeM' },
  { name: 'Universiti Malaysia Perlis', hint: 'UniMAP' },
  { name: 'Universiti Malaysia Pahang Al-Sultan Abdullah', hint: 'UMPSA', keywords: 'UMP' },
  { name: 'Universiti Sultan Zainal Abidin', hint: 'UniSZA' },
  { name: 'Universiti Malaysia Kelantan', hint: 'UMK' },
  { name: 'Universiti Pertahanan Nasional Malaysia', hint: 'UPNM' },
]
