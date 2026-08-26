import json
from collections import defaultdict

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.chat.context import build_context
from app.chat.llm import generate, generate_stream
from app.chat.prompts import get_system_prompt
from app.chat.schemas import ChatRequest, ChatResponse, WSMessage
from app.config import settings
from app.knowledge_base.retriever import search
from app.models.base import get_db
from app.models.user import User

router = APIRouter(prefix="/api/chat", tags=["chat"])

chat_history: dict[int, list[dict[str, str]]] = defaultdict(list)


@router.post("", response_model=ChatResponse)
def chat(body: ChatRequest, user: User = Depends(get_current_user)) -> ChatResponse:
    language = body.language or user.language
    history = chat_history[user.id]

    context = build_context(body.message, language, history)
    system_prompt = get_system_prompt(language)
    reply = generate(context, system_prompt)

    history.append({"role": "user", "content": body.message})
    history.append({"role": "assistant", "content": reply})

    if len(history) > 20:
        chat_history[user.id] = history[-20:]

    raw_sources = search(body.message, language=language, top_k=3)
    sources: list[str] = [str(r.get("source", "")) for r in raw_sources]
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

    db: Session = next(get_db())
    user = db.query(User).filter(User.id == user_id).first()
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

            context = build_context(user_message, language, history)
            system_prompt = get_system_prompt(language)

            full_reply_parts: list[str] = []
            for token_text in generate_stream(context, system_prompt):
                full_reply_parts.append(token_text)
                await websocket.send_text(
                    WSMessage(type="token", content=token_text).model_dump_json()
                )

            full_reply = "".join(full_reply_parts)
            history.append({"role": "user", "content": user_message})
            history.append({"role": "assistant", "content": full_reply})

            if len(history) > 20:
                chat_history[user.id] = history[-20:]

            await websocket.send_text(WSMessage(type="done", content="").model_dump_json())

    except WebSocketDisconnect:
        pass
