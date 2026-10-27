# Payments (PayPal)

Sandbox only. No real money, cards or PayPal passwords at any point.

Implementation detail comes from PayPal's own toolkit and current documentation, loaded as a repository skill. This file describes behavior and guarantees; it does not list endpoints or field names, which must be checked against the current PayPal docs before use.

## 1. Guarantees

1. **Paid work starts only after the server confirms the payment.** The browser's success screen is not proof.
2. **The ledger never changes.** It is append-only; corrections are new entries.
3. **Webhooks are idempotent.** A repeated webhook can never credit or charge twice.
4. **Every job has a hard cap.** Spending stops there.
5. **Unused money is refunded** through PayPal's refund capability.

## 2. Payment flow

1. The user approves a quote.
2. The server creates a payment order for the approved amount.
3. The user approves it in PayPal.
4. The server captures the payment and verifies it.
5. Only then is the project marked paid and training allowed.
6. When training ends, the server calculates actual cost and refunds the difference.

The amount charged is, by proposal, the cap (to confirm). The refund is cap minus actual cost.

## 3. Confirmation sources

Two independent signals can confirm a payment: the server's own capture result, and the PayPal webhook. Either confirms; both together are recorded once because of idempotency. Webhook authenticity is verified before anything is trusted.

## 4. Ledger

Each ledger entry records a signed amount, its kind (capture, usage, refund), the project it belongs to, and a unique key taken from PayPal's identifiers. The unique key is what makes repeats harmless. A project's balance is the sum of its entries.

## 5. Interface and test double

Payments sit behind a provider interface. The PayPal sandbox implementation lives in `integrations/paypal/`; the in-memory `MockPaymentProvider` lives in `doubles/payments.py` and is used only by tests and evals, never by the app. All tests of the ledger, caps and refunds run on the double, so they do not depend on credentials. The app has no mock mode: `PAYMENT_PROVIDER` defaults to `paypal`.

## 6. Stretch: funding a project

A creator can raise funds for a public project instead of paying alone. Backers contribute through PayPal; training starts only once the goal is met and the funds are confirmed. In the prototype the funding ledger is simulated and clearly labeled as such on screen. The real payment path (steps in section 2) is reused for the final training payment.

## 7. Human review

Payment code, webhook verification, the ledger and spend caps are reviewed by a person before they are considered done. Changes there are kept small and explained.

## 8. Status

The PayPal provider is tested on mocked HTTP (`tests/contract/`) and has partial real-sandbox checks (`RUN_REAL=1 pytest tests/real`, see status.md). A full buyer approval, capture and refund has not been run. The PayPal plugin is installed; its connection needs a working sandbox token.
