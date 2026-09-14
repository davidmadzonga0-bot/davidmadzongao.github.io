from __future__ import annotations

from collections import Counter

from personal_agents.bus import AgentBus
from personal_agents.models import TaskStatus


def build_activity_report(bus: AgentBus, *, limit: int = 25) -> str:
    tasks = bus.recent_tasks(limit=limit)
    if not tasks:
        return "Activity report\n\nNo tasks recorded yet."

    status_counts = Counter(task.status for task in tasks)
    agent_counts = Counter(task.to_agent for task in tasks)

    lines = [
        "Activity report",
        f"Last {len(tasks)} tasks:",
        "",
        "By status:",
        f"- queued: {status_counts.get(TaskStatus.QUEUED.value, 0)}",
        f"- running: {status_counts.get(TaskStatus.RUNNING.value, 0)}",
        f"- completed: {status_counts.get(TaskStatus.COMPLETED.value, 0)}",
        f"- failed: {status_counts.get(TaskStatus.FAILED.value, 0)}",
        "",
        "By agent:",
    ]
    for agent, count in sorted(agent_counts.items()):
        lines.append(f"- {agent}: {count}")

    lines.extend(["", "Recent work:"])
    for task in tasks[:8]:
        request = task.payload.get("request", task.kind)
        if len(request) > 70:
            request = request[:67] + "..."
        lines.append(f"- {task.id[:8]} | {task.to_agent} | {task.status} | {request}")

    return "\n".join(lines)
