# Wandr — AI-Powered Travel Planner

A multi-agent travel planning system built with LangGraph, FastAPI, and React. Give it a destination, budget, and dates — it dispatches parallel AI agents to research flights, hotels, activities, and visa requirements, checks the budget, and compiles a complete day-by-day itinerary.

---

## Architecture

```
travel_planner/
├── backend/
│   ├── src/
│   │   ├── state.py              # Shared TravelState TypedDict
│   │   ├── graph.py              # LangGraph orchestrator
│   │   ├── supervisor.py         # Supervisor agent (planner + retry logic)
│   │   ├── agents/
│   │   │   ├── flight_agent.py   # Searches flights, extracts cost
│   │   │   ├── hotel_agent.py    # Searches hotels, extracts cost
│   │   │   ├── activity_agent.py # Finds attractions, estimates budget
│   │   │   ├── visa_agent.py     # Checks visa requirements + fee
│   │   │   ├── optimizer.py      # Sequences agents into day-by-day plan
│   │   │   └── compiler.py       # Compiles final markdown itinerary
│   │   ├── tools/
│   │   │   ├── search.py         # Tavily search wrapper (used by all agents)
│   │   │   └── budget.py         # Cost calculator + budget validator
│   │   └── memory/
│   │       └── checkpointer.py   # SQLite checkpointer for LangGraph state
│   ├── main.py                   # FastAPI app
│   ├── .env                      # API keys (never commit this)
│   └── requirements.txt
│
└── frontend/
    └── travel-planner-ui/
        └── src/
            └── App.jsx           # Full React frontend (single file)
```

---

## How It Works

```
User Input
    ↓
Supervisor Agent         ← creates planning strategy, detects domestic/international
    ↓
┌─────────────────────────────────────────────┐
│  Parallel fan-out (LangGraph Send API)       │
│                                             │
│  Flight Agent   Hotel Agent   Activity Agent  │
│                                  Visa Agent*  │
│  (* skipped for domestic trips)             │
└─────────────────────────────────────────────┘
    ↓
Budget Checker           ← sums all costs vs user budget
    ↓
Over budget?  ──YES──→  Supervisor retries (max 3x, cheaper options)
    ↓ NO
Optimizer Agent          ← sequences into logical day-by-day plan
    ↓
Compiler Agent           ← writes final markdown itinerary
    ↓
Human Checkpoint         ← frontend shows cost breakdown, user approves/rejects
    ↓
Final Itinerary          ← returned to React frontend
```

---

## Tech Stack

| Layer | Tech |
|---|---|
| Agent orchestration | LangGraph |
| LLM | Gemini 2.0 Flash (via `langchain-google-genai`) |
| Web search | Tavily (`tavily-python`) |
| Backend API | FastAPI + Uvicorn |
| State persistence | SQLite via `langgraph-checkpoint-sqlite` |
| Frontend | React + Vite (plain JavaScript) |

---

## Prerequisites

