# graph.py
# ─────────────────────────────────────────────────────────────
# THE LANGGRAPH ORCHESTRATOR
#
# Wires together all agent nodes into a complete travel-planning
# multi-agent graph. Flow:
#
#   supervisor → [flights, hotels, activities, (visa?)] (parallel fan-out)
#              → budget_checker
#              → [over budget? → supervisor (retry)] | [ok? → itinerary_compiler]
#              → human_checkpoint
#              → END
#
# Key patterns used:
#   - fan_out with Send() for parallel agent execution
#   - conditional edges for budget retry loop
#   - interrupt_before for human-in-the-loop approval
# ─────────────────────────────────────────────────────────────

import os
import re
# FIX 1: Removed "from urllib import response" — it shadowed the llm response variable
from dotenv import load_dotenv

from langgraph.graph import StateGraph, END
from langgraph.constants import Send

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
# FIX 2: Removed broken "from langchain_tavily import TavilySearch" (package doesn't exist)
# FIX 3: Removed unused "from tavily import TavilyClient"
# FIX 4: Correct import for TavilySearchResults
from langchain_community.tools.tavily_search import TavilySearchResults

from src.state import TravelState, FlightResult, HotelResult, ActivityResult, VisaResult
from src.supervisor import supervisor_node, should_run_visa_agent

load_dotenv()

# ─────────────────────────────────────────────────────────────
# SHARED RESOURCES
# ─────────────────────────────────────────────────────────────

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.4,
)

# FIX 5: TavilySearchResults is now correctly imported above
tavily = TavilySearchResults(
    max_results=3,
    tavily_api_key=os.getenv("TAVILY_API_KEY"),
)

MAX_RETRIES = 3   # hard cap on supervisor retry loop


# ─────────────────────────────────────────────────────────────
# HELPER — run a Tavily web search and return top snippet + URL
# ─────────────────────────────────────────────────────────────

def _web_search(query: str) -> tuple[str, str]:
    """Returns (snippet_text, source_url)."""
    try:
        results = tavily.invoke(query)
        if results:
            top = results[0]
            return top.get("content", "No details found."), top.get("url", "web search")
    except Exception as e:
        print(f"[tavily] search failed: {e}")
    return "No results found.", "web search"


# ─────────────────────────────────────────────────────────────
# AGENT NODES
# ─────────────────────────────────────────────────────────────

def flights_node(state: TravelState) -> dict:
    """
    Searches for flights between origin and destination.
    Uses Tavily for real-time data, then asks Gemini to extract
    a cost estimate from the search result.
    """
    origin          = state["origin"]
    destination     = state["destination"]
    dates           = state["travel_dates"]
    travelers       = state["num_travelers"]
    budget          = state["budget"]
    supervisor_plan = state.get("supervisor_plan", "")

    print(f"[flights] Searching {origin} → {destination}...")

    query = f"cheapest flights {origin} to {destination} {dates} round trip price INR 2025"
    snippet, url = _web_search(query)

    prompt = f"""
You are a flight cost estimator.

Supervisor's budget strategy:
{supervisor_plan}

Web search result:
{snippet}

Trip details:
- Route: {origin} → {destination}
- Dates: {dates}
- Travelers: {travelers}
- Total budget: ₹{budget}

Task: Extract or estimate a realistic return flight cost in INR for {travelers} traveler(s).
Respond ONLY in this format (no extra text):
SUMMARY: <airline name and route, e.g. "IndiGo DEL→NRT, return">
COST: <number only, total INR for all travelers>
"""

    # FIX 6: "response" variable is now safe — urllib import removed
    llm_response = llm.invoke([HumanMessage(content=prompt)])
    text = llm_response.content.strip()

    summary = "Flight estimate"
    cost = 0.0
    for line in text.splitlines():
        if line.startswith("SUMMARY:"):
            summary = line.replace("SUMMARY:", "").strip()
        elif line.startswith("COST:"):
            try:
                raw_cost = line.replace("COST:", "").strip().replace(",", "").replace("₹", "")
                match = re.search(r'\d+(?:\.\d+)?', raw_cost)
                cost = float(match.group()) if match else 0.0

            except ValueError:
                cost = 0.0

    print(f"[flights] ✓ {summary} — ₹{cost:,.0f}")

    result: FlightResult = {
        "summary": summary,
        "estimated_cost": cost,
        "source": url,
    }
    return {"flights": result}


