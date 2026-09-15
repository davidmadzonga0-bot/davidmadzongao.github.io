from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any


@dataclass(frozen=True)
class GeoLocation:
    name: str
    latitude: float
    longitude: float
    timezone: str
    country: str = ""


@dataclass(frozen=True)
class DailyForecast:
    day: date
    weather_code: int
    temp_max_c: float
    temp_min_c: float
    precipitation_mm: float
    wind_max_kmh: float


WEATHER_CODE_LABELS = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


def weather_label(code: int) -> str:
    return WEATHER_CODE_LABELS.get(code, f"Weather code {code}")


def geocode_location(query: str) -> GeoLocation | None:
    params = urllib.parse.urlencode(
        {
            "name": query,
            "count": 1,
            "language": "en",
            "format": "json",
        }
    )
    url = f"https://geocoding-api.open-meteo.com/v1/search?{params}"
    payload = _get_json(url)
    results = payload.get("results") or []
    if not results:
        return None

    item = results[0]
    return GeoLocation(
        name=str(item.get("name") or query),
        latitude=float(item["latitude"]),
        longitude=float(item["longitude"]),
        timezone=str(item.get("timezone") or "UTC"),
        country=str(item.get("country") or ""),
    )


def fetch_forecast(*, latitude: float, longitude: float, timezone: str) -> list[DailyForecast]:
    params = urllib.parse.urlencode(
        {
            "latitude": latitude,
            "longitude": longitude,
            "daily": ",".join(
                [
                    "weathercode",
                    "temperature_2m_max",
                    "temperature_2m_min",
                    "precipitation_sum",
                    "windspeed_10m_max",
                ]
            ),
            "timezone": timezone,
            "forecast_days": 16,
        }
    )
    url = f"https://api.open-meteo.com/v1/forecast?{params}"
    payload = _get_json(url)
    daily = payload.get("daily") or {}
    times = daily.get("time") or []
    forecasts: list[DailyForecast] = []

    for index, day_text in enumerate(times):
        forecasts.append(
            DailyForecast(
                day=date.fromisoformat(day_text),
                weather_code=int((daily.get("weathercode") or [0])[index]),
                temp_max_c=float((daily.get("temperature_2m_max") or [0.0])[index]),
                temp_min_c=float((daily.get("temperature_2m_min") or [0.0])[index]),
                precipitation_mm=float((daily.get("precipitation_sum") or [0.0])[index]),
                wind_max_kmh=float((daily.get("windspeed_10m_max") or [0.0])[index]),
            )
        )

    return forecasts


def format_forecast_report(
    *,
    location: GeoLocation,
    forecasts: list[DailyForecast],
    request: str = "",
) -> str:
    today = date.today()
    tomorrow = today + timedelta(days=1)
    week_end = today + timedelta(days=7)
    month_end = today + timedelta(days=30)

    tomorrow_rows = [row for row in forecasts if row.day == tomorrow]
    week_rows = [row for row in forecasts if today < row.day <= week_end]
    month_rows = [row for row in forecasts if today < row.day <= month_end]

    place = location.name
    if location.country:
        place = f"{location.name}, {location.country}"

    lines = [
        f"Weather forecast for {place}",
        f"Timezone: {location.timezone}",
    ]
    if request:
        lines.append(f"Request: {request}")

    lines.extend(["", "Tomorrow:"])
    if tomorrow_rows:
        lines.append(format_day(tomorrow_rows[0]))
    else:
        lines.append("- No tomorrow forecast available yet.")

    lines.extend(["", "Next 7 days:"])
    if week_rows:
        lines.extend(f"- {format_day(row)}" for row in week_rows)
    else:
        lines.append("- No weekly forecast available.")

    lines.extend(["", "About the next month:"])
    if month_rows:
        lines.append(summarize_period(month_rows, label="16-day outlook (API limit)"))
        lines.append(
            "Note: free weather APIs usually cover about 16 days, not a full calendar month. "
            "I summarized the longest available outlook."
        )
    else:
        lines.append("- No monthly outlook available.")

    return "\n".join(lines)


def format_day(row: DailyForecast) -> str:
    return (
        f"{row.day.isoformat()} | {weather_label(row.weather_code)} | "
        f"{row.temp_min_c:.0f}-{row.temp_max_c:.0f}°C | "
        f"rain {row.precipitation_mm:.1f} mm | wind {row.wind_max_kmh:.0f} km/h"
    )


def summarize_period(rows: list[DailyForecast], *, label: str) -> str:
    if not rows:
        return f"- {label}: no data"

    avg_high = sum(row.temp_max_c for row in rows) / len(rows)
    avg_low = sum(row.temp_min_c for row in rows) / len(rows)
    total_rain = sum(row.precipitation_mm for row in rows)
    wet_days = sum(1 for row in rows if row.precipitation_mm >= 1.0)
    codes = [row.weather_code for row in rows]
    common_code = max(set(codes), key=codes.count)

    return (
        f"- {label}: mostly {weather_label(common_code).lower()}; "
        f"avg {avg_low:.0f}-{avg_high:.0f}°C; "
        f"{wet_days} wet day(s); total rain ~{total_rain:.1f} mm"
    )


def _get_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "MyPersonalAgents/0.1 (+local weather helper)"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))
