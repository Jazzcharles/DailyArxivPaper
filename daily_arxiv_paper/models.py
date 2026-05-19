from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class Summary:
    model: str
    core_contribution: str
    method: str
    source_used: str
    created_at: str
    status: str = "ok"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Paper:
    id: str
    title: str
    abstract: str
    authors: list[str]
    published: str
    updated: str
    abstract_url: str
    html_url: str
    pdf_url: str
    matched_keywords: list[str] = field(default_factory=list)
    source_used: str = "abstract"
    source_text_chars: int = 0
    summary: Summary | None = None
    first_seen_at: str = ""
    last_seen_at: str = ""

    def to_dict(self) -> dict:
        payload = asdict(self)
        if self.summary:
            payload["summary"] = self.summary.to_dict()
        else:
            payload["summary"] = None
        return payload

    @classmethod
    def from_dict(cls, data: dict) -> "Paper":
        payload = dict(data)
        summary = payload.get("summary")
        payload["summary"] = Summary(**summary) if isinstance(summary, dict) else None
        return cls(**payload)
