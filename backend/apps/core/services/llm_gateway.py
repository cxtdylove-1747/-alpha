from __future__ import annotations

import json
import logging
import os
import socket
import time
from urllib import error, request

logger = logging.getLogger(__name__)


def _read_int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)) or str(default))
    except Exception:
        return default


def _error_reason(exc: Exception) -> str:
    msg = str(exc)
    if isinstance(exc, error.HTTPError):
        if exc.code in (401, 403):
            return "auth_or_key_invalid"
        if 400 <= exc.code < 500:
            return "request_invalid_or_model_invalid"
        return "upstream_http_error"
    if isinstance(exc, socket.timeout) or "timed out" in msg.lower():
        return "network_timeout"
    if isinstance(exc, error.URLError):
        return "network_unreachable"
    return "unknown_error"


def call_llm(prompt: str, system_prompt: str, temperature: float = 0.35, timeout_seconds: int = 180) -> str | None:
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        return None

    base_url = os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com/v1").rstrip("/")
    model = os.getenv("OPENAI_MODEL", "deepseek-chat")
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
    }
    req = request.Request(
        url=f"{base_url}/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    env_timeout = _read_int_env("OPENAI_HTTP_TIMEOUT_SECONDS", 180)
    timeout = max(5, int(timeout_seconds or 0)) if int(timeout_seconds or 0) > 0 else max(5, env_timeout)
    retries = max(0, _read_int_env("OPENAI_HTTP_RETRIES", 1))
    total_attempts = 1 + retries

    for attempt in range(1, total_attempts + 1):
        try:
            with request.urlopen(req, timeout=timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            return str(payload["choices"][0]["message"]["content"]).strip()
        except Exception as exc:
            reason = _error_reason(exc)
            logger.warning("call_llm failed (%s) attempt=%s/%s: %s", reason, attempt, total_attempts, exc)
            # Do not retry auth/parameter/model errors; retry only transient network failures.
            if reason in {"auth_or_key_invalid", "request_invalid_or_model_invalid"}:
                return None
            if attempt >= total_attempts:
                return None
            time.sleep(min(2.0, 0.5 * attempt))

    return None
