"""
agents/purchase_agent.py — Agent 3: Purchase Verification Agent

Checks whether the reviewer actually purchased the product being reviewed
by looking up the local orders database.

This agent is always rule-based (no LLM needed — it's a database lookup).

Output shape:
    { "score": int (0 or 100), "verdict": "VERIFIED" | "UNVERIFIED", "reason": str }
"""

from db.store import load_data


def run_purchase_agent(state: dict) -> dict:
    """
    LangGraph node — reads `state["review"]`, writes `state["purchase_result"]`.
    """
    review  = state["review"]
    email   = review.get("reviewerEmail", "").lower().strip()
    prod_id = review.get("productId", "")

    data   = load_data()
    orders = data.get("orders", [])

    purchased = any(
        o.get("email", "").lower().strip() == email and o.get("productId") == prod_id
        for o in orders
    )

    if purchased:
        result = {
            "score":   100,
            "verdict": "VERIFIED",
            "reason":  f"Order found for {email} on product {prod_id}.",
        }
    else:
        result = {
            "score":   0,
            "verdict": "UNVERIFIED",
            "reason":  f"No purchase record found for {email} on product {prod_id}.",
        }

    return {**state, "purchase_result": result}
