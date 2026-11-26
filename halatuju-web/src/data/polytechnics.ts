/**
 * The 36 public polytechnics (Jabatan Pendidikan Politeknik dan Kolej Komuniti, Ministry of Higher
 * Education) offered by the "Pre-U institution" picker's "Polytechnics" chip (pre-U sprint,
 * 2026-11-26; closes TD-767). Community colleges (Kolej Komuniti) are NOT included.
 *
 * Source: the Ministry's "Senarai Institusi Pengajian Tinggi Awam (Politeknik)", 36 rows,
 * https://biasiswa.mohe.gov.my/sukan/doc/SENARAI%20INSTITUSI%20PENGAJIAN%20TINGGI%20AWAM(POLITEKNIK).pdf
 * Names are the official Malay names (the source prints them in capitals); `hint` is the official
 * abbreviation. No state is given: the source does not state one and none was typed from memory.
 */
export interface Polytechnic {
  name: string
  hint: string
}

export const POLYTECHNICS: Polytechnic[] = [
  { name: 'Politeknik Bagan Datuk', hint: 'PBD' },
  { name: 'Politeknik Balik Pulau', hint: 'PBU' },
  { name: 'Politeknik Banting', hint: 'PBS' },
  { name: 'Politeknik Besut', hint: 'PBT' },
  { name: 'Politeknik Hulu Terengganu', hint: 'PHT' },
  { name: 'Politeknik Ibrahim Sultan', hint: 'PIS' },
  { name: 'Politeknik Jeli', hint: 'PJK' },
  { name: 'Politeknik Kota Bharu', hint: 'PKB' },
  { name: 'Politeknik Kota Kinabalu', hint: 'PKK' },
  { name: 'Politeknik Kuala Terengganu', hint: 'PKT' },
  { name: 'Politeknik Kuching Sarawak', hint: 'PKS' },
  { name: 'Politeknik Melaka', hint: 'PMK' },
  { name: 'Politeknik Merlimau', hint: 'PMM' },
  { name: 'Politeknik Mersing', hint: 'PMJ' },
  { name: 'Politeknik METRO Betong', hint: 'PMBS' },
  { name: 'Politeknik METRO Johor Bahru', hint: 'PMJB' },
  { name: 'Politeknik METRO Kuala Lumpur', hint: 'PMKL' },
  { name: 'Politeknik METRO Kuantan', hint: 'PMKU' },
  { name: 'Politeknik METRO Tasek Gelugor', hint: 'PMTG' },
  { name: 'Politeknik Muadzam Shah', hint: 'PMS' },
  { name: 'Politeknik Mukah Sarawak', hint: 'PMU' },
  { name: 'Politeknik Nilai', hint: 'PNS' },
  { name: 'Politeknik Port Dickson', hint: 'PPD' },
  { name: 'Politeknik Sandakan', hint: 'PSS' },
  { name: 'Politeknik Seberang Perai', hint: 'PSP' },
  { name: "Politeknik Sultan Abdul Halim Mu'adzam Shah", hint: 'POLIMAS' },
  { name: 'Politeknik Sultan Azlan Shah', hint: 'PSAS' },
  { name: 'Politeknik Sultan Haji Ahmad Shah', hint: 'POLISAS' },
  { name: 'Politeknik Sultan Idris Shah', hint: 'PSIS' },
  { name: 'Politeknik Sultan Mizan Zainal Abidin', hint: 'PSMZA' },
  { name: 'Politeknik Sultan Salahuddin Abdul Aziz Shah', hint: 'PSA' },
  { name: 'Politeknik Tawau', hint: 'PTS' },
  { name: 'Politeknik Tuanku Sultanah Bahiyah', hint: 'PTSB' },
  { name: 'Politeknik Tuanku Syed Sirajuddin', hint: 'PTSS' },
  { name: 'Politeknik Tun Syed Nasir Syed Ismail', hint: 'PTSN' },
  { name: 'Politeknik Ungku Omar', hint: 'PUO' },
]
