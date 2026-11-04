/**
 * PILLS ON A PHONE (Mobile M8, owner 2026-11-04, option A): the pills people see most — filter chips, tabs,
 * status badges, requirement tags — are a softly squared label (`rounded-md`, 6 px) below md instead of a fully
 * rounded end, with the side padding cut to suit the smaller radius (~8 px of width saved per pill). From md
 * nothing changes: every class here is `max-md:`, added AFTER the pill's own desktop classes.
 *
 * Pick the constant by the pill's OWN desktop side padding. A tap target keeps its `min-h-11` (rule 3); text
 * sizes are untouched. Only text labels: avatars, dots, round icon buttons, progress bars, toggles and anything
 * truly circular stay `rounded-full`. `mobileStandard.test.ts` holds the converted sites to these constants.
 *
 * ⚠ Tailwind reads these literals from this file (its `content` covers `src/**`), so they must stay whole strings.
 */
/** A count badge (`px-1.5`). */
export const PHONE_PILL_XS = 'max-md:rounded-md max-md:px-1'
/** A small badge or tag (`px-2` / `px-2.5`). */
export const PHONE_PILL_SM = 'max-md:rounded-md max-md:px-1.5'
/** A chip (`px-3`, or `pl-3 pr-2`). */
export const PHONE_PILL = 'max-md:rounded-md max-md:px-2'
/** A large tap chip or tab (`px-4`). */
export const PHONE_PILL_LG = 'max-md:rounded-md max-md:px-3'
