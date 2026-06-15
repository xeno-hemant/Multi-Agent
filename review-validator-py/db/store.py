"""
db/store.py — Local JSON database layer.

All review and order data is stored in data/reviews.json.
No external database required.
"""

import json
import os
import uuid
from datetime import datetime, timedelta, timezone

# ── Path setup ────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_FILE  = os.path.join(DATA_DIR, "reviews.json")

# ── Sample seed data ──────────────────────────────────────────────────────────
SAMPLE_ORDERS = [
    {"email": "alice@example.com",   "productId": "prod_001", "orderedAt": "2023-12-28"},
    {"email": "bob@example.com",     "productId": "prod_002", "orderedAt": "2024-01-05"},
    {"email": "carol@example.com",   "productId": "prod_003", "orderedAt": "2023-11-14"},
    {"email": "david@example.com",   "productId": "prod_001", "orderedAt": "2024-01-08"},
    {"email": "grace@example.com",   "productId": "prod_004", "orderedAt": "2024-01-09"},
]

def _days_ago(n: int) -> str:
    """Return an ISO date string for n days ago."""
    return (datetime.now(timezone.utc) - timedelta(days=n)).strftime("%Y-%m-%d")

SAMPLE_REVIEWS = [
    {
        "reviewId": "rev_001",
        "reviewerName": "Alice Johnson",
        "reviewerEmail": "alice@example.com",
        "accountCreatedAt": _days_ago(730),
        "totalPastReviews": 23,
        "reviewsLast24h": 1,
        "productId": "prod_001",
        "productName": "Sony WH-1000XM5 Headphones",
        "reviewText": (
            "These headphones are absolutely incredible! The noise cancellation is the best "
            "I've ever experienced — perfect for commuting and working from home. Sound quality "
            "is crystal clear with deep, balanced bass. Battery lasts well over 30 hours. "
            "Build quality feels premium. Worth every penny for anyone serious about audio."
        ),
        "starRating": 5,
        "submittedAt": _days_ago(2),
        "status": "PENDING",
        "validationResult": None,
    },
    {
        "reviewId": "rev_002",
        "reviewerName": "Bob Fake",
        "reviewerEmail": "bob_fake_99@tempmail.com",
        "accountCreatedAt": _days_ago(3),
        "totalPastReviews": 0,
        "reviewsLast24h": 8,
        "productId": "prod_002",
        "productName": "Samsung Galaxy S24 Ultra",
        "reviewText": "Good product. Very good. I like it. Five stars.",
        "starRating": 5,
        "submittedAt": _days_ago(0),
        "status": "PENDING",
        "validationResult": None,
    },
    {
        "reviewId": "rev_003",
        "reviewerName": "Carol Martinez",
        "reviewerEmail": "carol@example.com",
        "accountCreatedAt": _days_ago(400),
        "totalPastReviews": 9,
        "reviewsLast24h": 1,
        "productId": "prod_003",
        "productName": "Dyson V15 Detect Vacuum",
        "reviewText": (
            "Bought this after my old vacuum gave up. The V15 is genuinely impressive — "
            "the laser reveals dust you never knew was there. The HEPA filter is great for "
            "my allergies. Docking and charging is seamless. Only gripe: the bin is smallish "
            "for a large house. Otherwise near-perfect. Would strongly recommend."
        ),
        "starRating": 4,
        "submittedAt": _days_ago(5),
        "status": "PENDING",
        "validationResult": None,
    },
    {
        "reviewId": "rev_004",
        "reviewerName": "David Singh",
        "reviewerEmail": "david@example.com",
        "accountCreatedAt": _days_ago(200),
        "totalPastReviews": 4,
        "reviewsLast24h": 2,
        "productId": "prod_001",
        "productName": "Sony WH-1000XM5 Headphones",
        "reviewText": (
            "Great headphones but a bit pricey. The ANC is top-tier, no complaints there. "
            "Comfort is excellent for long sessions. The app is intuitive. Downside — they "
            "don't fold flat which is annoying for travel. Overall still a solid 4/5."
        ),
        "starRating": 4,
        "submittedAt": _days_ago(3),
        "status": "PENDING",
        "validationResult": None,
    },
    {
        "reviewId": "rev_005",
        "reviewerName": "Eve Spammer",
        "reviewerEmail": "spammer123@fakeemail.xyz",
        "accountCreatedAt": _days_ago(1),
        "totalPastReviews": 0,
        "reviewsLast24h": 15,
        "productId": "prod_005",
        "productName": "Apple MacBook Pro M3",
        "reviewText": "Amazing product highly recommend best ever buy this now great quality.",
        "starRating": 5,
        "submittedAt": _days_ago(0),
        "status": "PENDING",
        "validationResult": None,
    },
    {
        "reviewId": "rev_006",
        "reviewerName": "Frank Nguyen",
        "reviewerEmail": "frank.nguyen@gmail.com",
        "accountCreatedAt": _days_ago(900),
        "totalPastReviews": 41,
        "reviewsLast24h": 1,
        "productId": "prod_006",
        "productName": "LG OLED C3 65\" TV",
        "reviewText": (
            "I debated between the LG C3 and Samsung S90C for months. Finally chose this and "
            "couldn't be happier. Black levels are otherworldly — watching dark scenes in movies "
            "is breathtaking. Gaming mode with 4K@120Hz is flawless for my PS5. The WebOS "
            "interface is snappy and well thought out. Only wish the stand were more flexible."
        ),
        "starRating": 5,
        "submittedAt": _days_ago(7),
        "status": "PENDING",
        "validationResult": None,
    },
    {
        "reviewId": "rev_007",
        "reviewerName": "Grace Liu",
        "reviewerEmail": "grace@example.com",
        "accountCreatedAt": _days_ago(550),
        "totalPastReviews": 12,
        "reviewsLast24h": 0,
        "productId": "prod_004",
        "productName": "Kindle Paperwhite",
        "reviewText": (
            "Perfect e-reader. The screen is crisp even in direct sunlight. Waterproofing "
            "gives me peace of mind at the pool. Battery easily lasts weeks. The flush-front "
            "design feels premium. My only wish is for physical page-turn buttons. "
            "Overall an excellent device for avid readers."
        ),
        "starRating": 5,
        "submittedAt": _days_ago(10),
        "status": "PENDING",
        "validationResult": None,
    },
    {
        "reviewId": "rev_008",
        "reviewerName": "Hank Bot",
        "reviewerEmail": "hank_bot@protonmail.com",
        "accountCreatedAt": _days_ago(5),
        "totalPastReviews": 0,
        "reviewsLast24h": 6,
        "productId": "prod_007",
        "productName": "Instant Pot Duo 7-in-1",
        "reviewText": "Good product. Works well. Recommended. Very happy with purchase.",
        "starRating": 5,
        "submittedAt": _days_ago(0),
        "status": "PENDING",
        "validationResult": None,
    },
    {
        "reviewId": "rev_009",
        "reviewerName": "Iris Patel",
        "reviewerEmail": "iris.patel@outlook.com",
        "accountCreatedAt": _days_ago(300),
        "totalPastReviews": 7,
        "reviewsLast24h": 1,
        "productId": "prod_008",
        "productName": "Nikon Z50 Mirrorless Camera",
        "reviewText": (
            "Switched from a DSLR and the difference is night and day in terms of portability. "
            "The Z50 produces stunning images — colours are accurate and the dynamic range is "
            "impressive. Kit lens is surprisingly capable. AF tracking in video mode is smooth. "
            "Battery life is shorter than I'd like but carrying a spare fixes that. Great buy."
        ),
        "starRating": 4,
        "submittedAt": _days_ago(4),
        "status": "PENDING",
        "validationResult": None,
    },
    {
        "reviewId": "rev_010",
        "reviewerName": "Jake Suspicious",
        "reviewerEmail": "jake_sus@randommail.io",
        "accountCreatedAt": _days_ago(10),
        "totalPastReviews": 0,
        "reviewsLast24h": 3,
        "productId": "prod_009",
        "productName": "Vitamix 5200 Blender",
        "reviewText": (
            "Excellent blender. Very powerful motor. Makes smooth smoothies. Container is big. "
            "Easy to clean. Good warranty. Happy with this. Would buy again."
        ),
        "starRating": 5,
        "submittedAt": _days_ago(1),
        "status": "PENDING",
        "validationResult": None,
    },
]


