// Universities commonly attended by Malaysians — used ONLY to power type-to-search
// on the reviewer's own "University" field (their alma mater). This is a convenience
// list, NOT a constraint: the picker allows free text, so any private/foreign/unknown
// institution the reviewer types is kept as-is. The list just gives spelling-consistent
// suggestions for the frequent cases. `hint` is shown on the right (acronym or country);
// `aliases` (EN renderings, acronyms, common variants) are searchable but not stored.
export interface UniversityOption {
  name: string       // canonical name (stored verbatim)
  hint?: string      // shown on the right — acronym or country
  aliases?: string[] // searchable only (acronyms, EN renderings, variants)
}

export const COMMON_UNIVERSITIES: UniversityOption[] = [
  // --- Malaysian public universities (IPTA / Universiti Awam), canonical BM name ---
  { name: 'Universiti Malaya', hint: 'UM', aliases: ['UM', 'University of Malaya', 'University Malaya'] },
  { name: 'Universiti Sains Malaysia', hint: 'USM', aliases: ['USM', 'University of Science Malaysia', 'Science University of Malaysia'] },
  { name: 'Universiti Kebangsaan Malaysia', hint: 'UKM', aliases: ['UKM', 'National University of Malaysia'] },
  { name: 'Universiti Putra Malaysia', hint: 'UPM', aliases: ['UPM', 'Putra University Malaysia', 'University Putra Malaysia'] },
  { name: 'Universiti Teknologi Malaysia', hint: 'UTM', aliases: ['UTM', 'University of Technology Malaysia', 'University Technology Malaysia'] },
  { name: 'Universiti Teknologi MARA', hint: 'UiTM', aliases: ['UiTM', 'MARA University of Technology', 'University Technology MARA'] },
  { name: 'Universiti Islam Antarabangsa Malaysia', hint: 'UIAM', aliases: ['UIAM', 'IIUM', 'International Islamic University Malaysia'] },
  { name: 'Universiti Utara Malaysia', hint: 'UUM', aliases: ['UUM', 'Northern University of Malaysia'] },
  { name: 'Universiti Malaysia Sarawak', hint: 'UNIMAS', aliases: ['UNIMAS', 'University of Malaysia Sarawak', 'University Malaysia Sarawak'] },
  { name: 'Universiti Malaysia Sabah', hint: 'UMS', aliases: ['UMS', 'University of Malaysia Sabah', 'University Malaysia Sabah'] },
  { name: 'Universiti Pendidikan Sultan Idris', hint: 'UPSI', aliases: ['UPSI', 'Sultan Idris Education University'] },
  { name: 'Universiti Sains Islam Malaysia', hint: 'USIM', aliases: ['USIM', 'Islamic Science University of Malaysia'] },
  { name: 'Universiti Teknikal Malaysia Melaka', hint: 'UTeM', aliases: ['UTeM', 'Technical University of Malaysia Malacca', 'University Technical Malaysia Melaka'] },
  { name: 'Universiti Malaysia Pahang Al-Sultan Abdullah', hint: 'UMPSA', aliases: ['UMPSA', 'UMP', 'University Malaysia Pahang'] },
  { name: 'Universiti Malaysia Perlis', hint: 'UniMAP', aliases: ['UniMAP', 'University Malaysia Perlis'] },
  { name: 'Universiti Tun Hussein Onn Malaysia', hint: 'UTHM', aliases: ['UTHM', 'University Tun Hussein Onn Malaysia'] },
  { name: 'Universiti Malaysia Terengganu', hint: 'UMT', aliases: ['UMT', 'University Malaysia Terengganu'] },
  { name: 'Universiti Malaysia Kelantan', hint: 'UMK', aliases: ['UMK', 'University Malaysia Kelantan'] },
  { name: 'Universiti Pertahanan Nasional Malaysia', hint: 'UPNM', aliases: ['UPNM', 'National Defence University of Malaysia'] },
  { name: 'Universiti Sultan Zainal Abidin', hint: 'UniSZA', aliases: ['UniSZA', 'Sultan Zainal Abidin University'] },

  // --- Malaysian private universities (IPTS) commonly attended ---
  { name: 'Universiti Tunku Abdul Rahman', hint: 'UTAR', aliases: ['UTAR', 'Tunku Abdul Rahman University'] },
  { name: 'Universiti Teknologi PETRONAS', hint: 'UTP', aliases: ['UTP', 'PETRONAS University of Technology'] },
  { name: 'Universiti Tenaga Nasional', hint: 'UNITEN', aliases: ['UNITEN', 'National Energy University'] },
  { name: 'Universiti Kuala Lumpur', hint: 'UniKL', aliases: ['UniKL', 'University of Kuala Lumpur'] },
  { name: 'Universiti Multimedia', hint: 'MMU', aliases: ['MMU', 'Multimedia University'] },
  { name: "Taylor's University", hint: "Taylor's", aliases: ['Taylors', 'Taylor College'] },
  { name: 'Sunway University', hint: 'Sunway', aliases: ['Sunway College'] },
  { name: 'UCSI University', hint: 'UCSI', aliases: ['UCSI'] },
  { name: 'Management and Science University', hint: 'MSU', aliases: ['MSU'] },
  { name: 'INTI International University', hint: 'INTI', aliases: ['INTI'] },
  { name: 'Asia Pacific University of Technology and Innovation', hint: 'APU', aliases: ['APU', 'APIIT'] },
  { name: 'International Medical University', hint: 'IMU', aliases: ['IMU'] },
  { name: 'HELP University', hint: 'HELP', aliases: ['HELP College'] },
  { name: 'SEGi University', hint: 'SEGi', aliases: ['SEGi', 'Segi'] },
  { name: 'MAHSA University', hint: 'MAHSA', aliases: ['MAHSA'] },
  { name: 'AIMST University', hint: 'AIMST', aliases: ['AIMST'] },
  { name: 'Open University Malaysia', hint: 'OUM', aliases: ['OUM'] },
  { name: 'Universiti Tun Abdul Razak', hint: 'UNIRAZAK', aliases: ['UNIRAZAK', 'Tun Abdul Razak University'] },

  // --- Foreign branch campuses in Malaysia ---
  { name: 'Monash University Malaysia', hint: 'Malaysia', aliases: ['Monash Malaysia'] },
  { name: 'University of Nottingham Malaysia', hint: 'Malaysia', aliases: ['Nottingham Malaysia'] },
  { name: 'Xiamen University Malaysia', hint: 'Malaysia', aliases: ['Xiamen Malaysia'] },
  { name: 'Heriot-Watt University Malaysia', hint: 'Malaysia', aliases: ['Heriot Watt Malaysia'] },
  { name: 'Curtin University Malaysia', hint: 'Malaysia', aliases: ['Curtin Sarawak', 'Curtin Miri'] },
  { name: 'Swinburne University of Technology Sarawak', hint: 'Malaysia', aliases: ['Swinburne Sarawak'] },

  // --- Overseas destinations popular with Malaysian students ---
  { name: 'National University of Singapore', hint: 'Singapore', aliases: ['NUS'] },
  { name: 'Nanyang Technological University', hint: 'Singapore', aliases: ['NTU Singapore'] },
  { name: 'University of Cambridge', hint: 'UK', aliases: ['Cambridge'] },
  { name: 'University of Oxford', hint: 'UK', aliases: ['Oxford'] },
  { name: 'Imperial College London', hint: 'UK', aliases: ['Imperial'] },
  { name: 'University College London', hint: 'UK', aliases: ['UCL'] },
  { name: "King's College London", hint: 'UK', aliases: ['KCL', 'Kings College London'] },
  { name: 'London School of Economics and Political Science', hint: 'UK', aliases: ['LSE'] },
  { name: 'University of Manchester', hint: 'UK', aliases: ['Manchester'] },
  { name: 'University of Nottingham', hint: 'UK', aliases: ['Nottingham'] },
  { name: 'University of Birmingham', hint: 'UK', aliases: ['Birmingham'] },
  { name: 'University of Leeds', hint: 'UK', aliases: ['Leeds'] },
  { name: 'University of Sheffield', hint: 'UK', aliases: ['Sheffield'] },
  { name: 'University of Warwick', hint: 'UK', aliases: ['Warwick'] },
  { name: 'University of Edinburgh', hint: 'UK', aliases: ['Edinburgh'] },
  { name: 'University of Melbourne', hint: 'Australia', aliases: ['Melbourne'] },
  { name: 'Monash University', hint: 'Australia', aliases: ['Monash Australia'] },
  { name: 'University of Sydney', hint: 'Australia', aliases: ['Sydney'] },
  { name: 'University of New South Wales', hint: 'Australia', aliases: ['UNSW'] },
  { name: 'University of Queensland', hint: 'Australia', aliases: ['UQ'] },
  { name: 'University of Adelaide', hint: 'Australia', aliases: ['Adelaide'] },
  { name: 'RMIT University', hint: 'Australia', aliases: ['RMIT'] },
  { name: 'Trinity College Dublin', hint: 'Ireland', aliases: ['TCD'] },
  { name: 'University of Auckland', hint: 'New Zealand', aliases: ['Auckland'] },
]
