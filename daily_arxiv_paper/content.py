from __future__ import annotations

import html
import re
import subprocess
import tempfile
import urllib.request

from .arxiv import http_config
from .config import AppConfig
from .http import request_with_retry
from .models import Paper

TAG_RE = re.compile(r"<[^>]+>")
SCRIPT_RE = re.compile(r"<(script|style).*?</\1>", re.IGNORECASE | re.DOTALL)
SPACE_RE = re.compile(r"\s+")


def clean_html(raw: bytes) -> str:
    text = raw.decode("utf-8", errors="ignore")
    text = SCRIPT_RE.sub(" ", text)
    text = TAG_RE.sub(" ", text)
    return SPACE_RE.sub(" ", html.unescape(text)).strip()


def fetch_text(url: str, cfg: AppConfig, operation_name: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "daily-arxiv-paper/1.0"})
    raw = request_with_retry(req, http_config(cfg), operation_name)
    return clean_html(raw)


def fetch_raw(url: str, cfg: AppConfig, operation_name: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "daily-arxiv-paper/1.0"})
    return request_with_retry(req, http_config(cfg), operation_name)


def extract_pdf_text(raw: bytes) -> str:
    with tempfile.NamedTemporaryFile(suffix=".pdf") as pdf_file:
        pdf_file.write(raw)
        pdf_file.flush()
        result = subprocess.run(
            ["pdftotext", pdf_file.name, "-"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    if result.returncode != 0:
        return ""
    return SPACE_RE.sub(" ", result.stdout).strip()


def fetch_pdf_text(url: str, cfg: AppConfig) -> str:
    try:
        return extract_pdf_text(fetch_raw(url, cfg, "arXiv PDF fallback fetch"))
    except Exception:
        return ""


def choose_source(paper: Paper, cfg: AppConfig) -> tuple[str, str]:
    try:
        text = fetch_text(paper.html_url, cfg, "arXiv HTML fetch")
        if len(text) >= 1200:
            return "html", text
    except Exception:
        pass

    if paper.abstract:
        return "abstract", f"{paper.title}\n\n{paper.abstract}"

    try:
        text = fetch_text(paper.abstract_url, cfg, "arXiv abstract fetch")
        if text:
            return "abstract", text
    except Exception:
        pass

    text = fetch_pdf_text(paper.pdf_url, cfg)
    if text:
        return "pdf", text

    return "abstract", f"{paper.title}\n\n{paper.abstract}"
