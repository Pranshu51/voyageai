# agents/compiler.py
# ─────────────────────────────────────────────────────────────
# ITINERARY COMPILER AGENT
#
# The LAST node before the final output.
# Takes the optimized plan + all agent data and compiles
# everything into a clean, formatted final itinerary.
#
# This is what gets sent back to the React frontend.
# Writes ONLY to state["itinerary"].
# ─────────────────────────────────────────────────────────────

import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from src.state import TravelState
from src.tools.budget import budget_summary

load_dotenv()

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.3,
    thinking_budget=0
)

COMPILER_SYSTEM_PROMPT = """
You are a professional travel writer and itinerary compiler.
Your job is to take all trip research and produce a beautiful,
complete, ready-to-use travel itinerary in clean Markdown format.

The itinerary must include:
1. Trip header (destination, dates, travelers, total budget)
2. Pre-trip checklist (visa, documents, packing essentials)
3. Day-by-day plan with morning / afternoon / evening sections
4. Accommodation details
5. Flight details
6. Budget breakdown table
7. Pro tips specific to the destination
8. Emergency contacts section (embassy, local emergency numbers)

Write in a friendly, practical tone. Use markdown formatting:
- ## for major sections
- **bold** for key info
- bullet points for lists
- > blockquotes for pro tips

Make it feel like it was written by an experienced traveler,
not a generic AI. Be specific with place names and practical details.
"""


def compiler_node(state: TravelState) -> dict:
    """
    LangGraph node — the final node in the graph.

    Assembles all agent outputs into a polished final itinerary
    in Markdown format. This is returned to the React frontend.
    """
    destination = state["destination"]
    origin      = state["origin"]
    duration    = state["duration_days"]
    dates       = state["travel_dates"]
    travelers   = state["num_travelers"]
    preferences = state.get("preferences", "")
    budget      = state["budget"]

    # Collect everything
    optimized_plan     = state.get("supervisor_plan", "")
    flights_summary    = state["flights"]["summary"]    if state.get("flights")    else "To be booked"
    flights_source     = state["flights"]["source"]     if state.get("flights")    else ""
    hotels_summary     = state["hotels"]["summary"]     if state.get("hotels")     else "To be booked"
    hotels_source      = state["hotels"]["source"]      if state.get("hotels")     else ""
    activities_summary = state["activities"]["summary"] if state.get("activities") else "See local guides"
    visa_summary       = state["visa_info"]["summary"]  if state.get("visa_info")  else "Domestic trip"
    budget_breakdown   = budget_summary(state)

    print(f"[compiler] Compiling final itinerary for {destination}...")

    user_message = f"""
Compile a complete travel itinerary using all the information below.

TRIP DETAILS:
- Destination: {destination}
- Departing from: {origin}
- Travel dates: {dates}
- Duration: {duration} days
- Number of travelers: {travelers}
- Total budget: ₹{budget:,.0f}
- Preferences: {preferences if preferences else 'general travel'}

OPTIMIZED DAY-BY-DAY PLAN:
{optimized_plan}

FLIGHTS:
{flights_summary}
Source: {flights_source}

ACCOMMODATION:
{hotels_summary}
Source: {hotels_source}

ACTIVITIES:
{activities_summary}

VISA & DOCUMENTS:
{visa_summary}

BUDGET BREAKDOWN:
{budget_breakdown}

Now compile this into a complete, beautifully formatted Markdown itinerary.
Make it detailed, practical, and ready to use. Include all sections listed
in your instructions. Add destination-specific pro tips at the end.
"""

    messages = [
        SystemMessage(content=COMPILER_SYSTEM_PROMPT),
        HumanMessage(content=user_message),
    ]

    response = llm.invoke(messages)
    itinerary = response.content

    print(f"[compiler] Final itinerary compiled ✓ ({len(itinerary)} chars)")

    return {
        "itinerary": itinerary,
        "messages": [HumanMessage(content="Final itinerary compiled successfully.")],
    }


