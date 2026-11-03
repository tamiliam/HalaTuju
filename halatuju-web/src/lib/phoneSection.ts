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
 *   * `PHONE_SECTION_FLAT` — the same plain section on a phone, for what was a borderless white card
 *     (`rounded-2xl bg-ground-0 p-5 shadow-sm` — My Bursary and its tabs): from `md` exactly that card again,
 *     with no border and no margin of its own (its parent spaces it) (Mobile M4c).
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
export const PHONE_SECTION_FLAT = 'border-b border-ground-100 py-4 md:rounded-2xl md:border-0 md:bg-ground-0 md:p-5 md:shadow-sm'
export const PHONE_ROWS = 'max-md:divide-y max-md:divide-ground-100 md:space-y-3'
export const PHONE_INNER_BOX = 'md:rounded-lg md:border md:border-ground-100 md:bg-ground-50/60 md:p-2.5'

/**
 * Mobile M7a: a hand-built UNDERLINED tab bar (the programme page, organisation settings) is the 44 px CHIPS of
 * `PanelTabs` on a phone — four tabs, so they wrap (owner: up to four tabs are chips). Added AFTER the bar's own
 * desktop classes, every one `max-md:`, so from md the underline bar is exactly what it was.
 */
export const PHONE_TAB_BAR = 'max-md:flex-wrap max-md:gap-2 max-md:border-b-0'
export const PHONE_TAB = 'max-md:mb-0 max-md:inline-flex max-md:min-h-11 max-md:items-center max-md:rounded-full max-md:border max-md:px-4 max-md:pb-0'
export const PHONE_TAB_ON = 'max-md:border-info-600 max-md:bg-brand-fill max-md:text-brand-fill-ink'
export const PHONE_TAB_OFF = 'max-md:border-ground-200 max-md:bg-ground-0'

/** Mobile M7a: the console's white card (`rounded-xl border border-ground-200 bg-ground-0 p-5` — the scholar file
 *  and its tabs) as a plain SECTION on a phone; exactly that card from md. */
export const PHONE_CARD_XL = 'border-b border-ground-100 py-4 md:rounded-xl md:border md:border-ground-200 md:bg-ground-0 md:p-5'
