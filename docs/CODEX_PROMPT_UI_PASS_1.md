# Codex task: UI fix pass 1 (AIOAC frontend)

Product: AIOAC, "Train with Proof. Pay for Results." PayPal AI Hackathon entry. Deadline Nov 12, 2026, 12:00 PT. Solo builder, about 4 days left.
Code: `D:\AIOAC\frontend` (Next.js 16 App Router, React 19, TypeScript, Tailwind v4, lucide-react, Geist). Backend: `D:\AIOAC\backend` (FastAPI).

## Goal
Make the UI look designed by a person, not AI-generated, and fix the UX problems below. **Fix what exists.**
No Figma. Figma is no longer the source of truth for this task. Do not rebuild screens from scratch and do not add new screens (except the small ones named here).

## Read first
`CLAUDE.md`, `LESSONS.md`, `frontend/AGENTS.md` (this Next.js has breaking changes: read `node_modules/next/dist/docs/` before touching routing or metadata), then this file.
Vendor sources for Lane 6 are in `docs/vendor/21st/` (`ai-agent-response.source.txt`, `environment-variables.source.txt`).
The Impeccable skill and its design hook are installed. Run `/impeccable init` first. If an Impeccable suggestion conflicts with the rules here, the rules here win.

## Hard rules (do not break)
- Money (never optional): PayPal Sandbox only. Hold on agreement, capture only after independent verification passes and never above the cap, void on miss/failure/cancel. The AI proposes, the backend decides spending. Never log or return secrets. **Do not change money logic, API shapes (`lib/api.ts`, `lib/adapters.ts`) or backend code** (only Part C may touch the backend).
- Honesty: no fake progress, no invented numbers or durations. Every figure shown must come from the server.
- Tokens only: colours, shadows, radii and type sizes live in `app/globals.css`. No raw hex and no raw Tailwind palette colours (`emerald-600`, `rose-300`, `violet-500`) in components. Missing style? Add a token first.
- Reuse `components/ui`. Never copy-paste styles. Plain, standard UX wording.
- Every async screen keeps loading, error, empty and retry states.
- Work on branch `feat/frontend-ui-pass`. One commit per lane. Never commit `.env` or secrets. Tell me before any destructive command.
- Keep green after every lane: `npm run lint`, `npm run typecheck`, `npm run test:unit`, `npm run test:e2e`. Never delete or weaken a test to make it pass. Update tests that assert old copy.

## Decisions already made (change only if I say so)
- One accent colour (violet), used **flat**: no gradients on buttons, tags, dots, logo, headline or avatar. No purple glow shadows.
- Cards: reduce the 7 pastel gradient variants to `plain`, `success`, `warning`, `danger`, and a quiet `highlight` (subtle tint, 1px border, small neutral shadow). Colour must carry meaning, never position.
- Tags: `neutral`, `brand`, `success`, `warning`, `danger`. Failures use `danger`/`warning`, not muted.
- Type scale tokens: title 24/600, section 16/600, body 14, small 13, micro 12. Remove all `text-[28px]` / `text-[13px]` / `text-[15px]`. Replace small-caps eyebrow labels (WHERE THIS PROJECT IS, RECEIPT, HELD...) with sentence-case headings. About 25 places.
- Radii scale: sm 6, md 8, lg 12, xl 16. Remove `rounded-[Npx]`.
- Layout width tokens (chat column, form column, page max width). Remove the hard-coded 640/680/720/560/520/380/360/820 widths.
- Contrast: all text at least 4.5:1 (`text-pending` is ~2:1 today; white on the light end of the violet gradient fails).
- Copy: "estimate, not a promise" appears about 13 times. Use one shared `EstimateNote` once per screen. Shorten long explanatory paragraphs. Keep the honest facts: sandbox/test money, a hold is not a charge, the cap.
- Open point (needs my confirmation, do not guess): the project **Chat** screen has a confusing order. Reproduce it in a browser first, write down what you see, then apply the standard chat layout: messages top to bottom, newest at the bottom directly above the composer, auto-scroll to the newest message unless I scrolled up, step cards live in one predictable place (not interleaved above and below the thread depending on the step).

## Lanes (use sub-agents). Lane 1 first, alone. Lanes 2 to 6 in parallel. Lane 7 last.
Each lane only edits the files it owns. If you need a change in another lane's file, leave a note in `docs/ui-pass-notes.md` and let that lane do it.

