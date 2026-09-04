import json
import logging
import time
from collections.abc import Generator

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

OLLAMA_GENERATE_URL = f"{settings.ollama_url}/api/generate"

GEMINI_OPENAI_BASE = "https://generativelanguage.googleapis.com/v1beta/openai"

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def _response_snippet(response: httpx.Response | None, limit: int = 500) -> str:
    if response is None:
        return ""
    body = ""
    try:
        text = response.text
        body = text[:limit]
    except Exception:
        try:
            content = response.content
            body = content[:limit].decode("utf-8", errors="replace")
        except Exception:
            body = "<unreadable>"
    return body


def _is_retryable(status_code: int | None) -> bool:
    return status_code is not None and status_code in _RETRYABLE_STATUS


def _retry_delay(attempt: int) -> float:
    configured: float = settings.gemini_retry_base_delay
    base = max(configured, 0.1)
    growth = max(float(settings.gemini_retry_growth), 1.5)
    return float(base * (growth ** (attempt - 1)))


def _log_httpx_failure(operation: str, exc: httpx.HTTPError) -> None:
    response = getattr(exc, "response", None)
    status_code = response.status_code if response is not None else "n/a"
    body = _response_snippet(response)
    logger.error(
        "gemini %s failed: %s status=%s url=%s body=%r: %s",
        operation,
        type(exc).__name__,
        status_code,
        response.url if response is not None else "n/a",
        body,
        exc,
        exc_info=exc,
    )


def _generate_ollama_stream(prompt: str, system: str) -> Generator[str]:
    with (
        httpx.Client(timeout=120.0) as client,
        client.stream(
            "POST",
            OLLAMA_GENERATE_URL,
            json={
                "model": settings.ollama_model,
                "prompt": prompt,
                "system": system,
                "stream": True,
            },
        ) as response,
    ):
        response.raise_for_status()
        for line in response.iter_lines():
            if not line:
                continue
            chunk: dict[str, object] = json.loads(line)
            if chunk.get("done"):
                break
            token = chunk.get("response", "")
            if token:
                yield str(token)


def _generate_ollama(prompt: str, system: str) -> str:
    with httpx.Client(timeout=120.0) as client:
        response = client.post(
            OLLAMA_GENERATE_URL,
            json={
                "model": settings.ollama_model,
                "prompt": prompt,
                "system": system,
                "stream": False,
            },
        )
        response.raise_for_status()
        data: dict[str, object] = response.json()
        return str(data.get("response", ""))


def _gemini_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }


def _gemini_messages(prompt: str, system: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]


def _gemini_generate(prompt: str, system: str) -> str:
    url = f"{GEMINI_OPENAI_BASE}/chat/completions"
    payload = {
        "model": settings.llm_model,
        "messages": _gemini_messages(prompt, system),
        "stream": False,
    }
    last_exc: httpx.HTTPError | None = None
    for attempt in range(1, settings.gemini_max_retries + 1):
        try:
            with httpx.Client(timeout=120.0) as client:
                response = client.post(url, headers=_gemini_headers(), json=payload)
                response.raise_for_status()
            data: dict[str, object] = response.json()
            choices = data.get("choices")
            if isinstance(choices, list) and choices and isinstance(choices[0], dict):
                message = choices[0].get("message")
                if isinstance(message, dict):
                    content = message.get("content")
                    if content is not None:
                        return str(content)
            return ""
        except httpx.HTTPError as exc:
            last_exc = exc
            resp = getattr(exc, "response", None)
            status = resp.status_code if resp is not None else None
            if not _is_retryable(status) or attempt == settings.gemini_max_retries:
                _log_httpx_failure("chat/generate", exc)
                raise
            logger.warning(
                "gemini chat/generate got %s on attempt %d/%d, retrying in %.1fs",
                status,
                attempt,
                settings.gemini_max_retries,
                _retry_delay(attempt),
            )
            time.sleep(_retry_delay(attempt))
    assert last_exc is not None
    _log_httpx_failure("chat/generate", last_exc)
    raise last_exc


def _gemini_generate_stream(prompt: str, system: str) -> Generator[str]:
    url = f"{GEMINI_OPENAI_BASE}/chat/completions"
    payload = {
        "model": settings.llm_model,
        "messages": _gemini_messages(prompt, system),
        "stream": True,
    }
    for attempt in range(1, settings.gemini_max_retries + 1):
        try:
            with (
                httpx.Client(timeout=120.0) as client,
                client.stream(
                    "POST",
                    url,
                    headers=_gemini_headers(),
                    json=payload,
                ) as response,
            ):
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    payload_line = line[len("data:") :].strip()
                    if not payload_line or payload_line == "[DONE]":
                        return
                    try:
                        chunk: dict[str, object] = json.loads(payload_line)
                    except json.JSONDecodeError:
                        continue
                    choices = chunk.get("choices")
                    if (
                        not isinstance(choices, list)
                        or not choices
                        or not isinstance(choices[0], dict)
                    ):
                        continue
                    delta = choices[0].get("delta")
                    if isinstance(delta, dict):
                        token = delta.get("content")
                        if token:
                            yield str(token)
            return
        except httpx.HTTPError as exc:
            resp = getattr(exc, "response", None)
            status = resp.status_code if resp is not None else None
            if not _is_retryable(status) or attempt == settings.gemini_max_retries:
                _log_httpx_failure("chat/generate_stream", exc)
                raise
            logger.warning(
                "gemini chat/generate_stream got %s on attempt %d/%d, retrying in %.1fs",
                status,
                attempt,
                settings.gemini_max_retries,
                _retry_delay(attempt),
            )
            time.sleep(_retry_delay(attempt))


def generate_stream(prompt: str, system: str) -> Generator[str]:
    if settings.llm_provider == "gemini":
        return _gemini_generate_stream(prompt, system)
    return _generate_ollama_stream(prompt, system)


def generate(prompt: str, system: str) -> str:
    if settings.llm_provider == "gemini":
        return _gemini_generate(prompt, system)
    return _generate_ollama(prompt, system)
