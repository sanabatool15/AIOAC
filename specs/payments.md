# Payments (PayPal)

Sandbox only. No real money, cards or PayPal passwords at any point.

Model: **"Forecast, then verify".** This is the final money design (2026-10-26). It replaces "charge the cap, then refund".

Implementation detail comes from PayPal's own documentation and OpenAPI schemas. This file describes behavior and guarantees. Endpoint and field names were checked against `developer.paypal.com/api/{orders,payments}/v2/schema.json` on 2026-10-26 and live in `providers/payments/paypal.py`.

## 1. Guarantees

1. **Paid work starts only after the server confirms the hold.** The browser's success screen is not proof.
2. **The ledger never changes.** It is append-only; corrections are new entries.
3. **Webhooks are idempotent.** A repeated webhook can never credit or charge twice.
4. **Every job has a hard cap.** Compute is never captured above the compute cap, and total captures never exceed the hold.
5. **The user always pays the compute for the full run**, whether the target is met or missed. The success fee is charged only if independent verification passes. Never "pay $0 if the target is missed" (see `LESSONS.md`).
6. **Our failure costs the user $0.** A bug or an infrastructure error voids the whole hold.
7. **Every capture and void carries an idempotency key.** Repeating one can never move money twice.

## 2. Flow

1. **Free baseline** (as before).
2. **Free pilot.** A small, cheap test on about 5-10% of the user's data (never the locked rows). It tries a few model types and drops weak ones early (successive halving). The user pays nothing.
3. **Forecast.** The customer sets a **target**: the accuracy they want, in plain words "X out of 100 right". A learning curve from the pilot predicts the full-run result with a band and a confidence, for example "an estimated 78% chance of reaching 80 out of 100 right". Everything is an estimate. If confidence is below `forecast_min_confidence` (0.60), or there is too little data, the run is **not sold**: the "Not eligible" state (screen 28) shows an honest reason. See section 2a for what the agent does then.
4. **Quote.** One fixed price for the full run: estimated compute + a success fee of 5% of compute, and a hard cap (compute cap + maximum success fee, where the maximum fee is 5% of the compute cap). The user approves it. Text: "You pay compute either way. The success fee only if the target is verified."
5. **PayPal hold** for the cap. Nothing is charged yet. The server confirms the hold with PayPal after the buyer approves.
6. **Full run.** Training uses only the work rows. Afterwards the model is scored **once** on a locked test set it never saw. This runs before any money moves.
7. **Settle.**
   - Capture the actual compute (never above the compute cap), always.
   - Capture the success fee only if verification passed. The fee is 5% of the actual compute, never above the maximum fee the hold carries.
   - Void whatever is left on the hold.
   - If the job fails on our side (training error, verification error, lost worker), void everything.
8. **Result screen** shows forecast and verified result side by side.
9. **Target missed:** "you paid compute only, no success fee". The best model is kept and a free-pilot "Improve" round is offered (the project reopens at the pilot step; a new quote needs a new hold).

A user stop mid-run captures the compute used so far and skips the fee (no verification). A cancel before the run voids the whole hold.

## 2a. When the forecast is too low (decided 2026-10-26)

If the forecast cannot support the target, the agent does not just refuse. In plain words it:

1. explains the data issues behind the forecast (for example too few rows, a lopsided answer column, noisy columns);
2. asks the customer for the **lowest result they would accept**;
3. offers a **suggested target** that we can honestly sell (an estimate, not a promise);
4. can re-run the free pilot against the new target, which costs nothing.

A "change of engineering approach" (trying different data preparation or model families to lift the forecast) is **to be designed** with the owner. It is not specified or built.

A user stop mid-run captures the compute used so far and no fee (see section 2). Our own failure still voids everything.

## 3. State machine (`payment_holds.state`)

```
none -> held -> compute_captured -> ( fee_captured | fee_skipped ) -> released
other end states: voided (our failure or cancel), expired, declined
```

- `none`: the order exists, the buyer has not approved, nothing is held.
- `held`: the server confirmed the hold. `verified` is set only here.
- Each step is saved before the next, so settle can resume after a crash or a PayPal outage without moving money twice.
- Capture rule: amount <= held. A capture on a hold that is voided or fully captured is refused. The remainder is voided after the captures; a void of a hold that was already fully captured is refused.
- `expired`: a hold nobody trained on is marked expired after `hold_ttl_hours` (24).

## 4. Data

- `payment_holds` (was `payments`): hold amount, `compute_amount_cents`, `fee_amount_cents`, `state`, authorization and capture ids, captured and released amounts.
- `forecasts(job_id, confidence, band_low, band_high, predicted_metric)` plus target, eligibility, reason and the pilot details. A job is a project.
- `quotes` gain `compute_cap_cents`, `fee_cents`, `forecast_id`. `estimate`, `low`, `high` and `cap` include the fee.
- Ledger kinds: `compute_capture` and `fee_capture`, positive amounts charged to the buyer. A void moves no money and is recorded on the hold.

## 5. Confirmation sources

The server's own calls to PayPal are the source of truth for the hold and for every capture. The webhook is a cross-check: a signed event for a capture we made is recorded once; an event for a capture we did not make is traced and ignored. A webhook can never create a hold or mark a project paid. Webhook authenticity is verified before anything is trusted. (PayPal's authorization-related webhook event names were not found in the published schema, so none are used.)

## 6. API (one id for chat, job and agreement: the project id)

There is one internal id, the project id. `/chats/{id}`, `/jobs/{id}` and `/agreements/{id}` are route aliases for it, not separate records.

- `POST /chats/{id}/pilot` body `{target}`: free pilot and forecast.
- `GET /jobs/{id}/forecast`
- `POST /agreements/{id}/quote`: refused (409, with the reason) unless the forecast is eligible.
- `POST /projects/{id}/quote/approve`, `POST /payments/orders` (creates the hold order), `POST /payments/{id}/authorize` (server confirms the hold), `GET /payments/{id}` (receipt: held, compute captured, fee captured, released), `POST /projects/{id}/train`, `POST /projects/{id}/cancel`, `POST /projects/{id}/settle/retry`.

## 7. Interface and test double

`PaymentProvider`: `create_hold`, `authorize_order`, `capture(authorization_id, amount, request_id)`, `void(authorization_id, request_id)`, `verify_webhook`, `parse_webhook`. There is a PayPal sandbox implementation and an in-memory mock that enforces the same limits (no capture above the hold, none after a void, same request id returns the first result). All tests of caps, captures and voids run on the mock.

## 8. Human review

Payment code, webhook verification, the ledger and spend caps are reviewed by a person before they are considered done. Changes there are kept small and explained.

## 9. Status

Built and tested on the mock and on mocked HTTP. **Not yet run against the real sandbox:** buyer approval, authorize, a partial capture for compute, a second capture for the fee on the same hold, void of the remainder after captures, and the webhook. PayPal may limit how many captures one authorization takes and how long a hold lasts; check both there. Funding a project (crowdfunding) is out of scope and was removed.
