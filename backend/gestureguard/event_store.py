"""Thread-safe SQLite event persistence with JSON-preserving serialization."""

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from threading import RLock
from typing import Any


class EventStore:
    def __init__(self, path: str | Path = ":memory:") -> None:
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.execute("CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, mode TEXT, session_id TEXT, type TEXT, payload TEXT NOT NULL)")
        self._db.execute("CREATE INDEX IF NOT EXISTS events_session ON events(session_id, mode)")
        self._db.commit()

    def append(self, event: dict[str, Any]) -> dict[str, Any]:
        record = {"timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"), "monotonic": 0.0, "type": "event", "severity": "info", "message": "", "mode": "gestureguard", "session_id": "", "station_id": None, "gesture": "None", "details": {}, **event}
        record.pop("id", None)
        payload = json.dumps(record, allow_nan=False, separators=(",", ":"))
        with self._lock:
            cursor = self._db.execute("INSERT INTO events(mode,session_id,type,payload) VALUES (?,?,?,?)", (record["mode"], record["session_id"], record["type"], payload))
            self._db.commit()
            record["id"] = cursor.lastrowid
        return record

    def query(self, limit: int = 200, exclude_types: list[str] | tuple[str, ...] | None = None, **filters: Any) -> list[dict[str, Any]]:
        limit = min(max(int(limit), 0), 200000)
        clauses, args = [], []
        for key in ("mode", "session_id", "type"):
            if filters.get(key) not in (None, "", "all"):
                clauses.append(f"{key} = ?")
                args.append(filters[key])
        if exclude_types:
            if not isinstance(exclude_types, (list, tuple)) or not all(isinstance(value, str) for value in exclude_types):
                raise ValueError("Excluded event types must be a list of strings.")
            clauses.append("type NOT IN (" + ",".join("?" for _ in exclude_types) + ")")
            args.extend(exclude_types)
        sql = "SELECT id,payload FROM events"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY id DESC"
        if not any(value not in (None, "", "all") and key not in {"mode", "session_id", "type"} for key, value in filters.items()):
            sql += " LIMIT ?"
            args.append(limit)
        with self._lock:
            rows = self._db.execute(sql, args).fetchall()
        result = []
        for identifier, payload in rows:
            record = json.loads(payload)
            record["id"] = identifier
            matched = True
            for key, value in filters.items():
                if value in (None, "", "all") or key in {"mode", "session_id", "type"}:
                    continue
                if key == "search":
                    matched = str(value).casefold() in json.dumps(record).casefold()
                else:
                    details = record.get("details", {})
                    actual = record.get(key, details.get(key, details.get("session", {}).get(key)))
                    matched = actual == value
                if not matched:
                    break
            if matched:
                result.append(record)
            if len(result) >= limit:
                break
        return result if limit else []

    def close(self) -> None:
        with self._lock:
            self._db.close()
