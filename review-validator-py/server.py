"""
server.py -- FastAPI HTTP server for the Multi-Agent Review Validator

Wraps the same agents and database used by the CLI into REST API endpoints
so the tool can be tested via Postman or any HTTP client.

Start server:
    python server.py

Server runs at: http://localhost:8000
API docs at:    http://localhost:8000/docs  (auto-generated Swagger UI)
"""

import os
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional
import uvicorn

# ── Import our existing modules ───────────────────────────────────────────────
from db.store import (
    get_all_reviews, get_review_by_id, get_pending_reviews,
    add_review, update_review, seed_reviews, clear_all, load_data
)
from graph.validator_graph import validate_review

# ── App setup ─────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Multi-Agent Review Validator API",
    description=(
        "REST API for validating e-commerce reviews using a LangGraph "
        "multi-agent pipeline (Credibility + Content + Purchase agents)."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Request / Response models ─────────────────────────────────────────────────

class NewReview(BaseModel):
    reviewerName:     str   = Field(..., example="Alice Johnson")
    reviewerEmail:    str   = Field(..., example="alice@example.com")
    accountCreatedAt: str   = Field(..., example="2022-03-15")
    totalPastReviews: int   = Field(0,   example=23)
    reviewsLast24h:   int   = Field(0,   example=1)
    productId:        str   = Field(..., example="prod_001")
    productName:      str   = Field(..., example="Sony WH-1000XM5 Headphones")
    reviewText:       str   = Field(..., example="These headphones are amazing! The noise cancellation is top tier.")
    starRating:       int   = Field(..., ge=1, le=5, example=5)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/", tags=["Health"])
def root():
    """Health check -- confirms the server is running."""
    groq_live         = bool(os.getenv("GROQ_API_KEY"))         and "your_" not in os.getenv("GROQ_API_KEY", "")
    groq_content_live = bool(os.getenv("GROQ_CONTENT_API_KEY")) and "your_" not in os.getenv("GROQ_CONTENT_API_KEY", "")
    return {
        "status": "ok",
        "message": "Multi-Agent Review Validator API is running",
        "agents": {
            "credibility": "LIVE (Groq LLaMA 3.3)" if groq_live         else "SIMULATED",
            "content":     "LIVE (Groq Qwen 2.5)"  if groq_content_live else "SIMULATED",
            "purchase":    "LIVE (Rule-based)",
        }
    }


@app.get("/reviews", tags=["Reviews"])
def list_reviews():
    """Get all reviews in the database."""
    reviews = get_all_reviews()
    return {
        "count": len(reviews),
        "reviews": reviews,
    }


@app.get("/reviews/{review_id}", tags=["Reviews"])
def get_review(review_id: str):
    """Get a single review by its ID (e.g. rev_001)."""
    review = get_review_by_id(review_id)
    if not review:
        raise HTTPException(status_code=404, detail=f"Review '{review_id}' not found")
    return review


@app.post("/reviews", tags=["Reviews"], status_code=201)
def create_review(body: NewReview):
    """Add a new review to the database (status will be PENDING)."""
    review = add_review(body.model_dump())
    return {
        "message": "Review added successfully",
        "reviewId": review["reviewId"],
        "review": review,
    }


@app.post("/seed", tags=["Database"])
def seed():
    """Wipe database and load 10 sample reviews + 5 orders."""
    seed_reviews()
    reviews = get_all_reviews()
    return {
        "message": "Database seeded successfully",
        "reviewsLoaded": len(reviews),
    }


@app.delete("/reviews", tags=["Database"])
def clear():
    """Delete ALL reviews and orders from the database."""
    clear_all()
    return {"message": "Database cleared"}


@app.get("/stats", tags=["Analytics"])
def stats():
    """Get summary dashboard statistics."""
    reviews = get_all_reviews()
    data    = load_data()
    orders  = data.get("orders", [])

    by_status: dict = {}
    scores = []
    for r in reviews:
        status = r.get("status", "PENDING")
        by_status[status] = by_status.get(status, 0) + 1
        vr = r.get("validationResult") or {}
        if "finalScore" in vr:
            scores.append(vr["finalScore"])

    return {
        "totalReviews":    len(reviews),
        "totalOrders":     len(orders),
        "byStatus":        by_status,
        "validatedCount":  len(scores),
        "averageScore":    round(sum(scores) / len(scores)) if scores else None,
    }


@app.post("/validate/{review_id}", tags=["Validation"])
def validate(review_id: str):
    """
    Run all 3 agents on a single review.

    Agents run in parallel via LangGraph:
    - Credibility Agent  (Groq LLaMA 3.3)
    - Content Agent      (Gemini 2.0 Flash Lite)
    - Purchase Agent     (Rule-based DB lookup)

    Returns the full agent breakdown + final verdict.
    """
    review = get_review_by_id(review_id)
    if not review:
        raise HTTPException(status_code=404, detail=f"Review '{review_id}' not found")

    result = validate_review(review)

    # Persist the result
    verdict = result.get("verdict", "HUMAN_REVIEW")
    update_review(review_id, {
        "status": verdict if verdict in ("APPROVED", "BLOCKED") else "HUMAN_REVIEW",
        "validationResult": {
            "cred":       result.get("cred"),
            "content":    result.get("content"),
            "purchase":   result.get("purchase"),
            "finalScore": result.get("score"),
            "verdict":    verdict,
        },
    })

    return {
        "reviewId":  review_id,
        "reviewer":  review.get("reviewerName"),
        "product":   review.get("productName"),
        "agents": {
            "credibility": result.get("cred"),
            "content":     result.get("content"),
            "purchase":    result.get("purchase"),
        },
        "finalScore":   result.get("score"),
        "finalVerdict": verdict,
        "weights": {
            "credibility": "40%",
            "content":     "40%",
            "purchase":    "20%",
        }
    }


@app.post("/validate-all", tags=["Validation"])
def validate_all():
    """
    Run all 3 agents on every PENDING review.
    Returns a summary of results for each review processed.
    """
    pending = get_pending_reviews()
    if not pending:
        return {"message": "No pending reviews to validate", "results": []}

    results = []
    for review in pending:
        rid = review["reviewId"]
        try:
            result  = validate_review(review)
            verdict = result.get("verdict", "HUMAN_REVIEW")
            update_review(rid, {
                "status": verdict if verdict in ("APPROVED", "BLOCKED") else "HUMAN_REVIEW",
                "validationResult": {
                    "cred":       result.get("cred"),
                    "content":    result.get("content"),
                    "purchase":   result.get("purchase"),
                    "finalScore": result.get("score"),
                    "verdict":    verdict,
                },
            })
            results.append({
                "reviewId":     rid,
                "reviewer":     review.get("reviewerName"),
                "finalScore":   result.get("score"),
                "finalVerdict": verdict,
                "success":      True,
            })
        except Exception as e:
            results.append({
                "reviewId": rid,
                "error":    str(e),
                "success":  False,
            })

    approved     = sum(1 for r in results if r.get("finalVerdict") == "APPROVED")
    blocked      = sum(1 for r in results if r.get("finalVerdict") == "BLOCKED")
    human_review = sum(1 for r in results if r.get("finalVerdict") == "HUMAN_REVIEW")

    return {
        "processed": len(results),
        "summary": {
            "APPROVED":     approved,
            "BLOCKED":      blocked,
            "HUMAN_REVIEW": human_review,
        },
        "results": results,
    }


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
