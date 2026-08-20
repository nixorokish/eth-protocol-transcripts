import unittest

from scripts.generate_readme_table import backfill_missing_forkcast_summaries


class BackfillForkcastSummariesTest(unittest.TestCase):
    def test_backfills_only_missing_summary(self):
        readme = (
            "| Date | Type | № | Issue | Summary | Discussion | Recording | Logs |\n"
            "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
            "| 13 Aug 2026 | ACDE | 243 | [#2178](issue) | - | [EthMag](discussion) | [video](video) | [logs](logs) |\n"
            "| 30 Jul 2026 | ACDE | 242 | [#2166](issue) | [forkcast](old-url) | - | - | [logs](logs) |\n"
        )
        calls = {
            ("ACDE", "243"): {"url": "https://forkcast.org/calls/acde/243"},
            ("ACDE", "242"): {"url": "https://forkcast.org/calls/acde/242"},
        }

        updated, count = backfill_missing_forkcast_summaries(readme, calls)

        self.assertEqual(count, 1)
        self.assertIn("[forkcast](https://forkcast.org/calls/acde/243)", updated)
        self.assertIn("[forkcast](old-url)", updated)
        self.assertIn("[EthMag](discussion) | [video](video) | [logs](logs)", updated)

    def test_matches_zero_padded_forkcast_number(self):
        readme = "| 17 Aug 2026 | ACDT | 92 | - | - | - | - | - |\n"
        calls = {
            ("ACDT", "092"): {"url": "https://forkcast.org/calls/acdt/092"},
        }

        updated, count = backfill_missing_forkcast_summaries(readme, calls)

        self.assertEqual(count, 1)
        self.assertIn("https://forkcast.org/calls/acdt/092", updated)


if __name__ == "__main__":
    unittest.main()
