# agents/flight_agent.py
# ─────────────────────────────────────────────────────────────
# FLIGHT SPECIALIST AGENT
#
# Runs in PARALLEL with hotel, activity, and visa agents.
# Searches for flights using Tavily, then uses Gemini to
# extract structured cost estimate from the raw results.
#
# Writes ONLY to state["flights"] — never touches other keys.
# ─────────────────────────────────────────────────────────────

import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from src.state import TravelState, FlightResult
from src.tools.search import search_web, format_results_for_llm

load_dotenv()

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.2,
    thinking_budget=0
)

FLIGHT_SYSTEM_PROMPT = """
You are a flight research specialist. Given web search results about flights,
extract the most relevant flight options for the user's trip.

Always respond in this EXACT format — no extra text:

SUMMARY:
[1-2 sentences describing the best flight option found]

ESTIMATED_COST_INR:
[single number, total return cost in INR for all travelers, e.g. 32000]

SOURCE:
[website name where this info was found, e.g. skyscanner.com]

If no clear price is found, make a reasonable estimate based on the route
and clearly say "estimated" in the summary.
"""


def flight_agent_node(state: TravelState) -> dict:
    """
    LangGraph node — runs in parallel during fan-out phase.

    1. Builds a targeted Tavily search query from state
    2. Searches for flights
    3. Passes results to Gemini for structured extraction
    4. Returns partial state update with flights key only
    """
    origin      = state["origin"]
    destination = state["destination"]
    dates       = state["travel_dates"]
    travelers   = state["num_travelers"]
    budget      = state["budget"]
    retry_count = state.get("retry_count", 0)

    # On retry, search specifically for budget/cheap options
    if retry_count > 0:
        query = (
            f"cheapest budget flights {origin} to {destination} "
            f"{dates} economy low cost airline price INR"
        )
    else:
        query = (
            f"flights {origin} to {destination} {dates} "
            f"return ticket price INR {travelers} passenger"
        )

    print(f"[flight_agent] Searching: {query}")

    # Step 1 — Tavily search
    results = search_web(query, max_results=5)
    formatted = format_results_for_llm(results)

    # Step 2 — Gemini extraction
    user_message = f"""
Trip details:
- Route: {origin} → {destination} (return)
- Dates: {dates}
- Travelers: {travelers}
- Total trip budget: ₹{budget}

Web search results:
{formatted}

Extract the best flight option and provide cost estimate.
"""

    messages = [
        SystemMessage(content=FLIGHT_SYSTEM_PROMPT),
        HumanMessage(content=user_message),
    ]

    response = llm.invoke(messages)
    raw = response.content

    print(f"[flight_agent] Raw response:\n{raw}")

    # Step 3 — Parse Gemini's structured response
    flight_result = _parse_flight_response(raw)

    print(f"[flight_agent] Done — estimated ₹{flight_result['estimated_cost']}")

    return {
        "flights": flight_result,
        "messages": [HumanMessage(content=f"Flight search complete: {flight_result['summary']}")],
    }


def _parse_flight_response(raw: str) -> FlightResult:
    """
    Parse the structured text Gemini returns into a FlightResult dict.
    Handles missing sections gracefully with fallback values.
    """
    summary = "Flight options found via web search."
    cost    = 0.0
    source  = "web search"

    lines = raw.strip().splitlines()
    current_section = None

    for line in lines:
        line = line.strip()
        if line.startswith("SUMMARY:"):
            current_section = "summary"
            # value might be on same line after colon
            after = line[len("SUMMARY:"):].strip()
            if after:
                summary = after
        elif line.startswith("ESTIMATED_COST_INR:"):
            current_section = "cost"
            after = line[len("ESTIMATED_COST_INR:"):].strip()
            if after:
                cost = _safe_float(after)
        elif line.startswith("SOURCE:"):
            current_section = "source"
            after = line[len("SOURCE:"):].strip()
            if after:
                source = after
        elif line and current_section == "summary" and not summary.endswith(line):
            summary += " " + line
        elif line and current_section == "cost" and cost == 0.0:
            cost = _safe_float(line)
        elif line and current_section == "source" and source == "web search":
            source = line

    return FlightResult(
        summary=summary,
        estimated_cost=cost,
        source=source,
    )


def _safe_float(value: str) -> float:
    """Convert a string like '32,000' or '₹32000' to float 32000.0"""
    try:
        cleaned = value.replace("₹", "").replace(",", "").replace(" ", "").strip()
        return float(cleaned)
    except (ValueError, AttributeError):
        return 0.0


