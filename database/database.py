#(©)CodeXBotz

import os
from typing import Optional

import pymongo
from pymongo.errors import ConfigurationError, InvalidURI, PyMongoError

from config import DB_NAME, DB_URI as CONFIG_DB_URI


def _load_db_uri() -> Optional[str]:
    """Load and validate MongoDB URI from environment/config."""
    raw_uri = (
        os.getenv("DB_URI")
        or os.getenv("DATABASE_URL")
        or CONFIG_DB_URI
        or ""
    )
    db_uri = raw_uri.strip()

    if not db_uri:
        print(
            "[ERROR] MongoDB URI is not configured. "
            "Set DB_URI (or DATABASE_URL) environment variable."
        )
        return None

    if not (db_uri.startswith("mongodb://") or db_uri.startswith("mongodb+srv://")):
        print(
            "[ERROR] Invalid MongoDB URI format. "
            "DB_URI must start with 'mongodb://' or 'mongodb+srv://'."
        )
        return None

    return db_uri


def _create_database():
    db_uri = _load_db_uri()
    if not db_uri:
        return None

    try:
        client = pymongo.MongoClient(db_uri)
        return client[DB_NAME]
    except (ConfigurationError, InvalidURI, PyMongoError) as exc:
        print(f"[ERROR] Failed to initialize MongoDB client: {exc}")
        return None


database = _create_database()
user_data = database["users"] if database is not None else None


async def present_user(user_id: int):
    if user_data is None:
        return False
    found = user_data.find_one({"_id": user_id})
    return bool(found)


async def add_user(user_id: int):
    if user_data is None:
        return
    user_data.insert_one({"_id": user_id})


async def full_userbase():
    if user_data is None:
        return []

    user_docs = user_data.find()
    user_ids = []
    for doc in user_docs:
        user_ids.append(doc["_id"])

    return user_ids


async def del_user(user_id: int):
    if user_data is None:
        return
    user_data.delete_one({"_id": user_id})
