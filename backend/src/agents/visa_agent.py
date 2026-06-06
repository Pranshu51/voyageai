# agents/visa_agent.py
# ─────────────────────────────────────────────────────────────
# VISA SPECIALIST AGENT
#
# Runs in PARALLEL with flight, hotel, and activity agents.
# ONLY runs for international trips — graph.py skips this
# node entirely for domestic trips (supervisor sets flag).
#
# Searches visa requirements using Tavily, then uses Gemini
# to extract structured requirements and cost estimate.
#
# Writes ONLY to state["visa_info"] — never touches other keys.
# ─────────────────────────────────────────────────────────────

import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from src.state import TravelState, VisaResult
from src.tools.search import search_web, format_results_for_llm

load_dotenv()

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.1,
    thinking_budget=0  # very low — visa info must be precise, not creative
)

VISA_SYSTEM_PROMPT = """
You are a visa and travel documentation specialist. Given web search results
about visa requirements, extract clear and accurate information.

Always respond in this EXACT format — no extra text:

SUMMARY:
[1-2 sentences describing visa requirement and process]

VISA_REQUIRED:
[YES or NO]

ESTIMATED_COST_INR:
[single number, visa fee in INR, e.g. 2000. Use 0 if visa not required or free]

SOURCE:
[website name where this info was found, e.g. mea.gov.in]

Be accurate. If unsure, say visa requirements should be verified
with the official embassy website.
"""


def visa_agent_node(state: TravelState) -> dict:
    """
    LangGraph node — runs in parallel during fan-out phase.
    Skipped entirely for domestic trips via graph routing.

    1. Builds a targeted Tavily search query from state
    2. Searches for visa requirements
    3. Passes results to Gemini for structured extraction
    4. Returns partial state update with visa_info key only
    """
    origin      = state["origin"]
    destination = state["destination"]

    # Extract country names for better search accuracy
    # e.g. "Delhi, India" → "India", "Tokyo, Japan" → "Japan"
    origin_country      = _extract_country(origin)
    destination_country = _extract_country(destination)

    query = (
        f"visa requirements {origin_country} passport "
        f"{destination_country} 2025 tourist visa fee apply"
    )

    print(f"[visa_agent] Searching: {query}")

    # Step 1 — Tavily search
    results = search_web(query, max_results=5)
    formatted = format_results_for_llm(results)

    # Step 2 — Gemini extraction
    user_message = f"""
Trip details:
- Traveler origin / passport: {origin} ({origin_country} passport)
- Destination: {destination} ({destination_country})

Web search results:
{formatted}

Extract visa requirements for a {origin_country} passport holder
traveling to {destination_country} as a tourist.
"""

    messages = [
        SystemMessage(content=VISA_SYSTEM_PROMPT),
        HumanMessage(content=user_message),
    ]

    response = llm.invoke(messages)
    raw = response.content

    print(f"[visa_agent] Raw response:\n{raw}")

    # Step 3 — Parse Gemini's structured response
    visa_result = _parse_visa_response(raw)

    print(f"[visa_agent] Done — visa required: {visa_result['required']}, cost ₹{visa_result['estimated_cost']}")

    return {
        "visa_info": visa_result,
        "messages": [HumanMessage(content=f"Visa check complete: {visa_result['summary']}")],
    }


def _extract_country(location: str) -> str:
    """
    Extract country name from a location string.

    Examples:
        "Delhi, India"   → "India"
        "Tokyo, Japan"   → "Japan"
        "Paris"          → "Paris"   (no comma, return as-is)
        "New York, USA"  → "USA"
    """
    if "," in location:
        return location.split(",")[-1].strip()
    return location.strip()


def _parse_visa_response(raw: str) -> VisaResult:
    """
    Parse the structured text Gemini returns into a VisaResult dict.
    Handles missing sections gracefully with fallback values.
    """
    summary  = "Visa information found via web search."
    required = True   # default to True (safer assumption)
    cost     = 0.0
    source   = "web search"

    lines = raw.strip().splitlines()
    current_section = None

    for line in lines:
        line = line.strip()
        if line.startswith("SUMMARY:"):
            current_section = "summary"
            after = line[len("SUMMARY:"):].strip()
            if after:
                summary = after
        elif line.startswith("VISA_REQUIRED:"):
            current_section = "visa_required"
            after = line[len("VISA_REQUIRED:"):].strip().upper()
            if after:
                required = after == "YES"
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
        elif line and current_section == "visa_required":
            required = line.upper() == "YES"
        elif line and current_section == "cost" and cost == 0.0:
            cost = _safe_float(line)
        elif line and current_section == "source" and source == "web search":
            source = line

    return VisaResult(
        summary=summary,
        required=required,
        estimated_cost=cost,
        source=source,
    )


def _safe_float(value: str) -> float:
    """Convert a string like '2,000' or '₹2000' to float 2000.0"""
    try:
        cleaned = value.replace("₹", "").replace(",", "").replace(" ", "").strip()
        return float(cleaned)
    except (ValueError, AttributeError):
        return 0.0


