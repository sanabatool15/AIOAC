import pytest

from app.integrations.datasets.links import LinkError, parse_dataset_link


@pytest.mark.parametrize("url,expected", [
    ("https://huggingface.co/datasets/scikit-learn/churn-prediction", "hf:scikit-learn/churn-prediction"),
    ("https://huggingface.co/datasets/owner/name/", "hf:owner/name"),
    ("  https://HuggingFace.co/datasets/owner/na.me_1?x=1#top  ", "hf:owner/na.me_1"),
    ("https://archive.ics.uci.edu/dataset/350", "uci:350"),
    ("https://archive.ics.uci.edu/dataset/350/default-of-credit-card", "uci:350"),
    ("https://openml.org/d/40945", "oml:40945"),
    ("https://www.openml.org/d/40945/", "oml:40945"),
    ("https://huggingface.co:443/datasets/a/b", "hf:a/b"),
])
def test_accepts_the_three_known_places(url, expected):
    assert parse_dataset_link(url).dataset_id == expected


@pytest.mark.parametrize("url", [
    "",
    "   ",
    "http://huggingface.co/datasets/a/b",                       # not https
    "ftp://huggingface.co/datasets/a/b",
    "file:///etc/passwd",
    "javascript:alert(1)",
    "https://huggingface.co.evil.test/datasets/a/b",             # look-alike hosts
    "https://evil-huggingface.co/datasets/a/b",
    "https://huggingface.co.evil.test@huggingface.co/datasets/a/b" ,
    "https://user:pass@huggingface.co/datasets/a/b",            # credentials in the address
    "https://user@archive.ics.uci.edu/dataset/1",
    "https://huggingface.co@evil.test/datasets/a/b",
    "https://archive.ics.uci.edu.evil.test/dataset/1",
    "https://xn--hugingface-9gb.co/datasets/a/b",                # punycode look-alike
    "https://huggingfасe.co/datasets/a/b",                       # Cyrillic a
    "https://localhost/datasets/a/b",
    "https://127.0.0.1/datasets/a/b",
    "https://[::1]/dataset/1",
    "https://169.254.169.254/d/1",
    "https://10.0.0.1:443/d/1",
    "https://huggingface.co:8443/datasets/a/b",                  # other port
    "https://huggingface.co/datasets/a",                         # no dataset name
    "https://huggingface.co/datasets/a/b/c",                     # extra path
    "https://huggingface.co/models/a/b",
    "https://huggingface.co/datasets/../../a/b",
    "https://huggingface.co/datasets/a%2Fb/c",
    "https://huggingface.co/datasets/a/b\\..\\c",
    "https://archive.ics.uci.edu/dataset/abc",
    "https://archive.ics.uci.edu/ml/datasets/Iris",              # old UCI address
    "https://openml.org/d/",
    "https://openml.org/search?type=data",
    "https://example.com/data.csv",                              # a plain CSV address: never fetched
    "https://raw.githubusercontent.com/o/r/main/data.csv",
    "https://huggingface.co/datasets/a/b\nhttps://evil.test",
    "https://huggingface.co/datasets/a/b " + "x" * 400,
])
def test_refuses_everything_else(url):
    with pytest.raises(LinkError):
        parse_dataset_link(url)


def test_the_parser_never_touches_the_network(monkeypatch):
    import socket
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: (_ for _ in ()).throw(AssertionError("network used")))
    assert parse_dataset_link("https://openml.org/d/1").dataset_id == "oml:1"
    with pytest.raises(LinkError):
        parse_dataset_link("https://nonexistent.invalid/d/1")
