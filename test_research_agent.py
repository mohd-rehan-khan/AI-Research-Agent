import unittest

from research_agent import ResearchAgent, SearchResult, Source


class FakeSearch:
    def __call__(self, question):
        return [SearchResult("Evidence page", "https://example.test/evidence")]


class MultiSearch:
    def __call__(self, question):
        return [
            SearchResult("Evidence one", "https://example.test/one"),
            SearchResult("Evidence two", "https://example.test/two"),
        ]


class FakeFetch:
    def __call__(self, result):
        return Source("", result.title, result.url, f"A verified fact from {result.title} is that solar power produces electricity from sunlight.")


class FailingFetch:
    def __call__(self, result):
        raise RuntimeError("network unavailable")


class ResearchAgentTests(unittest.TestCase):
    def test_rejects_non_research_requests(self):
        agent = ResearchAgent(search=FakeSearch(), fetch=FakeFetch(), max_steps=4)
        state = agent.run("make a code")
        self.assertEqual(state.answer, "I can only answer research questions.")
        self.assertEqual(state.phase, "done")
        self.assertEqual(len(state.sources), 0)

    def test_tool_loop_fetches_and_cites_every_claim(self):
        agent = ResearchAgent(search=FakeSearch(), fetch=FakeFetch(), max_steps=4)
        state = agent.run("How does solar power work?")
        self.assertEqual(state.step, 3)
        self.assertIn("[S1]", state.answer)
        self.assertEqual(len(state.sources), 1)

    def test_step_budget_prevents_infinite_loop(self):
        agent = ResearchAgent(search=FakeSearch(), fetch=FakeFetch(), max_steps=2)
        state = agent.run("How does solar power work?")
        self.assertEqual(state.step, 2)
        self.assertIn("step budget exhausted", " ".join(state.errors))

    def test_agent_collects_multiple_sources_before_summarizing(self):
        agent = ResearchAgent(search=MultiSearch(), fetch=FakeFetch(), max_steps=5)
        state = agent.run("How does solar power work?")
        self.assertEqual(len(state.sources), 2)
        self.assertIn("[S1]", state.answer)
        self.assertIn("[S2]", state.answer)

    def test_failed_fetch_is_reported_gracefully(self):
        agent = ResearchAgent(search=FakeSearch(), fetch=FailingFetch(), max_steps=4)
        state = agent.run("How does solar power work?")
        self.assertEqual(state.answer, "No answer available.")
        self.assertTrue(any("fetch_page failed" in error for error in state.errors))


if __name__ == "__main__":
    unittest.main()