def hotels_node(state: TravelState) -> dict:
    """
    Searches for hotel options and estimates total accommodation cost.
    """
    destination     = state["destination"]
    duration        = state["duration_days"]
    travelers       = state["num_travelers"]
    preferences     = state.get("preferences", "")
    supervisor_plan = state.get("supervisor_plan", "")

    print(f"[hotels] Searching hotels in {destination}...")

    style = "budget hostel" if "budget" in preferences.lower() else "hotel"
    query = f"{style} {destination} price per night INR 2025"
    snippet, url = _web_search(query)

    prompt = f"""
You are a hotel cost estimator.

Supervisor's budget strategy:
{supervisor_plan}

Web search result:
{snippet}

Trip details:
- Destination: {destination}
- Duration: {duration} nights
- Travelers: {travelers}
- Preferences: {preferences}

Task: Estimate total accommodation cost in INR for {duration} nights for {travelers} traveler(s).
Respond ONLY in this format:
SUMMARY: <hotel name and type, e.g. "Shinjuku Granbell Hotel, ₹4,500/night">
COST: <total INR for all nights>
"""

    llm_response = llm.invoke([HumanMessage(content=prompt)])
    text = llm_response.content.strip()

    summary = "Hotel estimate"
    cost = 0.0
    for line in text.splitlines():
        if line.startswith("SUMMARY:"):
            summary = line.replace("SUMMARY:", "").strip()
        elif line.startswith("COST:"):
            try:
                cost = float(line.replace("COST:", "").strip().replace(",", ""))
            except ValueError:
                cost = 0.0

    print(f"[hotels] ✓ {summary} — ₹{cost:,.0f}")

    result: HotelResult = {
        "summary": summary,
        "estimated_cost": cost,
        "source": url,
    }
    return {"hotels": result}


def activities_node(state: TravelState) -> dict:
    """
    Finds top activities/attractions and estimates their total cost.
    """
    destination     = state["destination"]
    duration        = state["duration_days"]
    preferences     = state.get("preferences", "")
    supervisor_plan = state.get("supervisor_plan", "")

    print(f"[activities] Searching things to do in {destination}...")

    query = f"top tourist activities {destination} entrance fee cost INR 2025 {preferences}"
    snippet, url = _web_search(query)

    prompt = f"""
You are a travel activities cost estimator.

Supervisor's budget strategy:
{supervisor_plan}

Web search result:
{snippet}

Trip details:
- Destination: {destination}
- Duration: {duration} days
- Preferences: {preferences}

Task: List 3-5 activities and estimate total cost in INR for the trip.
Respond ONLY in this format:
SUMMARY: <comma-separated list of activities>
COST: <total INR>
"""

    llm_response = llm.invoke([HumanMessage(content=prompt)])
    text = llm_response.content.strip()

    summary = "Activities estimate"
    cost = 0.0
    for line in text.splitlines():
        if line.startswith("SUMMARY:"):
            summary = line.replace("SUMMARY:", "").strip()
        elif line.startswith("COST:"):
            try:
                cost = float(line.replace("COST:", "").strip().replace(",", ""))
            except ValueError:
                cost = 0.0

    print(f"[activities] ✓ {summary} — ₹{cost:,.0f}")

    result: ActivityResult = {
        "summary": summary,
        "estimated_cost": cost,
        "source": url,
    }
    return {"activities": result}


