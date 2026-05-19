from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def load_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip()
    return env


@dataclass
class AppConfig:
    category: str = "cs.CV"
    keywords: list[str] = field(
        default_factory=lambda: [
            "video",
            "retrieval",
            "3d",
            "agent",
            "representation",
            "instance",
            "multimodal",
            "diffusion",
        ]
    )
    max_results: int = 100
    fetch_window_hours: int = 72
    daily_window_hours: int = 30
    request_timeout_seconds: int = 25
    retry_attempts: int = 4
    retry_base_delay_seconds: int = 10
    retry_max_delay_seconds: int = 120
    use_proxy: bool | str = "auto"
    openai_model: str = "gpt-5-mini"
    summary_max_input_chars: int = 14000
    summary_max_output_tokens: int = 280
    summary_reasoning_effort: str = "minimal"
    summarize_max_papers: int = 20
    data_dir: str = "data"
    public_dir: str = "public"

    @classmethod
    def load(cls, path: Path) -> "AppConfig":
        defaults = cls()
        if not path.exists():
            return defaults
        data = json.loads(path.read_text(encoding="utf-8"))
        allowed = {name for name in cls.__dataclass_fields__}
        values = {name: getattr(defaults, name) for name in allowed}
        values.update({key: value for key, value in data.items() if key in allowed})
        return cls(**values)

    @property
    def data_path(self) -> Path:
        return repo_root() / self.data_dir

    @property
    def public_path(self) -> Path:
        return repo_root() / self.public_dir


def load_runtime_env() -> dict[str, str]:
    file_env = load_env(repo_root() / ".env")
    merged = dict(os.environ)
    merged.update(file_env)
    return merged
