# supervisor.py
# ─────────────────────────────────────────────────────────────
# SUPERVISOR AGENT
#
# This is the FIRST node that runs in the graph.
# It does three things:
#   1. Reads user inputs from state
#   2. Uses Gemini to create a structured trip plan
#   3. Decides whether to skip visa agent (domestic trips)
#
# It also runs AGAIN if budget check fails —
# in that case it re-plans with a cheaper approach.
# ─────────────────────────────────────────────────────────────

import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from src.state import TravelState

load_dotenv()

# Initialize Gemini once at module level — not inside the function.
# This avoids re-creating the client on every supervisor call.
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.3,
    thinking_budget=0   # low temp = more consistent, structured output
)

SUPERVISOR_SYSTEM_PROMPT = """
You are a travel planning supervisor. Your job is to:
1. Analyze the user's trip request
2. Create a clear planning strategy for specialist agents
3. Flag any important constraints (budget is tight, visa complications, etc.)

Always respond in this exact format:

PLAN:
[2-3 sentences describing the overall trip strategy]

BUDGET STRATEGY:
[How to split the budget across flights, hotels, activities]

KEY CONSTRAINTS:
[Any important notes agents should know]

DOMESTIC TRIP: [YES or NO]
"""


def supervisor_node(state: TravelState) -> dict:
    """
    LangGraph node — runs first in the graph.

    Reads trip details from state, calls Gemini to produce
    a planning strategy, writes it back as supervisor_plan.

    On retry (retry_count > 0), tells Gemini to find
    cheaper alternatives.
    """
    retry_count = state.get("retry_count", 0)
    is_retry = retry_count > 0

    # Build the user message based on whether this is a retry
    if is_retry:
        total_cost = state.get("total_estimated_cost", 0)
        budget = state.get("budget", 0)
        overage = round(total_cost - budget, 2)

        user_message = f"""
RETRY PLANNING (attempt {retry_count}) — Previous plan was over budget by ₹{overage}.

Trip details:
- From: {state['origin']}
- To: {state['destination']}
- Duration: {state['duration_days']} days
- Dates: {state['travel_dates']}
- Travelers: {state['num_travelers']}
- Total Budget: ₹{state['budget']}
- Preferences: {state.get('preferences', 'none')}

Previous costs:
- Flights: ₹{state.get('flights', {}).get('estimated_cost', 0) if state.get('flights') else 0}
- Hotels: ₹{state.get('hotels', {}).get('estimated_cost', 0) if state.get('hotels') else 0}
- Activities: ₹{state.get('activities', {}).get('estimated_cost', 0) if state.get('activities') else 0}

Please create a CHEAPER plan. Suggest budget airlines, hostels, or free activities.
Focus on reducing the biggest cost item first.
"""
    else:
        user_message = f"""
Plan a trip with these details:
- From: {state['origin']}
- To: {state['destination']}
- Duration: {state['duration_days']} days
- Dates: {state['travel_dates']}
- Travelers: {state['num_travelers']}
- Total Budget: ₹{state['budget']}
- Preferences: {state.get('preferences', 'none')}

Create a planning strategy for the specialist agents.
"""

    messages = [
        SystemMessage(content=SUPERVISOR_SYSTEM_PROMPT),
        HumanMessage(content=user_message),
    ]

    print(f"[supervisor] Running {'retry #' + str(retry_count) if is_retry else 'initial plan'}...")

    response = llm.invoke(messages)
    plan_text = response.content

    print(f"[supervisor] Plan generated ✓")

    # Return only the keys this node updates
    return {
        "supervisor_plan": plan_text,
        "messages": [HumanMessage(content=user_message)],
    }


def should_run_visa_agent(state: TravelState) -> bool:
    """
    Helper used in graph.py to decide whether to include
    the visa agent in the fan-out.

    Checks if DOMESTIC TRIP: YES appears in the supervisor plan.
    Domestic trips skip visa checking entirely.
    """
    plan = state.get("supervisor_plan", "").upper()
    return "DOMESTIC TRIP: YES" not in plan


