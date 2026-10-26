"""Real PayPal SANDBOX check of the money model: hold, two partial captures, void, repeat safety.

Two phases because the buyer must approve in a browser:
  python scripts/paypal_sandbox_check.py --phase create --yes   prints the approval link
  (open the link, log in as the sandbox BUYER account, approve)
  python scripts/paypal_sandbox_check.py --phase finish --yes   authorize, capture compute, capture fee, void, repeat checks

Amounts are tiny: hold 50c, compute capture 20c, fee capture 5c, 25c voided. Sandbox money only.
Needs PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET (and PAYMENT_PROVIDER=paypal is not required here).
`--mock` runs the same steps against the in-memory mock, to test this script itself without the network.
Secrets are never printed.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.providers.payments.base import ProviderError  # noqa: E402

HOLD, COMPUTE, FEE = 50, 20, 5
results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    results.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" - {detail}" if detail else ""))
    return ok


def attempt(name, fn, expect_error=False):
    """Runs fn. With expect_error a refusal by the provider is the PASS."""
    try:
        out = fn()
    except ProviderError as exc:
        check(name, expect_error, f"provider said: {exc}")
        return None
    if expect_error:
        check(name, False, "the provider accepted something it should refuse")
        return None
    return out


def read_authorization(p, auth_id):
    if not hasattr(p, "_request"):
        return None
    r = p._request("GET", f"/v2/payments/authorizations/{auth_id}")
    return r.json() if r.status_code == 200 else {"http_status": r.status_code}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=["create", "finish"], required=True)
    ap.add_argument("--yes", action="store_true", help="confirm you understand this moves sandbox money")
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--state", default="/tmp/paypal_check_state.json")
    a = ap.parse_args()
    print(f"Maximum this check can capture: {COMPUTE + FEE} cents of a {HOLD} cent hold (sandbox only).")
    if not a.yes:
        print("Refusing to run without --yes.")
        return 2
    if a.mock:
        from app.providers.payments.mock import MockPaymentProvider
        p = MockPaymentProvider()
    else:
        from app.providers.payments.paypal import PayPalProvider
        try:
            p = PayPalProvider()
            p._access_token()
        except ProviderError as exc:
            print(f"Sign-in failed: {exc}. Check PAYPAL_CLIENT_ID / PAYPAL_CLIENT_SECRET (sandbox app).")
            return 1
    check("sign in to the sandbox", True)
    state = Path(a.state)

    if a.phase == "create":
        order = attempt("create a hold order (intent AUTHORIZE)", lambda: p.create_hold(HOLD, "sandbox-check"))
        if not order:
            return 1
        state.write_text(json.dumps({"order_id": order.order_id}))
        print(f"\nOpen this link, log in as the sandbox BUYER and approve:\n{order.approve_url}\n"
              "Then run: python scripts/paypal_sandbox_check.py --phase finish --yes")
        return 0

    order_id = json.loads(state.read_text())["order_id"]
    key = order_id[-8:]
    auth = attempt("authorize the order after buyer approval", lambda: p.authorize_order(order_id))
    if not auth or not check("hold is placed (status held)", auth.status == "held", f"status={auth.status}"):
        print("The buyer may not have approved yet, or PayPal left it pending/declined. Nothing was captured.")
        return 1
    check("hold amount matches what we asked", auth.amount_cents == HOLD, f"{auth.amount_cents} cents")
    again = attempt("authorize again (repeat is safe)", lambda: p.authorize_order(order_id))
    check("repeat authorize returns the same hold", bool(again) and again.authorization_id == auth.authorization_id)
    aid = auth.authorization_id

    c1 = attempt("capture compute (20c) from the hold", lambda: p.capture(aid, COMPUTE, f"check-compute-{key}"))
    check("compute capture confirmed", bool(c1) and c1.confirmed)
    c2 = attempt("capture the fee (5c) from the SAME hold", lambda: p.capture(aid, FEE, f"check-fee-{key}"))
    check("fee capture confirmed (two captures on one hold work)", bool(c2) and c2.confirmed)

    c1b = attempt("repeat the compute capture with the same request id", lambda: p.capture(aid, COMPUTE, f"check-compute-{key}"))
    check("repeat returns the same capture, no second charge", bool(c1b) and bool(c1) and c1b.capture_id == c1.capture_id)

    info = read_authorization(p, aid)
    if info:
        print("   authorization after captures:", {k: info.get(k) for k in ("status", "amount")})

    v = attempt("void the rest of the hold after two captures", lambda: p.void(aid, f"check-void-{key}"))
    check("void accepted", v is not None)
    attempt("repeat the void with the same request id", lambda: p.void(aid, f"check-void-{key}"))
    attempt("capture after the void is refused", lambda: p.capture(aid, 1, f"check-late-{key}"), expect_error=True)
    info = read_authorization(p, aid)
    if info:
        print("   authorization after void:", {k: info.get(k) for k in ("status", "amount")})

    print("\nSummary: " + ("ALL PASSED" if all(ok for _, ok, _ in results) else "SOME CHECKS FAILED") +
          f" ({sum(ok for _, ok, _ in results)}/{len(results)})")
    print("Now look in the sandbox dashboard: expected total charged = 25 cents (20 compute + 5 fee), 25 cents released.")
    return 0 if all(ok for _, ok, _ in results) else 1


if __name__ == "__main__":
    sys.exit(main())
