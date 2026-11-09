# UI Audit: AIOAC Frontend (`D:\AIOAC\frontend`)

Audited using the **Impeccable Design Skill** (design director lens, token fidelity, visual hierarchy, accessibility, and UX state completeness).

---

## 1. Executive Summary

* **Design System Baseline**: AIOAC enforces a clean, zero-slop token architecture in `app/globals.css` with a flat violet brand accent (`#7c3aed`), no background gradients, and strict WCAG 4.5:1 text-on-surface contrast ratios.
* **Overall Quality**: High architectural discipline. Pure separation between business adapters (`lib/screens.ts`, `lib/adapters.ts`, `lib/status.ts`) and React views.
* **Key Risk Areas**: A few isolated components (notably `public-result.tsx` and legacy button styles in `data-picker.tsx`) bypass design tokens using arbitrary Tailwind pixel values, missing focus indicators, or deprecated gradient classes.

---

## 2. Ranked Findings

### P0 — Critical (Design System Violations, Accessibility Barriers)

| ID | File Path | Finding | One-Line Fix |
|---|---|---|---|
| **P0-1** | `components/shell/public-result.tsx:21` | Logo badge uses illegal `bg-brand-gradient shadow-glow` and arbitrary pixel dimensions `size-[26px] rounded-[7px]`, violating the gradient ban in `globals.css`. | Replace with standard token classes `size-7 rounded-md bg-brand text-on-brand`. |
| **P0-2** | `components/shell/public-result.tsx:27,31,32` | Layout uses arbitrary widths and heights (`w-[720px]`, `h-[140px]`, `h-[110px]`, `pt-9`) rather than design tokens. | Replace arbitrary dimensions with `max-w-chat w-full py-8` and standard spacing tokens. |
| **P0-3** | `components/shell/public-result.tsx:44` | Retry action renders an unstyled raw `<button>` with hardcoded underline instead of accessible `<Button>`. | Replace with `<Button variant="outline" size="sm" onClick={retry}>Try again</Button>`. |
| **P0-4** | `components/shell/data-picker.tsx:25,30,38` | Data source selection tiles (`button`) lack visible focus rings on keyboard navigation (`Tab`). | Add `focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand` to button tiles. |
| **P0-5** | `components/shell/auth-screen.tsx:48` | Password visibility toggle button lacks an accessible, dynamic `aria-label`. | Add `aria-label={showPw ? "Hide password" : "Show password"}` to the toggle button. |

---

### P1 — High (Token Drift, Inconsistent Hierarchy, Semantic Gaps)

| ID | File Path | Finding | One-Line Fix |
|---|---|---|---|
| **P1-1** | `components/shell/quote-step.tsx:49,70` | Raw Tailwind type sizes (`text-sm leading-5 text-ink-2`) used instead of design token `text-body`. | Replace `text-sm leading-5` with `text-body`. |
| **P1-2** | `components/shell/training-step.tsx:44` | Inconsistent paragraph typography (`text-sm leading-5 text-ink-2`) bypassing `text-body` token. | Replace with `text-body text-ink-2`. |
| **P1-3** | `components/shell/public-result.tsx:37,42` | Uses non-standard typography token `text-xl` instead of semantic token `text-section`. | Replace `text-xl font-semibold text-ink` with `text-section text-ink`. |
| **P1-4** | `components/shell/usage-screen.tsx:25` | TopBar breadcrumb rendered as raw string literal `{"Account  /  Usage"}` rather than a semantic `<nav aria-label="Breadcrumb">`. | Replace with semantic breadcrumb navigation component matching `project-detail.tsx`. |
| **P1-5** | `components/shell/billing-screen.tsx:41` | TopBar breadcrumb rendered as raw string literal `{"Account  /  Billing history"}` rather than semantic breadcrumb. | Replace with semantic breadcrumb navigation component matching `project-detail.tsx`. |
| **P1-6** | `components/shell/model-tab.tsx:46` | "Open the project chat" renders an inline styled anchor `<a>` instead of the standard `<LinkButton>`. | Replace with `<LinkButton href={`/c/${projectId}`} variant="ghost">Open the project chat</LinkButton>`. |

---

### P2 — Medium (Visual Polish, Layout Refinements, Edge States)

| ID | File Path | Finding | One-Line Fix |
|---|---|---|---|
| **P2-1** | `components/shell/sidebar.tsx:48` | Project goal titles in sidebar rows can cause layout shift if goal text is unusually long. | Add `max-w-[170px] truncate` to sidebar project link titles with native `title` tooltip. |
| **P2-2** | `components/shell/auth-screen.tsx:68` | Fixed padding `p-16` on desktop branding split column can feel cramped on 1024px screens. | Change `p-16` to responsive scale `p-8 lg:p-12`. |
| **P2-3** | `components/shell/composer.tsx:35` | Chat composer textarea expands indefinitely on multi-line paste without max-height clamp. | Add `max-h-48 overflow-y-auto` to composer textarea. |
| **P2-4** | `components/shell/training-step.tsx:61` | Destructive "Stop training" action confirm dialog lacks explicit mention that compute incurred so far is captured. | Update confirm dialog body text to explicitly restate "Compute used so far will be charged; success fee is voided". |
| **P2-5** | `components/shell/home-screen.tsx:54` | Example prompt chips lack keyboard focus-visible styling when navigating by Tab. | Add `focus-visible:ring-2 focus-visible:ring-brand` to example chips. |

---

## 3. Recommended Fix Execution Order
1. **Patch `public-result.tsx`** (Clears P0 token violations: removes arbitrary sizes & gradient, aligns with design system).
2. **Standardize Breadcrumbs in `usage-screen.tsx` & `billing-screen.tsx`** (Aligns with `project-detail.tsx`).
3. **Normalize Typography in `quote-step.tsx` & `training-step.tsx`** (Enforces 100% token usage).
4. **Harden Focus Rings in `data-picker.tsx` & `composer.tsx`** (Full WCAG 2.1 AA keyboard accessibility).

