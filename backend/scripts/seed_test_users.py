"""
Seed the EchoConnect database with a few test users (MongoDB version).

Run:
    python -m backend.scripts.seed_test_users
"""

import os
import sys
import asyncio

# Ensure project root is on PYTHONPATH
PROJECT_ROOT = os.path.abspath(os.path.join(__file__, "..", ".."))
sys.path.append(PROJECT_ROOT)

# Import MongoDB database handle and helper functions
from backend.db.mongo import db, is_connected
from backend.services.auth import hash_password
from backend.services.preferences_service import set_language

# ----------------------------------------------------------------------
TEST_USERS = [
    {
        "user_id": "8143549f-4f87-48b2-b00f-b8173bb0328d",
        "name": "QA Test User",
        "email": "qa_test@echo.com",
        "password": "test123",
    },
    {
        "user_id": "cbfbbd4e-776a-480f-b0cb-ea29facba6e0",
        "name": "Test",
        "email": "verify@test.com",
        "password": "test123",
    },
    {
        "user_id": "ae9f21a3-3e2c-4efc-9106-bc929a8a1520",
        "name": "User1",
        "email": "user1@test.com",
        "password": "pass123",
    },
    {
        "user_id": "9542f05e-ca7a-4169-8620-1d757ab7fd8e",
        "name": "Audit User",
        "email": "audit@test.com",
        "password": "audit123",
    },
]

# ----------------------------------------------------------------------
def create_user(user_doc):
    """Insert a user if it does not already exist (idempotent)."""
    users_coll = db["users"]
    existing = users_coll.find_one({"email": user_doc["email"]})
    if existing:
        print(f"⚠️  {user_doc['email']} already exists – skipping.")
        return
    user_record = {
        "user_id": user_doc["user_id"],
        "name": user_doc["name"],
        "email": user_doc["email"],
        "hashed_password": hash_password(user_doc["password"]),
    }
    users_coll.insert_one(user_record)
    print(f"✅  Created {user_doc['email']}")

# ----------------------------------------------------------------------
if __name__ == "__main__":
    if not is_connected():
        print("[WARN] Database is offline – using mock collections. Data will not persist.")
    # Seed language preferences (set_language is now synchronous)
    languages = ["en", "hi", "es", "fr"]
    for idx, u in enumerate(TEST_USERS):
        create_user(u)
        set_language(u["user_id"], languages[idx % len(languages)])
    print("✅ Database seeding complete!")
