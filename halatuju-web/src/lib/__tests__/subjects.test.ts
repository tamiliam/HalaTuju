import {
  SPM_SUBJECTS,
  SPM_CORE_SUBJECTS,
  SPM_STREAM_POOLS,
  SPM_ALL_ELECTIVE_SUBJECTS,
  SPM_PREREQ_STREAM_POOLS,
  SUBJECT_NAMES,
  getSubjectName,
} from '../subjects'

describe('SPM_SUBJECTS model', () => {
  it('has exactly 4 core subjects', () => {
    expect(SPM_CORE_SUBJECTS.map(s => s.id)).toEqual(['bm', 'eng', 'math', 'hist'])
  })

  it('has no duplicate subject ids', () => {
    const ids = SPM_SUBJECTS.map(s => s.id)
    expect(new Set(ids).size).toBe(ids.length)
  })

  it('every non-core subject is electable', () => {
    const electable = new Set(SPM_ALL_ELECTIVE_SUBJECTS.map(s => s.id))
    SPM_SUBJECTS.filter(s => !s.core).forEach(s => {
      expect(electable.has(s.id)).toBe(true)
    })
    // core subjects are never in the elective pool
    SPM_CORE_SUBJECTS.forEach(s => expect(electable.has(s.id)).toBe(false))
  })
})

describe('Stream pools — official source coverage', () => {
  it('Arts pool covers the full non-Islamic official list (38 entries)', () => {
    expect(SPM_STREAM_POOLS.arts.length).toBe(38)
    const ids = SPM_STREAM_POOLS.arts.map(s => s.id)
    // a representative sample of the newly-added performance/language subjects
    for (const id of [
      'tarian', 'lakonan', 'seni_halus_2d', 'seni_halus_3d', 'reka_bentuk_grafik',
      'lit_tamil', 'lit_cina', 'bahasa_punjabi', 'bible_knowledge', 'music',
      'penulisan_skrip', 'sinografi', 'koreografi', 'multimedia_kreatif',
    ]) {
      expect(ids).toContain(id)
    }
  })

  it('Arts pool excludes every Islamic-stream subject', () => {
    const islamic = [
      'pqs', 'psi', 'tasawwur_islam', 'usul_aldin', 'al_syariah', 'manahij',
      'lughah_arabiah', 'adab_balaghah', 'hifz_alquran', 'maharat_alquran',
      'turath_islamiah', 'turath_quran_sunnah', 'turath_bahasa_arab', 'islam',
    ]
    const artsIds = new Set(SPM_STREAM_POOLS.arts.map(s => s.id))
    islamic.forEach(id => expect(artsIds.has(id)).toBe(false))
  })

  it('Technical pool covers the full official Science-Tech list (16 entries)', () => {
    expect(SPM_STREAM_POOLS.technical.length).toBe(16)
    const ids = SPM_STREAM_POOLS.technical.map(s => s.id)
    for (const id of [
      'eng_civil', 'eng_mech', 'eng_elec', 'eng_draw', 'gkt', 'comp_sci',
      'reka_cipta', 'kelestarian', 'pertanian', 'srt', 'sports_sci', 'addsci',
      'phy', 'chem', 'bio', 'addmath',
    ]) {
      expect(ids).toContain(id)
    }
  })

  it('sciences appear in BOTH Science and Technical pools', () => {
    for (const id of ['phy', 'chem', 'bio', 'addmath']) {
      expect(SPM_STREAM_POOLS.science.map(s => s.id)).toContain(id)
      expect(SPM_STREAM_POOLS.technical.map(s => s.id)).toContain(id)
    }
  })

  it('Multimedia is elective-only (moved out of Technical)', () => {
    expect(SPM_STREAM_POOLS.technical.map(s => s.id)).not.toContain('multimedia')
    expect(SPM_ALL_ELECTIVE_SUBJECTS.map(s => s.id)).toContain('multimedia')
  })
})

describe('Stream / elective overlap + dedup invariant', () => {
  it('a stream subject is still electable until chosen as a stream subject', () => {
    // 'tarian' lives in the Arts stream pool AND the elective pool...
    expect(SPM_STREAM_POOLS.arts.map(s => s.id)).toContain('tarian')
    expect(SPM_ALL_ELECTIVE_SUBJECTS.map(s => s.id)).toContain('tarian')

    // ...but once selected as a stream subject, the grades page excludes it
    // from the elective dropdown (replicates the elektifPool computation).
    const coreIds = SPM_CORE_SUBJECTS.map(s => s.id)
    const selectedAliran = ['tarian']
    const excluded = new Set([...coreIds, ...selectedAliran])
    const elektifPool = SPM_ALL_ELECTIVE_SUBJECTS.filter(s => !excluded.has(s.id))
    expect(elektifPool.map(s => s.id)).not.toContain('tarian')
  })
})

describe('Labels resolve for every selectable subject', () => {
  it('every selectable subject has a real SUBJECT_NAMES entry', () => {
    const pooled = [
      ...SPM_STREAM_POOLS.science,
      ...SPM_STREAM_POOLS.arts,
      ...SPM_STREAM_POOLS.technical,
      ...SPM_ALL_ELECTIVE_SUBJECTS,
    ]
    pooled.forEach(s => {
      expect(SUBJECT_NAMES[s.id]).toBeDefined()
    })
  })

  it('resolves the two newly added keys', () => {
    expect(getSubjectName('bahasa_punjabi', 'en')).toBe('Punjabi Language')
    expect(getSubjectName('bible_knowledge', 'en')).toBe('Bible Knowledge')
    expect(getSubjectName('bible_knowledge', 'ms')).toBe('Pengetahuan Bible')
  })
})

describe('STPM SPM-prerequisite pools', () => {
  it('mirror the stream pools and add a vocational pool, with no Islamic subjects', () => {
    expect(SPM_PREREQ_STREAM_POOLS.arts).toEqual(SPM_STREAM_POOLS.arts)
    expect(SPM_PREREQ_STREAM_POOLS.technical).toEqual(SPM_STREAM_POOLS.technical)
    expect(SPM_PREREQ_STREAM_POOLS.vocational.map(s => s.id)).toContain('pertanian')
    expect(SPM_PREREQ_STREAM_POOLS.vocational.every(s => !s.id.startsWith('al_'))).toBe(true)
  })
})