def visa_node(state: TravelState) -> dict:
    """
    Checks visa requirements for the traveler's origin country.
    Skipped entirely for domestic trips (see should_run_visa_agent).
    """
    origin      = state["origin"]
    destination = state["destination"]

    print(f"[visa] Checking visa requirements: {origin} → {destination}...")

    query = f"visa requirements India passport {destination} 2025 cost"
    snippet, url = _web_search(query)

    prompt = f"""
You are a visa requirements checker.

Web search result:
{snippet}

Trip details:
- Traveler's origin: {origin}
- Destination: {destination}

Task: State whether a visa is required for an Indian passport holder
and estimate the visa fee in INR if applicable.
Respond ONLY in this format:
SUMMARY: <brief visa status, e.g. "Visa required, e-visa available ~₹2,000">
REQUIRED: <YES or NO>
COST: <fee in INR, or 0 if not required>
"""

    llm_response = llm.invoke([HumanMessage(content=prompt)])
    text = llm_response.content.strip()

    summary  = "Visa info"
    required = False
    cost     = 0.0
    for line in text.splitlines():
        if line.startswith("SUMMARY:"):
            summary = line.replace("SUMMARY:", "").strip()
        elif line.startswith("REQUIRED:"):
            required = "YES" in line.upper()
        elif line.startswith("COST:"):
            try:
                cost = float(line.replace("COST:", "").strip().replace(",", ""))
            except ValueError:
                cost = 0.0

    print(f"[visa] ✓ {summary}")

    # FIX 7: VisaResult now includes estimated_cost (also fixed in state.py)
    result: VisaResult = {
        "summary": summary,
        "required": required,
        "estimated_cost": cost,
        "source": url,
    }
    return {"visa_info": result}


# ─────────────────────────────────────────────────────────────
# BUDGET CHECKER NODE
# ─────────────────────────────────────────────────────────────

def budget_checker_node(state: TravelState) -> dict:
    """
    Sums up all agent costs and compares to the user's budget.
    Sets budget_status to "ok" or "over_budget".
    """
    flights    = state.get("flights") or {}
    hotels     = state.get("hotels") or {}
    activities = state.get("activities") or {}
    visa       = state.get("visa_info") or {}

    total = (
        flights.get("estimated_cost", 0)
        + hotels.get("estimated_cost", 0)
        + activities.get("estimated_cost", 0)
        + visa.get("estimated_cost", 0)
    )

    budget = state.get("budget", 0)
    status = "ok" if total <= budget else "over_budget"

    print(f"[budget] Total: ₹{total:,.0f} / Budget: ₹{budget:,.0f} → {status}")

    return {
        "total_estimated_cost": total,
        "budget_status": status,
    }


# ─────────────────────────────────────────────────────────────
# ITINERARY COMPILER NODE
# ─────────────────────────────────────────────────────────────

def itinerary_compiler_node(state: TravelState) -> dict:
    """
    Takes all agent outputs and produces a complete day-by-day
    itinerary in markdown, ready for the human checkpoint.
    """
    print("[itinerary] Compiling final itinerary...")

    flights    = state.get("flights") or {}
    hotels     = state.get("hotels") or {}
    activities = state.get("activities") or {}
    visa       = state.get("visa_info") or {}

    prompt = f"""
You are a travel itinerary writer.

Trip summary:
- From: {state['origin']} → {state['destination']}
- Dates: {state['travel_dates']} ({state['duration_days']} days)
- Travelers: {state['num_travelers']}
- Preferences: {state.get('preferences', 'none')}
- Total budget: ₹{state['budget']:,.0f}
- Estimated cost: ₹{state['total_estimated_cost']:,.0f}

Research results:
- Flights: {flights.get('summary', 'N/A')} — ₹{flights.get('estimated_cost', 0):,.0f}
- Hotels: {hotels.get('summary', 'N/A')} — ₹{hotels.get('estimated_cost', 0):,.0f}
- Activities: {activities.get('summary', 'N/A')} — ₹{activities.get('estimated_cost', 0):,.0f}
- Visa: {visa.get('summary', 'Not required')} — ₹{visa.get('estimated_cost', 0):,.0f}

Write a detailed, friendly day-by-day travel itinerary in Markdown.
Include: transport, accommodation, daily activities, food suggestions, and tips.
End with a cost breakdown table.
"""

    llm_response = llm.invoke([HumanMessage(content=prompt)])
    itinerary_text = llm_response.content

    print("[itinerary] ✓ Itinerary compiled")

    return {
        "itinerary": itinerary_text,
        "human_approved": False,   # reset — human must approve below
    }


