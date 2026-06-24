# backend/services/preferences_service.py
"""Simple user‑preference store (language code) for EchoConnect.

Uses the MongoDB client defined in `backend.db.mongo`.
Each document is:
{
    "user_id": "<uuid>",
    "language_code": "en"  # ISO‑639‑1 code
}
"""

import logging
from typing import Optional
from backend.db.mongo import db

logger = logging.getLogger(__name__)

_PREFS_COLL = "user_preferences"


def set_language(user_id: str, language_code: str) -> None:
    """Create or update the language preference for *user_id*."""
    coll = db[_PREFS_COLL]
    coll.update_one(
        {"user_id": user_id},
        {"$set": {"language_code": language_code.lower()}},
        upsert=True,
    )
    logger.info("[PREF] Set %s for user %s", language_code, user_id)


def get_language(user_id: str) -> Optional[str]:
    """Return the stored language code, or ``None`` if not set."""
    coll = db[_PREFS_COLL]
    doc = coll.find_one({"user_id": user_id}, {"_id": 0, "language_code": 1})
    return doc.get("language_code") if doc else None
