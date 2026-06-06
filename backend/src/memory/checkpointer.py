# memory/checkpointer.py
# ─────────────────────────────────────────────────────────────
# SQLITE CHECKPOINTER SETUP
#
# LangGraph saves the entire TravelState to SQLite after
# every single node execution. This means:
#   - If your server crashes mid-graph, resume from last node
#   - Each user trip gets its own thread_id
#   - You can inspect any past trip by thread_id
#
# The .db file is auto-created on first run at:
#   backend/travel_memory.db
# ─────────────────────────────────────────────────────────────

import os
import uuid
import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver

# Path to the SQLite file — sits at backend/ root level
DB_PATH = os.path.join(
    os.path.dirname(__file__),  # backend/src/memory/
    "..",                        # backend/src/
    "..",                        # backend/
    "travel_memory.db"           # backend/travel_memory.db
)

DB_PATH = os.path.normpath(DB_PATH)


def get_checkpointer() -> SqliteSaver:
    """
    Returns a SqliteSaver instance connected to travel_memory.db.

    FIX: SqliteSaver.from_conn_string() returns a context manager,
    NOT a saver instance directly. You must open the connection
    manually and pass it to SqliteSaver() instead.

    Call this once at startup in main.py:
        checkpointer = get_checkpointer()
        graph = build_graph(checkpointer=checkpointer)
    """
    print(f"[checkpointer] Using DB at: {DB_PATH}")
    # Open a persistent sqlite3 connection and pass it directly.
    # This gives us a real SqliteSaver instance (not a context manager).
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    return SqliteSaver(conn)


def generate_thread_id(user_identifier: str = "") -> str:
    """
    Generate a unique thread_id for each trip planning session.

    thread_id is what LangGraph uses to separate different
    users / sessions in the same SQLite database.

    Usage in main.py (FastAPI):
        thread_id = generate_thread_id(user_email)
        config = {"configurable": {"thread_id": thread_id}}
        result = graph.invoke(initial_state, config=config)

    Args:
        user_identifier : optional string (email, username, etc.)
                          makes the ID slightly more readable in logs

    Returns:
        A unique string like "trip-a3f9b2c1" or "user@email.com-a3f9b2c1"
    """
    unique_part = uuid.uuid4().hex[:8]
    if user_identifier:
        return f"{user_identifier}-{unique_part}"
    return f"trip-{unique_part}"


def get_thread_config(thread_id: str) -> dict:
    """
    Returns the config dict that LangGraph expects when
    invoking or resuming a graph run.

    Usage:
        config = get_thread_config(thread_id)

        # Start new run
        graph.invoke(state, config=config)

        # Resume after human checkpoint
        graph.invoke(None, config=config)

        # Get current state of a run
        graph.get_state(config)
    """
    return {"configurable": {"thread_id": thread_id}}
