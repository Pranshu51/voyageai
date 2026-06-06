# agents/optimizer.py
# ─────────────────────────────────────────────────────────────
# ITINERARY OPTIMIZER AGENT
#
# Runs AFTER the budget check passes (fan-in complete).
# Takes all 4 agent outputs and creates a logical day-by-day
# sequence — ordering activities, accounting for travel time,
# and fitting everything within the trip duration.
#
# Writes ONLY to state["supervisor_plan"] (extended plan)
# The compiler then uses this to generate the final itinerary.
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

OPTIMIZER_SYSTEM_PROMPT = """
You are a travel itinerary optimizer. Your job is to take all the
research from specialist agents and create a logical, day-by-day
sequence for the trip.

Consider:
- Geographical proximity (group nearby attractions on same day)
- Travel fatigue (don't overpack day 1 after a long flight)
- Opening hours and best times to visit
- Mix of paid and free activities
- Buffer time for travel between locations

Always respond in this EXACT format:

OPTIMIZED_PLAN:
Day 1: [Theme/focus of the day]
- Morning: [activity]
- Afternoon: [activity]
- Evening: [activity]

Day 2: [Theme/focus of the day]
- Morning: [activity]
- Afternoon: [activity]
- Evening: [activity]

[continue for all days]

LOGISTICS:
[2-3 sentences about transport between locations, best areas to stay, tips]

HIGHLIGHTS:
[Top 3 must-do experiences from the whole trip]
"""


def optimizer_node(state: TravelState) -> dict:
    """
    LangGraph node — runs after budget validation passes.

    Collects all agent research from state and asks Gemini
    to sequence it into a logical day-by-day optimized plan.
    """
    destination = state["destination"]
    origin      = state["origin"]
    duration    = state["duration_days"]
    dates       = state["travel_dates"]
    preferences = state.get("preferences", "")

    # Gather all agent summaries
    flights_summary    = state["flights"]["summary"]    if state.get("flights")    else "No flight info"
    hotels_summary     = state["hotels"]["summary"]     if state.get("hotels")     else "No hotel info"
    activities_summary = state["activities"]["summary"] if state.get("activities") else "No activity info"
    visa_summary       = state["visa_info"]["summary"]  if state.get("visa_info")  else "Domestic trip — no visa needed"

    # Get budget breakdown string from budget tool
    budget_breakdown = budget_summary(state)

    print(f"[optimizer] Building optimized {duration}-day plan for {destination}...")

    user_message = f"""
Trip overview:
- Route: {origin} → {destination}
- Dates: {dates}
- Duration: {duration} days
- Preferences: {preferences if preferences else 'general travel'}

Research gathered by specialist agents:

FLIGHTS:
{flights_summary}

ACCOMMODATION:
{hotels_summary}

ACTIVITIES & ATTRACTIONS:
{activities_summary}

VISA & DOCUMENTS:
{visa_summary}

BUDGET:
{budget_breakdown}

Create an optimized day-by-day itinerary for all {duration} days.
Group activities logically, avoid overloading any single day,
and account for the flight arrival/departure days.
"""

    messages = [
        SystemMessage(content=OPTIMIZER_SYSTEM_PROMPT),
        HumanMessage(content=user_message),
    ]

    response = llm.invoke(messages)
    optimized_plan = response.content

    print(f"[optimizer] Optimized plan generated ✓")

    return {
        "supervisor_plan": optimized_plan,
        "messages": [HumanMessage(content="Itinerary optimization complete.")],
    }


