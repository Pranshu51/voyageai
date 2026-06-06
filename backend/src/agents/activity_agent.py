# agents/activity_agent.py
# ─────────────────────────────────────────────────────────────
# ACTIVITY SPECIALIST AGENT
#
# Runs in PARALLEL with flight, hotel, and visa agents.
# Searches for things to do at the destination using Tavily,
# then uses Gemini to extract structured cost estimate.
#
# Writes ONLY to state["activities"] — never touches other keys.
# ─────────────────────────────────────────────────────────────

import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from src.state import TravelState, ActivityResult
from src.tools.search import search_web, format_results_for_llm

load_dotenv()

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.4,
    thinking_budget=0  # slightly higher — more creative activity suggestions
)

ACTIVITY_SYSTEM_PROMPT = """
You are a travel activities specialist. Given web search results about
things to do at a destination, extract the best activity recommendations.

Always respond in this EXACT format — no extra text:

SUMMARY:
[2-3 sentences listing the top activities and experiences recommended]

ESTIMATED_COST_INR:
[single number, total estimated activity spend for ALL days for ALL travelers in INR, e.g. 8000]

SOURCE:
[website name where this info was found, e.g. tripadvisor.com]

Include both paid attractions and free experiences in the summary.
If no clear price is found, estimate based on typical costs for the destination.
"""


def activity_agent_node(state: TravelState) -> dict:
    """
    LangGraph node — runs in parallel during fan-out phase.

    1. Builds a targeted Tavily search query from state
    2. Searches for activities and attractions
    3. Passes results to Gemini for structured extraction
    4. Returns partial state update with activities key only
    """
    destination = state["destination"]
    duration    = state["duration_days"]
    travelers   = state["num_travelers"]
    budget      = state["budget"]
    preferences = state.get("preferences", "")
    retry_count = state.get("retry_count", 0)

    # Build interest tags from user preferences
    interest_tags = _extract_interests(preferences)

    # On retry, focus on free and cheap activities
    if retry_count > 0:
        query = (
            f"free things to do {destination} cheap attractions "
            f"budget travel tips {duration} days"
        )
    else:
        query = (
            f"best things to do {destination} {duration} days "
            f"{interest_tags} attractions cost price INR"
        )

    print(f"[activity_agent] Searching: {query}")

    # Step 1 — Tavily search
    results = search_web(query, max_results=5)
    formatted = format_results_for_llm(results)

    # Step 2 — Gemini extraction
    user_message = f"""
Trip details:
- Destination: {destination}
- Duration: {duration} days
- Travelers: {travelers}
- Interests / preferences: {preferences if preferences else 'general sightseeing'}
- Total trip budget: ₹{budget}

Web search results:
{formatted}

Recommend the best activities and estimate TOTAL activity spend
for all days combined for all travelers in INR.
If web search results are empty or unhelpful, use your own knowledge to estimate
realistic activity costs for {destination} for {duration} days for {travelers} traveler(s).
Always provide a number — never return 0.
"""

    messages = [
        SystemMessage(content=ACTIVITY_SYSTEM_PROMPT),
        HumanMessage(content=user_message),
    ]

    response = llm.invoke(messages)
    raw = response.content

    print(f"[activity_agent] Raw response:\n{raw}")

    # Step 3 — Parse Gemini's structured response
    activity_result = _parse_activity_response(raw)

    print(f"[activity_agent] Done — estimated ₹{activity_result['estimated_cost']}")

    return {
        "activities": activity_result,
        "messages": [HumanMessage(content=f"Activity search complete: {activity_result['summary']}")],
    }


def _extract_interests(preferences: str) -> str:
    """
    Pull interest keywords from preferences to improve search query.

    Examples:
        "I love anime and street food"  → "anime street food"
        "adventure trekking photography" → "adventure trekking photography"
        ""                               → "sightseeing culture food"
    """
    if not preferences:
        return "sightseeing culture food"

    # Common interest keywords to look for
    keywords = [
        "anime", "manga", "food", "street food", "culture", "history",
        "museum", "art", "photography", "adventure", "trekking", "hiking",
        "beach", "shopping", "nightlife", "temple", "nature", "wildlife",
        "architecture", "music", "festival", "sport", "diving", "surfing",
    ]

    found = []
    prefs_lower = preferences.lower()
    for kw in keywords:
        if kw in prefs_lower:
            found.append(kw)

    return " ".join(found) if found else "sightseeing"


def _parse_activity_response(raw: str) -> ActivityResult:
    """
    Parse the structured text Gemini returns into an ActivityResult dict.
    Handles missing sections gracefully with fallback values.
    """
    summary = "Activity recommendations found via web search."
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

    return ActivityResult(
        summary=summary,
        estimated_cost=cost,
        source=source,
    )


def _safe_float(value: str) -> float:
    """Convert a string like '8,000' or '₹8000' to float 8000.0"""
    try:
        cleaned = value.replace("₹", "").replace(",", "").replace(" ", "").strip()
        return float(cleaned)
    except (ValueError, AttributeError):
        return 0.0


