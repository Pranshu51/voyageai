# state.py
# ─────────────────────────────────────────────────────────────
# THE SHARED BRAIN OF THE ENTIRE GRAPH
#
# Every agent node receives this state as INPUT and returns a
# PARTIAL update to it. LangGraph merges updates automatically.
#
# Rule: never import this into graph.py circularly.
#       Every other file imports FROM here, nothing imports INTO here.
# ─────────────────────────────────────────────────────────────

from typing import TypedDict, Annotated, Optional
import operator


class FlightResult(TypedDict):
    summary: str          # e.g. "IndiGo DEL→NRT, ~₹32,000 return"
    estimated_cost: float # in INR (or whatever currency user sets)
    source: str           # Tavily result URL or "web search"


class HotelResult(TypedDict):
    summary: str          # e.g. "Shinjuku Granbell Hotel, ₹4,500/night"
    estimated_cost: float # total for all nights
    source: str


class ActivityResult(TypedDict):
    summary: str          # e.g. "Senso-ji, TeamLab, Shibuya crossing"
    estimated_cost: float # total activities budget
    source: str


# FIX 1: Added missing "estimated_cost" field to VisaResult.
# graph.py, budget.py, and compiler.py all call
# visa_info.get("estimated_cost", 0) — without this field defined
# in the TypedDict, type checkers error and the dict construction
# in visa_node raises a TypedDict validation error at runtime.
class VisaResult(TypedDict):
    summary: str          # e.g. "Indian passport: Japan visa required, ~₹2,000"
    required: bool        # True if visa needed
    estimated_cost: float # FIX 1: was missing — visa fee in INR (0 if not required)
    source: str


class TravelState(TypedDict):
    # ── User inputs (set once at the start) ──────────────────
    destination: str              # "Tokyo, Japan"
    origin: str                   # "Delhi, India"
    duration_days: int            # 5
    budget: float                 # 80000.0  (in INR)
    travel_dates: str             # "Jan 15 - Jan 20, 2026"
    num_travelers: int            # 1
    preferences: str              # "budget hotels, street food, anime"

    # ── Agent outputs (filled during graph execution) ─────────
    flights: Optional[FlightResult]
    hotels: Optional[HotelResult]
    activities: Optional[ActivityResult]
    visa_info: Optional[VisaResult]

    # ── Supervisor + budget tracking ──────────────────────────
    supervisor_plan: str          # Supervisor's reasoning / plan text
    total_estimated_cost: float   # Sum of all agent costs
    budget_status: str            # "ok" | "over_budget"
    retry_count: int              # How many times budget loop has retried

    # ── Final output ──────────────────────────────────────────
    itinerary: str                # Compiled day-by-day plan (markdown)
    human_approved: bool          # True after human checkpoint passes

    # ── LangGraph message history (for Gemini chat calls) ─────
    # Annotated with operator.add means new messages are APPENDED
    # not replaced — this is critical for multi-turn agent memory
    messages: Annotated[list, operator.add]


# ─────────────────────────────────────────────────────────────
# DEFAULT STATE — used to initialize a new graph run
# Call this in graph.py when starting a fresh trip plan
# ─────────────────────────────────────────────────────────────

def default_state(
    destination: str,
    origin: str,
    duration_days: int,
    budget: float,
    travel_dates: str,
    num_travelers: int = 1,
    preferences: str = "",
) -> TravelState:
    return TravelState(
        destination=destination,
        origin=origin,
        duration_days=duration_days,
        budget=budget,
        travel_dates=travel_dates,
        num_travelers=num_travelers,
        preferences=preferences,

        flights=None,
        hotels=None,
        activities=None,
        visa_info=None,

        supervisor_plan="",
        total_estimated_cost=0.0,
        budget_status="ok",
        retry_count=0,

        itinerary="",
        human_approved=False,
        messages=[],
    )
