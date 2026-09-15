from __future__ import annotations

from typing import Any

from personal_agents.agents.base import BaseAgent
from personal_agents.bus import AgentBus
from personal_agents.config import AppConfig
from personal_agents.llm import LLMClient
from personal_agents.models import AgentName, Task
from personal_agents.web_search import SearchResult, fetch_page_text, search_web


class ResearchAgent(BaseAgent):
    def __init__(self, *, bus: AgentBus, config: AppConfig) -> None:
        super().__init__(name=AgentName.RESEARCH.value, bus=bus, config=config)
        self.llm = LLMClient(config)

    async def handle_task(self, task: Task) -> dict[str, Any]:
        request = task.payload.get("request", "")
        if task.kind != "deep_research":
            return {
                "title": "Research Agent",
                "summary": f"I do not know how to handle task type: {task.kind}",
            }

        return self.deep_research(request)

    def deep_research(self, request: str) -> dict[str, Any]:
        try:
            results = search_web(request, max_results=5)
        except Exception as exc:
            return {
                "title": "Research Agent",
                "summary": (
                    "I could not reach web search right now. "
                    f"Reason: {exc}. Try again when network access is available."
                ),
            }

        page_notes = collect_page_notes(results[:3])
        sources = [result.url for result in results]

        llm_summary = self._summarize_with_llm(request, results, page_notes)
        if llm_summary:
            summary = llm_summary
        else:
            summary = format_research_without_llm(request, results, page_notes)

        return {
            "title": "Study & Research Agent Report",
            "summary": summary,
            "sources": sources,
        }

    def _summarize_with_llm(
        self,
        request: str,
        results: list[SearchResult],
        page_notes: list[str],
    ) -> str | None:
        source_block = "\n".join(
            f"{index + 1}. {result.title}\nURL: {result.url}\nSnippet: {result.snippet}"
            for index, result in enumerate(results)
        )
        notes_block = "\n\n".join(page_notes)
        return self.llm.complete(
            system=(
                "You are a careful study and research sub-agent. Help with school assignments "
                "and research questions. Produce clear explanations, solution approaches, "
                "and concise findings. Separate facts from recommendations, mention uncertainty, "
                "and support learning rather than opaque copy-paste answers."
            ),
            user=(
                f"Study/research request:\n{request}\n\n"
                f"Search results:\n{source_block}\n\n"
                f"Fetched page notes:\n{notes_block}\n\n"
                "Return: key findings or solution steps, explanations, practical implications, "
                "risks/gaps, sources to cite, and next study actions."
            ),
        )


def collect_page_notes(results: list[SearchResult]) -> list[str]:
    notes: list[str] = []
    for result in results:
        try:
            text = fetch_page_text(result.url, max_chars=2200)
        except Exception:
            text = ""

        if text:
            notes.append(f"{result.title}\n{result.url}\n{text[:1200]}")

    return notes


def format_research_without_llm(
    request: str,
    results: list[SearchResult],
    page_notes: list[str],
) -> str:
    if not results:
        return f"I searched for '{request}' but did not find usable results."

    lines = [f"I researched: {request}", "", "Useful starting points:"]
    for result in results:
        snippet = f" - {result.snippet}" if result.snippet else ""
        lines.append(f"- {result.title}{snippet}")

    if page_notes:
        lines.append("")
        lines.append("Page notes:")
        for note in page_notes:
            lines.append(f"- {note[:500]}")

    lines.append("")
    lines.append("For deeper synthesis, set OPENAI_API_KEY and OPENAI_MODEL in .env.")
    return "\n".join(lines)
