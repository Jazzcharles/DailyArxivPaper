from __future__ import annotations

import datetime as dt
from pathlib import Path

from .arxiv import fetch_by_id, fetch_recent
from .config import AppConfig, load_runtime_env, repo_root
from .content import choose_source
from .models import Paper
from .site import build_site
from .store import PaperStore
from .summarizer import summarize_with_openai, summarize_without_api


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def is_recent_for_daily(paper: Paper, now: dt.datetime, window_hours: int) -> bool:
    if not paper.published:
        return True
    try:
        published = dt.datetime.fromisoformat(paper.published.replace("Z", "+00:00"))
    except ValueError:
        return True
    return published >= now - dt.timedelta(hours=window_hours)


def enrich_papers(papers: list[Paper], cfg: AppConfig, api_key: str | None) -> None:
    limit = max(cfg.summarize_max_papers, 0)
    for index, paper in enumerate(papers):
        if paper.summary:
            continue
        if index >= limit:
            continue
        source_used, source_text = choose_source(paper, cfg)
        paper.source_used = source_used
        paper.source_text_chars = len(source_text)
        if api_key:
            try:
                paper.summary = summarize_with_openai(
                    paper, source_text, source_used, api_key, cfg
                )
                continue
            except Exception as exc:
                paper.summary = summarize_without_api(paper, source_used, cfg)
                paper.summary.status = f"api_failed: {exc.__class__.__name__}"
                continue
        paper.summary = summarize_without_api(paper, source_used, cfg)


def run_daily(cfg: AppConfig, build_public_site: bool = True) -> dict:
    now = utc_now()
    env = load_runtime_env()
    store = PaperStore(cfg.data_path)
    incoming = fetch_recent(cfg, now)
    existing = store.load_papers()
    visible = [
        paper
        for paper in incoming
        if is_recent_for_daily(paper, now, cfg.daily_window_hours)
    ]
    to_enrich: list[Paper] = []
    for paper in visible:
        old = existing.get(paper.id)
        if old and old.summary:
            paper.summary = old.summary
            paper.source_used = old.source_used
            paper.source_text_chars = old.source_text_chars
        else:
            to_enrich.append(paper)
    enrich_papers(to_enrich, cfg, env.get("OPENAI_API_KEY"))
    latest_papers = store.replace_papers(visible, existing)
    payload = {
        "generated_at_utc": now.isoformat(timespec="seconds"),
        "category": cfg.category,
        "keywords": cfg.keywords,
        "fetch_window_hours": cfg.fetch_window_hours,
        "daily_window_hours": cfg.daily_window_hours,
        "match_count": len(visible),
        "new_or_recent_papers": [paper.to_dict() for paper in visible],
        "tracked_paper_count": len(latest_papers),
        "storage_mode": "latest_overwrite",
    }
    store.save_latest_run(payload)
    if not store.favorites_path.exists():
        store.save_favorites([])
    if build_public_site:
        build_site(cfg.data_path, cfg.public_path)
    return payload


def add_favorite(
    arxiv_id: str, cfg: AppConfig, tags: list[str] | None = None, note: str = ""
) -> dict:
    now = utc_now()
    store = PaperStore(cfg.data_path)
    paper = fetch_by_id(arxiv_id, cfg, now)
    if not paper:
        raise RuntimeError(f"Paper not found: {arxiv_id}")
    favorites = [item for item in store.load_favorites() if item.get("id") != paper.id]
    favorite = {
        "id": paper.id,
        "title": paper.title,
        "abstract": paper.abstract,
        "authors": paper.authors,
        "abstract_url": paper.abstract_url,
        "html_url": paper.html_url,
        "pdf_url": paper.pdf_url,
        "url": paper.abstract_url,
        "tags": tags or [],
        "note": note,
        "added_at": now.isoformat(timespec="seconds"),
    }
    favorites.insert(0, favorite)
    store.save_favorites(favorites)
    build_site(cfg.data_path, cfg.public_path)
    return favorite


def remove_favorite(arxiv_id: str, cfg: AppConfig) -> bool:
    store = PaperStore(cfg.data_path)
    favorites = store.load_favorites()
    kept = [item for item in favorites if item.get("id") != arxiv_id]
    store.save_favorites(kept)
    build_site(cfg.data_path, cfg.public_path)
    return len(kept) != len(favorites)


def search_favorites(query: str, cfg: AppConfig) -> list[dict]:
    q = query.lower()
    store = PaperStore(cfg.data_path)
    results = []
    for favorite in store.load_favorites():
        blob = " ".join(
            [
                favorite.get("id", ""),
                favorite.get("title", ""),
                favorite.get("note", ""),
                " ".join(favorite.get("tags", [])),
            ]
        ).lower()
        if q in blob:
            results.append(favorite)
    return results


def load_config_from_repo(config_path: Path | None = None) -> AppConfig:
    return AppConfig.load(config_path or repo_root() / "config.json")
