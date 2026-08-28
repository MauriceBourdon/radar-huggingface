import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "radar.yml"


class WorkflowContractTest(unittest.TestCase):
    def setUp(self):
        self.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_collection_persistence_and_schedule_contract_remain_unchanged(self):
        self.assertIn("cron: '30 1,5,9,13,17,21 * * *'", self.workflow)
        self.assertIn("run: python radar_huggingface.py", self.workflow)
        self.assertIn("git add feed.json feed.md summary.txt", self.workflow)
        self.assertIn("git push origin HEAD:main", self.workflow)

    def test_legacy_discord_step_is_explicitly_disabled(self):
        self.assertIn("Send Discord delta (temporarily disabled)", self.workflow)
        self.assertIn("if: ${{ false }}", self.workflow)
        self.assertIn("run: python discord_notifier.py", self.workflow)


if __name__ == "__main__":
    unittest.main()