### Lane 1: Foundations (blocking)
Owns: `app/globals.css`, `components/ui/*`, `lib/utils.ts`.
- Rework tokens per the decisions above. Delete dead tokens/utilities (`overlay`, gradients no longer used, unused shadows). Add `--scrim: rgb(15 23 42 / 0.55)`.
- New `components/ui/modal.tsx`: dark translucent scrim over the current page, `role` dialog/alertdialog, `aria-modal`, focus trap, restore focus, body scroll lock, Esc closes (top modal only), backdrop click optional.
- New `components/ui/tabs.tsx` (roving tabindex, arrow keys, `aria-controls`), `PageHeader` (title, subtitle, actions), `EstimateNote`, `Stepper` (see Lane 3), `StatusChip`.
- `Button`: one size scale (sm, md, lg, icon), no per-call overrides like `rounded-[9px] shadow-glow`. Export a `LinkButton` so links styled as buttons stop being hand-built (see `chat-blocks.tsx`).
- `Tag`, `Card`, `EmptyState` (real lucide icons, no "·" placeholder), `ErrorState`, toast (`role="alert"` for errors).
- Visible focus ring on all inputs, including the composer wrapper (`focus-within`).

### Lane 2: Shell, navigation, responsive
Owns: `components/shell/app-shell.tsx`, `sidebar.tsx`, `top-bar.tsx`, `user-menu.tsx`, `app/(app)/layout.tsx`, `lib/nav.ts`.
- Sidebar: under `lg` it becomes a drawer. Skip-to-content link. User menu shows the same icons as the sidebar.
- Project management: "New project" "+" next to Projects, rename, delete (with the confirm dialog). **Check the backend routes first.** If rename/delete endpoints exist, wire them. If not, report that and stop. Do not fake them in the UI.
- One destination per project: decide a single primary page (chat+steps) and make `/projects/[id]` clearly secondary. Remove the duplicate "Open chat" buttons.
- Heading semantics: one `h1` per page, correct order. Per-route document titles.

### Lane 3: Chat
Owns: `project-chat.tsx`, `composer.tsx`, `inline-chat.tsx`, `chat-blocks.tsx`, `chat-screen.tsx`, `use-follow-chat.ts`, `step-parts.tsx` (Stepper), `markdown-text.tsx`.
- Fix the chat order (see open point above).
- Real visual Stepper (numbered, check on done, current highlighted; collapses to "Step 3 of 7" on small screens). Remove the duplicate step tag in the top bar.
- Replace the text-only "Thinking" with the agent trace from Lane 6 once it lands (until then keep the current one).
- Keep our safe `lib/markdown.ts` (blocks `javascript:` links). Do NOT replace it with the vendor Markdown.

### Lane 4: Steps and money screens
Owns: `step-cards.tsx`, `step-actions.tsx`, `quote-step.tsx`, `training-step.tsx`, `result-step.tsx`, `pay-return.tsx`, `billing-screen.tsx`, `usage-screen.tsx`, `fix-panel.tsx`.
- PayPal flow polish (keep all logic): a clear three-part summary of **Cap / Held / Charged** on the price and pay steps. Clear states for waiting, approved, declined, expired. Replace the inline `alertdialog` boxes (Stop run, Cancel run) with the shared confirm dialog.
- Free-test chart: replace `BAR_PX_PER_PCT` and inline heights with proportional bars on a 0 to 100 scale with an axis.
- Billing: status chip, right-aligned `tabular-nums` money, fewer jargon columns, card list on mobile instead of an 820px table. Usage tiles: colour by meaning, not by index.

### Lane 5: Project pages, welcome, auth
Owns: `project-detail.tsx`, `projects-screen.tsx`, `welcome-screen.tsx`, `auth-screen.tsx`, `home-screen.tsx`, `share-dialog.tsx`, `confirm-dialog.tsx`, `data-picker.tsx`, `data-upload.tsx`, `link-panel.tsx`.
- Use `PageHeader`, `Tabs`, `Modal`. Share and Confirm dialogs move onto `Modal` (no more `bg-overlay`).
- Home: remove the gradient headline and template look. Keep the composer and the examples.
- Auth: same logo mark as the sidebar. Password show/hide.
- Long project goals: truncate in headings, show the full text in the page body.

