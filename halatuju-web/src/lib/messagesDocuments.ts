/**
 * THE STUDENT DOCUMENTS TAB'S OWN WORDS — third results route S3 (2026-10-26), the TD-360 slice
 * pattern (`lib/messagesAdmin.ts`) applied to one student surface.
 *
 * ⚠ IMPORTED FOR ITS SIDE EFFECT BY `components/ScholarshipDocuments.tsx` ONLY, which is reached
 * through `components/scholarship/LazyScholarshipDocuments.tsx` (an `import()`) on
 * `/scholarship/application` and statically by the design sandbox — so these words travel with the
 * Documents tab's CHUNK and are in no route's first-load JS. WHY: every core string moves every
 * route, and the higher-results card's words had left the median 0.12 kB under its budget.
 *
 * What evaluating this module does (exactly what the admin slice does):
 *  1. merges the English `documentsTab` slice INTO the English catalogue, so the tab's first paint
 *     has every word;
 *  2. marks `documents` REQUIRED, so `loadCatalogue('ms' | 'ta')` waits for core AND this slice;
 *  3. announces it, so `I18nProvider` fetches the slice of the language ON SCREEN only — one
 *     locale per visitor still holds (`oneLocalePerVisitor.test.ts`).
 * A reader in Malay or Tamil sees the tab's new words in English for the moment that chunk is in
 * the air, the first time per tab only (the admin slice's accepted state).
 */
import enDocuments from '@/messages/en.json?slice=documents'
import { requireSlice } from '@/lib/messages'

requireSlice('documents', enDocuments)

export {}
