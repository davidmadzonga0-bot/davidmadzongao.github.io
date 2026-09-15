from __future__ import annotations

from typing import Any

from personal_agents.agents.base import BaseAgent
from personal_agents.bus import AgentBus
from personal_agents.config import AppConfig
from personal_agents.llm import LLMClient
from personal_agents.models import AgentName, Task


class ProjectsAgent(BaseAgent):
    def __init__(self, *, bus: AgentBus, config: AppConfig) -> None:
        super().__init__(name=AgentName.PROJECTS.value, bus=bus, config=config)
        self.llm = LLMClient(config)

    async def handle_task(self, task: Task) -> dict[str, Any]:
        request = task.payload.get("request", "")
        if task.kind != "project_support":
            return {
                "title": "Projects Agent",
                "summary": f"I do not know how to handle task type: {task.kind}",
            }

        return self.project_support(str(request))

    def project_support(self, request: str) -> dict[str, Any]:
        llm_plan = self.llm.complete(
            system=(
                "You are a practical projects sub-agent for personal and school projects. "
                "Help break work into milestones, clarify requirements, suggest tools, "
                "risks, and a realistic execution plan. Be concrete and actionable."
            ),
            user=(
                f"User project request:\n{request}\n\n"
                "Return: project goal, scope, milestones, tasks for this week, "
                "resources/tools, risks, and how to know the project is done."
            ),
        )

        if llm_plan:
            summary = llm_plan
        else:
            summary = build_template_project_plan(request)

        return {
            "title": "Projects Agent Plan",
            "summary": summary,
        }


def build_template_project_plan(request: str) -> str:
    return "\n".join(
        [
            f"Project request: {request}",
            "",
            "Goal:",
            "- Write one sentence that defines a finished, usable result.",
            "",
            "Scope:",
            "- Must-have features or deliverables.",
            "- Nice-to-have items to leave for later.",
            "- Explicit out-of-scope items.",
            "",
            "Milestones:",
            "1. Clarify requirements and success criteria.",
            "2. Design or outline the approach.",
            "3. Build the first working version.",
            "4. Test, revise, and polish.",
            "5. Submit, present, or publish.",
            "",
            "This week:",
            "- Define the final deliverable in writing.",
            "- List materials, tools, and people needed.",
            "- Complete the first concrete task that reduces risk.",
            "",
            "Done when:",
            "- The main deliverable works or is submission-ready.",
            "- You can explain what you built and why.",
            "",
            "Set OPENAI_API_KEY and OPENAI_MODEL in .env for a customized project plan.",
        ]
    )
