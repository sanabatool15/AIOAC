# Build Checklist (MoSCoW) - decided Nov 9, 2026
Rule: MUST = in the money flow or required by project rules. WON'T = no backend endpoint, or ruled out (no packages/upgrade).
Figma file u1n7fiOWgwkzWNGiWX03R8, page High Fidelity. Backend decides behaviour; Figma decides visuals.

## MUST
| Figma frame (node) | Built in | Backend | Work needed |
|---|---|---|---|
| 1 Login / sign up (76:339) | auth-screen.tsx | auth/login, signup, demo | polish only |
| 2 Chat home (76:382) | home-screen.tsx, chat-screen.tsx | projects, chat | chat order bug (needs browser check) |
| 3a Upload (76:557), 3b Paste link (76:757) | data-picker, data-upload, link-panel | data, data/link | polish |
| 4 Baseline result (76:1216) | step-cards.tsx | baseline | match Figma |
| 5 Performance agreement (76:2) | quote-step.tsx | agreements/quote | price line-items, Accept button style |
| 6 PayPal authorization (76:1558) | pay-return.tsx | payments orders, authorize | polish |
| 7 Agent working (62:1310), 10 Training (76:2216) | training-step.tsx | training, stop | ETA/stage ONLY if backend returns them |
| 12 Verified (76:2693), 13 Target missed (76:3086), 14 Receipt (76:3340) | result-step.tsx | training, payment | match Figma |
| 28 Not eligible (76:5886) | fix-panel.tsx | fix/propose, fix/apply | fix copy |
| 18 System states (76:4348) | components/ui/state.tsx | none | loading/error/empty/retry on every screen |
| 31 Confirm dialogs (76:6521) | confirm-dialog.tsx, ui/modal.tsx | cancel, stop | all stop/cancel use shared modal |

## SHOULD
- 30 Use your model (76:6300): model-tab.tsx (predict, predict-batch, download)
- 16 Projects and share (76:3589), 27 Public result (76:5819): share-dialog.tsx, public-result.tsx
- 34 Project page (76:6980), 20 User menu (76:4706), 21 Usage (76:4902), 26 Billing history (76:5467)
- 35 First run / empty states (76:7221)
- 32 Payment states (76:6708): only states the backend returns
- 11 Budget panel (76:2458): only if quote cap data is enough, else move to COULD

## COULD
- 29 Improve round (76:6092): second train call exists, screen not built
- 3c Connect an account (76:984): no real connect endpoint
- 8 Files and links tab (76:1748): could use activity/trace

## WON'T
- 17 / 17b API keys (no backend)
- 22-25 Choose a plan, 33 Payment methods (no plan endpoint; no packages/upgrade)
- 9 Live view browser/research (no backend)
- 19 Motion spec (spec, not a screen)
