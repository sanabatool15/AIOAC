# Lane 3 notes (chat)

## 1. The confusing chat order, as reproduced (before any change)

Reproduced on 2026-11-08 with the test launcher (scripted model, mock PayPal) in system Chrome at 1440x900, goal, "No data" button, dataset approval card, Approve, then the steps. Script: `scratchpad/repro.mjs`; screenshots in `/tmp/claude-0/-home-user-AIOAC/7911dd15-399d-5960-9538-0dfae2b20d81/scratchpad/shots/before-*.png`. Order of children in the one scroll column (top to bottom), with positions in the scroll box:

| Moment | Order in the column |
|---|---|
| Data step, empty chat (`before-1-data-step.png`) | Stepper line, chat thread (goal + one assistant line), **data picker under the chat** |
| Dataset card shown (`before-2-dataset-card.png`) | Stepper, chat thread (goal, reply, "No data", approval card), **data picker below the thread** (so the picker sits between the card and the composer) |
| After Approve (`before-3-after-approve.png`) | Stepper, **step cards (dataset, "Check your data") now ABOVE the chat**, chat thread below |
| Data check done (`before-4-readiness.png`) | Stepper, dataset card, data check card, "Run the free test" card, then the chat thread |
| Free test done (`before-5-free-test.png`) | Stepper, dataset, data check, free test, "Pick your target", then the chat thread. The page was scrolled to scrollTop 578 of 1525, so the first thing on screen is the middle of a finished card, and the chat (an old thread starting with the goal message) is partly cut off under the composer |
| After a reply (`before-6-after-reply.png`) | Same, chat last and scrolled into view |

What is confusing:

1. The step cards moved from **below** the chat (data step, picker) to **above** the chat (every later step). The same kind of content jumps sides when the status changes.
2. After a few steps the cards are 700+ px tall, so the conversation is the last thing, far below the fold; with the page opened at the top you see cards first and the chat looks like history under them.
3. The newest event is not at one place: a new step card appears in the middle of the column (above the thread) while a new chat message appears at the bottom.
4. The step is announced twice: a "Step 4 of 7: ..." tag in the top bar and a plain text list of 7 labels in the column.

## 2. Layout applied (OWNER MUST CONFIRM)

One scroll column, always in this order, on every step (data step included):

1. Progress: the `Stepper` (numbered circles, check on done steps, current highlighted; "Step N of M: label" under `sm`).
2. "Current step" region: the step cards or the data picker for the project's status. This is the only place step cards ever appear.
3. "Conversation": messages top to bottom, oldest first, newest at the bottom, directly above the composer. The Thinking indicator and errors are the last items of the thread.
4. Composer fixed under the scroll area.

Scrolling: opening a page shows it from the top. A new chat message or live step scrolls the newest into view only when the reader was near the end or just sent a message (rules in `lib/scroll.ts`, unchanged). New in this lane: when the project moves to a **different step** (for example after pressing "Check my data"), the current-step region is scrolled to the top of the view so the new card is seen, not left above the fold.

Trade-off the owner should judge: with a long history of cards the conversation is below them. The alternative (cards as the last item of the thread, or a two-column layout on wide screens) was not applied because it changes more than the spec asks.

The duplicate step tag in the top bar is removed (`inline-chat.tsx` no longer passes it); `top-bar.tsx` is unchanged.

## 3. Notes for other lanes

- Lane 2: nothing needed. `TopBar` still takes `left` and `actions`; the chat no longer sends a step tag.
- Lane 4/5: `Panel` in `step-parts.tsx` still accepts the old pastel variant names (it forwards to `Card`, which aliases them). `Panel` is used by `link-panel.tsx` and `data-upload.tsx` (Lane 5); `ErrorLine`, `Row`, `useAction` are used by Lane 4 and 5 files and are unchanged.
- The step-parts `Stepper` export was renamed `ProjectStepper` (only `chat-screen.tsx` imported it).
- E2E specs: no assertion on the removed top-bar tag or the old order was found in `frontend/tests` (searched for "Step N of", "Steps", labels). `chat-position.spec.ts` (thread last child in view after a reply) still describes the new layout.

## 4. Other changes in this lane

- Stepper: `step-parts.tsx` now exports `ProjectStepper` (wraps `components/ui` `Stepper`, short labels `SHORT_STEP_LABELS` so all 7 fit in the 704 px column; full names stay in `STEP_LABELS`). It sits in a sticky strip at the top of the chat column. Under `sm` it shows "Step N of 7: label". Note for Lane 1/7: with the full labels the shared Stepper truncated every label ("Your d...") at chat width; consider showing only the current label when space is tight.
- After screenshots (scratchpad `shots/after*-*.png`) were taken at 1440 and 390 wide. At 390 the sidebar (Lane 2) still takes most of the width, so the phone view cannot be judged until Lane 2 lands.
- Migrated off deprecated names: Card variants (green/blue/peach/amber -> plain/highlight/warning), `LinkButton` for "Go to PayPal (sandbox)", Button variant `icon` -> `ghost`, `shadow-composer`/`shadow-glow`/`bg-brand-gradient` removed (agent avatar is a flat `bg-brand` dot), arbitrary `text-[..]`, `rounded-[..]`, `w-[..]`, `gap-[..]` replaced by tokens, `text-pending` removed, eyebrow label in the approval card is sentence case.
- Composer uses `FieldShell` (focus-within ring around the whole box).
- Estimates: the chat blocks no longer repeat "first signal, not a promise". The thread shows ONE `EstimateNote` when it contains a free-test or price block. Lane 4's step cards may show their own note on the same screen; if the owner wants one per screen, Lane 4 should drop theirs or the chat note should be removed.
- Thinking indicator: still the text-only one (steps list or rotating text), unchanged apart from tokens.
- Tests: `unit/chat-layout.test.ts` (region order, order independent of step, step-change scroll rule, auto-scroll rules, estimate-note rule, stepper). `unit/scroll.test.ts` untouched and passing.
