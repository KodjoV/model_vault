"""Offline validation for the staged Vault queue, no NAS or Docker required."""
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.util.spec_from_file_location("queue_next_vault", ROOT / "tools" / "queue-next-vault.py")
queue = importlib.util.module_from_spec(loader)
loader.loader.exec_module(queue)


class QueueTests(unittest.TestCase):
    def test_catalog_contains_only_expected_next_repos(self):
        catalog = json.loads((ROOT / "models.json").read_text(encoding="utf-8"))
        chosen = queue.selected(catalog)
        self.assertEqual(len(chosen), 5)
        for tier, expected in queue.EXPECTED_REPOS.items():
            self.assertEqual({name for name, value in chosen.items()
                              if value["tier"] == tier}, expected)

    def test_status_needs_complete_and_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            status = folder / "status.json"
            data = {
                "phase": "complete", "verified_complete": True,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "all_models": 1, "active": {}
            }
            with patch.object(queue, "DOT", folder), patch.object(queue, "STATUS", status):
                status.write_text(json.dumps(data))
                self.assertTrue(queue.finished_status())
                data["phase"] = "idle"
                status.write_text(json.dumps(data))
                self.assertFalse(queue.finished_status())
                data["phase"] = "complete"
                data["verified_complete"] = False
                status.write_text(json.dumps(data))
                self.assertFalse(queue.finished_status())

    def test_merge_never_removes_local_models(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "models.json").write_text(json.dumps({
                "models": [{"repo": "test/local", "tier": "P0",
                            "allow_patterns": ["*"], "enabled": True}]
            }))
            pending = root / "pending.json"
            pending.write_text((ROOT / "models.json").read_text(encoding="utf-8"))
            with patch.object(queue, "CODE", root), patch.object(queue, "PENDING", pending):
                updated = queue.merged_catalog()
                self.assertEqual(updated["models"][0]["repo"], "test/local")
                self.assertEqual(len(queue.selected(updated)), 5)
                self.assertEqual(len(updated["models"]), 6)


if __name__ == "__main__":
    unittest.main()
