/*
 * Paints the person's theme BEFORE the first pixel (Layer 1 F1).
 *
 * ⚠ THIS RUNS AS A RENDER-BLOCKING SCRIPT IN <head>, AND THAT PLACEMENT IS THE FEATURE.
 * A person's Light/Dark/Auto choice lives on their ACCOUNT, which arrives with the session — long
 * after first paint. Resolve it in React and someone who chose dark watches a white page turn dark
 * on every single navigation. So the device's cached copy is read synchronously here, ahead of
 * everything, and the account reconciles afterwards.
 *
 * It sets ONE attribute; `globals.css` does the rest. That is why changing mode costs no re-render
 * and cannot lose a half-filled form when the device flips at sunset.
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
