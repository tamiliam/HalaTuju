'use client'

/**
 * The Profile page's cards, gathered into ONE lazily loaded chunk (common profile S1, 2026-10-31).
 *
 * ⚠ WHY ONE CHUNK AND NOT ONE PER CARD. Every lazily loaded chunk adds an entry to the webpack
 * runtime that EVERY route downloads. One chunk per card (eight) put ~0.12 kB on every route and took
 * the median to 0.127 kB under its 148 kB line (`npm run bundle-budget`, TD-427); a second chunk for
 * the heavy `QualificationsCard` alone still cost ~0.04 kB. One chunk replaces the retired
 * `SourceProfile` chunk, so the runtime is the size it was. The cost: a person without `review`
 * fetches the university list with the other cards — after first load, never in the budgeted figure.
 */
export { default as YouCard } from './YouCard'
export { default as ContactCard } from './ContactCard'
export { default as MentoringCard } from './MentoringCard'   // S7a: a mentor's area
export { default as AccessCard } from './AccessCard'
export { default as QualificationsCard } from './QualificationsCard'
export { default as AddressCard } from './AddressCard'
export { default as TakingPartCard } from './TakingPartCard'
export { default as OrganisationCard } from './OrganisationCard'
export { default as SignInCard } from './SignInCard'
