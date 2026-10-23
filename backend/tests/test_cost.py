import pytest

from app.services.cost import QuoteTooExpensive, estimate_quote, project_seconds


def test_projection_grows_with_rows():
    samples = [(100, 1.0), (200, 2.0), (400, 4.0)]
    secs, err = project_seconds(samples, 4000)
    assert 35 < secs < 45 and err < 0.05


def test_range_is_ordered_and_never_falsely_tight():
    q = estimate_quote([(100, 1.0), (200, 2.0), (400, 4.0)], 4000, max_cap_cents=10_000)
    assert q.low_cents <= q.estimate_cents <= q.high_cents == q.cap_cents
    assert q.high_cents > q.low_cents


def test_includes_fees_and_labels_prices():
    q = estimate_quote([(100, 0.01), (200, 0.02)], 200, max_cap_cents=10_000)
    assert q.breakdown["platform_fee_cents"] == 50 and q.breakdown["storage_cents"] == 1
    assert q.estimate_cents >= 51
    assert q.prices_version.startswith("placeholder")


def test_refuses_quote_above_job_maximum():
    with pytest.raises(QuoteTooExpensive):
        estimate_quote([(100, 100.0), (200, 400.0)], 1_000_000, max_cap_cents=700)


def test_single_sample_still_works():
    q = estimate_quote([(100, 1.0)], 1000, max_cap_cents=10_000)
    assert q.cap_cents >= q.estimate_cents
