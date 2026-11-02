/**
 * The three staff Development screens as ONE lazy chunk (student maintenance S10): Programme → Development, a
 * module's Progress, and the scholar file's Growth tab each `import()` THIS module.
 *
 * ⚠ WHY ONE CHUNK: every async chunk adds an entry to webpack's runtime chunk map, and the runtime is on EVERY
 * route — four new chunks put +0.057 kB on each student route and left /scholarship/apply 0.236 kB under its
 * line (the bundle-budget near-line refuses < 0.25). Three staff screens sharing one chunk keep the runtime two
 * entries smaller; the cost is a staff-only download of the other two screens on first open.
 */
export { default as DevelopmentAdmin } from './DevelopmentAdmin'
export { default as ModuleProgressView } from './ModuleProgressView'
export { default as ScholarGrowth } from '@/components/admin/ScholarGrowth'
