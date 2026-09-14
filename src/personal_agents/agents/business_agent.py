from __future__ import annotations

from typing import Any

from personal_agents.agents.base import BaseAgent
from personal_agents.bus import AgentBus
from personal_agents.config import AppConfig
from personal_agents.llm import LLMClient
from personal_agents.models import AgentName, Task


class BusinessAgent(BaseAgent):
    def __init__(self, *, bus: AgentBus, config: AppConfig) -> None:
        super().__init__(name=AgentName.BUSINESS.value, bus=bus, config=config)
        self.llm = LLMClient(config)

    async def handle_task(self, task: Task) -> dict[str, Any]:
        request = task.payload.get("request", "")
        if task.kind != "business_support":
            return {
                "title": "Business Agent",
                "summary": f"I do not know how to handle task type: {task.kind}",
            }

        return self.business_support(request)

    def business_support(self, request: str) -> dict[str, Any]:
        llm_plan = self.llm.complete(
            system=(
                "You are a practical business operations sub-agent. Help the user create "
                "business ideas, requirements, operating plans, budgets, marketing plans, "
                "and weekly actions. Be realistic and clear."
            ),
            user=(
                f"User request:\n{request}\n\n"
                "Return a business-ready answer with: opportunity, customers, offer, "
                "requirements, startup costs to estimate, risks, and next actions."
            ),
        )

        if llm_plan:
            summary = llm_plan
        else:
            summary = build_template_business_plan(request)

        return {
            "title": "Business Agent Plan",
            "summary": summary,
        }


def build_template_business_plan(request: str) -> str:
    return "\n".join(
        [
            f"Business request: {request}",
            "",
            "Opportunity:",
            "- Identify a painful problem people already pay to solve.",
            "- Start with a small offer you can deliver quickly and improve weekly.",
            "",
            "Customers:",
            "- Define one clear customer group.",
            "- List where they spend time online and offline.",
            "- Speak to 10 potential customers before buying equipment or stock.",
            "",
            "Offer:",
            "- Create one simple package with a clear result, price, and delivery time.",
            "- Add a premium version for customers who want speed, convenience, or support.",
            "",
            "Requirements:",
            "- Product or service checklist.",
            "- Supplier or tool list.",
            "- Pricing and basic budget.",
            "- Sales channel, delivery process, and customer support process.",
            "- Legal, tax, license, and record-keeping requirements for your location.",
            "",
            "Next actions:",
            "- Choose the customer group.",
            "- Write the first offer in one sentence.",
            "- Estimate startup costs and monthly expenses.",
            "- Find 20 leads and contact the first 5 today.",
            "",
            "Set OPENAI_API_KEY and OPENAI_MODEL in .env for a more customized plan.",
        ]
    )
