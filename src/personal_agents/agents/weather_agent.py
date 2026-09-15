from __future__ import annotations

import re
from typing import Any

from personal_agents.agents.base import BaseAgent
from personal_agents.bus import AgentBus
from personal_agents.config import AppConfig
from personal_agents.models import AgentName, Task
from personal_agents.weather import (
    fetch_forecast,
    format_forecast_report,
    geocode_location,
)


class WeatherAgent(BaseAgent):
    def __init__(self, *, bus: AgentBus, config: AppConfig) -> None:
        super().__init__(name=AgentName.WEATHER.value, bus=bus, config=config)

    async def handle_task(self, task: Task) -> dict[str, Any]:
        request = str(task.payload.get("request", "")).strip()
        if task.kind != "weather_forecast":
            return {
                "title": "Weather Agent",
                "summary": f"I do not know how to handle task type: {task.kind}",
            }

        return self.weather_forecast(request)

    def weather_forecast(self, request: str) -> dict[str, Any]:
        location_query = extract_location(request) or self.config.default_weather_location
        if not location_query:
            return {
                "title": "Weather Agent",
                "summary": (
                    "Tell me a city, for example: 'Weather for Harare tomorrow and this week'. "
                    "Or set WEATHER_DEFAULT_LOCATION in .env."
                ),
            }

        try:
            location = geocode_location(location_query)
        except Exception as exc:
            return {
                "title": "Weather Agent",
                "summary": f"I could not look up that location. Reason: {exc}",
            }

        if location is None:
            return {
                "title": "Weather Agent",
                "summary": (
                    f"I could not find a location matching '{location_query}'. "
                    "Try a clearer city or town name."
                ),
            }

        try:
            forecasts = fetch_forecast(
                latitude=location.latitude,
                longitude=location.longitude,
                timezone=location.timezone,
            )
        except Exception as exc:
            return {
                "title": "Weather Agent",
                "summary": f"I found the location but could not fetch the forecast. Reason: {exc}",
            }

        summary = format_forecast_report(
            location=location,
            forecasts=forecasts,
            request=request,
        )
        return {
            "title": "Weather Agent Forecast",
            "summary": summary,
            "location": {
                "name": location.name,
                "country": location.country,
                "timezone": location.timezone,
            },
        }


def extract_location(request: str) -> str | None:
    patterns = [
        r"\b(?:in|for|at)\s+([A-Za-z][A-Za-z\s\-']{1,40})",
        r"\bweather\s+(?:in|for|at)\s+([A-Za-z][A-Za-z\s\-']{1,40})",
    ]
    stop_words = {
        "tomorrow",
        "today",
        "week",
        "month",
        "daily",
        "forecast",
        "weather",
        "the",
        "this",
        "next",
        "whole",
        "and",
        "please",
    }

    for pattern in patterns:
        match = re.search(pattern, request, flags=re.IGNORECASE)
        if not match:
            continue

        candidate = match.group(1).strip(" .,!?:;")
        words = [word for word in candidate.split() if word.lower() not in stop_words]
        cleaned = " ".join(words).strip(" .,!?:;")
        if cleaned:
            return cleaned

    return None
