from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.routes import router as auth_router
from app.chat.routes import router as chat_router
from app.feedback.routes import router as feedback_router
from app.metrics.routes import router as metrics_router
from app.models.base import init_db
from app.personalization.routes import router as personalization_router
from app.scenarios.routes import router as scenarios_router

app = FastAPI(title="Virtual Onboarding Mentor", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    init_db()


app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(scenarios_router)
app.include_router(personalization_router)
app.include_router(feedback_router)
app.include_router(metrics_router)
