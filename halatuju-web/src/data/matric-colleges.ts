export interface MatricCollege {
  id: string
  name: string
  state: string
  tracks: ('sains' | 'sains_komputer' | 'kejuruteraan' | 'perakaunan')[]
  phone: string
  website: string
}

export const MATRIC_COLLEGES: MatricCollege[] = [
  { id: 'kmp', name: 'KM Perlis', state: 'Perlis', tracks: ['sains', 'perakaunan'], phone: '04-9868613', website: 'kmp.matrik.edu.my' },
  { id: 'kmk', name: 'KM Kedah', state: 'Kedah', tracks: ['sains', 'perakaunan'], phone: '04-9286100', website: 'kmk.matrik.edu.my' },
  { id: 'kmpp', name: 'KM Pulau Pinang', state: 'Pulau Pinang', tracks: ['sains', 'perakaunan'], phone: '04-5756090', website: 'kmpp.matrik.edu.my' },
  { id: 'kmpk', name: 'KM Perak', state: 'Perak', tracks: ['sains', 'sains_komputer', 'perakaunan'], phone: '05-3594449', website: 'kmpk.matrik.edu.my' },
  { id: 'kms', name: 'KM Selangor', state: 'Selangor', tracks: ['sains', 'perakaunan'], phone: '03-31201410', website: 'kms.matrik.edu.my' },
  { id: 'kmns', name: 'KM Negeri Sembilan', state: 'Negeri Sembilan', tracks: ['sains', 'perakaunan'], phone: '06-4841825', website: 'kmns.matrik.edu.my' },
  { id: 'kmm', name: 'KM Melaka', state: 'Melaka', tracks: ['sains', 'perakaunan'], phone: '06-3832000', website: 'kmm.matrik.edu.my' },
  { id: 'kmj', name: 'KM Johor', state: 'Johor', tracks: ['sains', 'sains_komputer', 'perakaunan'], phone: '06-9781613', website: 'kmj.matrik.edu.my' },
  { id: 'kmph', name: 'KM Pahang', state: 'Pahang', tracks: ['sains', 'perakaunan'], phone: '09-5495000', website: 'kmph.matrik.edu.my' },
  { id: 'kmkt', name: 'KM Kelantan', state: 'Kelantan', tracks: ['sains', 'sains_komputer', 'perakaunan'], phone: '09-7808000', website: 'kmkt.matrik.edu.my' },
  { id: 'kml', name: 'KM Labuan', state: 'Labuan', tracks: ['sains', 'sains_komputer', 'perakaunan'], phone: '087-465311', website: 'kml.matrik.edu.my' },
  { id: 'kmsw', name: 'KM Sarawak', state: 'Sarawak', tracks: ['sains'], phone: '082-439100', website: 'kmsw.matrik.edu.my' },
  { id: 'kmkk', name: 'KMK Kedah', state: 'Kedah', tracks: ['kejuruteraan'], phone: '04-4682508', website: 'kmkk.matrik.edu.my' },
  { id: 'kmkph', name: 'KMK Pahang', state: 'Pahang', tracks: ['kejuruteraan'], phone: '09-4677103', website: 'kmkph.matrik.edu.my' },
  { id: 'kmkj', name: 'KMK Johor', state: 'Johor', tracks: ['kejuruteraan'], phone: '07-6881629', website: 'kmkj.matrik.edu.my' },
]
