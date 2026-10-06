# Retrospective — the design sandbox (Config roadmap, Sprint 1)

**Date:** 2026-07-28
**Deliverable:** `/sandbox` — real components, invented data, no repo access, no real people.
**Verification:** 1120 jest / 73 suites · i18n 4258 × 3 · both builds (route absent by default,
present with the flag) · browser-checked, console clean.

---

## Why this sprint exists

Suresh wants his UI/UX team shaping our screens. The owner's reason for *not* handing over the
repository was the sharpest thing said in planning: *"Suresh's team may have the enthusiasm today,
but this may not last. And we don't want to end up with a broken system."*

A sandbox is the smallest thing that lets an outside team work hands-on while the system stays
ours. It also happens to be the review surface every later sprint needs — TD-194 means the console
still cannot be driven locally.

## The bug worth keeping

The sandbox has its own provider stack, written specifically to omit `AuthProvider`, because that
provider mints an **anonymous Supabase user on mount** and a page handed to outsiders must not
create real auth rows.

It minted them anyway. The first browser check showed two 401s against `/auth/v1/signup`.

The sandbox layout nests inside the **root** layout, whose `<Providers>` mounts the real
`AuthProvider` above everything. Writing a clean stack for my subtree removed nothing — the
provider was still there, one level up, doing exactly what I had excluded it for.

**The generalisation:** when a component must not run somewhere, gate it *at the component*, not by
declining to mount it in your own tree.

It was caught by reading the console on a screen whose entire purpose is to touch nothing real. No
test would have found it, and there is now a test.

## A one-line fix I deliberately didn't take

`isPrivilegedConsolePath()` already makes the student auth stack inert on `/admin` and `/sponsor`.
Adding `/sandbox` to that array would have worked today and been wrong: that predicate is read
elsewhere as a statement about privileged consoles, and a sandbox is not one.

It became `isAnonymousAuthSuppressed()` — composing the console rule with the sandbox rule, each
with its reason written down. Same family as the 2026-07-15 surface-partition incident, where a
display rule and a security rule were confused and the cost arrived later.

## Compiled out, not hidden

The obvious implementation is one route plus `notFound()` on an env check. That ships the fixtures
and the stubbed `fetch` to every production visitor and merely declines to render them.

Instead the pages are named `page.sandbox.tsx`, and that extension is only a route when
`NEXT_PUBLIC_SANDBOX` is set. A default build contains no sandbox route and no sandbox code —
verified by grepping the build's own route table in both directions.

*A runtime guard answers "can they see it". A build-time one answers "is it there".*

## What keeps it honest

Four properties, all mechanical, because this is handed to people outside the organisation and
"remember not to" is not a control:

1. **Typed fixtures.** Written against the real interfaces, so a payload change breaks the build.
   It earned this on its first run — `tsc` caught four missing `ConsentStatus` fields before the
   file was ever executed.
2. **Mounts, never markup.** A test asserts every product import comes from the app's own modules.
3. **No real people.** No NRIC-shaped digits, every email on a `.invalid` domain, no live-roster
   names. Identity numbers render `XXXXXX-XX-XXXX`, which is unmistakable in a screenshot.
4. **Provider parity.** A test compares the sandbox's stack against the app's and fails on drift,
   minus the two exclusions — because `tsc` cannot see that gap.

## Deliberately not done

One surface (Documents) is mounted, not five. The mounting pattern is what needed proving; adding
surfaces is now cheap and can follow what Suresh's team actually asks to see. No editing in the
sandbox — that is Sprint 5, and it needs Layer 0 underneath it to mean anything.

## Owner step

The sandbox is **built but not deployed**. It needs a second Cloud Run service, and a decision on
whether the URL should be private (Cloud Run IAM, not code) — which also decides how it reaches
Suresh's team.
