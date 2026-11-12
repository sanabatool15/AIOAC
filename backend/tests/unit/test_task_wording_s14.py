"""Slice S14 (backend part): the agent's state block speaks each task type's own words, and a compute-only quote says so."""
import re

import pytest

from app.services.agent import context
from app.services.data import task_wording
from tests.helpers.builders import held

JARGON = re.compile(r"\b(f1|precision|recall|mae|rmse|r2|r-squared|train/test split|split|hyperparameters?|leakage|"
                    r"feature importance|silhouette|ari|isolation forest|k-means|kmeans|stability)\b", re.I)


@pytest.mark.parametrize("task", ["grouping", "unusual"])
def test_plain_words_for_the_no_answer_types(task):
    for text in (task_wording.plain_score(task, 0.82), task_wording.plain_guess(task)):
        assert not JARGON.search(text), text
    assert "an estimate" in task_wording.plain_score(task, 0.82) and "82 out of 100" in task_wording.plain_score(task, 0.82)


def test_state_block_uses_the_types_own_words_not_out_of_100_right(session, storage, chosen):
    chosen.baseline_result = {"accuracy": 0.7, "simple_guess_accuracy": 0.0, "task_type": "regression", "score": 0.7,
                              "extras": {"error": 12000, "guess_error": 40000, "unit": "$"}}
    chosen.trust_level = "Medium"
    session.commit()
    text = context.state_block(session, chosen)
    assert "off by about $12,000" in text and "out of 100 right" not in text


def test_a_compute_only_quote_does_not_mention_a_success_fee_percent(session, storage, chosen, provider):
    q, _ = held(session, storage, chosen, provider)
    q.fee_cents = 0
    session.commit()
    text = context.state_block(session, chosen)
    assert "no success fee for this kind of task" in text and "5% of compute" not in text
