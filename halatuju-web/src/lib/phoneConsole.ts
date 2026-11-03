/**
 * The CONSOLE's phone classes (Mobile M7a) — rule 15 and the tab rule for admin screens only. Kept OUT of
 * `phoneSection.ts`, which every student page imports: a constant there ships to every student route whether it
 * is used or not (measured: the M7a classes rode on /scholarship/apply until they moved here).
 *
 * ⚠ Tailwind reads these literals from this file (its `content` covers `src/**`), so they must stay whole strings.
 */
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
