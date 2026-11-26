/**
 * The polytechnics offered by the "Pre-U institution" picker's "Polytechnics" chip (pre-U sprint,
 * 2026-11-26).
 *
 * TODO (TD-767): EMPTY ON PURPOSE. The repo holds no list of polytechnic names: the course
 * catalogue names its institutions only in the live database, and the data files under
 * `halatuju_api/data/` carry the word "Politeknik" without a campus. Nothing was typed from
 * memory and nothing was read from live. Until the owner supplies the list (or an export of the
 * catalogue's Politeknik institutions is checked in), the chip shows only the "Not in the list?
 * Use it as typed" row, so a Diploma student still names her polytechnic in free text.
 */
export interface Polytechnic {
  name: string
  hint: string
}

export const POLYTECHNICS: Polytechnic[] = []
