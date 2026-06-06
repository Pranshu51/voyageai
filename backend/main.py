# main.py
# ─────────────────────────────────────────────────────────────
# FASTAPI BACKEND — ENTRY POINT
#
# Endpoints:
#   POST /api/plan        → start a new trip planning run
#   POST /api/approve     → resume after human checkpoint
#   GET  /api/status/{id} → poll current graph state
#   GET  /api/trip/{id}   → get final itinerary
#   GET  /health          → health check
#
# CORS is open for localhost:5173 (Vite dev server)
# ─────────────────────────────────────────────────────────────

import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional

load_dotenv()

from src.state import default_state
from src.graph import build_graph
from src.memory.checkpointer import get_checkpointer, generate_thread_id, get_thread_config

# ─────────────────────────────────────────────────────────────
# APP INIT
# ─────────────────────────────────────────────────────────────

app = FastAPI(
    title="AI Travel Planner API",
    description="LangGraph multi-agent travel planning backend",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite dev
        "http://localhost:3000",   # CRA dev fallback
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Build graph once at startup — reused across all requests
checkpointer = get_checkpointer()
graph = build_graph(checkpointer=checkpointer)

# In-memory job status store
# { thread_id: { "status": "running"|"awaiting_approval"|"done"|"error", "error": str } }
_job_store: dict[str, dict] = {}


# ─────────────────────────────────────────────────────────────
# REQUEST / RESPONSE MODELS
# ─────────────────────────────────────────────────────────────

class PlanRequest(BaseModel):
    destination:   str            = Field(..., example="Tokyo, Japan")
    origin:        str            = Field(..., example="Delhi, India")
    duration_days: int            = Field(..., ge=1, le=30, example=5)
    budget:        float          = Field(..., gt=0, example=80000)
    travel_dates:  str            = Field(..., example="Jan 15 - Jan 20, 2026")
    num_travelers: int            = Field(1, ge=1, le=10)
    preferences:   Optional[str] = Field("", example="budget hotels, street food, anime")


class ApproveRequest(BaseModel):
    thread_id: str
    approved:  bool


class StatusResponse(BaseModel):
    thread_id:            str
    status:               str        # "running" | "awaiting_approval" | "done" | "error"
    budget_status:        Optional[str]
    total_estimated_cost: Optional[float]
    budget:               Optional[float]
    flights:              Optional[dict]
    hotels:               Optional[dict]
    activities:           Optional[dict]
    visa_info:            Optional[dict]
    supervisor_plan:      Optional[str]
    error:                Optional[str]


class ItineraryResponse(BaseModel):
    thread_id:            str
    itinerary:            str
    total_estimated_cost: float
    budget:               float
    budget_status:        str
    flights:              Optional[dict]
    hotels:               Optional[dict]
    activities:           Optional[dict]
    visa_info:            Optional[dict]


# ─────────────────────────────────────────────────────────────
# BACKGROUND TASK — runs graph in background thread
# ─────────────────────────────────────────────────────────────

def _run_graph(thread_id: str, initial_state: dict):
    """
    Runs the LangGraph up to the human checkpoint interrupt.
    Updates _job_store with status as graph progresses.
    """
    import concurrent.futures

    config = get_thread_config(thread_id)
    _job_store[thread_id] = {"status": "running", "error": None}

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(graph.invoke, initial_state, config)
            future.result(timeout=300)  # 5 minute timeout

        _job_store[thread_id]["status"] = "awaiting_approval"
        print(f"[main] Thread {thread_id} paused at human checkpoint ✓")

    except concurrent.futures.TimeoutError:
        print(f"[main] Graph timed out for {thread_id}")
        _job_store[thread_id]["status"] = "error"
        _job_store[thread_id]["error"] = "Graph timed out after 5 minutes"

    except Exception as e:
        print(f"[main] Graph error for {thread_id}: {e}")
        _job_store[thread_id]["status"] = "error"
        _job_store[thread_id]["error"] = str(e)


def _resume_graph(thread_id: str):
    """
    Resumes graph after human approval, runs to END.

    FIX 1: Must pass None (not a state dict) to resume a paused graph.
    FIX 2: Must pass the same thread config so the checkpointer
           loads the correct saved state for this thread.
    """
    config = get_thread_config(thread_id)
    _job_store[thread_id]["status"] = "running"

    try:
        # FIX 1: Pass None — not {"human_approved": True}
        # LangGraph resumes from the checkpointed state automatically.
        # Passing a new state dict would restart the graph, not resume it.
        graph.invoke(None, config=config)
        _job_store[thread_id]["status"] = "done"
        print(f"[main] Thread {thread_id} completed ✓")

    except Exception as e:
        print(f"[main] Resume error for {thread_id}: {e}")
        _job_store[thread_id]["status"] = "error"
        _job_store[thread_id]["error"] = str(e)


# ─────────────────────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "travel-planner-api"}


@app.post("/api/plan", response_model=dict)
def start_plan(req: PlanRequest, background_tasks: BackgroundTasks):
    """
    Start a new trip planning run.
    Returns a thread_id immediately — frontend polls /api/status/{id}.
    Graph runs in background and pauses at human checkpoint.
    """
    thread_id = generate_thread_id()

    initial = default_state(
        destination=req.destination,
        origin=req.origin,
        duration_days=req.duration_days,
        budget=req.budget,
        travel_dates=req.travel_dates,
        num_travelers=req.num_travelers,
        preferences=req.preferences or "",
    )

    background_tasks.add_task(_run_graph, thread_id, initial)

    return {
        "thread_id": thread_id,
        "message":   "Trip planning started. Poll /api/status/{thread_id} for updates.",
    }


@app.get("/api/status/{thread_id}", response_model=StatusResponse)
def get_status(thread_id: str):
    """
    Poll the current state of a graph run.
    Returns agent results as they fill in, plus current job status.
    """
    job = _job_store.get(thread_id)
    if not job:
        raise HTTPException(status_code=404, detail="Thread not found")

    # Try to read current LangGraph state from checkpointer
    config = get_thread_config(thread_id)
    try:
        snapshot = graph.get_state(config)
        state    = snapshot.values if snapshot else {}
    except Exception:
        state = {}

    return StatusResponse(
        thread_id=thread_id,
        status=job["status"],
        budget_status=state.get("budget_status"),
        total_estimated_cost=state.get("total_estimated_cost"),
        budget=state.get("budget"),
        flights=state.get("flights"),
        hotels=state.get("hotels"),
        activities=state.get("activities"),
        visa_info=state.get("visa_info"),
        supervisor_plan=state.get("supervisor_plan"),
        error=job.get("error"),
    )


@app.post("/api/approve")
def approve_itinerary(req: ApproveRequest, background_tasks: BackgroundTasks):
    """
    Human approval / rejection gate.
    - approved=true  → resume graph to generate final itinerary
    - approved=false → mark job as rejected, no further processing
    """
    job = _job_store.get(req.thread_id)
    if not job:
        raise HTTPException(status_code=404, detail="Thread not found")

    if job["status"] != "awaiting_approval":
        raise HTTPException(
            status_code=400,
            detail=f"Thread is not awaiting approval (status: {job['status']})"
        )

    if not req.approved:
        _job_store[req.thread_id]["status"] = "rejected"
        return {"message": "Trip plan rejected."}

    background_tasks.add_task(_resume_graph, req.thread_id)
    return {"message": "Approved. Compiling final itinerary..."}


@app.get("/api/trip/{thread_id}", response_model=ItineraryResponse)
def get_itinerary(thread_id: str):
    """
    Get the final compiled itinerary.
    Only available once status == "done".
    """
    job = _job_store.get(thread_id)
    if not job:
        raise HTTPException(status_code=404, detail="Thread not found")

    if job["status"] != "done":
        raise HTTPException(
            status_code=400,
            detail=f"Itinerary not ready yet (status: {job['status']})"
        )

    config = get_thread_config(thread_id)
    try:
        snapshot = graph.get_state(config)
        state    = snapshot.values
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not read state: {e}")

    return ItineraryResponse(
        thread_id=thread_id,
        itinerary=state.get("itinerary", ""),
        total_estimated_cost=state.get("total_estimated_cost", 0),
        budget=state.get("budget", 0),
        budget_status=state.get("budget_status", "ok"),
        flights=state.get("flights"),
        hotels=state.get("hotels"),
        activities=state.get("activities"),
        visa_info=state.get("visa_info"),
    )


# ─────────────────────────────────────────────────────────────
# DEV RUNNER
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
