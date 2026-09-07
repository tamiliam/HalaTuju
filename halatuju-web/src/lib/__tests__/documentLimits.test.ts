import {
  limitsFrom,
  DEFAULT_MAX_DOCS_PER_APPLICATION, DEFAULT_MAX_DOC_SIZE_MB, DEFAULT_MAX_OTHER_DOCS,
} from '../documentLimits'
import en from '@/messages/en.json'
import ms from '@/messages/ms.json'
import ta from '@/messages/ta.json'

describe('the upload limits are SERVED, not mirrored (Org Config Sprint E)', () => {
  test('the served numbers win, and MB becomes bytes exactly once', () => {
    const limits = limitsFrom({
      max_doc_size_mb: 20, max_docs_per_application: 12, max_other_docs: 2,
    })
    expect(limits).toEqual({
      maxDocSizeMb: 20,
      maxDocSizeBytes: 20 * 1024 * 1024,
      maxDocsPerApplication: 12,
      maxOtherDocs: 2,
    })
  })

  test('a payload with the fields missing falls back to the platform limits, per field', () => {
    const platform = {
      maxDocSizeMb: DEFAULT_MAX_DOC_SIZE_MB,
      maxDocSizeBytes: DEFAULT_MAX_DOC_SIZE_MB * 1024 * 1024,
      maxDocsPerApplication: DEFAULT_MAX_DOCS_PER_APPLICATION,
      maxOtherDocs: DEFAULT_MAX_OTHER_DOCS,
    }
    expect(limitsFrom(undefined)).toEqual(platform)
    expect(limitsFrom(null)).toEqual(platform)
    expect(limitsFrom({})).toEqual(platform)
    expect(limitsFrom({ max_other_docs: 3 })).toEqual({ ...platform, maxOtherDocs: 3 })
  })

  test('a nonsense size is refused on its own — never a limit that rejects every file', () => {
    // 0 would make `file.size > 0` true for every upload, so the student could send nothing at
    // all and the message would say "under 0 MB". One bad field must not poison the rest.
    expect(limitsFrom({ max_doc_size_mb: 0, max_other_docs: 3 })).toEqual({
      maxDocSizeMb: DEFAULT_MAX_DOC_SIZE_MB,
      maxDocSizeBytes: DEFAULT_MAX_DOC_SIZE_MB * 1024 * 1024,
      maxDocsPerApplication: DEFAULT_MAX_DOCS_PER_APPLICATION,
      maxOtherDocs: 3,
    })
    expect(limitsFrom({ max_doc_size_mb: -5 }).maxDocSizeMb).toBe(DEFAULT_MAX_DOC_SIZE_MB)
  })
})

describe('the upload copy states no fixed size', () => {
  // ⚠ THE COPY IS A READ SITE (the Sprint D lesson). "Each file must be under 8 MB" was a claim
  // in three languages that nothing would have updated when the limit became the organisation's.
  type Leaf = Record<string, unknown>
  const dig = (obj: Leaf, path: string[]): unknown =>
    path.reduce<unknown>((o, part) => (o as Leaf | undefined)?.[part as keyof Leaf], obj)

  it.each([['en', en], ['ms', ms], ['ta', ta]] as const)('%s', (_lang, messages) => {
    const text = dig(messages as unknown as Leaf,
      ['scholarship', 'docs', 'file_too_large']) as string
    expect(text).toContain('{mb}')
    expect(text).not.toMatch(/\b8\b/)
  })
})
