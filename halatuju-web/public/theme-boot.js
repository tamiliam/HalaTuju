/*
 * Paints the person's theme BEFORE the first pixel (Layer 1 F1).
 *
 * ⚠ THIS RUNS AS A RENDER-BLOCKING SCRIPT IN <head>, AND THAT PLACEMENT IS THE FEATURE.
 * A person's Light/Dark/Auto choice is DEVICE-LOCAL (owner ruling, 2026-09-02) and lives in the
 * storage key below. Even so, anything read in React lands after first paint — so someone who chose
 * dark would watch a white page turn dark on every single navigation. It is read synchronously
 * here, ahead of everything.
 *
 * It sets ONE attribute; `globals.css` does the rest. That is why changing mode costs no re-render
 * and cannot lose a half-filled form when the device flips at sunset.
 *
 * ⚠ IT RESOLVES `auto` ONCE, at load, and that is on purpose — a head script should not hold a
 * subscription for the life of the tab. The sunset flip is `ThemeWatcher`'s job, in the React tree.
 *
 * ⚠ NO LONGER FLAG-GATED (Layer 1 F7d). Every surface is painted and the switch is reachable.
 *
 * ⚠ KEEP IN STEP WITH `src/lib/theme.ts`. A blocking head script cannot import a module, so the key,
 * the attribute and the default are spelled out twice on purpose. `src/lib/__tests__/theme.test.ts`
 * READS THIS FILE and asserts it agrees with the module — the only acceptable form of that
 * duplication is one a test refuses to let drift.
 */
(function () {
  try {
    var mode = localStorage.getItem('halatuju.theme');
    if (mode !== 'light' && mode !== 'dark' && mode !== 'auto') mode = 'auto';
    var dark = mode === 'dark' || (
      mode === 'auto'
      && typeof window.matchMedia === 'function'
      && window.matchMedia('(prefers-color-scheme: dark)').matches
    );
    document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light');
  } catch (e) {
    /* Private-mode Safari throws on localStorage read. Light is the correct fallback. */
  }
})();
