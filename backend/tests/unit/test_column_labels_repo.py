"""Repository for cached column labels, on in-memory SQLite."""
from app.repositories import column_labels as repo


def test_get_is_none_before_anything_is_saved(session):
    assert repo.get(session, "nope") is None


def test_save_then_get_returns_the_labels(session, chosen):
    vid = chosen.chosen_dataset_version_id
    assert repo.get(session, vid) is None
    repo.save(session, vid, {"a": "Label A"}, "small-model")
    assert repo.get(session, vid) == {"a": "Label A"}


def test_second_save_is_ignored_first_one_wins(session, chosen):
    vid = chosen.chosen_dataset_version_id
    repo.save(session, vid, {"a": "First"}, "m1")
    repo.save(session, vid, {"a": "Second"}, "m2")
    assert repo.get(session, vid) == {"a": "First"}
