import json
from collections.abc import Generator

import httpx

from app.config import settings

OLLAMA_GENERATE_URL = f"{settings.ollama_url}/api/generate"


def generate_stream(prompt: str, system: str) -> Generator[str]:
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


def generate(prompt: str, system: str) -> str:
    parts: list[str] = []
    for token in generate_stream(prompt, system):
        parts.append(token)
    return "".join(parts)
