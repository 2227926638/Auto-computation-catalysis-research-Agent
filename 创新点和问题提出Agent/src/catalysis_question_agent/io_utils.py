from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable

from pydantic import BaseModel


def ensure_parent(path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def write_json(path: str | Path, obj: object) -> Path:
    p = ensure_parent(path)
    with p.open("w", encoding="utf-8") as f:
        json.dump(_to_jsonable(obj), f, ensure_ascii=False, indent=2)
    return p


def write_jsonl(path: str | Path, rows: Iterable[object]) -> Path:
    p = ensure_parent(path)
    with p.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(_to_jsonable(row), ensure_ascii=False) + "\n")
    return p


def write_csv(path: str | Path, rows: list[dict[str, object]]) -> Path:
    p = ensure_parent(path)
    fieldnames = sorted({key for row in rows for key in row.keys()})
    with p.open("w", encoding="utf-8-sig", newline="") as f:
        if not fieldnames:
            f.write("")
            return p
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: _cell(v) for k, v in row.items()})
    return p


def write_text(path: str | Path, text: str) -> Path:
    p = ensure_parent(path)
    with p.open("w", encoding="utf-8") as f:
        f.write(text)
    return p


def model_rows(items: Iterable[BaseModel], exclude: set[str] | None = None) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for item in items:
        data = item.model_dump(mode="json")
        if exclude:
            for key in exclude:
                data.pop(key, None)
        rows.append(data)
    return rows


def _cell(value: object) -> object:
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return value


def _to_jsonable(obj: object) -> object:
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    if isinstance(obj, list):
        return [_to_jsonable(item) for item in obj]
    if isinstance(obj, dict):
        return {key: _to_jsonable(value) for key, value in obj.items()}
    return obj
