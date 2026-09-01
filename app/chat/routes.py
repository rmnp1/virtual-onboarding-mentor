import json
from collections import defaultdict

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.chat.context import build_context
from app.chat.llm import generate, generate_stream
from app.chat.schemas import ChatRequest, ChatResponse, WSMessage
from app.config import settings
from app.models.base import SessionLocal, get_db
from app.models.user import User
from app.models.user_profile import UserProfile
from app.personalization.service import build_system_prompt, get_profile

router = APIRouter(prefix="/api/chat", tags=["chat"])

chat_history: dict[int, list[dict[str, str]]] = defaultdict(list)


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
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatResponse:
    history = chat_history[user.id]
    profile = get_profile(db, user)
    reply, sources = _handle_message(user, body.message, history, profile)
    return ChatResponse(reply=reply, sources=sources)


@router.websocket("/ws")
async def websocket_chat(websocket: WebSocket) -> None:
    await websocket.accept()

    token = websocket.query_params.get("token", "")
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

    try:
        while True:
            data = await websocket.receive_text()
            msg: dict[str, str] = json.loads(data)
            user_message = msg.get("message", "")

            context, chunks = build_context(user_message, language, history)
            system_prompt = build_system_prompt(language, user, profile)

            full_reply_parts: list[str] = []
            try:
                for token_text in generate_stream(context, system_prompt):
                    full_reply_parts.append(token_text)
                    await websocket.send_text(
                        WSMessage(type="token", content=token_text).model_dump_json()
                    )
            except Exception:
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
        pass
