# agents/hotel_agent.py
# ─────────────────────────────────────────────────────────────
# HOTEL SPECIALIST AGENT
#
# Runs in PARALLEL with flight, activity, and visa agents.
# Searches for hotels using Tavily, then uses Gemini to
# extract structured cost estimate from the raw results.
#
# Writes ONLY to state["hotels"] — never touches other keys.
# ─────────────────────────────────────────────────────────────

import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from src.state import TravelState, HotelResult
from src.tools.search import search_web, format_results_for_llm

load_dotenv()

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.2,
    thinking_budget=0
)

HOTEL_SYSTEM_PROMPT = """
You are a hotel research specialist. Given web search results about hotels,
extract the most relevant accommodation options for the user's trip.

Always respond in this EXACT format — no extra text:

SUMMARY:
[1-2 sentences describing the best hotel option found]

ESTIMATED_COST_INR:
[single number, total cost for ALL nights for ALL travelers in INR, e.g. 24000]

SOURCE:
[website name where this info was found, e.g. booking.com]

If no clear price is found, make a reasonable estimate based on the destination
and clearly say "estimated" in the summary.
"""


def hotel_agent_node(state: TravelState) -> dict:
    """
    LangGraph node — runs in parallel during fan-out phase.

    1. Builds a targeted Tavily search query from state
    2. Searches for hotels
    3. Passes results to Gemini for structured extraction
    4. Returns partial state update with hotels key only
    """
    destination  = state["destination"]
    dates        = state["travel_dates"]
    duration     = state["duration_days"]
    travelers    = state["num_travelers"]
    budget       = state["budget"]
    preferences  = state.get("preferences", "")
    retry_count  = state.get("retry_count", 0)

    # Extract hotel preference hints from user preferences
    budget_hint = ""
    if any(word in preferences.lower() for word in ["budget", "cheap", "hostel", "backpack"]):
        budget_hint = "hostel budget guesthouse"
    elif any(word in preferences.lower() for word in ["luxury", "5 star", "premium"]):
        budget_hint = "luxury 5 star hotel"
    else:
        budget_hint = "hotel"

    # On retry, force budget accommodation search
    if retry_count > 0:
        query = (
            f"cheapest hostel guesthouse budget accommodation {destination} "
            f"{dates} price per night INR"
        )
    else:
        query = (
            f"{budget_hint} {destination} {dates} "
            f"{duration} nights {travelers} person price INR"
        )

    print(f"[hotel_agent] Searching: {query}")

    # Step 1 — Tavily search
    results = search_web(query, max_results=5)
    formatted = format_results_for_llm(results)

    # Step 2 — Gemini extraction
    user_message = f"""
Trip details:
- Destination: {destination}
- Dates: {dates}
- Duration: {duration} nights
- Travelers: {travelers}
- Preferences: {preferences if preferences else 'no specific preference'}
- Total trip budget: ₹{budget}

Web search results:
{formatted}

Extract the best hotel option and provide TOTAL cost for all nights combined.
If web search results are empty or unhelpful, use your own knowledge to estimate
a realistic hotel cost for {destination} for {duration} nights for {travelers} traveler(s) in INR.
Always provide a number — never return 0.
"""

    messages = [
        SystemMessage(content=HOTEL_SYSTEM_PROMPT),
        HumanMessage(content=user_message),
    ]

    response = llm.invoke(messages)
    raw = response.content

    print(f"[hotel_agent] Raw response:\n{raw}")

    # Step 3 — Parse Gemini's structured response
    hotel_result = _parse_hotel_response(raw)

    print(f"[hotel_agent] Done — estimated ₹{hotel_result['estimated_cost']}")

    return {
        "hotels": hotel_result,
        "messages": [HumanMessage(content=f"Hotel search complete: {hotel_result['summary']}")],
    }


def _parse_hotel_response(raw: str) -> HotelResult:
    """
    Parse the structured text Gemini returns into a HotelResult dict.
    Handles missing sections gracefully with fallback values.
    """
    summary = "Hotel options found via web search."
    cost    = 0.0
    source  = "web search"

    lines = raw.strip().splitlines()
    current_section = None

    for line in lines:
        line = line.strip()
        if line.startswith("SUMMARY:"):
            current_section = "summary"
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

    return HotelResult(
        summary=summary,
        estimated_cost=cost,
        source=source,
    )


def _safe_float(value: str) -> float:
    """Convert a string like '24,000' or '₹24000' or 'approximately 24000' to float 24000.0"""
    import re
    try:
        cleaned = value.replace("₹", "").replace(",", "")
        # Extract first number found in the string (handles "approximately 24000" etc.)
        match = re.search(r'\d+(?:\.\d+)?', cleaned)
        if match:
            return float(match.group())
        return 0.0
    except (ValueError, AttributeError):
        return 0.0


