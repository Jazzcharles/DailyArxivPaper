from __future__ import annotations

import json
from pathlib import Path

from .models import Paper


def read_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


class PaperStore:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.papers_path = data_dir / "papers.json"
        self.latest_path = data_dir / "latest.json"
        self.favorites_path = data_dir / "favorites.json"

    def load_papers(self) -> dict[str, Paper]:
        rows = read_json(self.papers_path, [])
        return {row["id"]: Paper.from_dict(row) for row in rows}

    def save_papers(self, papers: dict[str, Paper]) -> None:
        ordered = sorted(
            (paper.to_dict() for paper in papers.values()),
            key=lambda row: row.get("published", ""),
            reverse=True,
        )
        write_json(self.papers_path, ordered)

    def replace_papers(self, incoming: list[Paper], cache: dict[str, Paper]) -> dict[str, Paper]:
        latest: dict[str, Paper] = {}
        for paper in incoming:
            old = cache.get(paper.id)
            if old:
                paper.first_seen_at = old.first_seen_at or paper.first_seen_at
                if old.summary and not paper.summary:
                    paper.summary = old.summary
                if old.source_used and paper.source_used == "abstract":
                    paper.source_used = old.source_used
                if old.source_text_chars and not paper.source_text_chars:
                    paper.source_text_chars = old.source_text_chars
            latest[paper.id] = paper
        self.save_papers(latest)
        return latest

    def save_latest_run(self, payload: dict) -> None:
        write_json(self.latest_path, payload)

    def load_favorites(self) -> list[dict]:
        return read_json(self.favorites_path, [])

    def save_favorites(self, favorites: list[dict]) -> None:
        write_json(self.favorites_path, favorites)
