"""
agents/credibility_agent.py — Agent 1: Credibility Agent

Assesses reviewer trustworthiness using account metadata.
  - REAL LLM mode: Uses Groq + LLaMA 3.3 70B (set GROQ_API_KEY in .env)
  - SIMULATION mode: Rule-based scoring (works without any API key)

Output shape:
    { "score": int (0-100), "verdict": "REAL"|"SUSPICIOUS"|"FAKE", "reason": str }
"""

import os
import json
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()


def _is_mock() -> bool:
    """Return True if the Groq key is missing or a placeholder."""
    key = os.getenv("GROQ_API_KEY", "")
    return not key or "xxxxxx" in key or key == "your_groq_api_key_here"


def _account_age_days(account_created_at: str) -> int:
    try:
        created = datetime.fromisoformat(account_created_at.replace("Z", "+00:00"))
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return max(0, (datetime.now(timezone.utc) - created).days)
    except Exception:
        return 0


# ── Rule-based simulation ─────────────────────────────────────────────────────

def _simulate_credibility(account_created_at: str, total_past_reviews: int,
                           reviews_last_24h: int, star_rating: int) -> dict:
    age_days = _account_age_days(account_created_at)
    score = 70
    reasons = []

    if age_days < 7:
        score -= 40
        reasons.append(f"new account ({age_days} days old)")
    if reviews_last_24h > 5:
        score -= 30
        reasons.append(f"high review velocity ({reviews_last_24h} in 24 h)")
    if total_past_reviews == 0:
        score -= 20
        reasons.append("no prior review history")
    if age_days > 180 and total_past_reviews >= 5:
        score += 30
        reasons.append("established account with good history")

    score = max(0, min(100, score))

    if score >= 75:
        verdict = "REAL"
    elif score < 45:
        verdict = "FAKE"
    else:
        verdict = "SUSPICIOUS"

    reason = (
        f"[SIM] {'; '.join(reasons)}." if reasons
        else "[SIM] Standard behaviour — no red flags detected."
    )
    return {"score": score, "verdict": verdict, "reason": reason}


# ── LLM-powered scoring ───────────────────────────────────────────────────────

def _llm_credibility(account_created_at: str, total_past_reviews: int,
                     reviews_last_24h: int, star_rating: int) -> dict:
    from langchain_groq import ChatGroq
    from langchain_core.messages import SystemMessage, HumanMessage

    age_days = _account_age_days(account_created_at)

    prompt = f"""You are a fraud-detection AI for an e-commerce platform.

REVIEWER DATA:
- Account age: {age_days} days (created {account_created_at})
- Total past reviews on platform: {total_past_reviews}
- Reviews submitted in last 24 hours: {reviews_last_24h}
- Star rating given: {star_rating}/5

SCORING RULES (start at 70):
1. Account < 7 days old → subtract 40
2. More than 5 reviews in last 24 h → subtract 30
3. Zero total past reviews → subtract 20
4. Account > 6 months old AND 5+ past reviews → add 30

VERDICT:
- score >= 75 → "REAL"
- score >= 45 → "SUSPICIOUS"
- score < 45  → "FAKE"

Respond with ONLY valid JSON, no markdown, no explanation:
{{"score": <int 0-100>, "verdict": "<REAL|SUSPICIOUS|FAKE>", "reason": "<under 20 words>"}}"""

    llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.1, max_tokens=200)
    response = llm.invoke([
        SystemMessage(content="You are a fraud-detection AI. Always respond with valid JSON only."),
        HumanMessage(content=prompt),
    ])

    raw = response.content.strip()
    match = __import__("re").search(r"\{[\s\S]*\}", raw)
    if not match:
        raise ValueError(f"No JSON in LLM response: {raw}")

    parsed = json.loads(match.group())
    parsed["score"] = max(0, min(100, int(parsed["score"])))
    return parsed


# ── LangGraph node function ───────────────────────────────────────────────────

def run_credibility_agent(state: dict) -> dict:
    """
    LangGraph node — reads `state["review"]`, writes `state["credibility_result"]`.
    """
    review = state["review"]
    try:
        if _is_mock():
            result = _simulate_credibility(
                review["accountCreatedAt"],
                review["totalPastReviews"],
                review["reviewsLast24h"],
                review["starRating"],
            )
        else:
            result = _llm_credibility(
                review["accountCreatedAt"],
                review["totalPastReviews"],
                review["reviewsLast24h"],
                review["starRating"],
            )
    except Exception as e:
        result = {"score": 50, "verdict": "SUSPICIOUS", "reason": f"Agent error: {e}"}

    return {**state, "credibility_result": result}
