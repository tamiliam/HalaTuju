/**
 * Her Surveys and Growth tab bodies as ONE lazy chunk (student maintenance S10): `LazyBursarySurveys` and
 * `LazyBursaryGrowth` each `import()` THIS module, so each tab still loads only when it is first opened.
 *
 * ⚠ WHY ONE CHUNK: every async chunk adds an entry to webpack's runtime chunk map, and the runtime is on EVERY
 * route. A chunk of its own for Growth left /scholarship/apply 0.248 kB under its first-load line (the
 * bundle-budget near-line refuses < 0.25). Sharing the Surveys chunk adds no entry; the cost is that whichever
 * of the two tabs she opens first also downloads the other's body.
 */
export { default as BursarySurveys } from './BursarySurveys'
export { default as BursaryGrowth } from './BursaryGrowth'
