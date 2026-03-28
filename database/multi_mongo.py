import asyncio
import logging
import os
from typing import Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import ConfigurationError, InvalidURI, PyMongoError

from config import DB_NAME, DB_URI

LOGGER = logging.getLogger(__name__)


class MultiMongoManager:
    """Async MongoDB pool with failover, retry, and runtime URI management."""

    def __init__(self) -> None:
        env_list = os.getenv("MONGO_URIS", "")
        seed_uris = [u.strip() for u in env_list.split(",") if u.strip()]
        if DB_URI and DB_URI.strip() and DB_URI.strip() not in seed_uris:
            seed_uris.insert(0, DB_URI.strip())

        self._uris: List[str] = seed_uris
        self._clients: Dict[str, AsyncIOMotorClient] = {}
        self._active_uri: Optional[str] = None
        self._init_lock = asyncio.Lock()

    async def initialize(self, retries: int = 2) -> bool:
        async with self._init_lock:
            LOGGER.info("Connecting to MongoDB...")
            for attempt in range(retries + 1):
                db = await self._select_available_db()
                if db is not None:
                    LOGGER.info("MongoDB Connected")
                    return True
                if attempt < retries:
                    await asyncio.sleep(1.2 * (attempt + 1))
            LOGGER.error("DB is None ERROR")
            return False

    async def ensure_database(self) -> AsyncIOMotorDatabase:
        db = await self.get_database()
        if db is None:
            LOGGER.error("DB is None ERROR")
            raise Exception("Error: Database not initialized")
        return db

    async def _build_client(self, uri: str) -> Optional[AsyncIOMotorClient]:
        try:
            if not (uri.startswith("mongodb://") or uri.startswith("mongodb+srv://")):
                LOGGER.warning("Invalid URI format skipped")
                return None
            client = self._clients.get(uri)
            if client is None:
                client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=3000)
                self._clients[uri] = client
            return client
        except (ConfigurationError, InvalidURI) as e:
            LOGGER.warning("Invalid URI skipped: %s", e)
            return None

    async def _is_alive(self, uri: str) -> bool:
        client = await self._build_client(uri)
        if client is None:
            return False
        try:
            await client.admin.command("ping")
            return True
        except PyMongoError:
            return False

    async def _select_available_db(self) -> Optional[AsyncIOMotorDatabase]:
        if self._active_uri and await self._is_alive(self._active_uri):
            return self._clients[self._active_uri][DB_NAME]

        for uri in list(self._uris):
            if await self._is_alive(uri):
                self._active_uri = uri
                return self._clients[uri][DB_NAME]

        self._active_uri = None
        return None

    async def get_database(self) -> Optional[AsyncIOMotorDatabase]:
        db = await self._select_available_db()
        if db is None and self._uris:
            LOGGER.warning("Primary DB unavailable; trying fallback pool")
            db = await self._select_available_db()
        return db

    def list_uris(self) -> List[str]:
        return list(self._uris)

    async def add_uri(self, uri: str) -> bool:
        clean = (uri or "").strip()
        if not clean:
            return False

        if clean in self._uris:
            return True

        if not await self._is_alive(clean):
            return False

        self._uris.append(clean)
        if not self._active_uri:
            self._active_uri = clean
        return True

    async def remove_uri(self, uri: str) -> bool:
        clean = (uri or "").strip()
        if clean not in self._uris:
            return False
        self._uris.remove(clean)
        if self._active_uri == clean:
            self._active_uri = None
        return True


mongo_manager = MultiMongoManager()
