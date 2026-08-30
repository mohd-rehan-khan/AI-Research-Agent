"""A bounded, source-grounded research agent using a small tool set."""

from __future__ import annotations

import argparse
import html
import re
import sys
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any, Callable
from urllib.parse import parse_qs, quote_plus, unquote, urlparse
from urllib.request import Request, urlopen


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str = ""


@dataclass
class Source:
    source_id: str
    title: str
    url: str
    text: str


@dataclass
class AgentState:
    question: str
    step: int = 0
    max_steps: int = 8
    phase: str = "search"
    search_results: list[SearchResult] = field(default_factory=list)
    sources: list[Source] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    answer: str = ""


class WebSearchTool:
    """Search DuckDuckGo's HTML endpoint without requiring an API key."""

    name = "web_search"

    def __call__(self, query: str, limit: int = 5) -> list[SearchResult]:
        request = Request(
            "https://lite.duckduckgo.com/lite/?q=" + quote_plus(query),
            headers={"User-Agent": "research-agent/1.0"},
        )
        with urlopen(request, timeout=12) as response:
            markup = response.read().decode("utf-8", errors="replace")

        results: list[SearchResult] = []
        pattern = (
            r'<a[^>]+href=["\']([^"\']+)["\'][^>]*'
            r'class=["\']result(?:__a|-link)["\'][^>]*>(.*?)</a>'
        )
        for match in re.finditer(
            pattern,
            markup,
            flags=re.I | re.S,
        ):
            url = self._clean_url(html.unescape(match.group(1)))
            title = self._clean_text(match.group(2))
            if url.startswith("http"):
                results.append(SearchResult(title=title, url=url))
            if len(results) >= limit:
                break
        return results

    @staticmethod
    def _clean_url(url: str) -> str:
        parsed = urlparse(url)
        if parsed.path == "/l/":
            target = parse_qs(parsed.query).get("uddg", [url])[0]
            return unquote(target)
        return url

    @staticmethod
    def _clean_text(value: str) -> str:
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", value)).strip()


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            text = re.sub(r"\s+", " ", data).strip()
            if text:
                self.parts.append(text)


class FetchPageTool:
    name = "fetch_page"

    def __call__(self, result: SearchResult) -> Source:
        request = Request(result.url, headers={"User-Agent": "research-agent/1.0"})
        with urlopen(request, timeout=12) as response:
            markup = response.read().decode("utf-8", errors="replace")
        parser = _TextExtractor()
        parser.feed(markup)
        text = " ".join(parser.parts)
        if any(
            marker in text.lower()
            for marker in ("client challenge", "captcha", "please check your connection")
        ):
            raise ValueError("page returned an anti-bot challenge")
        if len(text) < 80:
            raise ValueError("page returned too little readable text")
        return Source(
            source_id="",
            title=result.title or result.url,
            url=result.url,
            text=text[:12000],
        )


class SummarizeTool:
    name = "summarize"

    def __call__(self, question: str, sources: list[Source], limit: int = 5) -> str:
        if not sources:
            raise ValueError("no fetched sources are available")
        terms = {word.lower() for word in re.findall(r"[A-Za-z]{4,}", question)}
        candidates: list[tuple[int, Source, str]] = []
        for source in sources:
            sentences = re.split(r"(?<=[.!?])\s+", source.text)
            for sentence in sentences:
                sentence = sentence.strip()
                lower_sentence = sentence.lower()
                boilerplate = (
                    "skip to main content",
                    "here's how you know",
                    "find articles by",
                    "search in pmc",
                    "see all ",
                )
                if len(sentence) < 45 or len(sentence) > 320 or any(
                    marker in lower_sentence for marker in boilerplate
                ):
                    continue
                score = sum(term in sentence.lower() for term in terms)
                candidates.append((score, source, sentence))
        candidates.sort(key=lambda item: item[0], reverse=True)
        selected: list[str] = []
        seen: set[str] = set()
        for _, source, sentence in candidates:
            if sentence in seen:
                continue
            seen.add(sentence)
            selected.append(f"{sentence} [{source.source_id}]")
            if len(selected) >= limit:
                break
        if not selected:
            return "No source contained a usable claim."
        return " ".join(selected)


Tool = Callable[..., Any]


class ResearchAgent:
    """Decides the next tool from state and stops after max_steps."""

    def __init__(
        self,
        search: Tool | None = None,
        fetch: Tool | None = None,
        summarize: Tool | None = None,
        max_steps: int = 8,
    ) -> None:
        self.search = search or WebSearchTool()
        self.fetch = fetch or FetchPageTool()
        self.summarize = summarize or SummarizeTool()
        self.max_steps = max_steps

    def run(self, question: str) -> AgentState:
        state = AgentState(question=question, max_steps=self.max_steps)
        while state.step < state.max_steps and state.phase != "done":
            state.step += 1
            if state.phase == "search":
                try:
                    state.search_results = self.search(state.question)
                    state.notes.append(f"web_search returned {len(state.search_results)} result(s)")
                    state.phase = "fetch" if state.search_results else "done"
                    if not state.search_results:
                        state.errors.append("web_search returned no results")
                except Exception as error:  # tool failures are recoverable
                    state.errors.append(f"web_search failed: {error}")
                    state.phase = "done"
            elif state.phase == "fetch":
                result = state.search_results.pop(0)
                try:
                    source = self.fetch(result)
                    source.source_id = f"S{len(state.sources) + 1}"
                    state.sources.append(source)
                    state.notes.append(f"fetch_page succeeded: {source.source_id} ({source.url})")
                except Exception as error:
                    state.errors.append(f"fetch_page failed for {result.url}: {error}")
                state.phase = "summarize" if len(state.sources) >= 3 else (
                    "fetch" if state.search_results else ("summarize" if state.sources else "done")
                )
            elif state.phase == "summarize":
                try:
                    state.answer = self.summarize(state.question, state.sources)
                    state.notes.append(f"summarize used {len(state.sources)} fetched source(s)")
                except Exception as error:
                    state.errors.append(f"summarize failed: {error}")
                    state.answer = "I could not produce a source-backed answer."
                state.phase = "done"
        if state.phase != "done":
            state.errors.append(f"step budget exhausted ({state.max_steps})")
            if state.sources:
                state.answer = self.summarize(state.question, state.sources)
            else:
                state.answer = "I could not produce a source-backed answer."
            state.phase = "done"
        elif not state.answer and not state.sources:
            state.answer = "No answer available."
        return state


def format_report(state: AgentState) -> str:
    lines = [state.answer or "No answer available.", "", "Sources:"]
    if state.sources:
        lines.extend(f"[{source.source_id}] {source.title} - {source.url}" for source in state.sources)
    else:
        lines.append("No pages were successfully fetched.")
    if state.notes or state.errors:
        lines.append("")
        lines.append("Tool notes (non-fatal failures are included):")
        lines.extend(f"- {note}" for note in state.notes)
        lines.extend(f"- {error}" for error in state.errors)
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Answer a research question with fetched-source citations.")
    parser.add_argument("question", nargs="+", help="the research question")
    parser.add_argument("--max-steps", type=int, default=8)
    args = parser.parse_args()
    if args.max_steps < 1:
        parser.error("--max-steps must be at least 1")
    state = ResearchAgent(max_steps=args.max_steps).run(" ".join(args.question))
    print(format_report(state))
    return 0 if state.sources and state.answer else 1


if __name__ == "__main__":
    sys.exit(main())
