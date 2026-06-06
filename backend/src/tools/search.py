# tools/search.py
# ─────────────────────────────────────────────────────────────
# TAVILY SEARCH WRAPPER
#
# This is the only file that talks to the Tavily API.
# All 4 agents import and call search_web() from here.
# If you ever swap Tavily for another search API,
# you only change THIS file — nothing else breaks.
# ─────────────────────────────────────────────────────────────

import os
from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv()

# Initialize once at module level — not inside the function.
# This avoids re-creating the client on every agent call.
_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))


def search_web(query: str, max_results: int = 5) -> list[dict]:
    """
    Run a Tavily web search and return a clean list of results.

    Args:
        query       : natural language search query
        max_results : how many results to return (default 5)

    Returns:
        List of dicts, each with:
            - title   (str)
            - url     (str)
            - content (str)  ← the actual useful text snippet
    """
    try:
        response = _client.search(
            query=query,
            max_results=max_results,
            search_depth="advanced",   # "basic" is faster, "advanced" is more thorough
            include_answer=True,       # Tavily summarises the top result for you
        )

        results = []
        for item in response.get("results", []):
            results.append({
                "title":   item.get("title", ""),
                "url":     item.get("url", ""),
                "content": item.get("content", ""),
            })

        return results

    except Exception as e:
        # Never crash the graph because search failed.
        # Return an empty list — the agent will handle it gracefully.
        print(f"[search_web] Tavily error: {e}")
        return []


def format_results_for_llm(results: list[dict]) -> str:
    """
    Convert raw search results into a clean string
    that you paste directly into a Gemini prompt.

    Example output:
        [1] Cheapest flights Delhi to Tokyo (skyscanner.com)
            Round trip from ₹28,000 on IndiGo via Bangkok...

        [2] ...
    """
    if not results:
        return "No search results found."

    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"[{i}] {r['title']} ({r['url']})")
        lines.append(f"    {r['content'][:300]}")  # cap at 300 chars per result
        lines.append("")

    return "\n".join(lines)
