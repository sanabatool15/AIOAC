# Lane 2 notes (shell, navigation, responsive)

## Done
- `AppShell`: sidebar is a fixed column from `lg` (1024px) up; below that a top bar with a menu button (`aria-expanded`, `aria-controls`) opens a drawer (`nav-drawer.tsx`: dialog, focus trap, Esc, backdrop click, scroll lock, focus returns to the button; closes on navigation). Skip-to-content link; all route content now renders inside `<main id="main-content" tabIndex={-1}>`.
- Sidebar: "+" (`New project`, `LinkButton`) next to Projects replaces the big button; flat logo; no deprecated aliases; sentence-case "Recent projects".
- User menu: same icons as the sidebar (`NAV_ITEMS[].icon`), arrow/Home/End keys, Esc handled in capture phase so an enclosing drawer does not also close.
- Per-route titles: `(app)/layout.tsx` has the template `%s | AIOAC`; each `(app)` page sets a short title (the thin page files were edited for this only). `/c/[id]` and `/projects/[id]` use static titles ("Project", "Project details") because the goal is only known after a client-side fetch.

## Project rename and delete: NOT DONE, endpoints missing
`backend/app/routes/projects.py` and `screens.py` have no PATCH/PUT/DELETE for a project (only `DELETE /projects/{id}/share`), and `lib/api.ts` has no such call. Nothing was faked in the UI. Needs a backend route plus an api call first; then add a "..." menu per sidebar row using `Modal role="alertdialog"` (or Lane 5's confirm dialog).

## Needs from other lanes
- Every screen puts a breadcrumb in `TopBar left` as an `<h2>` (projects-screen, usage-screen, billing-screen, home-screen, welcome-screen, chat-screen, project-detail...). That puts an h2 before the page's h1. Change those to `<p>` (TopBar now documents this). Screen roots are `<section aria-label>` with `h-full flex-1`; that still works inside `<main>` (it is a flex row).
- Lane 5 (`project-detail.tsx`): the "Open chat" button (line ~58) is a duplicate of the sidebar link and uses `shadow-glow`/`rounded-[9px]`; make /c/[id] the primary page and keep one clear "Back to chat" link. Make `/projects/[id]` visibly secondary.
- Lane 3/5: `Logo` is exported from `sidebar.tsx` if the auth screen wants the same mark.
- Any page that renders its own `<main>` inside the shell must switch to a `div`/`section` (none found in the shell routes).
