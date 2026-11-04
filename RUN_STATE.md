# RUN_STATE — HalaTuju autonomous run

## Grant
Owner, 2026-11-04: "Yes, push TD-481. Then continue as a run: T5c on your own. Ask me before each deploy."

- Scope: T5c (team tables, permissions) only.
- Every deploy is asked first. A push deploys, so nothing is pushed to main without the owner's yes.

## Sprint cursor
- TD-481: done and live (main 307d204c; api halatuju-api-01249-zqp, web halatuju-web-01078-pgb).
- T5c: in progress on branch `t5c` in worktree `.worktrees/t5c`.
  - P1: committed at 42101dc0. Fresh review pending.
  - P2: building.
  - P3 and P4: next.

## Stops waiting on the owner
- **Programmes landing choice.**
  - Option 1: admins land on the existing Organisation overview; reviewers and qc unchanged. Lead recommends this.
  - Option 2: a new page for all users. Needs a Stitch prototype first.
- **TD-487 and TD-488 rulings** (from the TD-481 adversarial review).
- **Mentors list key ruling** (TD-489).

## Open risks
- T5c changes permissions. The owner's phone check comes before it goes live.
