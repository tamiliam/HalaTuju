/**
 * THE DRIFT TEST for `MIN_PASSWORD_LENGTH` in `lib/adminPassword.ts` — named by its `drift-test:`
 * marker (common profile S1, 2026-10-31). The server's number is the rule; the screen's copy must
 * say the same, and both password screens must read the copy rather than a literal of their own.
 */
import * as fs from 'fs'
import * as path from 'path'
import { MIN_PASSWORD_LENGTH } from '@/lib/adminPassword'
import { readApi } from '@/test/apiSource'

it('the web minimum is the server minimum', () => {
  const m = readApi('apps/courses/supabase_admin.py').match(/^MIN_PASSWORD_LENGTH = (\d+)$/m)
  if (!m) throw new Error('drift test: MIN_PASSWORD_LENGTH is no longer an int literal in supabase_admin.py')
  expect(MIN_PASSWORD_LENGTH).toBe(Number(m[1]))
})

it.each([
  'app/admin/set-password/page.tsx',
  'components/adminProfile/SignInCard.tsx',
])('%s reads the shared constant, not a literal', (rel) => {
  const src = fs.readFileSync(path.join(__dirname, '..', '..', ...rel.split('/')), 'utf8')
  expect(src).toContain("from '@/lib/adminPassword'")
  expect(src).not.toMatch(/MIN_LEN\s*=\s*\d/)
})
