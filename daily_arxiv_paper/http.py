from __future__ import annotations

import os
import socket
import ssl
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass


PROXY_ENV_VARS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
)


@dataclass
class HttpConfig:
    timeout_seconds: int
    attempts: int
    base_delay_seconds: int
    max_delay_seconds: int
    use_proxy: bool | str


def ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    try:
        import certifi  # type: ignore

        ctx.load_verify_locations(certifi.where())
    except Exception:
        pass
    return ctx


def should_use_proxy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return any(os.environ.get(name) for name in PROXY_ENV_VARS)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
        if normalized == "auto":
            return any(os.environ.get(name) for name in PROXY_ENV_VARS)
    raise ValueError("Invalid use_proxy config. Expected true, false, or 'auto'.")


def request_bytes(req: urllib.request.Request, cfg: HttpConfig) -> bytes:
    if should_use_proxy(cfg.use_proxy):
        with urllib.request.urlopen(
            req, timeout=cfg.timeout_seconds, context=ssl_context()
        ) as resp:
            return resp.read()

    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        urllib.request.HTTPSHandler(context=ssl_context()),
    )
    with opener.open(req, timeout=cfg.timeout_seconds) as resp:
        return resp.read()


def is_retryable_error(exc: BaseException) -> bool:
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code in {408, 409, 425, 429} or 500 <= exc.code < 600
    if isinstance(exc, urllib.error.URLError):
        return True
    return isinstance(exc, (TimeoutError, socket.timeout, ssl.SSLError))


def retry_after_seconds(exc: BaseException) -> int | None:
    if not isinstance(exc, urllib.error.HTTPError) or not exc.headers:
        return None
    value = exc.headers.get("Retry-After")
    if not value:
        return None
    try:
        return max(int(value), 0)
    except ValueError:
        return None


def error_text(exc: BaseException) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        return f"HTTP {exc.code}"
    if isinstance(exc, urllib.error.URLError) and exc.reason:
        return str(exc.reason)
    return str(exc) or exc.__class__.__name__


def request_with_retry(
    req: urllib.request.Request, cfg: HttpConfig, operation_name: str
) -> bytes:
    attempts = max(int(cfg.attempts), 1)
    last_exc: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            return request_bytes(req, cfg)
        except Exception as exc:
            last_exc = exc
            if attempt >= attempts or not is_retryable_error(exc):
                raise
            delay = cfg.base_delay_seconds * (2 ** max(attempt - 1, 0))
            retry_after = retry_after_seconds(exc)
            if retry_after is not None:
                delay = max(delay, retry_after)
            delay = max(1, min(delay, cfg.max_delay_seconds))
            print(
                f"{operation_name} failed on attempt {attempt}/{attempts}: "
                f"{error_text(exc)}; retrying in {delay}s.",
                file=sys.stderr,
            )
            time.sleep(delay)
    if last_exc:
        raise last_exc
    raise RuntimeError(f"{operation_name} failed before making a request.")
