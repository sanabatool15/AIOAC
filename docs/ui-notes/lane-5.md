# Lane 5 notes (project pages, welcome, auth)

- **Logo:** `sidebar.tsx` builds its mark inline. I added `components/shell/logo.tsx` (`<Logo />`, flat brand square with "A" plus wordmark, same markup as the sidebar) and used it on the auth screen. Lane 2: replace the inline mark in `sidebar.tsx` with `<Logo />` (or move it to `components/ui` if you prefer).
- **ConfirmDialog:** props unchanged (`title, body, confirmLabel, busyLabel, onConfirm, onCancel, requireText, requireCheck`). Render it only while open, as before. It is now an `alertdialog` on `Modal`: Cancel gets first focus, Esc and backdrop click do not close it while busy or (backdrop) at all. Lane 4 can use it for Stop and Cancel run.
- **ShareDialog** is a `dialog` on `Modal`; the Stop sharing confirm stacks on top of it (Esc closes the top one only). `tests/sharing.spec.ts` text "SHARING IS OFF" was changed to "Sharing is off" (heading text is now sentence case, shown as a Tag).
- **Auth:** password show/hide button has the accessible name "Show characters" / "Hide characters" on purpose: a name containing "password" would make `getByLabel("Password")` in the e2e specs ambiguous.
- **TopBar:** my screens pass a `<p>` or `<nav>` as `left`, not an `h2`, so each page has one h1 (from `PageHeader`). Lane 2 owns `top-bar.tsx`; other screens may still pass an `h2` there.
- **Project detail:** one Open chat link (header). The Overview card no longer has a second "Go to the chat" button. Overview now shows the full goal as a row; headings clamp it to two lines and the breadcrumb truncates it (`lib/goal.ts`, `truncateGoal`). One `EstimateNote` on Overview only.
- `Panel` in `step-parts.tsx` (used by data-upload and link-panel) still lists the old Card variant names in its prop type; Lane 3/4 can tidy it.
- `Tabs` (lazy variant) is used on the project page; History and Activity keep their own loading, error, empty and retry states.
