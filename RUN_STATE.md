# RUN_STATE — HalaTuju autonomous run

## Grant
Owner, 2026-11-04: "Yes, push TD-481. Then continue as a run: T5c on your own. Ask me before each deploy."

- Scope: T5c (team tables, permissions) only.
- Every deploy is asked first. A push deploys, so nothing is pushed to main without the owner's yes.

## Sprint cursor
- TD-481: done and live (main 307d204c; api halatuju-api-01249-zqp, web halatuju-web-01078-pgb).
- T5c: on branch `t5c` in worktree `.worktrees/t5c`. P1-P4 built and reviewed (fresh reviews PASS, adversarial review SHIP).
  Awaiting: full gates, the owner's phone check, and deploy approval.
  - P5 = the Programmes landing. Owner ruling 2026-11-04: everyone on partner login lands on Programmes; admins see
    the other Organisation items by keys; reviewers and mentors see only Programmes, listing only the programmes
    where they have work; pick one -> Programme Overview. Stitch draft awaiting the owner's approval (project
    10844973747787673276, nodes 919496a7d36e407db96212baabb52eaa, 40a623069cd64a7b898c6db1b1f0b8ad,
    515f7bab8edf4dbc8e668ab89801f525, b370b2afe43142219f4f582927619249).

## Stops waiting on the owner
- **Programmes landing (P5): approve the Stitch draft.**
- **TD-487 and TD-488 rulings** (from the TD-481 adversarial review).
- **Mentors list key ruling** (TD-496; TD-489 on main is now the mentor-screen cards).

## Open risks
- T5c changes permissions. The owner's phone check comes before it goes live.
