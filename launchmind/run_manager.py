import json
import logging
import threading
from datetime import datetime, timezone

import redis

from launchmind.bus.transport import MessageBus
from launchmind.agents.ceo import CEOAgent
from launchmind.agents.product import ProductAgent
from launchmind.agents.engineer import EngineerAgent
from launchmind.agents.marketing import MarketingAgent
from launchmind.agents.qa import QAAgent
from launchmind.config import Settings

logger = logging.getLogger(__name__)

RUN_TTL = 3600
PHASES = ["decompose", "product", "engineer", "marketing", "qa"]
MAX_CONCURRENT = 2


class RunManager:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._redis = redis.from_url(settings.UPSTASH_REDIS_URL, decode_responses=True)
        self._active_runs = 0
        self._lock = threading.Lock()

    def start_run(self, idea: str) -> dict:
        with self._lock:
            if self._active_runs >= MAX_CONCURRENT:
                raise RuntimeError("Server is busy, please try again later")
            self._active_runs += 1

        run_id = f"run-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{id(idea) % 10000:04d}"
        now = datetime.now(timezone.utc).isoformat()

        state_key = f"launchmind:run:{run_id}:state"
        self._redis.hset(state_key, mapping={
            "status": "started",
            "current_phase": "initializing",
            "progress_pct": "0",
            "created_at": now,
            "updated_at": now,
            "error": "",
            "idea": idea,
        })
        self._redis.expire(state_key, RUN_TTL)

        events_key = f"launchmind:run:{run_id}:events"
        self._redis.delete(events_key)
        self._redis.expire(events_key, RUN_TTL)

        phases_key = f"launchmind:run:{run_id}:phases_completed"
        self._redis.delete(phases_key)
        self._redis.expire(phases_key, RUN_TTL)

        thread = threading.Thread(
            target=self._run_pipeline,
            args=(run_id, idea),
            daemon=True,
        )
        thread.start()

        return {"run_id": run_id, "status": "started", "created_at": now}

    def _run_pipeline(self, run_id: str, idea: str):
        try:
            self._update_status(run_id, "running", "decompose", progress=5)
            self._add_event(run_id, "pipeline", "started", "Initializing agents")

            bus = MessageBus(self.settings.UPSTASH_REDIS_URL)
            self._clear_message_bus(bus)

            ceo = CEOAgent(bus, self.settings)
            agents = [
                ProductAgent(bus, self.settings),
                EngineerAgent(bus, self.settings),
                MarketingAgent(bus, self.settings),
                QAAgent(bus, self.settings),
            ]
            for agent in agents:
                threading.Thread(target=agent.listen, daemon=True).start()

            self._add_event(run_id, "decompose", "started", "Decomposing idea into agent tasks")

            original_log = ceo._log_decision

            def track_progress(phase: str, summary: str, details: str):
                original_log(phase, summary, details)
                if phase == "decompose":
                    self._mark_phase_completed(run_id, "decompose")
                    self._update_status(run_id, "running", "product", progress=20)
                    self._add_event(run_id, "decompose", "completed", summary)
                    self._add_event(run_id, "product", "started", "Generating product spec")
                elif phase.startswith("review_product") and "Approved" in summary:
                    self._mark_phase_completed(run_id, "product")
                    self._update_status(run_id, "running", "engineer", progress=40)
                    self._add_event(run_id, "product", "completed", summary)
                    self._add_event(run_id, "engineer", "started", "Building landing page and opening PR")
                    self._add_event(run_id, "marketing", "started", "Generating marketing copy")
                elif phase.startswith("revision_product"):
                    self._add_event(run_id, "product", "revision", summary)
                elif phase == "qa_verdict":
                    self._mark_phase_completed(run_id, "engineer")
                    self._mark_phase_completed(run_id, "marketing")
                    self._mark_phase_completed(run_id, "qa")
                    self._update_status(run_id, "running", "finalizing", progress=90)
                    self._add_event(run_id, "qa", "completed", summary)
                elif phase == "run_complete":
                    self._update_status(run_id, "running", "done", progress=95)

            ceo._log_decision = track_progress
            summary = ceo.run(idea)

            for agent in agents:
                agent.stop()

            result_key = f"launchmind:run:{run_id}:result"
            self._redis.set(result_key, json.dumps(summary["phases"]), ex=RUN_TTL)

            self._update_status(run_id, "completed", "done", progress=100)
            self._add_event(run_id, "pipeline", "completed", "All phases finished successfully")

        except Exception as e:
            error_msg = f"{type(e).__name__}: {e}"
            logger.exception("Pipeline failed for run %s", run_id)
            self._update_status(run_id, "failed", "error", error=error_msg)
            self._add_event(run_id, "pipeline", "failed", error_msg)
        finally:
            with self._lock:
                self._active_runs -= 1

    def get_run_state(self, run_id: str) -> dict | None:
        state_key = f"launchmind:run:{run_id}:state"
        state = self._redis.hgetall(state_key)
        if not state:
            return None

        phases_key = f"launchmind:run:{run_id}:phases_completed"
        phases_completed = self._redis.lrange(phases_key, 0, -1)

        result = None
        if state.get("status") == "completed":
            result_key = f"launchmind:run:{run_id}:result"
            result_raw = self._redis.get(result_key)
            if result_raw:
                result = json.loads(result_raw)

        return {
            "run_id": run_id,
            "status": state.get("status", "unknown"),
            "current_phase": state.get("current_phase", ""),
            "phases_completed": phases_completed,
            "phases_total": PHASES,
            "progress_pct": int(state.get("progress_pct", 0)),
            "result": result,
            "error": state.get("error") or None,
            "created_at": state.get("created_at", ""),
            "updated_at": state.get("updated_at", ""),
        }

    def get_events(self, run_id: str, after: int = -1) -> list | None:
        state_key = f"launchmind:run:{run_id}:state"
        if not self._redis.exists(state_key):
            return None

        events_key = f"launchmind:run:{run_id}:events"
        start = after + 1
        raw_events = self._redis.lrange(events_key, start, -1)
        return [json.loads(e) for e in raw_events]

    def check_redis(self) -> bool:
        try:
            self._redis.ping()
            return True
        except Exception:
            return False

    def _update_status(self, run_id: str, status: str, phase: str, progress: int = 0, error: str = ""):
        state_key = f"launchmind:run:{run_id}:state"
        now = datetime.now(timezone.utc).isoformat()
        self._redis.hset(state_key, mapping={
            "status": status,
            "current_phase": phase,
            "progress_pct": str(progress),
            "updated_at": now,
            "error": error,
        })

    def _mark_phase_completed(self, run_id: str, phase: str):
        phases_key = f"launchmind:run:{run_id}:phases_completed"
        existing = self._redis.lrange(phases_key, 0, -1)
        if phase not in existing:
            self._redis.rpush(phases_key, phase)

    def _clear_message_bus(self, bus: MessageBus):
        keys = self._redis.keys("launchmind:inbox:*")
        history = self._redis.keys("launchmind:history")
        to_delete = keys + history
        if to_delete:
            self._redis.delete(*to_delete)
        logger.info("Message bus cleared (run state preserved)")

    def _add_event(self, run_id: str, phase: str, event: str, message: str):
        events_key = f"launchmind:run:{run_id}:events"
        now = datetime.now(timezone.utc).isoformat()
        index = self._redis.llen(events_key)
        event_data = json.dumps({
            "index": index,
            "phase": phase,
            "event": event,
            "message": message,
            "timestamp": now,
        })
        self._redis.rpush(events_key, event_data)
