"""
agents/content_agent.py -- Agent 2: Content Quality Agent

Analyses the review text to determine whether it is genuine or fake.
  - REAL LLM mode: Uses Groq + LLaMA 3.3 70B (set GROQ_CONTENT_API_KEY in .env)
  - SIMULATION mode: Heuristic text analysis (works without any API key)

Output shape:
    {
      "score":   int (0-100),
      "verdict": "GENUINE" | "GENERIC" | "SUSPICIOUS",
      "reason":  str,
      "flags":   list[str],
    }
"""

import os
import re
import json
from dotenv import load_dotenv

load_dotenv()

# Generic / spammy phrases that indicate fake reviews
GENERIC_PHRASES = [
    "good product", "great product", "very good", "highly recommend",
    "best ever", "works well", "love it", "amazing product", "buy this",
    "five stars", "would buy again", "very happy", "great quality",
    "awesome", "perfect product", "nice product", "must buy",
]


def _is_mock() -> bool:
    """Return True if the Groq Qwen key is missing or a placeholder."""
    key = os.getenv("GROQ_CONTENT_API_KEY", "")
    return not key or "xxxxxx" in key or key == "your_groq_content_api_key_here"


# ── Rule-based simulation ─────────────────────────────────────────────────────

def _simulate_content(review_text: str, product_name: str, star_rating: int) -> dict:
    text_lower = review_text.lower()
    words      = review_text.split()
    word_count = len(words)
    flags      = []
    score      = 70

    # Length checks
    if word_count < 10:
        score -= 40
        flags.append("extremely short review")
    elif word_count < 25:
        score -= 20
        flags.append("very short review")
    elif word_count > 80:
        score += 15
        flags.append("detailed review")

    # Generic phrase check
    hits = [p for p in GENERIC_PHRASES if p in text_lower]
    if len(hits) >= 3:
        score -= 30
        flags.append(f"multiple generic phrases ({len(hits)} detected)")
    elif len(hits) >= 1:
        score -= 10
        flags.append(f"some generic language ({len(hits)} phrase(s))")

    # Specificity — does it mention the product name or specific features?
    product_words = [w.lower() for w in product_name.split() if len(w) > 3]
    specific_hits = sum(1 for w in product_words if w in text_lower)
    if specific_hits == 0 and word_count > 20:
        score -= 15
        flags.append("no specific product details mentioned")
    elif specific_hits >= 2:
        score += 10

    # Sentence variety — rough proxy for real writing
    sentences = re.split(r"[.!?]+", review_text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]
    if len(sentences) >= 3:
        score += 5

    score = max(0, min(100, score))

    if score >= 70:
        verdict = "GENUINE"
    elif score < 45:
        verdict = "SUSPICIOUS"
    else:
        verdict = "GENERIC"

    flag_str = ", ".join(flags) if flags else "No issues detected"
    reason = f"[SIM] {flag_str}."
    return {"score": score, "verdict": verdict, "reason": reason, "flags": flags}


# ── LLM-powered analysis via Groq + Qwen ─────────────────────────────────────

def _llm_content(review_text: str, product_name: str, star_rating: int) -> dict:
    from langchain_groq import ChatGroq
    from langchain_core.messages import SystemMessage, HumanMessage

    prompt = f"""You are a review-authenticity AI for an e-commerce platform.

PRODUCT: {product_name}
STAR RATING: {star_rating}/5
REVIEW TEXT:
\"\"\"{review_text}\"\"\"

Analyse the review and score it 0-100 for authenticity.

SCORING GUIDE (start at 70):
- Review < 10 words: subtract 40
- Review < 25 words: subtract 20
- Review > 80 words with specific details: add 15
- Contains 3+ generic phrases (e.g. "good product", "highly recommend"): subtract 30
- No product-specific details mentioned: subtract 15
- Well-structured sentences with varied language: add 10

VERDICT:
- score >= 70 -> "GENUINE"
- score >= 45 -> "GENERIC"
- score < 45  -> "SUSPICIOUS"

Respond with ONLY valid JSON, no markdown, no explanation:
{{"score": <int 0-100>, "verdict": "<GENUINE|GENERIC|SUSPICIOUS>", "reason": "<under 25 words>", "flags": ["<flag1>", "<flag2>"]}}"""

    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=os.getenv("GROQ_CONTENT_API_KEY"),
        temperature=0.1,
        max_tokens=300,
    )

    response = llm.invoke([
        SystemMessage(content="You are a review-authenticity AI. Always respond with valid JSON only. Never include markdown or code blocks."),
        HumanMessage(content=prompt),
    ])

    raw = response.content.strip()
    # Strip any markdown code fences if model adds them
    raw = re.sub(r"```(?:json)?", "", raw).strip()
    match = re.search(r"\{[\s\S]*\}", raw)
    if not match:
        raise ValueError(f"No JSON in Qwen response: {raw[:200]}")

    parsed = json.loads(match.group())
    parsed["score"] = max(0, min(100, int(parsed["score"])))
    if "flags" not in parsed or not isinstance(parsed["flags"], list):
        parsed["flags"] = []
    return parsed


# ── LangGraph node function ───────────────────────────────────────────────────

def run_content_agent(state: dict) -> dict:
    """
    LangGraph node -- reads `state["review"]`, writes `state["content_result"]`.
    """
    review = state["review"]
    try:
        if _is_mock():
            result = _simulate_content(
                review["reviewText"],
                review["productName"],
                review["starRating"],
            )
        else:
            result = _llm_content(
                review["reviewText"],
                review["productName"],
                review["starRating"],
            )
    except Exception as e:
        err_str = str(e)
        # On quota or auth errors, fall back to simulation cleanly
        if any(code in err_str for code in ["429", "400", "RESOURCE_EXHAUSTED", "403", "401", "decom"]):
            print(f"  Content Agent: Groq quota/auth issue, using simulation fallback.")
            result = _simulate_content(
                review["reviewText"],
                review["productName"],
                review["starRating"],
            )
            result["reason"] = "[FALLBACK] " + result["reason"]
        else:
            result = {
                "score": 50, "verdict": "GENERIC",
                "reason": f"Agent error: {err_str[:80]}", "flags": [],
            }

    return {**state, "content_result": result}
