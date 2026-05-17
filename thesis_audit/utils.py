"""Utility helpers."""
from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger("thesis_audit")


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_stem(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", Path(name).stem).strip("_") or "document"


def json_default(obj: Any) -> Any:
    if is_dataclass(obj):
        return asdict(obj)
    if isinstance(obj, Path):
        return obj.as_posix()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def write_json(path: str | Path, data: Any) -> None:
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2, default=json_default), encoding="utf-8")