- Python 3.11+
- Node.js 18+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- API keys for:
  - [Google Gemini](https://aistudio.google.com/) — free tier works
  - [Tavily](https://tavily.com/) — free tier works

---

## Setup

### 1. Clone and create virtual environment

```bash
git clone https://github.com/your-username/wandr.git
cd travel_planner
uv venv
```

Activate it:

```bash
# Windows
.venv\Scripts\activate

# Mac/Linux
source .venv/bin/activate
```

### 2. Install backend dependencies

```bash
cd backend
uv add fastapi uvicorn python-dotenv pydantic
uv add langgraph langchain langchain-core langchain-google-genai langchain-community
uv add langgraph-checkpoint-sqlite
uv add tavily-python
```

### 3. Configure environment variables

Create `backend/.env`:

```env
GEMINI_API_KEY=your_gemini_api_key_here
TAVILY_API_KEY=your_tavily_api_key_here
```

### 4. Create Python package init files

Run from inside `backend/`:

```powershell
# Windows PowerShell
New-Item src/__init__.py -Force
New-Item src/agents/__init__.py -Force
New-Item src/tools/__init__.py -Force
New-Item src/memory/__init__.py -Force
```

```bash
# Mac/Linux
touch src/__init__.py src/agents/__init__.py src/tools/__init__.py src/memory/__init__.py
```

### 5. Install frontend dependencies

```bash
cd ../frontend/travel-planner-ui
npm install
```

---

## Running

### Backend

Always run from inside the `backend/` folder:

```powershell
# Windows PowerShell
cd D:\travel_planner\backend
$env:PYTHONPATH="."; uv run uvicorn main:app --reload
```

```bash
# Mac/Linux
cd travel_planner/backend
PYTHONPATH=. uv run uvicorn main:app --reload
```

Server starts at `http://localhost:8000`

### Frontend

```bash
cd frontend/travel-planner-ui
npm run dev
```

App opens at `http://localhost:5173`

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/api/plan` | Start a new trip planning run |
| `GET` | `/api/status/{thread_id}` | Poll live agent progress |
| `POST` | `/api/approve` | Approve or reject the draft plan |
| `GET` | `/api/trip/{thread_id}` | Fetch the final compiled itinerary |

### Example: Start a plan

```bash
curl -X POST http://localhost:8000/api/plan \
  -H "Content-Type: application/json" \
  -d '{
    "destination": "Tokyo, Japan",
    "origin": "Delhi, India",
    "duration_days": 5,
    "budget": 80000,
    "travel_dates": "Jan 15 - Jan 20, 2026",
    "num_travelers": 1,
    "preferences": "budget hotels, street food, anime"
  }'
```

Response:
```json
{
  "thread_id": "trip-a3f9b2c1",
  "message": "Trip planning started. Poll /api/status/{thread_id} for updates."
}
```

---

## Frontend Flow

1. **Plan Form** — enter destination, origin, dates, budget, preferences
2. **Processing** — live agent cards light up as each agent finishes (polls every 2.5s)
3. **Review Gate** — shows full cost breakdown; approve to compile or reject to restart
4. **Final Itinerary** — rendered markdown with day-by-day plan, budget table, and tips

---

## Key Design Decisions

**Parallel agents via `Send()`** — LangGraph's `Send` API dispatches all 4 specialist agents simultaneously. A 5-agent run takes roughly the same time as 1 agent.

**Budget retry loop** — if total cost exceeds budget, the supervisor re-runs (up to 3 times) with instructions to find cheaper alternatives. The retry count is tracked in state so each agent knows to suggest budget options.

**Domestic trip detection** — the supervisor's response is checked for `DOMESTIC TRIP: YES`. If found, the visa agent is skipped entirely from the fan-out.

**Human-in-the-loop** — LangGraph's `interrupt_before` pauses the graph at the human checkpoint node. The frontend polls until status is `awaiting_approval`, shows the cost breakdown, then resumes the graph on approval via a second `invoke()` call.

**SQLite checkpointing** — every node write is persisted to `travel_memory.db`. If the server crashes mid-run, the graph can resume from the last completed node using the `thread_id`.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | Yes | Google Gemini API key |
| `TAVILY_API_KEY` | Yes | Tavily search API key |

---

## Common Errors

**`ModuleNotFoundError: No module named 'src'`**
→ You're not setting `PYTHONPATH`. Run with `$env:PYTHONPATH="."; uv run uvicorn main:app --reload` from inside `backend/`.

**`ModuleNotFoundError: No module named 'langgraph.checkpoint.sqlite'`**
→ Run `uv add langgraph-checkpoint-sqlite` and update the import to `from langgraph_checkpoint_sqlite import SqliteSaver`.

**`Attribute "app" not found in module "main"`**
→ You're running uvicorn from the wrong folder. Must be run from inside `backend/`, not the project root.

**`NameError: TavilySearchResults is not defined`**
→ Remove the LangChain Tavily import from `graph.py`. Search is handled directly in `src/tools/search.py` using `tavily-python`.

---

## License

MIT

---

## Author

**Pranshu Tiwari** — [github.com/Pranshu51](https://github.com/Pranshu51)
