# Retrospective — External Links & MOHE Sprint (2026-03-14)

## What Was Built

1. **MOHE ePanduan integration** — `mohe_url` field on StpmCourse, auto-generated URL pattern for all 1,113 STPM courses, Selenium-based dead link validator, MOHE scraper for catalogue auditing
2. **Course-level "More Info" links** — Contextual external links on course detail pages: MOHE for UA/STPM, MOE for matric/form 6/PISMP, institution hyperlink for TVET
3. **Institution website links** — Institution cards now link to the institution's own website (not course-level hyperlink). 27 IPG campus URLs + 1 KKom URL populated.
4. **ILJTM/ILKBS filter split** — Search API resolves TVET → ILJTM/ILKBS using pathway_map; filter dropdown shows them as separate options
5. **Security hardening** — Default-deny permissions, 401 for unauthenticated, SECRET_KEY/CORS guards
6. **API consistency** — DRF status constants, SupabaseAuthentication class
7. **Refactoring** — EligibilityCheckView business logic extracted to eligibility_service.py (310 → 100 lines)

## What Went Well

- **Selenium URL validation was the right call.** HTTP status checks are useless for MOHE (always returns 302→200). Checking rendered page content ("daripada 0 carian") correctly identified 1 dead link out of 1,113.
- **Cross-referencing scraper vs validator.** Both approaches independently confirmed: 1 dead URL (UJ6521004), 0 missing courses. High confidence in data integrity.
- **Course-level vs institution-level link distinction.** Clean separation: About section "More Info" links to external portal (course-level), institution card "More Info" links to institution website. Pattern works consistently across all 7 source types.
- **Tech debt sprints paid off.** 17/52 items resolved. Security posture significantly improved. Code is more maintainable.

## What Went Wrong

1. **Assumed MOHE URLs were broken without testing.**
   - Symptom: Claimed MOHE URLs "always return 200 and are useless" based on HTTP status.
   - Root cause: Tested with httpx (checks HTTP response), not a browser (checks rendered content). MOHE is server-rendered and always returns 200, but the page content correctly filters courses.
   - Fix: Rewrote validator to use Selenium. Lesson: for server-rendered portals, always check rendered output, not HTTP status.

2. **IPG campus URL guesses were 5/27 wrong.**
   - Symptom: 5 IPG URLs returned 404 or redirect loops.
   - Root cause: Guessed URL patterns from a few known examples (ipgk{initial}.moe.edu.my). IPG naming is inconsistent — some use campus initials, some use location abbreviations, one uses acronym.
   - Fix: User provided the correct URLs from the IPGM website. Lesson: never guess institution URLs — scrape the authoritative listing page.

3. **MOHE scraper JS card parser returned 0 results initially.**
   - Symptom: `execute_script` card parser found no elements.
   - Root cause: DOM structure didn't match the assumed CSS selectors.
   - Fix: Switched to regex on `body.text` to extract course codes. Lesson: for fragile DOM structures, prefer text-based extraction over CSS selectors.

## Design Decisions

- **Selenium over Playwright for validation**: Playwright MCP couldn't launch because Chrome was already running. Selenium with headless Chrome is simpler for CLI tools anyway.
- **Course-level URL computed in frontend**: `courseInfoUrl` is computed client-side from `courseId` prefix and `sourceType`. Could be moved to backend, but the logic is trivial and avoids an API change.
- **Search limit 10000**: Removed the 100-cap to show all results. Acceptable because the total course count is ~1,500. Will need pagination if data grows significantly.

## Numbers

- Tests: 407 passing (was 406)
- MOHE URLs validated: 1,113 (1 dead, 1,112 alive)
- Institution URLs populated: 28 (27 IPG + 1 KKom)
- Tech debt items resolved: 17/52 (TD-001, TD-002, TD-004, TD-007, TD-008, TD-010, TD-011, TD-012, TD-015, TD-017, TD-018, TD-019, TD-020, TD-033, TD-036, TD-038, TD-044, TD-045, TD-050)
- Deploys: API rev 00090, Web building
