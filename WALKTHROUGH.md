# Short walkthrough

This is a 60-90 second script for a screen recording.

1. Open the project folder in VS Code and show `research_agent.py`.
2. Point out the three tool classes: `WebSearchTool`, `FetchPageTool`, and `SummarizeTool`.
3. Show `ResearchAgent.run`: the `phase` field selects the next tool and `state.step < state.max_steps` prevents an infinite loop.
4. Run:

   ```powershell
   python research_agent.py "How does exercise affect sleep quality?"
   ```

5. Explain that the output contains claims marked `[S1]` or `[S2]`, followed by the fetched URLs that define those source IDs.
6. Run the tests:

   ```powershell
   python -m unittest -v
   ```

7. Optionally demonstrate graceful failure with `--max-steps 2` or by showing the `Tool notes` entries for blocked pages. Emphasize that failed pages are skipped and are never used as evidence.