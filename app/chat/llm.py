import json
import logging
from collections.abc import Generator

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

OLLAMA_GENERATE_URL = f"{settings.ollama_url}/api/generate"

GEMINI_OPENAI_BASE = "https://generativelanguage.googleapis.com/v1beta/openai"


def _log_httpx_failure(operation: str, exc: httpx.HTTPError) -> None:
    response = getattr(exc, "response", None)
    detail = ""
    if response is not None:
        body = ""
        try:
            body = response.text[:500]
        except Exception:
            body = "<unreadable>"
        detail = f" status={response.status_code} url={response.url} body={body!r}"
    logger.error(
        "gemini %s failed: %s%s: %s",
        operation,
        type(exc).__name__,
        detail,
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
    try:
        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                f"{GEMINI_OPENAI_BASE}/chat/completions",
                headers=_gemini_headers(),
                json={
                    "model": settings.llm_model,
                    "messages": _gemini_messages(prompt, system),
                    "stream": False,
                },
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        _log_httpx_failure("chat/generate", exc)
        raise
    data: dict[str, object] = response.json()
    choices = data.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        message = choices[0].get("message")
        if isinstance(message, dict):
            content = message.get("content")
            if content is not None:
                return str(content)
    return ""


def _gemini_generate_stream(prompt: str, system: str) -> Generator[str]:
    try:
        with (
            httpx.Client(timeout=120.0) as client,
            client.stream(
                "POST",
                f"{GEMINI_OPENAI_BASE}/chat/completions",
                headers=_gemini_headers(),
                json={
                    "model": settings.llm_model,
                    "messages": _gemini_messages(prompt, system),
                    "stream": True,
                },
            ) as response,
        ):
            response.raise_for_status()
            for line in response.iter_lines():
                if not line or not line.startswith("data:"):
                    continue
                payload = line[len("data:") :].strip()
                if not payload or payload == "[DONE]":
                    return
                try:
                    chunk: dict[str, object] = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                choices = chunk.get("choices")
                if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
                    continue
                delta = choices[0].get("delta")
                if isinstance(delta, dict):
                    token = delta.get("content")
                    if token:
                        yield str(token)
    except httpx.HTTPError as exc:
        _log_httpx_failure("chat/generate_stream", exc)
        raise


def generate_stream(prompt: str, system: str) -> Generator[str]:
    if settings.llm_provider == "gemini":
        return _gemini_generate_stream(prompt, system)
    return _generate_ollama_stream(prompt, system)


def generate(prompt: str, system: str) -> str:
    if settings.llm_provider == "gemini":
        return _gemini_generate(prompt, system)
    return _generate_ollama(prompt, system)