### Lane 6: Vendor components (from 21st.dev; adapt, do not paste)
Owns: new files `components/ui/agent-trace.tsx`, `components/ui/key-list.tsx` (+ unit tests).
**A. `docs/vendor/21st/ai-agent-response.source.txt` -> `agent-trace.tsx`**
1. The pasted source is corrupted: about a dozen string literals contain raw line breaks (around lines 455, 528, 563, 601, 652, 782, 854, 860, 878, 896, 1340). Fix them to `"\n"`.
2. Move the four keyframes (`agent-row-in`, `agent-fade`, `agent-pixel-on`, `agent-shimmer`) into `globals.css`.
3. Replace shadcn token names and raw palette colours with our tokens.
4. **Delete** its `Markdown`, `StreamingText`, `highlightCode`, `FileDiff`, `CodeBlock` and the demo. Keep `TerminalCommand` only if training logs are shown.
5. **No fake pacing.** Remove the random 1.8 to 2.2 s sentence reveal, the typing effect and invented durations. Drive everything from real events (`liveSteps` from `lib/chat-controller.ts` and the activity API). Show **steps only**, not model reasoning text.
6. Map our real steps to trace nodes with plain labels ("Searched Hugging Face", "Read your dataset", "Checked your data", "Ran the free test"). Keep the one-line group summary ("searched 3 times · read 1 file").
7. Remove `any` types and ref writes during render (lint). Respect reduced motion.
8. Wire into `project-chat.tsx` (replace `Thinking`) and the Activity tab. Coordinate through `docs/ui-pass-notes.md`.

**B. `docs/vendor/21st/environment-variables.source.txt` -> `key-list.tsx`**
1. Build and test it, but **do not wire it into a screen yet** (there is no API-keys screen; I will decide where it goes).
2. Import `cn` from `@/lib/utils` (do not install the `cn` package). Use our `Button`. Replace `@solar-icons/react` with lucide icons. Replace `@base-ui/react` Menu with a simple accessible menu (no new dependencies). Our tokens, no `shadow-card` glow.
3. **Security:** the component must never receive a full secret. Items carry `last4` only. Reveal and Copy call an async callback that fetches from the backend on click (audit-logged server-side), then auto-hide after 10 s.
4. Add/Edit use `Modal`; Delete uses the confirm dialog.

### Lane 7: QA, accessibility, tests (last)
- Playwright screenshots of every screen at 1440 px and 390 px wide. Save to `docs/ui-audit/after/`. Run `/impeccable critique` on Home, Data step, Price/Pay, Result, Billing before and after (`docs/ui-audit/before|after`).
- Contrast check on every text/background pair. Keyboard pass: tab order, focus visible, dialogs trap focus, tabs use arrows.
- Add tests: modal (scrim, Esc, focus trap/restore), tabs keyboard, chat order and auto-scroll, stepper, agent trace order, key-list masking.
- Update `docs/PROGRESS.md`. Write `DESIGN.md` with `/impeccable document` last, so it describes the new system.

## Part C (only after lanes 1 to 7 are merged and green; time-box to what fits)
Generative UI so the agent can ask answerable questions and draw charts. Library choice: `json-render` (`@json-render/core`, `@json-render/react`, `zod`). Verify exact package names and versions on npm before installing.
- Catalog (closed allow-list, Zod props): `Question` (single choice, multiple choice, number, text, yes/no), `ChoiceButtons`, `ApprovalCard` (map the existing card), `UseModelButton`, `Notice`, `Chart` (Vega-Lite), `Diagram` (Mermaid).
- Backend: an `ask_user` tool that returns a validated spec. New endpoint for answers (`POST /projects/{id}/answers` with `question_id` and `value`). The **backend validates** the value against the question's options and passes it to the agent as the next turn. Store the spec with the chat message.
- Allowed actions in a spec: send an answer, internal navigation. **No spec can trigger payment, hold, capture or void.** Money stays in the existing PayPal endpoints.
- `Chart`: agent writes a Vega-Lite spec. Validate on the server and the client: inline data only (`data.values`), no `url` data, no expressions or signals. Cap data size. `Diagram`: Mermaid with `securityLevel: "strict"`.
- Tests for the schema validation, answer validation (reject values outside the options) and rendering.

## Do not
Reintroduce gradients or glow. Add colours that are not tokens. Change money logic or API shapes. Use Figma. Add dependencies other than the Part C ones. Edit another lane's files. Skip tests.

## Report after each lane (3 lines)
done / still open / next. List anything you could not finish or had to guess.
