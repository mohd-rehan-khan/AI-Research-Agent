# Source-grounded Research Agent

A small Python research agent that answers a question by choosing among three tools:

- `web_search`: finds candidate pages through DuckDuckGo HTML.
- `fetch_page`: downloads and extracts readable page text.
- `summarize`: selects relevant sentences from fetched text and adds source IDs.

The agent loop is phase-driven (`search -> fetch -> summarize`) and has a hard `--max-steps` budget. It fetches up to three usable pages, while continuing past individual failures. Fetch failures and empty search results are recorded and do not crash the process. Final claims are only produced by `summarize`, which appends `[S1]`, `[S2]`, and so on; the report maps each ID to the successfully fetched URL.

## How the agent decides

The loop chooses its next tool from the current state: it searches first, fetches candidate URLs until it has enough usable sources or reaches the step budget, then summarizes the fetched text. A failed tool call is recorded in `Tool notes` and the loop moves on. If no source can be fetched, it returns a clear no-answer message instead of inventing evidence.

## Run

```powershell
python research_agent.py "What are the main benefits of solar energy?"
python research_agent.py --max-steps 6 "How do vaccines train the immune system?"
python research_agent.py --max-steps 2 "What are the barriers to remote work for small businesses?"
```

The third run intentionally demonstrates the hard step limit: with only two steps, the agent may stop before summarizing and reports `step budget exhausted` in its tool notes.

The live search needs network access. Tests use fakes and require no network:

```powershell
python -m unittest -v
```

See [WALKTHROUGH.md](WALKTHROUGH.md) for a short recorded-walkthrough script.
