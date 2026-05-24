from __future__ import annotations

import json
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_QUERY_FILE = SKILL_ROOT / "tmp" / "latest_query.json"


def resolve_query_path(path=None) -> str:
    """Return the runtime query file path without reading or writing it."""
    return str(Path(path) if path is not None else DEFAULT_QUERY_FILE)


def write_latest_query(payload: dict, path=None) -> str:
    """Write the single runtime query file, overwriting previous content."""
    if not isinstance(payload, dict):
        raise ValueError("payload must be a dict")

    query_path = Path(resolve_query_path(path))
    query_path.parent.mkdir(parents=True, exist_ok=True)
    query_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return str(query_path)


def read_latest_query(path=None) -> dict:
    """Read the single runtime query file."""
    query_path = Path(resolve_query_path(path))
    if not query_path.exists():
        raise FileNotFoundError(f"query file not found: {query_path}")
    data = json.loads(query_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("query file must contain a JSON object")
    return data
