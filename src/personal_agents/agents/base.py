from __future__ import annotations

import asyncio
import traceback
from abc import ABC, abstractmethod
from typing import Any

from personal_agents.bus import AgentBus
from personal_agents.config import AppConfig
from personal_agents.models import Task


class BaseAgent(ABC):
    def __init__(self, *, name: str, bus: AgentBus, config: AppConfig) -> None:
        self.name = name
        self.bus = bus
        self.config = config

    async def run_once(self) -> int:
        processed = 0
        while True:
            task = self.bus.claim_next_task(self.name)
            if task is None:
                return processed

            processed += 1
            try:
                result = await self.handle_task(task)
            except Exception as exc:
                self.bus.fail_task(task.id, f"{exc}\n{traceback.format_exc(limit=5)}")
            else:
                self.bus.complete_task(task.id, result)

    async def run_forever(self) -> None:
        while True:
            processed = await self.run_once()
            if processed == 0:
                await asyncio.sleep(self.config.worker_poll_seconds)

    @abstractmethod
    async def handle_task(self, task: Task) -> dict[str, Any]:
        raise NotImplementedError
