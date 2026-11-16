/**
 * H8: the sample-document map. Every document type the server knows (except "other") has a drawn sample,
 * the file is really in public/, and no drawing sits there unused.
 */
import * as fs from 'fs'
import * as path from 'path'

import { DOC_TYPES } from '@/lib/scholarship'
import { SAMPLE_FILE, sampleFor, samplePath } from '@/lib/docSamples'
import { pyChoiceValues, readApi } from '@/test/apiSource'

const PUBLIC = path.resolve(__dirname, '..', '..', '..', 'public')
const onDisk = (name: string) => fs.existsSync(path.join(PUBLIC, 'samples', `${name}.svg`))
const SERVER_TYPES = pyChoiceValues(readApi('apps/scholarship/models/documents.py'), 'DOC_TYPES')

describe('sampleFor', () => {
  it('read the server list (parse sanity)', () => {
    expect(SERVER_TYPES.length).toBeGreaterThanOrEqual(19)
    expect(SERVER_TYPES).toContain('other')
  })

  it.each(SERVER_TYPES.filter((d) => d !== 'other'))('%s has a sample whose file exists in public/', (docType) => {
    const name = sampleFor(docType)
    expect(name).toBeTruthy()
    expect(onDisk(name as string)).toBe(true)
    expect(samplePath(name as string)).toBe(`/samples/${name}.svg`)
  })

  it('"other" and unknown types have none', () => {
    expect(sampleFor('other')).toBeNull()
    expect(sampleFor('no_such_type')).toBeNull()
  })

  it('every type the web lists is covered', () => {
    for (const d of DOC_TYPES) expect(sampleFor(d)).toBeTruthy()
  })

  it('a parent IC shows the MyKad sample; income proofs show their own', () => {
    expect(sampleFor('parent_ic')).toBe('mykad')
    expect(sampleFor('ic')).toBe('mykad')
    expect(sampleFor('salary_slip')).toBe('payslip')
    expect(sampleFor('epf')).toBe('epf_statement')
    expect(sampleFor('str')).toBe('str')
    expect(sampleFor('bank_statement')).toBe('bank_statement')
    expect(sampleFor('income_support_doc')).toBe('income_support_doc')
  })

  it('higher results picks the Matriculation drawing only for matric', () => {
    expect(sampleFor('higher_results', 'matric')).toBe('higher_results_matric')
    expect(sampleFor('higher_results', 'stpm')).toBe('higher_results_stpm')
    expect(sampleFor('higher_results')).toBe('higher_results_stpm')
    expect(onDisk('higher_results_matric')).toBe(true)
  })

  it('every drawing in public/samples is used by the map', () => {
    const used = new Set([...Object.values(SAMPLE_FILE), 'higher_results_matric'])
    const files = fs.readdirSync(path.join(PUBLIC, 'samples')).filter((f) => f.endsWith('.svg')).map((f) => f.slice(0, -4))
    expect(files.sort()).toEqual([...used].sort())
  })
})
