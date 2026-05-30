import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from launchmind.config import Settings
from launchmind.logging_config import setup_logging
from launchmind.run_manager import RunManager

setup_logging()
logger = logging.getLogger(__name__)

settings = Settings()
run_manager = RunManager(settings)

app = FastAPI(title="LaunchMind API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class LaunchRequest(BaseModel):
    idea: str = Field(..., min_length=10, max_length=1000)


@app.post("/api/runs", status_code=201)
def create_run(req: LaunchRequest):
    try:
        return run_manager.start_run(req.idea)
    except RuntimeError as e:
        raise HTTPException(status_code=429, detail=str(e))


@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    state = run_manager.get_run_state(run_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return state


@app.get("/api/runs/{run_id}/events")
def get_events(run_id: str, after: int = -1):
    events = run_manager.get_events(run_id, after=after)
    if events is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return {"run_id": run_id, "events": events}


@app.get("/api/health")
def health():
    redis_ok = run_manager.check_redis()
    return {
        "status": "ok" if redis_ok else "degraded",
        "redis": "connected" if redis_ok else "disconnected",
        "version": "0.1.0",
    }
