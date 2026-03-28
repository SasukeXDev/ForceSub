import asyncio
import logging
import os
from typing import Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import ConfigurationError, InvalidURI, PyMongoError

from config import DB_NAME, DB_URI

LOGGER = logging.getLogger(__name__)


def _mask_uri(uri: str) -> str:
    if len(uri) < 18:
        return "***"
    return f"{uri[:14]}...{uri[-6:]}"


class MultiMongoManager:
    """Async MongoDB pool with failover, retry, and runtime URI management."""

    def __init__(self) -> None:
        seed_uris: List[str] = []

        comma_uris = os.getenv("MONGO_URIS", "")
        seed_uris.extend([u.strip() for u in comma_uris.split(",") if u.strip()])

        indexed_keys = sorted(k for k in os.environ if k.startswith("MONGO_URI_"))
        for key in indexed_keys:
            val = os.getenv(key, "").strip()
            if val:
                seed_uris.append(val)

        if DB_URI and DB_URI.strip():
            seed_uris.insert(0, DB_URI.strip())

        # de-duplicate while preserving order
        self._uris = list(dict.fromkeys(seed_uris))
        self._clients: Dict[str, AsyncIOMotorClient] = {}
        self._active_uri: Optional[str] = None
        self._init_lock = asyncio.Lock()
        self._has_logged_active_uri = False

    async def initialize(self, retries: int = 2) -> bool:
        async with self._init_lock:
            LOGGER.info("Connecting to MongoDB...")
            if not self._uris:
                LOGGER.error("Database not connected: no MongoDB URI configured")
                return False

            for attempt in range(retries + 1):
                db = await self._select_available_db()
                if db is not None:
                    if self._active_uri:
                        LOGGER.info("MongoDB connected (%s)", _mask_uri(self._active_uri))
                    else:
                        LOGGER.info("MongoDB connected")
                    return True
                if attempt < retries:
                    LOGGER.warning("MongoDB retrying connection (attempt %s/%s)", attempt + 1, retries + 1)
                    await asyncio.sleep(1.2 * (attempt + 1))

            LOGGER.error("Database not connected: all MongoDB connections failed")
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
        # 1) try current active URI first
        if self._active_uri and await self._is_alive(self._active_uri):
            if not self._has_logged_active_uri:
                LOGGER.info("Using MongoDB URI: %s", _mask_uri(self._active_uri))
                self._has_logged_active_uri = True
            return self._clients[self._active_uri][DB_NAME]

        # 2) fallback across full pool
        for uri in list(self._uris):
            if await self._is_alive(uri):
                self._active_uri = uri
                LOGGER.info("Switched MongoDB URI: %s", _mask_uri(uri))
                self._has_logged_active_uri = True
                return self._clients[uri][DB_NAME]

        self._active_uri = None
        self._has_logged_active_uri = False
        return None

    async def get_database(self) -> Optional[AsyncIOMotorDatabase]:
        db = await self._select_available_db()
        if db is None:
            return None
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
