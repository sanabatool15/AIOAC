"""First step of the analyzer: does the user's own text say what to predict? (plain code, no model call)

A goal like "help me predict stuff for my business" names no outcome. Searching for data then only guesses, so the
dataset search tools answer with a question to ask instead. A goal counts as clear when, after dropping filler words,
at least two different words are left (for example "customers", "cancel"). Words in any script count, so goals in
Urdu or Roman Urdu pass. This is a cheap backstop for a model that skips the written rule; it is not a language check.
"""
import re

FILLER = frozenset("""
the and for with that this these those from into onto over under about than then them they their there here have has had
will would could should can may might shall must are was were been being not but also just only very much many some any
all each every other another your you our ours mine his her its who whom whose which what when where why how
please help helps helping want wants need needs like likes use uses using used make makes made making get gets let lets
predict predicts prediction predictions predicting forecast tell know show find give try
better best good great improve improves improving improved grow growth
business businesses company companies work works working stuff thing things something anything everything
data dataset datasets record records model models artificial intelligence
yes okay sure go ahead next step carry out
""".split())

_WORD = re.compile(r"\w{3,}", re.UNICODE)

QUESTION_HINT = (
    "The goal does not say what to predict yet, so do not search. Ask the user ONE short question in plain words, for example: "
    "'What would you like to predict? For instance which customers may leave, or which loan applicants may not pay back.'"
)


def content_words(text: str) -> set[str]:
    return {w for w in _WORD.findall(str(text).lower()) if w not in FILLER and not w.isdigit()}


def is_clear(texts: list[str]) -> bool:
    words: set[str] = set()
    for t in texts:
        words |= content_words(t)
    return len(words) >= 2
