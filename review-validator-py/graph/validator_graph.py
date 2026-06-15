"""
graph/validator_graph.py — LangGraph Multi-Agent Orchestration

Graph layout:
                     START
                    /  |  \\
                   /   |   \\
          credibility content purchase   ← runs in parallel
                   \\   |   /
                    \\  |  /
                   aggregate
                      |
                     END

The three agent nodes execute concurrently (LangGraph runs parallel branches
in separate threads). The aggregate node combines their scores into a final
verdict once all three finish.
"""

from typing import TypedDict, Optional, Annotated
import operator

from langgraph.graph import StateGraph, START, END

from agents.credibility_agent import run_credibility_agent
from agents.content_agent      import run_content_agent
from agents.purchase_agent     import run_purchase_agent


# ── State schema ──────────────────────────────────────────────────────────────

class ReviewState(TypedDict):
    review:              dict
    credibility_result:  Annotated[Optional[dict], operator.or_]
    content_result:      Annotated[Optional[dict], operator.or_]
    purchase_result:     Annotated[Optional[dict], operator.or_]
    final_result:        Optional[dict]


# ── Aggregator node ───────────────────────────────────────────────────────────

def aggregate_results(state: ReviewState) -> dict:
    """
    Combines the three agent scores into a single final verdict.

    Weights:
        Credibility  → 40%
        Content      → 40%
        Purchase     → 20%
    """
    cred     = state.get("credibility_result") or {}
    content  = state.get("content_result")     or {}
    purchase = state.get("purchase_result")    or {}

    cred_score     = cred.get("score", 50)
    content_score  = content.get("score", 50)
    purchase_score = purchase.get("score", 0)

    final_score = round(
        cred_score     * 0.40 +
        content_score  * 0.40 +
        purchase_score * 0.20
    )

    if final_score >= 70:
        verdict = "APPROVED"
    elif final_score >= 45:
        verdict = "HUMAN_REVIEW"
    else:
        verdict = "BLOCKED"

    return {
        "final_result": {
            "score":   final_score,
            "verdict": verdict,
            "cred":    cred,
            "content": content,
            "purchase": purchase,
        }
    }


# ── Wrapped agent nodes ───────────────────────────────────────────────────────
# IMPORTANT: Each parallel node must return ONLY its own output key.

def _credibility_node(state: ReviewState) -> dict:
    result = run_credibility_agent(state)
    return {"credibility_result": result["credibility_result"]}

def _content_node(state: ReviewState) -> dict:
    result = run_content_agent(state)
    return {"content_result": result["content_result"]}

def _purchase_node(state: ReviewState) -> dict:
    result = run_purchase_agent(state)
    return {"purchase_result": result["purchase_result"]}


# ── Graph builder ─────────────────────────────────────────────────────────────

def build_validator_graph():
    """
    Compile and return the LangGraph StateGraph for review validation.
    The returned graph is callable: graph.invoke({"review": review_dict})
    """
    builder = StateGraph(ReviewState)

    # Register nodes
    builder.add_node("credibility", _credibility_node)
    builder.add_node("content",     _content_node)
    builder.add_node("purchase",    _purchase_node)
    builder.add_node("aggregate",   aggregate_results)

    # Fan-out: START → all three agents in parallel
    builder.add_edge(START, "credibility")
    builder.add_edge(START, "content")
    builder.add_edge(START, "purchase")

    # Fan-in: all three agents → aggregate
    builder.add_edge("credibility", "aggregate")
    builder.add_edge("content",     "aggregate")
    builder.add_edge("purchase",    "aggregate")

    # Final edge
    builder.add_edge("aggregate", END)

    return builder.compile()


# Singleton — compiled once and reused
_graph = None

def get_graph():
    global _graph
    if _graph is None:
        _graph = build_validator_graph()
    return _graph


def validate_review(review: dict) -> dict:
    """
    Run the full multi-agent pipeline on a single review dict.
    Returns the `final_result` dict from the graph's output state.
    """
    graph  = get_graph()
    output = graph.invoke({"review": review})
    return output["final_result"]
