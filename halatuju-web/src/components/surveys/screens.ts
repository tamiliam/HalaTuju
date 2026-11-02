/**
 * The three staff Surveys screens as ONE lazy chunk (applied in student maintenance S10): Programme → Surveys, a
 * survey's Results, and the scholar file's Surveys tab each `import()` THIS module.
 *
 * ⚠ WHY ONE CHUNK: every async chunk adds an entry to webpack's runtime chunk map, and the runtime is on EVERY
 * route. S10's new lazy screens left /scholarship/apply under the bundle-budget near-line (0.247 kB of room,
 * < 0.25); folding these three staff screens into one chunk (as `development/screens.ts` does) takes two entries
 * off the runtime. The cost is a staff-only download of the other two screens on first open.
 */
export { default as SurveysAdmin } from './SurveysAdmin'
export { default as SurveyResults } from './SurveyResults'
export { default as ScholarSurveys } from '@/components/admin/ScholarSurveys'
