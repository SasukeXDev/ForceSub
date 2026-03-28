import os
import threading
from typing import List, Optional

import pymongo
from pymongo.errors import PyMongoError

from config import DB_NAME, DB_URI


class MultiMongoManager:
    """Simple MongoDB pool with failover and runtime URI management."""

    def __init__(self) -> None:
        env_list = os.getenv("MONGO_URIS", "")
        seed_uris = [u.strip() for u in env_list.split(",") if u.strip()]
        if DB_URI and DB_URI.strip() and DB_URI.strip() not in seed_uris:
            seed_uris.insert(0, DB_URI.strip())

        self._lock = threading.Lock()
        self._uris: List[str] = seed_uris
        self._clients: dict[str, pymongo.MongoClient] = {}
        self._active_uri: Optional[str] = None
        self._bootstrap_active_uri()

    def _bootstrap_active_uri(self) -> None:
        for uri in list(self._uris):
            if self._is_alive(uri):
                self._active_uri = uri
                return

    def _is_alive(self, uri: str) -> bool:
        try:
            client = self._clients.get(uri)
            if client is None:
                client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=2500)
                self._clients[uri] = client
            client.admin.command("ping")
            return True
        except PyMongoError:
            return False

    def get_database(self):
        with self._lock:
            if self._active_uri and self._is_alive(self._active_uri):
                return self._clients[self._active_uri][DB_NAME]

            for uri in list(self._uris):
                if self._is_alive(uri):
                    self._active_uri = uri
                    return self._clients[uri][DB_NAME]

            return None

    def list_uris(self) -> List[str]:
        return list(self._uris)

    def add_uri(self, uri: str) -> bool:
        clean = (uri or "").strip()
        if not clean:
            return False
        if not (clean.startswith("mongodb://") or clean.startswith("mongodb+srv://")):
            return False

        with self._lock:
            if clean in self._uris:
                return True
            if not self._is_alive(clean):
                return False
            self._uris.append(clean)
            if not self._active_uri:
                self._active_uri = clean
            return True

    def remove_uri(self, uri: str) -> bool:
        clean = (uri or "").strip()
        with self._lock:
            if clean not in self._uris:
                return False
            self._uris.remove(clean)
            if self._active_uri == clean:
                self._active_uri = None
            return True


mongo_manager = MultiMongoManager()
