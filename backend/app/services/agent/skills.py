"""Skills (specs/agent.md section 5): short playbooks loaded on demand, so the prompt stays small."""
from functools import lru_cache
from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parents[2] / "skills"


@lru_cache
def _load() -> dict[str, tuple[str, str]]:
    out = {}
    for f in sorted(SKILLS_DIR.glob("*.md")):
        text = f.read_text(encoding="utf-8")
        _, front, body = text.split("---", 2)
        meta = dict(line.split(":", 1) for line in front.strip().splitlines())
        out[meta["name"].strip()] = (meta["description"].strip(), body.strip())
    return out


def index() -> str:
    return "\n".join(f"- {n}: {d}" for n, (d, _) in _load().items())


def load(name: str) -> str | None:
    hit = _load().get(name)
    return hit[1] if hit else None


def names() -> list[str]:
    return list(_load())
