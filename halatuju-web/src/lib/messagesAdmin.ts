/**
 * THE ADMIN CONSOLE'S WORDS — TD-360 Sprint 1 (2026-10-21).
 *
 * ⚠ **IMPORTED FOR ITS SIDE EFFECT, BY THE ADMIN LAYOUT AND THE SANDBOX LAYOUT ONLY.** The
 * `admin.*` namespace is more than half of `en.json` (2,918 keys, 49.9 kB gz on 2026-10-20) and
 * only the console reads it. Until this sprint every student, public and sponsor route downloaded
 * it anyway, inside the one English catalogue. It is now its own slice, and this module is the
 * only place that asks for it — so it travels with `app/admin/layout.tsx`, not with any page.
 *
 * What evaluating this module does, before the layout renders a single word:
 *  1. merges the English `admin` slice INTO the English catalogue (the same object, so
 *     `FALLBACK_CATALOGUE` keeps its identity and `contentLocale` is untouched) — the server render
 *     and the first client paint of every admin page therefore have every admin word;
 *  2. marks `admin` REQUIRED, so `loadCatalogue('ms' | 'ta')` waits for core AND admin, and a
 *     language switch on an admin page commits only when both are in hand;
 *  3. announces the change, so `I18nProvider` asks for the admin slice of the language ON SCREEN
 *     (only that one), and a stored-locale warm start already in the air waits for it too.
 *
 * ⚠ THE ONE NEW STATE (accepted by the owner, 2026-10-21): a staff member who browsed the public
 * site in Malay or Tamil and then opens `/admin` in the same tab. Core is in memory, the admin
 * slice is not; `t()` answers an ABSENT namespace in English until the chunk lands, then the page
 * re-renders in the reader's language. First time per tab only.
 *
 * ⚠ DO NOT IMPORT THIS FROM A COMPONENT. A component can be reused on a student route, and this
 * import would then put the admin slice back on it. `sliceReach.test.ts` proves no route outside
 * `/admin` (and the sandbox) reaches an `admin.*` key; `oneLocalePerVisitor.test.ts` names the
 * only modules allowed to import a slice.
 */
import enAdmin from '@/messages/en.json?slice=admin'
import { requireSlice } from '@/lib/messages'

requireSlice('admin', enAdmin)

export {}
