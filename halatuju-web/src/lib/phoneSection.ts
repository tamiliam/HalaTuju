/**
 * ONE BOX LEVEL; SECTIONS ON PHONES — the Mobile Standard's rule 15 (owner, 2026-11-02, after comparing
 * our phone screens with the Grab app). Class strings in ONE place so every student page can sweep onto
 * them (the next sprint does the rest):
 *
 *   * `PHONE_GUTTER` — the page's side gutter: 16 px on a phone, 24 px from `md`.
 *   * `PHONE_BLEED` — a bar that runs edge to edge across that gutter (the sticky action bars).
 *   * `PHONE_SECTION` — what was a card: on a phone a plain full-width SECTION (no border, no rounded
 *     corners, no padding beyond the gutter), separated from the next by a thin divider; from `md` the
 *     card it always was.
 *   * `PHONE_ROWS` — the items inside a section: divided by hairlines on a phone, never their own boxes;
 *     from `md` they keep their own spacing. ⚠ `max-md:` dividers, never `divide-y … md:divide-y-0`: Tailwind's
 *     divide selector (`> :not([hidden]) ~ :not([hidden])`) is stronger than an item's own `md:border`, so
 *     `md:divide-y-0` stripped the top and bottom borders of every box after the first from `md`, and an
 *     unprefixed `divide-ground-100` recoloured them at every width (M4b review; `mobileStandard.test.ts` pins it).
 *   * `PHONE_SECTION_NO_GAP` — the same, with no margin of its own from `md`: for a section inside a parent that
 *     already spaces its children (`md:space-y-*`, a `gap`), so the desktop keeps exactly its old spacing (M4b).
 *   * `PHONE_INNER_BOX` — a box that sat INSIDE a card (a group, a sub-panel): no box on a phone, a box
 *     from `md`. Genuine controls (inputs, buttons, chips) and coloured status callouts keep theirs.
 *
 * ⚠ Tailwind reads these literals from this file (its `content` covers `src/**`), so they must stay
 * whole strings — never assemble a class name from pieces.
 */
export const PHONE_GUTTER = 'px-4 md:px-6'
export const PHONE_BLEED = '-mx-4 px-4 md:-mx-6 md:px-6'
export const PHONE_SECTION = 'border-b border-ground-100 py-4 md:mb-4 md:rounded-2xl md:border md:bg-ground-0 md:p-5 md:shadow-sm'
export const PHONE_SECTION_NO_GAP = 'border-b border-ground-100 py-4 md:rounded-2xl md:border md:bg-ground-0 md:p-5 md:shadow-sm'
export const PHONE_ROWS = 'max-md:divide-y max-md:divide-ground-100 md:space-y-3'
export const PHONE_INNER_BOX = 'md:rounded-lg md:border md:border-ground-100 md:bg-ground-50/60 md:p-2.5'
