from app.integrations.factory import build_registry
from app.integrations.datasets.registry import as_registry, single
from tests.helpers.fakes import FakeSource

SAMPLES = {"sample-churn"}


def test_prefixes_resolve_to_their_sources():
    reg = build_registry(hf=FakeSource(), uci=FakeSource(), oml=FakeSource())
    for did, prefix, local in [("hf:o/n", "hf", "o/n"), ("uci:144", "uci", "144"), ("oml:40945", "oml", "40945")]:
        r = reg.resolve(did)
        assert (r.prefix, r.local_id) == (prefix, local) and r.entry.source is not None
    assert reg.get("uci").label.startswith("UCI") and reg.get("oml").url("5").endswith("/d/5")


def test_samples_resolve_plain_or_prefixed_and_have_no_source():
    reg = build_registry()
    for did in ("sample-churn", "sample:sample-churn"):
        r = reg.resolve(did, SAMPLES)
        assert r.prefix == "sample" and r.entry is None
    assert reg.resolve("sample:other", SAMPLES) is None


def test_unknown_ids_do_not_resolve():
    reg = build_registry()
    for did in ("", "nope", "kaggle:x/y", "hf:", ":x", "good/churn"):
        assert reg.resolve(did, SAMPLES) is None


def test_a_bare_source_becomes_a_hugging_face_registry():
    src = FakeSource()
    assert single(src).resolve("hf:good/churn").entry.source is src
    reg = as_registry(src)
    assert reg.resolve("uci:144") is None and as_registry(reg) is reg
