/**
 * The shapes every Programme Overview section shares. A LEAF module: it imports no section and not
 * `OverviewSections`, so a section may take these without importing the file that imports it back
 * (the import-loop guard, `lib/__tests__/importCycles.test.ts`).
 */

import type { ProgrammeOverview } from '@/lib/admin-api'

/** The translator handle, as `useT` hands it over. Passed in rather than read from the context
 *  here, so a section stays a plain function of its data and the tests can hand it a stub. */
export type Translate = (key: string, params?: Record<string, string>) => string

/** What every section is given: the whole payload (it reads only its own slice) and the words. */
export interface SectionProps {
  data: ProgrammeOverview
  t: Translate
}
