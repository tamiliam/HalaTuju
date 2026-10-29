import {
  SPM_SUBJECTS,
  SPM_CORE_SUBJECTS,
  SPM_STREAM_POOLS,
  SPM_ALL_ELECTIVE_SUBJECTS,
  SPM_PREREQ_STREAM_POOLS,
  SPM_PREREQ_COMPULSORY,
  SUBJECT_NAMES,
  getSubjectName,
} from '../subjects'

// The Pendidikan Islam elective plus the 13 Islamic-studies subjects (Bumi Sprint C, owner ruling
// 2026-10-28: ordinary SPM subjects, open to anyone, no religion question).
const ISLAMIC_KEYS = [
  'islam', 'tasawwur_islam', 'pqs', 'psi', 'usul_aldin', 'al_syariah', 'manahij',
  'lughah_arabiah', 'adab_balaghah', 'hifz_alquran', 'maharat_alquran',
  'turath_islamiah', 'turath_quran_sunnah', 'turath_bahasa_arab',
]

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
  it('Arts pool covers the full official Arts list (38 entries; Islamic studies are electives)', () => {
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

  it('Islamic-studies subjects are electives, never stream subjects (no merit-pool mirror)', () => {
    const streamIds = new Set([
      ...SPM_STREAM_POOLS.science, ...SPM_STREAM_POOLS.arts, ...SPM_STREAM_POOLS.technical,
    ].map(s => s.id))
    ISLAMIC_KEYS.forEach(id => expect(streamIds.has(id)).toBe(false))
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
  it('mirror the stream pools and add a vocational pool; Islamic studies stay electives', () => {
    expect(SPM_PREREQ_STREAM_POOLS.arts).toEqual(SPM_STREAM_POOLS.arts)
    expect(SPM_PREREQ_STREAM_POOLS.technical).toEqual(SPM_STREAM_POOLS.technical)
    expect(SPM_PREREQ_STREAM_POOLS.vocational.map(s => s.id)).toContain('pertanian')
    const prereqStreamIds = new Set(Object.values(SPM_PREREQ_STREAM_POOLS).flat().map(s => s.id))
    ISLAMIC_KEYS.forEach(id => expect(prereqStreamIds.has(id)).toBe(false))
  })
})

describe('Islamic-studies subjects in grade entry (Bumi Sprint C)', () => {
  it.each(ISLAMIC_KEYS)('%s is selectable on the SPM grades form', id => {
    // the grades page offers SPM_ALL_ELECTIVE_SUBJECTS minus core and the stream picks
    expect(SPM_ALL_ELECTIVE_SUBJECTS.map(s => s.id)).toContain(id)
  })

  it.each(ISLAMIC_KEYS)("%s is selectable in the STPM page's SPM block", id => {
    // SpmResultsBlock's elective pool: SPM_ALL_ELECTIVE_SUBJECTS minus the four compulsory
    // subjects and the stream picks — replicated here as the grades page test above does.
    const taken = new Set([...SPM_PREREQ_COMPULSORY.map(s => s.id), 'phy', 'chem'])
    expect(SPM_ALL_ELECTIVE_SUBJECTS.filter(s => !taken.has(s.id)).map(s => s.id)).toContain(id)
  })

  it('names each subject as the result slip prints it', () => {
    const bm = (id: string) => getSubjectName(id, 'ms')
    expect(bm('tasawwur_islam')).toBe('Tasawwur Islam')
    expect(bm('pqs')).toBe('Pendidikan Al-Quran dan Al-Sunnah')
    expect(bm('psi')).toBe('Pendidikan Syariah Islamiah')
    expect(bm('manahij')).toBe("Manahij Al-'Ulum Al-Islamiah")
    expect(bm('lughah_arabiah')).toBe("Al-Lughah Al-'Arabiah Al-Mu'asirah")
    expect(bm('adab_balaghah')).toBe('Al-Adab Wa Al-Balaghah')
    expect(bm('turath_islamiah')).toBe('Turath Dirasat Islamiah')
    expect(bm('turath_quran_sunnah')).toBe('Turath Al-Quran dan Al-Sunnah')
  })

  it('no subject name carries a religion label', () => {
    ISLAMIC_KEYS.forEach(id => {
      const { bm, en } = SUBJECT_NAMES[id]
      expect(`${bm} ${en}`).not.toMatch(/muslim|agama/i)
    })
  })
})