# ── Core helpers ──────────────────────────────────────────────────────────────

def _ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def load_data() -> dict:
    """Load the full database from JSON file."""
    _ensure_data_dir()
    if not os.path.exists(DB_FILE):
        return {"reviews": [], "orders": []}
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"reviews": [], "orders": []}


def save_data(data: dict):
    """Save the full database to JSON file."""
    _ensure_data_dir()
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


# ── Review CRUD ───────────────────────────────────────────────────────────────

def get_all_reviews() -> list:
    return load_data().get("reviews", [])


def get_review_by_id(review_id: str) -> dict | None:
    for r in get_all_reviews():
        if r.get("reviewId") == review_id:
            return r
    return None


def get_pending_reviews() -> list:
    return [r for r in get_all_reviews() if r.get("status") == "PENDING"]


def add_review(review: dict) -> dict:
    data = load_data()
    if "reviewId" not in review:
        review["reviewId"] = f"rev_{uuid.uuid4().hex[:8]}"
    if "submittedAt" not in review:
        review["submittedAt"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    review.setdefault("status", "PENDING")
    review.setdefault("validationResult", None)
    data["reviews"].append(review)
    save_data(data)
    return review


def update_review(review_id: str, updates: dict):
    data = load_data()
    for i, r in enumerate(data["reviews"]):
        if r.get("reviewId") == review_id:
            data["reviews"][i] = {**r, **updates}
            save_data(data)
            return data["reviews"][i]
    return None


def seed_reviews():
    """Wipe existing data and insert sample reviews + orders."""
    save_data({"reviews": SAMPLE_REVIEWS, "orders": SAMPLE_ORDERS})


def clear_all():
    """Delete all data from the database."""
    save_data({"reviews": [], "orders": []})
