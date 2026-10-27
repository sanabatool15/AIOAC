"""Proves: the live Hugging Face search still works and returns hits, and the hand-checked curated list loads.
Read-only public HTTP calls (HF_TOKEN optional).

Run: RUN_REAL=1 pytest tests/real/test_datasets_live.py -v -s
"""


def test_huggingface_search_returns_hits(real_settings):
    from app.integrations.datasets.huggingface import HuggingFaceSource

    hits = HuggingFaceSource(real_settings.hf_token).search("customer churn", limit=3)
    print([h.id for h in hits])
    assert hits and all(h.id for h in hits)


def test_curated_list_loads(real_settings):
    from app.integrations.datasets.curated import load_curated

    items = load_curated()
    assert len(items) >= 1
