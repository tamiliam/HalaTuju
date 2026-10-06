# HalaTuju documentation — what lives where

Updated at the v3.0.0 release cut (2026-10-06). **Living documents** describe the system as it is
today and are kept current at every sprint close. **History** is never edited after the fact
except to fix a path.

## Living documents (read these first)

| File | What it is for |
|---|---|
| [architecture.md](architecture.md) | How the system fits together today (services, apps, data, jobs) |
| [../halatuju_api/CLAUDE.md](../halatuju_api/CLAUDE.md) | Operating manual: setup, gates, deploy, env vars, code standards, the current Next Sprint |
| [technical-debt.md](technical-debt.md) | The debt register — every TD, with the Open Items Index in working order |
| [decisions.md](decisions.md) | Every non-obvious decision and owner ruling, dated |
| [lessons.md](lessons.md) | Cross-cutting lessons learned the hard way |
| [security-posture.md](security-posture.md) | Roles, fences, RLS, secrets (by name), alerts — dated reviews |
| [code-health.md](code-health.md) | Code-health readings over time and their reviews |
| [consolidation-log.md](consolidation-log.md) | Small changes waiting for, and passed through, a Consolidation Review |
| [build-for-tenancy-conventions.md](build-for-tenancy-conventions.md) | Mandatory rules for every new piece of work (multi-tenant) |
| [roadmap.md](roadmap.md), [plans/](plans/) | Roadmaps and sprint plans (each states its own status) |
| [scholarship/](scholarship/) | The bursary programme: specs, catalogues, playbooks, cutover SQL |
| [security/](security/), [infra/](infra/) | Security SQL, monitoring definitions, Cloud Build trigger exports |
| `auth-onboarding-flow.md`, `contrast-sweep.md`, `course-data-source-inventory.md`, `reviewer-guide-content.md`, `whatsapp-*.md`, `halatuju_scholarship_landing_copy.md`, `partner-pagination-plan.md` | Reference procedures and source copy still in use |

## History (append-only)

| Folder / file | What it holds |
|---|---|
| [../CHANGELOG.md](../CHANGELOG.md) | Every change since v2.0-rc; older history in [changelog/](changelog/) |
| [sprint-history.md](sprint-history.md) | The sprint, batch and incident notes that used to fill `halatuju_api/CLAUDE.md`, word for word |
| [retrospectives/](retrospectives/) | One retrospective per sprint or release (new ones go here) |
| [releases/](releases/) | Release notes per version, and the v3.0.0 migration list |
| [archive/](archive/) | Finished one-off audits, proposals and superseded plans |
| `CHANGELOG.md` (this folder) | The pre-v2.0 course-selector changelog, kept as it was |

A new retrospective goes in `docs/retrospectives/`; a new release's notes go in `docs/releases/`.
