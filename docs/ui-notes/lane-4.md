# Lane 4 notes (steps and money screens)

## For Lane 5 (confirm-dialog.tsx)
- Stop run (`training-step.tsx`) and Cancel run (`quote-step.tsx` PayStep) now use `ConfirmDialog` with its current props only: `title`, `body`, `confirmLabel`, `busyLabel`, `onConfirm`, `onCancel`.
- Wanted but not available: a custom label for the cancel button. The old inline boxes said "Keep going" / "Keep it"; the dialog says "Cancel". Suggest an optional `cancelLabel` prop.
- e2e relies on: role `alertdialog` named "Stop the run" (the title), confirm button "Yes, stop now". Keep the title as the accessible name when moving onto `Modal`.
- `onConfirm` must be allowed to resolve without throwing when the caller handles the error itself (Stop does this and shows the error under the card).

## For Lane 7
- New pure logic: `lib/money-summary.ts` (Cap / Held / Charged, hold phases) and `lib/chart-scale.ts` (0 to 100 axis); tests in `unit/money-summary.test.ts`.
- Shared pieces added inside Lane 4 files: `MoneyTriplet` and `ScoreChart` in `step-cards.tsx`.
- No deprecated aliases left in the nine owned files (gradients, shadow aliases, arbitrary sizes, old Card/Tag variants, `track=`).
- Billing keeps a real table at `md` and up (column header "Total charged" is asserted by `tests/project-pages.spec.ts`); under `md` it is a card list.
- Text that e2e asserts and that changed: "WHAT HAPPENED TO THE MONEY" is now the sentence-case heading "What happened to the money" (Playwright text match is case-insensitive); "The most you can ever be charged (the cap)" is now the Cap caption in the Cap / Held / Charged summary instead of a table row. No spec edits were needed.
- `Panel` and `Stepper` in `step-parts.tsx` (Lane 3 file) still use old Card variant names and `text-pending`.
