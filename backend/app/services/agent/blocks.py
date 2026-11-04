"""Typed blocks for the chat screen, built by code from tool results (never from model text).

The shapes are listed in specs/api.md. All money is in cents, all rates are 0 to 1, estimates carry `is_estimate`.
"""


def blocks_from_result(name: str, result, project) -> list[dict]:
    if not isinstance(result, dict) or "error" in result:
        return []
    if name == "run_readiness":
        return [{"type": "readiness", "grade": result.get("grade"), "findings": result.get("findings", []),
                 "trust": getattr(project, "trust_level", None)}]
    if name == "run_baseline":
        return [{"type": "baseline", "accuracy": result["accuracy"], "simple_guess_accuracy": result["simple_guess_accuracy"],
                 "trust": result.get("trust_level")}]
    if name == "create_quote":
        low, high = result["range_cents"]
        return [{"type": "quote", "quote_id": result["quote_id"], "estimate_cents": result["estimate_cents"], "low_cents": low,
                 "high_cents": high, "cap_cents": result["cap_cents"], "success_fee_cents": result["success_fee_cents"], "is_estimate": True}]
    if name == "request_payment":
        return [{"type": "pay", "payment_id": result["payment_id"], "approve_url": result["approve_url"], "hold_cents": result["hold_cents"]}]
    return []
