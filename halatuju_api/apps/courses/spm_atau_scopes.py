"""REVIEWED SCOPES FOR MOHE's "ATAU" (Bumi coverage Sprint D2) — data, not code.

A Syarat Khas that says "X ATAU Y" is a choice between alternatives, but the scraped text is flat
(`scrape_mohe_stpm.clean_modal_text` strips every tag), so it cannot say how many clauses each
alternative spans: "A- in English ATAU B+ in English. B in Arabic." may be (A-) or (B+), then
Arabic for everyone — or (A-) or (B+ AND Arabic). The parser (`spm_syarat.parse_requirements`)
therefore reads an ATAU ONLY through an entry here, and flags the row otherwise. Never guess one.

Each entry: course id -> one list per ATAU chain, giving the NUMBER OF CLAUSES in each alternative,
in text order. [[1, 1, 1]] = "A ATAU B ATAU C", one clause each; [[1, 2]] = "A ATAU (B AND C)".
The parser checks the scope against the text (every ATAU covered, each later alternative starts at
its ATAU) and flags the row when it does not fit.

SOURCE: each programme's Syarat modal HTML (`modalSyarat/A/<code>`), read 2026-10-29. The modal
numbers the requirements every applicant must meet as `<li>` items and prints each alternative
OUTSIDE the list, as `<div>` / bare text with a centred `<p>ATAU</p>` between; an alternative runs
from its ATAU to the next `<li>` or the next ATAU. That layout is the evidence for each count:
  UY0000004  li(C in Kimia/Fizik/Biologi) ATAU div(A in Sains) ATAU text(B in Sains Tambahan),
             then li(two more)                                                   -> [[1, 1, 1]]
  UY0000007  li(A- in English) ATAU text(B+ in English) text(B in an Arabic subject), then
             li(two more) — so the Arabic clause belongs to the second alternative -> [[1, 2]]
  UM0221002  three li, then div(B in THREE sciences) ATAU div(B in TWO Islamic) div(B in TWO
             others)                                                             -> [[1, 2]]
  UQ0010002  li(C in one of a long list) ATAU div(C in Maths / Add Maths)        -> [[1, 1]]
  UE4811004  li(C in Sains Tambahan / Sains) ATAU div(E in Kimia/Biologi/Fizik)  -> [[1, 1]]
A re-scrape whose text changes is re-read the same way before its entry is kept.
"""

ATAU_SCOPES = {
    'UY0000004': [[1, 1, 1]],
    'UY0000007': [[1, 2]],
    'UM0221002': [[1, 2]],
    'UQ0010002': [[1, 1]],
    'UE4811004': [[1, 1]],
}
