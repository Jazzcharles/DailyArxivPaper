from __future__ import annotations

import datetime as dt
import json
import urllib.request

from .arxiv import http_config
from .config import AppConfig
from .http import request_with_retry
from .models import Paper, Summary

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"


def trim(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "..."


def build_prompt(paper: Paper, source_text: str, source_used: str, cfg: AppConfig) -> str:
    return (
        "请基于下面的论文内容，为技术读者生成简洁中文总结。\n"
        "只输出 JSON，不要输出 Markdown。JSON schema:\n"
        "{\"core_contribution\":\"...\",\"method\":\"...\"}\n"
        "要求：不要编造数据集、指标或结论；如果来源只包含摘要，就只按摘要总结。\n\n"
        f"Title: {paper.title}\n"
        f"Authors: {', '.join(paper.authors)}\n"
        f"Source used: {source_used}\n"
        f"Content:\n{trim(source_text, cfg.summary_max_input_chars)}\n"
    )


def extract_output_text(payload: dict) -> str:
    parts: list[str] = []
    for item in payload.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text" and content.get("text"):
                parts.append(content["text"].strip())
    return "\n".join(parts).strip()


def parse_summary_text(text: str) -> tuple[str, str]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.removeprefix("json").strip()
    try:
        payload = json.loads(cleaned)
        return (
            str(payload.get("core_contribution", "")).strip(),
            str(payload.get("method", "")).strip(),
        )
    except json.JSONDecodeError:
        lines = [line.strip("- :") for line in cleaned.splitlines() if line.strip()]
        core = lines[0] if lines else cleaned[:180]
        method = lines[1] if len(lines) > 1 else "方法细节需阅读全文确认。"
        return core, method


def summarize_with_openai(
    paper: Paper, source_text: str, source_used: str, api_key: str, cfg: AppConfig
) -> Summary:
    payload = {
        "model": cfg.openai_model,
        "store": False,
        "reasoning": {"effort": cfg.summary_reasoning_effort},
        "max_output_tokens": cfg.summary_max_output_tokens,
        "instructions": "You are a careful research assistant. Return faithful JSON only.",
        "input": build_prompt(paper, source_text, source_used, cfg),
    }
    req = urllib.request.Request(
        OPENAI_RESPONSES_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    raw = request_with_retry(req, http_config(cfg), "OpenAI summary request")
    text = extract_output_text(json.loads(raw.decode("utf-8")))
    if not text:
        raise RuntimeError("OpenAI summary response did not include text output.")
    core, method = parse_summary_text(text)
    return Summary(
        model=cfg.openai_model,
        core_contribution=core or "未能从模型响应中解析核心贡献。",
        method=method or "未能从模型响应中解析方法要点。",
        source_used=source_used,
        created_at=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    )


def summarize_without_api(paper: Paper, source_used: str, cfg: AppConfig) -> Summary:
    abstract = trim(paper.abstract, 260)
    keywords = ", ".join(paper.matched_keywords) or "关键词"
    return Summary(
        model="fallback-no-api",
        core_contribution=f"该论文与 {keywords} 相关；摘要显示其主要贡献为：{abstract}",
        method="未配置 OPENAI_API_KEY，方法细节未调用模型总结。",
        source_used=source_used,
        created_at=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        status="fallback",
    )
