/**
 * Chip S1 landing (2026-11-28): the cockpit's document viewer loads as its own chunk, and only
 * while a document is open (the viewer's own render condition). Jest cannot measure kilobytes
 * (`npm run bundle-budget` does), so the import lines are pinned.
 */
import { readWeb } from '@/test/sourceGuard'

describe('the document viewer arrives on demand', () => {
  it('the view imports the lazy wrapper, mounts it only while a document is open, and takes only the TYPE from the viewer', () => {
    const view = readWeb('src/app/admin/scholarship/[id]/view.tsx', 'the cockpit view whose first-load budget this pays for')
    expect(view).toContain("from './view/LazyDocViewer'")
    expect(view).toMatch(/\{viewerDoc && <LazyDocViewer /)
    expect(view).not.toMatch(/^import (?!type)[^\n]*'@\/components\/DocViewer'/m)
  })

  it('the wrapper owns a LITERAL import() of the viewer and stays quiet while it loads', () => {
    const lazy = readWeb('src/app/admin/scholarship/[id]/view/LazyDocViewer.tsx', 'the lazy boundary itself')
    expect(lazy).toMatch(/import\('@\/components\/DocViewer'\)/)
    expect(lazy).not.toMatch(/^import (?!type)[^\n]*'@\/components\/DocViewer'/m)
    expect(lazy).toContain('quiet: true')
  })

  it('the drawer takes only the viewer TYPE, so it does not pull the viewer back into the route', () => {
    const drawer = readWeb('src/app/admin/scholarship/[id]/view/DocumentsDrawer.tsx', 'the drawer that opens the viewer')
    expect(drawer).not.toMatch(/^import (?!type)[^\n]*'@\/components\/DocViewer'/m)
  })
})
