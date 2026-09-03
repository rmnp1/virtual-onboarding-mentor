import asyncio
import json
import logging
import time
from collections import defaultdict
from contextlib import suppress

import httpx
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from jose import JWTError, jwt
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.ratelimit import chat_ip, check_rate_limit, ip_enforce
from app.chat.context import build_context
from app.chat.llm import generate, generate_stream
from app.chat.schemas import ChatRequest, ChatResponse, WSMessage
from app.config import settings
from app.models.base import SessionLocal, get_db
from app.models.user import User
from app.models.user_profile import UserProfile
from app.personalization.service import build_system_prompt, get_profile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])

chat_history: dict[int, list[dict[str, str]]] = defaultdict(list)
_ws_last_message: dict[int, float] = {}

_WS_AUTH_TIMEOUT = 10.0


def _clean_pending_history(pending: object) -> list[dict[str, str]]:
    if not isinstance(pending, list):
        return []
    cleaned: list[dict[str, str]] = []
    for item in pending[-20:]:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content")
        if role in ("user", "assistant") and isinstance(content, str) and content:
            cleaned.append({"role": role, "content": content})
    return cleaned


def _handle_message(
    user: User,
    message: str,
    history: list[dict[str, str]],
    profile: UserProfile | None,
) -> tuple[str, list[str]]:
    language = user.language
    context, chunks = build_context(message, language, history)
    system_prompt = build_system_prompt(language, user, profile)
    reply = generate(context, system_prompt)

    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": reply})

    if len(history) > 20:
        chat_history[user.id] = history[-20:]

    sources: list[str] = [str(c.get("source", "")) for c in chunks]
    return reply, sources


@router.post("", response_model=ChatResponse)
def chat(
    body: ChatRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatResponse:
    ip_enforce(chat_ip, request)
    history = chat_history[user.id]
    profile = get_profile(db, user)
    try:
        reply, sources = _handle_message(user, body.message, history, profile)
    except (httpx.HTTPError, SQLAlchemyError) as exc:
        logger.error(
            "chat request failed for user=%s: %s: %s",
            user.id,
            type(exc).__name__,
            exc,
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM service unavailable",
        ) from exc
    return ChatResponse(reply=reply, sources=sources)


@router.websocket("/ws")
async def websocket_chat(websocket: WebSocket) -> None:
    await websocket.accept()

    try:
        first_frame = json.loads(
            await asyncio.wait_for(websocket.receive_text(), timeout=_WS_AUTH_TIMEOUT)
        )
    except (TimeoutError, json.JSONDecodeError):
        error_msg = WSMessage(type="error", content="Authentication required")
        await websocket.send_text(error_msg.model_dump_json())
        await websocket.close()
        return

    is_auth = first_frame.get("type") == "auth"
    token = str(first_frame.get("content", "")) if is_auth else ""
    pending_history = first_frame.get("history") if is_auth else None
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        user_id = int(payload.get("sub", 0))
    except JWTError:
        error_msg = WSMessage(type="error", content="Invalid token")
        await websocket.send_text(error_msg.model_dump_json())
        await websocket.close()
        return

    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        profile = get_profile(db, user) if user else None
    finally:
        db.close()

    if not user:
        error_msg = WSMessage(type="error", content="User not found")
        await websocket.send_text(error_msg.model_dump_json())
        await websocket.close()
        return

    language = user.language
    history = chat_history[user.id]

    if not history:
        cleaned = _clean_pending_history(pending_history)
        if cleaned:
            chat_history[user.id] = cleaned
            history = cleaned

    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
            except (json.JSONDecodeError, TypeError) as exc:
                logger.warning(
                    "ws received invalid json from user=%s host=%s: %s",
                    user.id,
                    websocket.client.host if websocket.client else "unknown",
                    exc,
                )
                continue
            if not isinstance(msg, dict):
                continue
            if msg.get("type") == "ping" or msg.get("message", "") == "__ping__":
                await websocket.send_text(WSMessage(type="pong", content="").model_dump_json())
                continue
            user_message = msg.get("message", "")
            if not user_message:
                continue

            now = time.monotonic()
            last = _ws_last_message.get(user.id, 0.0)
            if now - last < settings.ws_min_interval:
                error_msg = WSMessage(
                    type="error", content="Please wait a moment before sending another message."
                )
                await websocket.send_text(error_msg.model_dump_json())
                continue
            _ws_last_message[user.id] = now

            ws_host = websocket.client.host if websocket.client else "unknown"
            try:
                check_rate_limit(chat_ip, ws_host)
            except Exception:
                error_msg = WSMessage(type="error", content="Too many requests")
                await websocket.send_text(error_msg.model_dump_json())
                continue

            try:
                context, chunks = build_context(user_message, language, history)
            except httpx.HTTPError as exc:
                logger.error(
                    "ws context build failed (http) user=%s: %s: %s",
                    user.id,
                    type(exc).__name__,
                    exc,
                    exc_info=exc,
                )
                error_msg = WSMessage(type="error", content="LLM service unavailable")
                await websocket.send_text(error_msg.model_dump_json())
                continue
            except SQLAlchemyError as exc:
                logger.error(
                    "ws context build failed (db) user=%s: %s: %s",
                    user.id,
                    type(exc).__name__,
                    exc,
                    exc_info=exc,
                )
                error_msg = WSMessage(type="error", content="Retrieval failed")
                await websocket.send_text(error_msg.model_dump_json())
                continue
            except Exception as exc:
                logger.error(
                    "ws context build failed (unexpected) user=%s: %s",
                    user.id,
                    exc,
                    exc_info=exc,
                )
                error_msg = WSMessage(type="error", content="Retrieval failed")
                await websocket.send_text(error_msg.model_dump_json())
                continue

            system_prompt = build_system_prompt(language, user, profile)

            full_reply_parts: list[str] = []
            try:
                for token_text in generate_stream(context, system_prompt):
                    full_reply_parts.append(token_text)
                    await websocket.send_text(
                        WSMessage(type="token", content=token_text).model_dump_json()
                    )
            except httpx.HTTPError as exc:
                response = getattr(exc, "response", None)
                status_code = response.status_code if response is not None else "n/a"
                logger.error(
                    "ws stream failed (http) user=%s status=%s: %s: %s",
                    user.id,
                    status_code,
                    type(exc).__name__,
                    exc,
                    exc_info=exc,
                )
                if status_code in (429, 503):
                    error_msg = WSMessage(
                        type="error",
                        content="Gemini is busy or rate-limited. Please try again in a moment.",
                    )
                else:
                    error_msg = WSMessage(type="error", content="LLM service unavailable")
                await websocket.send_text(error_msg.model_dump_json())
                continue
            except Exception as exc:
                logger.error(
                    "ws stream failed (unexpected) user=%s: %s: %s",
                    user.id,
                    type(exc).__name__,
                    exc,
                    exc_info=exc,
                )
                error_msg = WSMessage(type="error", content="LLM service unavailable")
                await websocket.send_text(error_msg.model_dump_json())
                continue

            full_reply = "".join(full_reply_parts)
            history.append({"role": "user", "content": user_message})
            history.append({"role": "assistant", "content": full_reply})

            if len(history) > 20:
                chat_history[user.id] = history[-20:]

            await websocket.send_text(WSMessage(type="done", content="").model_dump_json())

    except WebSocketDisconnect:
        logger.info("ws client disconnected user=%s", user.id)
    except Exception as exc:
        logger.error(
            "ws loop crashed user=%s: %s: %s",
            user.id,
            type(exc).__name__,
            exc,
            exc_info=exc,
        )
        with suppress(Exception):
            await websocket.close()
