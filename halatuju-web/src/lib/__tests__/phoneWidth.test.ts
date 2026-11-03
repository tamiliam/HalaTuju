/**
 * ONE line decides "phone" in the console (Mobile M6b review): below md by width. The tab chooser's query
 * (`phoneWidth.ts`) and the document viewer's (`DocViewer.tsx`) must be the same string, and it must be md.
 */
import { PHONE_WIDTH_QUERY } from '@/lib/phoneWidth'
import { PHONE_QUERY } from '@/components/DocViewer'

it('the tab chooser and the document viewer draw the same line, below md', () => {
  expect(PHONE_WIDTH_QUERY).toBe(PHONE_QUERY)
  expect(PHONE_WIDTH_QUERY).toBe('(max-width: 767.98px)')
})
