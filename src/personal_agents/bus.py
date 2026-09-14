from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .models import AgentMessage, MessageKind, Task, TaskStatus


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class AgentBus:
    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.db_path, timeout=30)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    from_agent TEXT NOT NULL,
                    to_agent TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    result_json TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_tasks_queue
                ON tasks(to_agent, status, created_at);

                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    from_agent TEXT NOT NULL,
                    to_agent TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    body_json TEXT NOT NULL,
                    task_id TEXT,
                    created_at TEXT NOT NULL,
                    delivered INTEGER NOT NULL DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS idx_messages_delivery
                ON messages(to_agent, delivered, created_at);

                CREATE TABLE IF NOT EXISTS agent_state (
                    agent TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (agent, key)
                );
                """
            )

    def enqueue_task(
        self,
        *,
        from_agent: str,
        to_agent: str,
        kind: str,
        payload: dict[str, Any],
    ) -> str:
        task_id = str(uuid.uuid4())
        timestamp = utc_now()

        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO tasks (
                    id, from_agent, to_agent, kind, payload_json, status,
                    result_json, error, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?)
                """,
                (
                    task_id,
                    from_agent,
                    to_agent,
                    kind,
                    json.dumps(payload),
                    TaskStatus.QUEUED.value,
                    timestamp,
                    timestamp,
                ),
            )

        self.send_message(
            from_agent=from_agent,
            to_agent=to_agent,
            kind=MessageKind.ASSIGNMENT.value,
            body={"task_id": task_id, "kind": kind, "payload": payload},
            task_id=task_id,
        )
        return task_id

    def claim_next_task(self, agent_name: str) -> Task | None:
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT * FROM tasks
                WHERE to_agent = ? AND status = ?
                ORDER BY created_at ASC
                LIMIT 1
                """,
                (agent_name, TaskStatus.QUEUED.value),
            ).fetchone()

            if row is None:
                connection.commit()
                return None

            timestamp = utc_now()
            connection.execute(
                """
                UPDATE tasks
                SET status = ?, updated_at = ?
                WHERE id = ?
                """,
                (TaskStatus.RUNNING.value, timestamp, row["id"]),
            )
            connection.commit()

        task = self.get_task(row["id"])
        return task

    def complete_task(self, task_id: str, result: dict[str, Any]) -> None:
        timestamp = utc_now()

        with self.connect() as connection:
            task = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if task is None:
                raise ValueError(f"Task not found: {task_id}")

            connection.execute(
                """
                UPDATE tasks
                SET status = ?, result_json = ?, error = NULL, updated_at = ?
                WHERE id = ?
                """,
                (TaskStatus.COMPLETED.value, json.dumps(result), timestamp, task_id),
            )

        self.send_message(
            from_agent=task["to_agent"],
            to_agent=task["from_agent"],
            kind=MessageKind.RESULT.value,
            body={"task_id": task_id, "result": result},
            task_id=task_id,
        )

    def fail_task(self, task_id: str, error: str) -> None:
        timestamp = utc_now()

        with self.connect() as connection:
            task = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if task is None:
                raise ValueError(f"Task not found: {task_id}")

            connection.execute(
                """
                UPDATE tasks
                SET status = ?, error = ?, updated_at = ?
                WHERE id = ?
                """,
                (TaskStatus.FAILED.value, error, timestamp, task_id),
            )

        self.send_message(
            from_agent=task["to_agent"],
            to_agent=task["from_agent"],
            kind=MessageKind.RESULT.value,
            body={"task_id": task_id, "error": error},
            task_id=task_id,
        )

    def send_message(
        self,
        *,
        from_agent: str,
        to_agent: str,
        kind: str,
        body: dict[str, Any],
        task_id: str | None = None,
    ) -> str:
        message_id = str(uuid.uuid4())
        timestamp = utc_now()

        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO messages (
                    id, from_agent, to_agent, kind, body_json, task_id,
                    created_at, delivered
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    message_id,
                    from_agent,
                    to_agent,
                    kind,
                    json.dumps(body),
                    task_id,
                    timestamp,
                ),
            )

        return message_id

    def fetch_messages(
        self,
        *,
        to_agent: str,
        undelivered_only: bool = True,
        mark_delivered: bool = True,
        limit: int = 20,
    ) -> list[AgentMessage]:
        where_clause = "WHERE to_agent = ?"
        params: list[Any] = [to_agent]
        if undelivered_only:
            where_clause += " AND delivered = 0"

        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM messages
                {where_clause}
                ORDER BY created_at ASC
                LIMIT ?
                """,
                [*params, limit],
            ).fetchall()

            if mark_delivered and rows:
                connection.executemany(
                    "UPDATE messages SET delivered = 1 WHERE id = ?",
                    [(row["id"],) for row in rows],
                )

        return [self._row_to_message(row) for row in rows]

    def get_task(self, task_id: str) -> Task | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()

        if row is None:
            return None

        return self._row_to_task(row)

    def recent_tasks(self, limit: int = 10) -> list[Task]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM tasks
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [self._row_to_task(row) for row in rows]

    def get_state(self, *, agent: str, key: str, default: Any = None) -> Any:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT value_json FROM agent_state
                WHERE agent = ? AND key = ?
                """,
                (agent, key),
            ).fetchone()

        if row is None:
            return default

        return json.loads(row["value_json"])

    def set_state(self, *, agent: str, key: str, value: Any) -> None:
        timestamp = utc_now()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO agent_state (agent, key, value_json, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(agent, key) DO UPDATE SET
                    value_json = excluded.value_json,
                    updated_at = excluded.updated_at
                """,
                (agent, key, json.dumps(value), timestamp),
            )

    def _row_to_task(self, row: sqlite3.Row) -> Task:
        return Task(
            id=row["id"],
            from_agent=row["from_agent"],
            to_agent=row["to_agent"],
            kind=row["kind"],
            payload=json.loads(row["payload_json"]),
            status=row["status"],
            result=json.loads(row["result_json"]) if row["result_json"] else None,
            error=row["error"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _row_to_message(self, row: sqlite3.Row) -> AgentMessage:
        return AgentMessage(
            id=row["id"],
            from_agent=row["from_agent"],
            to_agent=row["to_agent"],
            kind=row["kind"],
            body=json.loads(row["body_json"]),
            task_id=row["task_id"],
            created_at=row["created_at"],
            delivered=bool(row["delivered"]),
        )
