from __future__ import annotations

import datetime as dt
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from .config import AppConfig
from .http import HttpConfig, request_with_retry
from .models import Paper

BASE_URL = "https://export.arxiv.org/api/query"
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}


def http_config(cfg: AppConfig) -> HttpConfig:
    return HttpConfig(
        timeout_seconds=cfg.request_timeout_seconds,
        attempts=cfg.retry_attempts,
        base_delay_seconds=cfg.retry_base_delay_seconds,
        max_delay_seconds=cfg.retry_max_delay_seconds,
        use_proxy=cfg.use_proxy,
    )


def build_query(category: str, from_dt: dt.datetime, to_dt: dt.datetime) -> str:
    from_str = from_dt.strftime("%Y%m%d%H%M")
    to_str = to_dt.strftime("%Y%m%d%H%M")
    return f"cat:{category} AND submittedDate:[{from_str} TO {to_str}]"


def fetch_atom(params: dict[str, str], cfg: AppConfig) -> bytes:
    url = BASE_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "daily-arxiv-paper/1.0"})
    try:
        return request_with_retry(req, http_config(cfg), "arXiv fetch")
    except Exception as exc:
        raise RuntimeError(f"Failed to fetch arXiv feed: {url}") from exc


def resource_urls(arxiv_id: str, abstract_url: str) -> dict[str, str]:
    if not abstract_url:
        abstract_url = f"https://arxiv.org/abs/{arxiv_id}"
    html_url = abstract_url.replace("/abs/", "/html/", 1)
    pdf_url = abstract_url.replace("/abs/", "/pdf/", 1)
    if pdf_url and not pdf_url.endswith(".pdf"):
        pdf_url += ".pdf"
    return {
        "abstract_url": abstract_url,
        "html_url": html_url,
        "pdf_url": pdf_url,
    }


def parse_entries(xml_bytes: bytes, now: dt.datetime) -> list[Paper]:
    root = ET.fromstring(xml_bytes)
    papers: list[Paper] = []
    now_iso = now.isoformat(timespec="seconds")
    for entry in root.findall("atom:entry", ATOM_NS):
        title = (
            entry.findtext("atom:title", default="", namespaces=ATOM_NS) or ""
        ).strip()
        abstract = (
            entry.findtext("atom:summary", default="", namespaces=ATOM_NS) or ""
        ).strip()
        id_url = (
            entry.findtext("atom:id", default="", namespaces=ATOM_NS) or ""
        ).strip()
        published = (
            entry.findtext("atom:published", default="", namespaces=ATOM_NS) or ""
        ).strip()
        updated = (
            entry.findtext("atom:updated", default="", namespaces=ATOM_NS) or ""
        ).strip()
        abstract_url = ""
        for link in entry.findall("atom:link", ATOM_NS):
            if link.get("rel") == "alternate":
                abstract_url = link.get("href") or ""
                break
        authors = []
        for author in entry.findall("atom:author", ATOM_NS):
            name = (
                author.findtext("atom:name", default="", namespaces=ATOM_NS) or ""
            ).strip()
            if name:
                authors.append(name)
        arxiv_id = id_url.rsplit("/", 1)[-1] if id_url else ""
        urls = resource_urls(arxiv_id, abstract_url or id_url)
        papers.append(
            Paper(
                id=arxiv_id,
                title=" ".join(title.split()),
                abstract=" ".join(abstract.split()),
                authors=authors,
                published=published,
                updated=updated,
                abstract_url=urls["abstract_url"],
                html_url=urls["html_url"],
                pdf_url=urls["pdf_url"],
                first_seen_at=now_iso,
                last_seen_at=now_iso,
            )
        )
    return papers


def matched_keywords(paper: Paper, keywords: list[str]) -> list[str]:
    blob = f"{paper.title}\n{paper.abstract}".lower()
    return [keyword for keyword in keywords if keyword.lower() in blob]


def fetch_recent(cfg: AppConfig, now: dt.datetime) -> list[Paper]:
    since = now - dt.timedelta(hours=cfg.fetch_window_hours)
    params = {
        "search_query": build_query(cfg.category, since, now),
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "max_results": str(cfg.max_results),
    }
    papers = parse_entries(fetch_atom(params, cfg), now)
    matches: list[Paper] = []
    for paper in papers:
        hits = matched_keywords(paper, cfg.keywords)
        if hits:
            paper.matched_keywords = hits
            matches.append(paper)
    return matches


def fetch_by_id(arxiv_id: str, cfg: AppConfig, now: dt.datetime) -> Paper | None:
    papers = parse_entries(fetch_atom({"id_list": arxiv_id}, cfg), now)
    return papers[0] if papers else None
