"""The claim guard (guards.false_claims) must block false statements about money and training, and must NOT block honest
wording. Per-status phrases. The guard is a keyword check, not a security boundary: the gate stops spending."""
import pytest

from app.services.agent import guards

ALL = ["described", "data_chosen", "readiness_done", "baseline_done", "quoted", "awaiting_payment", "paid", "training",
       "done", "failed", "stopped", "voided"]

# honest in every status: free work, explanations, conditions about the future
HONEST = [
    "I've trained a quick model on your data and it got about 78 out of 100 right.",
    "I trained a small free model to get a first signal.",
    "The free test model is ready; here is what it found.",
    "Once your payment is confirmed, training starts.",
    "When the run is complete, the unused part of the hold is released.",
    "If the check passes, the success fee is charged; otherwise the hold is released.",
    "After training finishes, the model is checked once on rows it never saw.",
    "Let me start with what the data check found.",
    "I can try to explain why the result is only 70 out of 100.",
    "I'll try to put it in plainer words.",
]

# false claims, with the statuses where they would be untrue
FALSE_BEFORE_PAID = [
    "Good news, your payment was received.",
    "You have been charged for the compute.",
    "Paid training has started.",
    "Training is now running on your data.",
    "I've started the training now.",
    "I have launched training.",
]


@pytest.mark.parametrize("text", HONEST)
@pytest.mark.parametrize("status", ALL)
def test_honest_wording_is_never_blocked(text, status):
    assert not guards.false_claims(text, status), (status, text)


@pytest.mark.parametrize("text", FALSE_BEFORE_PAID)
@pytest.mark.parametrize("status", ["described", "baseline_done", "quoted", "awaiting_payment"])
def test_false_payment_and_training_claims_are_blocked_before_payment(text, status):
    assert guards.false_claims(text, status), (status, text)


@pytest.mark.parametrize("text", ["I'll run it again now.", "I will retrain it with better settings.", "Let me re-run the test.",
                                  "Do you want me to run the free small test for 99?"])
@pytest.mark.parametrize("status", ["training", "done", "failed", "stopped", "voided"])
def test_a_promise_to_run_something_is_still_blocked_where_there_are_no_tools(text, status):
    assert guards.false_claims(text, status), (status, text)


@pytest.mark.parametrize("status", ["data_chosen", "baseline_done", "quoted"])
def test_the_same_promise_is_fine_where_tools_exist(status):
    assert not guards.false_claims("I'll run the free small test now.", status)
