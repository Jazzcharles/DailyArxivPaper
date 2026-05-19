from __future__ import annotations

import argparse
import json
import sys

from .arxiv import fetch_recent
from .pipeline import (
    add_favorite,
    load_config_from_repo,
    remove_favorite,
    run_daily,
    search_favorites,
    utc_now,
)
from .site import build_site
from .store import PaperStore


def print_json(payload) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def format_daily_message(payload: dict) -> str:
    lines = [
        f"arXiv {payload['category']} daily",
        f"Matches: {payload['match_count']}",
        "",
    ]
    for paper in payload["new_or_recent_papers"]:
        summary = paper.get("summary") or {}
        lines.extend(
            [
                paper["title"],
                paper["abstract_url"],
                f"- 核心贡献: {summary.get('core_contribution', '暂无总结。')}",
                f"- 方法要点: {summary.get('method', '暂无总结。')}",
                "",
            ]
        )
    return "\n".join(lines).rstrip()


def cmd_run_daily(args: argparse.Namespace) -> int:
    cfg = load_config_from_repo()
    payload = run_daily(cfg, build_public_site=not args.no_site)
    if args.json:
        print_json(payload)
    else:
        print(format_daily_message(payload))
    return 0


def cmd_fetch(args: argparse.Namespace) -> int:
    cfg = load_config_from_repo()
    now = utc_now()
    papers = fetch_recent(cfg, now)
    payload = {
        "generated_at_utc": now.isoformat(timespec="seconds"),
        "category": cfg.category,
        "keywords": cfg.keywords,
        "match_count": len(papers),
        "papers": [paper.to_dict() for paper in papers],
    }
    if args.json:
        print_json(payload)
    else:
        print(format_daily_message({**payload, "new_or_recent_papers": payload["papers"]}))
    return 0


def cmd_build_site(args: argparse.Namespace) -> int:
    cfg = load_config_from_repo()
    build_site(cfg.data_path, cfg.public_path)
    print(f"Built site at {cfg.public_path}")
    return 0


def cmd_favorite_add(args: argparse.Namespace) -> int:
    cfg = load_config_from_repo()
    favorite = add_favorite(args.arxiv_id, cfg, args.tag or [], args.note or "")
    print(f"Favorited {favorite['id']}: {favorite['title']}")
    return 0


def cmd_favorite_remove(args: argparse.Namespace) -> int:
    cfg = load_config_from_repo()
    removed = remove_favorite(args.arxiv_id, cfg)
    if removed:
        print(f"Removed favorite {args.arxiv_id}")
        return 0
    print(f"Favorite not found: {args.arxiv_id}", file=sys.stderr)
    return 1


def cmd_favorite_list(args: argparse.Namespace) -> int:
    cfg = load_config_from_repo()
    favorites = PaperStore(cfg.data_path).load_favorites()
    if args.json:
        print_json(favorites)
        return 0
    if not favorites:
        print("No favorites.")
        return 0
    for favorite in favorites:
        tags = ", ".join(favorite.get("tags", []))
        suffix = f" [{tags}]" if tags else ""
        print(f"{favorite['id']} | {favorite['title']}{suffix}\n{favorite['url']}\n")
    return 0


def cmd_favorite_search(args: argparse.Namespace) -> int:
    cfg = load_config_from_repo()
    favorites = search_favorites(args.query, cfg)
    if args.json:
        print_json(favorites)
        return 0
    if not favorites:
        print("No favorite matches.")
        return 0
    for favorite in favorites:
        print(f"{favorite['id']} | {favorite['title']}\n{favorite['url']}\n")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="daily_arxiv_paper")
    sub = parser.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run-daily", help="Fetch, summarize, persist data, and build Pages site")
    run.add_argument("--json", action="store_true")
    run.add_argument("--no-site", action="store_true", help="Skip public site generation")
    run.set_defaults(func=cmd_run_daily)

    fetch = sub.add_parser("fetch", help="Fetch matching papers without writing data")
    fetch.add_argument("--json", action="store_true")
    fetch.add_argument("--dry-run", action="store_true", help="Kept for compatibility")
    fetch.set_defaults(func=cmd_fetch)

    site = sub.add_parser("build-site", help="Build public/ from data/")
    site.set_defaults(func=cmd_build_site)

    favorite = sub.add_parser("favorite", help="Manage persisted favorites")
    favorite_sub = favorite.add_subparsers(dest="favorite_cmd", required=True)

    favorite_add = favorite_sub.add_parser("add", help="Add a paper to data/favorites.json")
    favorite_add.add_argument("arxiv_id")
    favorite_add.add_argument("--tag", action="append")
    favorite_add.add_argument("--note")
    favorite_add.set_defaults(func=cmd_favorite_add)

    favorite_remove = favorite_sub.add_parser("remove", help="Remove a favorite")
    favorite_remove.add_argument("arxiv_id")
    favorite_remove.set_defaults(func=cmd_favorite_remove)

    favorite_list = favorite_sub.add_parser("list", help="List favorites")
    favorite_list.add_argument("--json", action="store_true")
    favorite_list.set_defaults(func=cmd_favorite_list)

    favorite_search = favorite_sub.add_parser("search", help="Search favorites")
    favorite_search.add_argument("query")
    favorite_search.add_argument("--json", action="store_true")
    favorite_search.set_defaults(func=cmd_favorite_search)

    legacy_star = sub.add_parser("star", help="Alias for favorite add")
    legacy_star.add_argument("arxiv_id")
    legacy_star.set_defaults(func=cmd_favorite_add, tag=None, note="")

    legacy_list = sub.add_parser("list", help="Alias for favorite list")
    legacy_list.add_argument("--json", action="store_true")
    legacy_list.set_defaults(func=cmd_favorite_list)

    legacy_search = sub.add_parser("search", help="Alias for favorite search")
    legacy_search.add_argument("query")
    legacy_search.add_argument("--json", action="store_true")
    legacy_search.set_defaults(func=cmd_favorite_search)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
