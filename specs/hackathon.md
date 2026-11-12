# PayPal AI Hackathon: Rules, Fit and Submission Checklist

Status: written 2026-11-12 (deadline day). This file is about the contest, not the product. Product behaviour lives in the other specs. The deep write-up for the Devpost form is `docs/SUBMISSION.md`.

## 1. Source quality (read this first)

| Fact | Source | Confidence |
|---|---|---|
| Name "Build What's Next with PayPal and AI", runs online, Devpost at `paypalaihackathon.devpost.com` | PayPal developer blog (read 2026-11-12) | High |
| Only fundamental requirement: the project must meaningfully use both PayPal and AI. No set tracks or problem statements | PayPal developer blog | High |
| Submissions open Oct 1, close Nov 12, 2026. Winners announced Dec 21, 2026 | PayPal developer blog | High for dates, **no time or timezone on the blog** |
| Prize list (section 3) | PayPal developer blog | High |
| Deadline "12:00 pm PT", judging Dec 1 to 15, two-stage judging, five equal criteria, public repo with visible licence, YouTube video under 3 minutes | Third-party listings (internshala, startupgrantsindia, reconscribe, tierones, devgrantsdaily) | **Medium. Not confirmed on Devpost** |

The Devpost pages (`/` and `/rules`) answered HTTP 403 to our automated fetch, so the rules text was **not read directly**. Before submitting, a human must open the Devpost Rules tab and check: the exact cutoff time, the required form fields, the video rules, and the judging criteria wording. CLAUDE.md already uses "Nov 12, 12:00 pm PT" as the deadline; treat that as the working assumption and submit well before it.

## 2. What judges are reported to look at (unverified, from listings)

Stage One is a pass/fail fit check (does the project really use PayPal and AI, and does it work). Stage Two scores five equally weighted criteria:

| Criterion | How AIOAC answers it |
|---|---|
| Technical implementation | Real PayPal Orders v2 authorize, two captures, void; server-confirmed hold; idempotency keys; append-only ledger; real SageMaker job with a hard cap enforced by AWS; about 500 offline tests; live sandbox lifecycle test |
| Design | One path, plain words, seven steps, no ML jargon, approval card before every paid step |
| Potential impact | Non-experts get a trained model without an ML engineer; the user can never be charged more than they approved |
| Innovation | Hold for the cap, capture actual compute only, success fee only if verified on locked test rows, void the rest. Forecast before the price |
| Presentation | Under-3-minute video, README, `docs/SUBMISSION.md` |

## 3. Prizes worth targeting

Grand: $12,000 / $8,000 / $5,000. Honorable mentions, $5,000 each: Most Creative, Most Impactful, Best Demo Delivery, **Best Use of PayPal + AI**, Best Use of Agentic Commerce. A team can reach one main prize plus sponsor prizes (Render, AG Grid, APIMatic, Bryntum, Channel3). Sponsor prizes need that sponsor's product in the project. AIOAC uses none of them today, so do not claim them.

Best fit: **Best Use of PayPal + AI** and **Best Use of Agentic Commerce**. Be careful with the second one: the agent here proposes and ordinary code disposes. The agent cannot spend money. State that as a design choice, not as autonomous payments.

## 4. Submission checklist

Items marked (owner) cannot be done by the code or by Claude.

- [ ] Public GitHub repo, MIT `LICENSE` visible in the About box (owner: check the GitHub sidebar shows "MIT license")
- [ ] README has setup, run steps and sandbox test instructions (done: `README.md`; re-read on a clean clone)
- [ ] Working demo path. No hosted URL exists, so the repo must run from the README (judges "may never run the code")
- [ ] Text description on Devpost (draft in `docs/SUBMISSION.md` sections 1 to 9)
- [ ] "Built with" tool list (draft in `docs/SUBMISSION.md` section 10)
- [ ] Public YouTube video under 3 minutes (owner). Script in `docs/SUBMISSION.md` section 11
- [ ] Screenshots / image gallery (list in `docs/SUBMISSION.md` section 12)
- [ ] Explain how PayPal is used and how AI is used, in plain text (done in README and submission doc)
- [ ] Nothing secret committed: run a secret scan on the repo before making it public (owner: `.env` is git-ignored, `.env.example` has placeholders only)
- [ ] Project stays free and open to judges until judging ends (reported rule; do not put the demo behind a paywall)
- [ ] Submit at least a few hours before the cutoff

## 5. Honesty rules for the write-up

These follow CLAUDE.md hard rules 2 and 7 and the status in `specs/status.md`.

1. Say "PayPal sandbox" everywhere. Never imply real money moved.
2. Do not say the full paid cycle ran in a browser against real PayPal and real SageMaker unless the owner did it (README lists it as not yet done, finding F2). What is proven: the sandbox hold lifecycle (2026-11-02), real capped SageMaker jobs (2026-10-30 and 2026-11-01), the full flow on the mock payment double and in browser tests.
3. The PayPal webhook has never run live. Say so, or leave it out of claims.
4. Do not promise model accuracy. Forecasts are estimates.
5. Prices are placeholders checked against one small real job. A real small job costs about 0.4 cents of AWS compute; the app quote is about 53 cents because the 50 cent platform fee dominates.
6. Tabular data only, 50,000 rows / 50 MB, one CPU instance type. ML task type work (regression and others) is in progress on this branch (`specs/ml-tasks/`); describe classification as the shipped path.
7. Do not claim sponsor-prize tools (AG Grid, Render and so on) unless used.
