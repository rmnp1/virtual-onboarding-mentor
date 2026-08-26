from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    language: str | None = None


class ChatResponse(BaseModel):
    reply: str
    sources: list[str]


class WSMessage(BaseModel):
    type: str
    content: str
