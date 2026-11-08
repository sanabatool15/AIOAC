"""Postgres refuses the bare token NaN in a JSON column; SQLite accepts it, so tests on SQLite never caught it.
Every JSON column goes through the engine's serializer, which writes strict JSON (null instead of NaN)."""
import json
import math

from sqlalchemy import JSON, Column, Integer, MetaData, Table, insert, select

from app.db.session import build_engine, json_dumps


def test_json_dumps_turns_nan_and_infinity_into_null():
    out = json_dumps({"contact": float("nan"), "x": [1.5, float("inf"), {"y": float("-inf")}], "ok": 2, "s": "NaN"})
    assert json.loads(out) == {"contact": None, "x": [1.5, None, {"y": None}], "ok": 2, "s": "NaN"}
    assert "NaN" not in out.replace('"NaN"', "") and "Infinity" not in out  # strict JSON: no bare tokens


def test_json_dumps_keeps_normal_values():
    value = {"a": 1, "b": 0.25, "c": None, "d": [True, "x"], "e": {"f": -3}}
    assert json.loads(json_dumps(value)) == value


def test_engine_stores_nan_as_null_in_a_json_column():
    eng = build_engine("sqlite://")
    t = Table("t_json", MetaData(), Column("id", Integer, primary_key=True), Column("body", JSON))
    t.create(eng)
    with eng.begin() as c:
        c.execute(insert(t).values(id=1, body={"row": {"contact": float("nan"), "age": 30.0}}))
    with eng.connect() as c:
        body = c.execute(select(t.c.body)).scalar()
    assert body == {"row": {"contact": None, "age": 30.0}}
    assert not math.isnan(body["row"]["age"])