# ─────────────────────────────────────────────────────────────
# HUMAN CHECKPOINT NODE
# ─────────────────────────────────────────────────────────────

def human_checkpoint_node(state: TravelState) -> dict:
    """
    Pauses graph execution for human review.
    LangGraph's interrupt_before mechanism stops BEFORE this node.
    When the graph is resumed via graph.invoke(None, config=config),
    this node runs and marks the trip as approved.
    """
    print("[human] ⏸  Waiting for human approval...")
    print("[human] ✅ Approved — trip plan accepted!")
    return {"human_approved": True}


# ─────────────────────────────────────────────────────────────
# EDGE CONDITIONS
# ─────────────────────────────────────────────────────────────

def after_supervisor(state: TravelState) -> list[Send]:
    """
    Fan-out edge: after supervisor runs, dispatch all specialist
    agents in parallel using LangGraph's Send() API.

    Visa agent is skipped for domestic trips.
    """
    sends = [
        Send("flights_agent",    state),
        Send("hotels_agent",     state),
        Send("activities_agent", state),
    ]
    if should_run_visa_agent(state):
        sends.append(Send("visa_agent", state))
    return sends


def after_budget_check(state: TravelState) -> str:
    """
    Conditional edge after budget_checker.
    - If over budget AND retries remain → back to supervisor
    - Otherwise → itinerary_compiler
    """
    retry_count = state.get("retry_count", 0)
    if state.get("budget_status") == "over_budget" and retry_count < MAX_RETRIES:
        print(f"[router] Over budget — retrying (attempt {retry_count + 1}/{MAX_RETRIES})")
        return "retry_supervisor"
    if state.get("budget_status") == "over_budget":
        print("[router] Max retries reached — proceeding anyway")
    return "compile"


def increment_retry(state: TravelState) -> dict:
    """
    Small pass-through node that bumps retry_count before
    routing back to supervisor, so the supervisor knows
    how many attempts have been made.
    """
    return {"retry_count": state.get("retry_count", 0) + 1}


# ─────────────────────────────────────────────────────────────
# BUILD THE GRAPH
# ─────────────────────────────────────────────────────────────

# FIX 8: Added checkpointer parameter so main.py can pass SqliteSaver in
def build_graph(checkpointer=None):
    """
    Assembles and compiles the full LangGraph state machine.

    Args:
        checkpointer: optional LangGraph checkpointer (e.g. SqliteSaver).
                      Required for human-in-the-loop interrupt + resume to work
                      correctly across separate graph.invoke() calls.

    Returns a compiled graph ready to invoke with:
        graph.invoke(default_state(...), config={"configurable": {"thread_id": "..."}})
    """
    builder = StateGraph(TravelState)

    # ── Add all nodes ─────────────────────────────────────────
    builder.add_node("supervisor",         supervisor_node)
    builder.add_node("flights_agent",      flights_node)
    builder.add_node("hotels_agent",       hotels_node)
    builder.add_node("activities_agent",   activities_node)
    builder.add_node("visa_agent",         visa_node)
    builder.add_node("budget_checker",     budget_checker_node)
    builder.add_node("retry_counter",      increment_retry)
    builder.add_node("itinerary_compiler", itinerary_compiler_node)
    builder.add_node("human_checkpoint",   human_checkpoint_node)

    # ── Entry point ───────────────────────────────────────────
    builder.set_entry_point("supervisor")

    # ── Supervisor → parallel fan-out (flights/hotels/activities/visa) ──
    builder.add_conditional_edges(
        "supervisor",
        after_supervisor,
        ["flights_agent", "hotels_agent", "activities_agent", "visa_agent"],
    )

    # ── All parallel agents → budget checker ──────────────────
    # LangGraph automatically waits for ALL Send() branches
    # before advancing to the next node in the path.
    for agent in ["flights_agent", "hotels_agent", "activities_agent", "visa_agent"]:
        builder.add_edge(agent, "budget_checker")

    # ── Budget checker → compile or retry ─────────────────────
    builder.add_conditional_edges(
        "budget_checker",
        after_budget_check,
        {
            "retry_supervisor": "retry_counter",
            "compile":          "itinerary_compiler",
        },
    )

    # ── Retry counter → back to supervisor ────────────────────
    builder.add_edge("retry_counter", "supervisor")

    # ── Itinerary → human checkpoint → END ────────────────────
    builder.add_edge("itinerary_compiler", "human_checkpoint")
    builder.add_edge("human_checkpoint",   END)

    # FIX 9: Pass checkpointer to compile() — required for interrupt+resume to work
    graph = builder.compile(
        checkpointer=checkpointer,
        interrupt_before=["human_checkpoint"],
    )

    return graph


