from pathlib import Path


class LocalStorage:
    """Folder-backed storage for development and tests. S3 comes later behind the same interface."""

    def __init__(self, root: str):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, key: str) -> str:
        p = (self.root / key).resolve()
        if self.root not in p.parents and p != self.root:
            raise ValueError("key escapes storage root")
        return str(p)

    def put(self, key: str, data: bytes) -> None:
        p = Path(self.path(key))
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def get(self, key: str) -> bytes:
        return Path(self.path(key)).read_bytes()

    def delete(self, key: str) -> None:
        Path(self.path(key)).unlink(missing_ok=True)

    def exists(self, key: str) -> bool:
        return Path(self.path(key)).exists()

    def list(self, prefix: str) -> list[str]:
        base = Path(self.path(prefix))
        if not base.exists():
            return []
        files = [base] if base.is_file() else [f for f in base.rglob("*") if f.is_file()]
        return sorted(f.relative_to(self.root).as_posix() for f in files)
