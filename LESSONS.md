# Lessons

Short rules we learned the hard way. Read before changing money, pricing or payment copy.

## Money model

- **Never describe or build "pay $0 if the target is missed". The user always pays compute for the full run.**
  The only $0 case is our own failure (our bug or an infrastructure error): then the whole hold is voided.
  The success fee is the only part that depends on the verified result.
- A PayPal hold is not a charge. Say "hold" and "released", never "charged" until a capture exists.
- The agent forecasts and the free pilot is free. Neither is a promise. Label every forecast and price an estimate.
- Verify before capturing. The check on the locked test set runs before any money moves, so a failure to verify (ours)
  can still void everything and the user pays $0.
- Compute is captured at the actual cost, never above the compute cap, and never more than what is held.
- A webhook can confirm a capture we made. It can never create a hold or mark a project paid.

## Process

- Do not guess PayPal endpoints, fields, error codes or event names. Check the published OpenAPI schema first.
  (Authorize, partial capture and void were checked on 2026-10-26; the webhook names for authorizations were not found
  in the schema, so no code depends on them.)
- Verify the real sandbox before calling a payment change done. Tests on the mock prove our rules, not PayPal's.
