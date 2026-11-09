"""Typed blocks for the chat screen, built by code from tool results (never from model text).

The shapes are listed in specs/api.md. All money is in cents, all rates are 0 to 1, estimates carry `is_estimate`.
"""
from ..data import families


def _unwrap(value):
    """The tools wrap dataset-derived text for the model ({"untrusted_dataset_text": ...}); the screen shows it as plain text."""
    if isinstance(value, dict) and "untrusted_dataset_text" in value:
        return value["untrusted_dataset_text"]
    return value


def _text(x, n: int) -> str:
    return " ".join(str(x).split())[:n]


def _profile_block(result: dict) -> list[dict]:
    target = _unwrap(result.get("target")) or {}
    suspects = _unwrap(result.get("suspects")) or []
    if not isinstance(target, dict) or not isinstance(suspects, list):
        return []
    return [{"type": "profile", "rows": result.get("rows"), "columns_total": result.get("columns_total"),
             "target": {"name": _text(target.get("name", ""), 80), "balance": _text(target.get("balance_text", ""), 160)},
             "suspects": [{"column": _text(x.get("column", ""), 80), "reason": _text(x.get("reason", ""), 200),
                           "strength": x.get("strength") if x.get("strength") in ("weak", "strong") else "weak"}
                          for x in suspects[:5] if isinstance(x, dict)]}]


def _clues_block(result: dict) -> list[dict]:
    clues = _unwrap(result.get("top_clues")) or []
    if not isinstance(clues, list) or not isinstance(result.get("kinds"), list):
        return []
    return [{"type": "clues", "verdict": _text(result.get("verdict", ""), 220),
             "more_data": _text((result.get("effect_of_more_data") or {}).get("text", ""), 260),
             "clues": [{"column": _text(x.get("column", ""), 80),
                        "how_much": x.get("how_much") if x.get("how_much") in ("a lot", "some", "a little") else "a little",
                        "plain_effect": _text(x.get("plain_effect", ""), 160)} for x in clues[:5] if isinstance(x, dict)],
             "note": _text(result.get("clues_note", ""), 160), "is_estimate": True}]


def _result_block(result: dict) -> list[dict]:
    if result.get("outcome") not in ("done", "stopped", "failed"):
        return []
    return [{"type": "result", "outcome": result["outcome"], "verified_out_of_100": result.get("verified_out_of_100"),
             "target_out_of_100": result.get("target_out_of_100"), "simple_guess_out_of_100": result.get("simple_guess_out_of_100"),
             "target_met": result.get("target_met"), "model_type": result.get("model_type")}]


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
                 "high_cents": high, "cap_cents": result["cap_cents"], "success_fee_cents": result["success_fee_cents"], "is_estimate": True,
                 **({"breakdown": result["breakdown"]} if result.get("breakdown") else {}),
                 **({"model_type": {"name": result["model_type"], "note": families.TYPE_NOTE}} if result.get("model_type") else {})}]
    if name == "profile_data" and "suspects" in result:
        return _profile_block(result)
    if name == "compare_models" and "kinds" in result:
        return _clues_block(result)
    if name == "explain_result":
        return _result_block(result)
    if name == "request_payment":
        return [{"type": "pay", "payment_id": result["payment_id"], "approve_url": result["approve_url"], "hold_cents": result["hold_cents"]}]
    if name == "show_table":
        return [{"type": "table", "title": result["title"], "columns": result["columns"], "rows": result["rows"]}]
    if name == "show_chart":
        return [{"type": "chart", "title": result["title"], "kind": result["kind"], "labels": result["labels"], "values": result["values"], "unit": result.get("unit", "")}]
    if name == "show_diagram":
        return [{"type": "diagram", "title": result["title"], "source": result["source"]}]
    if name == "show_links":
        return [{"type": "links", "items": result["items"]}]
    if name == "ask_choice" and result.get("options"):
        return [{"type": "choices", "question": result["question"], "options": result["options"]}]
    return []
