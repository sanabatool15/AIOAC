"""Replay a stored conversation without a model: python -m evals.replay <run folder> [--full]

Loads conversation.json (written next to events.jsonl by the eval runner) into a throwaway database and rebuilds the
exact messages the model was given before each of its replies. Only the conversation is replayed: the project state
block comes from a fresh project, so it shows the starting state. Use it to see what the model saw when it went wrong.
"""
import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.db.tables import Message, Project
from app.services.agent import memory

from .show import resolve


def replay(data: dict, full: bool = False) -> str:
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    out = []
    with sessionmaker(engine, expire_on_commit=False)() as s:
        project = Project(goal=data.get("goal") or "(unknown goal)")
        s.add(project)
        s.commit()
        conv = memory.import_conversation(s, project, data)
        for m in s.query(Message).filter_by(conversation_id=conv.id, role="assistant").order_by(Message.seq):
            msgs, skills, stubbed, dropped = memory.history(s, conv, upto_seq=m.seq)
            calls = ", ".join(c["function"]["name"] for c in (m.tool_calls or [])) or "a reply"
            out.append(f"--- before message {m.seq}: model sees {len(msgs)} history messages (stubbed {stubbed}, dropped {dropped}); it answered with {calls}")
            if full:
                out.append(json.dumps(msgs, indent=1, default=str))
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m evals.replay", description=__doc__.split("\n\n")[0])
    ap.add_argument("target")
    ap.add_argument("--full", action="store_true", help="print every message the model was given")
    ap.add_argument("--log-dir")
    a = ap.parse_args(argv)
    folder = resolve(a.target, Path(a.log_dir) if a.log_dir else None)
    path = folder / "conversation.json" if folder.is_dir() else folder
    print(replay(json.loads(path.read_text()), a.full))
    return 0


if __name__ == "__main__":
    sys.exit(main())
