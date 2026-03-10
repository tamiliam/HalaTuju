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