# ─────────────────────────────────────────────────────────────
# CONVENIENCE RUNNER (CLI / testing only — not used by FastAPI)
# ─────────────────────────────────────────────────────────────

def run_trip_planner(
    destination: str,
    origin: str,
    duration_days: int,
    budget: float,
    travel_dates: str,
    num_travelers: int = 1,
    preferences: str = "",
    auto_approve: bool = False,
) -> TravelState:
    """
    High-level CLI entry point. Builds the graph, runs it, handles the
    human checkpoint, and returns the final state.

    Args:
        auto_approve: If True, skip human prompt and approve automatically.
                      Useful for testing / CI.
    """
    from src.state import default_state
    # FIX 10: Import SqliteSaver for CLI runner's own checkpointer
    from langgraph.checkpoint.sqlite import SqliteSaver

    # CLI runner gets its own in-memory SQLite checkpointer
    checkpointer = SqliteSaver.from_conn_string(":memory:")
    graph = build_graph(checkpointer=checkpointer)

    initial = default_state(
        destination=destination,
        origin=origin,
        duration_days=duration_days,
        budget=budget,
        travel_dates=travel_dates,
        num_travelers=num_travelers,
        preferences=preferences,
    )

    # FIX 11: Must pass a thread config so the checkpointer can save/restore state
    # between the two graph.invoke() calls (before and after human approval)
    thread_id = "cli-run-001"
    config = {"configurable": {"thread_id": thread_id}}

    # ── Phase 1: run until human checkpoint ───────────────────
    print("\n" + "═" * 60)
    print("  🌏  TRAVEL PLANNER — STARTING")
    print("═" * 60)

    # FIX 12: Pass config to first invoke so state is saved to checkpointer
    state_after_plan = graph.invoke(initial, config=config)

    # ── Show itinerary to user ────────────────────────────────
    print("\n" + "─" * 60)
    print("📋  DRAFT ITINERARY")
    print("─" * 60)
    print(state_after_plan.get("itinerary", "No itinerary generated."))
    print("─" * 60)
    print(f"💰  Estimated total: ₹{state_after_plan.get('total_estimated_cost', 0):,.0f}")
    print(f"    Budget:          ₹{state_after_plan.get('budget', 0):,.0f}")

    # ── Phase 2: human approval gate ─────────────────────────
    if auto_approve:
        approved = True
    else:
        answer = input("\n✅  Approve this itinerary? [y/n]: ").strip().lower()
        approved = answer == "y"

    if not approved:
        print("❌  Trip plan rejected. Exiting.")
        return state_after_plan

    # FIX 13: Resume with None (not a dict) and pass the SAME config
    # so the checkpointer loads the paused state for this thread
    final_state = graph.invoke(None, config=config)

    print("\n" + "═" * 60)
    print("  ✈️   TRIP PLAN FINALISED — HAVE A GREAT TRIP!")
    print("═" * 60 + "\n")

    return final_state


# ─────────────────────────────────────────────────────────────
# MAIN — quick smoke test
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    run_trip_planner(
        destination="Tokyo, Japan",
        origin="Delhi, India",
        duration_days=5,
        budget=80_000,
        travel_dates="Jan 15 - Jan 20, 2026",
        num_travelers=1,
        preferences="budget hotels, street food, anime",
        auto_approve=False,
    )
