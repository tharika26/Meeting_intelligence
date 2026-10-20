from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app import models  # noqa: F401 (ensures models are registered before create_all)
from app.routers import meetings, actions, insights

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Meeting Intelligence & Project Action Tracker",
    description="Transcribes meetings, extracts decisions/actions/risks, and enables semantic search.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(meetings.router)
app.include_router(actions.router)
app.include_router(insights.router)


@app.get("/health")
def health():
    return {"status": "ok"}
