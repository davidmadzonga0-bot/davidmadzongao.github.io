from __future__ import annotations

import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str


class DuckDuckGoHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[SearchResult] = []
        self._capture_link = False
        self._capture_snippet = False
        self._current_title: list[str] = []
        self._current_url = ""
        self._current_snippet: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)
        class_name = attr_map.get("class", "")

        if tag == "a" and "result__a" in class_name:
            self._capture_link = True
            self._current_title = []
            self._current_url = attr_map.get("href", "") or ""

        if tag in {"a", "div"} and "result__snippet" in class_name:
            self._capture_snippet = True
            self._current_snippet = []

    def handle_data(self, data: str) -> None:
        if self._capture_link:
            self._current_title.append(data)

        if self._capture_snippet:
            self._current_snippet.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._capture_link:
            self._capture_link = False
            title = clean_text(" ".join(self._current_title))
            url = clean_duckduckgo_url(self._current_url)
            if title and url:
                self.results.append(SearchResult(title=title, url=url, snippet=""))

        if tag in {"a", "div"} and self._capture_snippet:
            self._capture_snippet = False
            snippet = clean_text(" ".join(self._current_snippet))
            if snippet and self.results and not self.results[-1].snippet:
                last = self.results[-1]
                self.results[-1] = SearchResult(last.title, last.url, snippet)


def search_web(query: str, *, max_results: int = 5) -> list[SearchResult]:
    encoded_query = urllib.parse.urlencode({"q": query})
    url = f"https://duckduckgo.com/html/?{encoded_query}"
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
            )
        },
    )

    with urllib.request.urlopen(request, timeout=20) as response:
        html = response.read().decode("utf-8", errors="ignore")

    parser = DuckDuckGoHtmlParser()
    parser.feed(html)
    return parser.results[:max_results]


def fetch_page_text(url: str, *, max_chars: int = 3500) -> str:
    parsed_url = urllib.parse.urlparse(url)
    if parsed_url.scheme not in {"http", "https"}:
        return ""

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
            )
        },
    )

    with urllib.request.urlopen(request, timeout=20) as response:
        content_type = response.headers.get("Content-Type", "")
        if "text/html" not in content_type and "text/plain" not in content_type:
            return ""
        raw = response.read(max_chars * 4).decode("utf-8", errors="ignore")

    text = re.sub(r"(?is)<(script|style|noscript).*?</\1>", " ", raw)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return clean_text(unescape(text))[:max_chars]


def clean_duckduckgo_url(url: str) -> str:
    if url.startswith("//duckduckgo.com/l/"):
        parsed = urllib.parse.urlparse(f"https:{url}")
        query = urllib.parse.parse_qs(parsed.query)
        return query.get("uddg", [url])[0]

    return url


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(value)).strip()
