"""OrcaRouter gated Mix-256G archive catalog guards (stdlib only)."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "DeepSeek-V4.1-Flash-1017-abliterated-Mix-256G"


class OrcaArchiveCatalogTests(unittest.TestCase):
    def test_isolated_orca_selection(self):
        models = json.loads((ROOT / "models.json").read_text(encoding="utf-8"))["models"]
        selected = [m for m in models if m.get("tier") == "ORCA"]
        self.assertEqual(len(selected), 1)
        m = selected[0]
        self.assertEqual(m["repo"], "orcarouter/DeepSeek-V4.1-Flash-1017-abliterated-GGUF")
        self.assertTrue(m["enabled"])
        expected = {
            f"Mix-256G/{PREFIX}-{i:05d}-of-00007.gguf" for i in range(1, 8)
        }
        expected.add("imatrix.gguf")
        self.assertEqual(set(m["required_patterns"]), expected)
        self.assertEqual(set(m["allow_patterns"]), expected | {"README.md"})
        self.assertFalse(any("Mix-128G" in f or f == "*" for f in m["allow_patterns"]))
        self.assertEqual(len([m for m in models if m.get("tier") == "ABL"]), 6)
        self.assertEqual(len([m for m in models if m.get("tier") == "DS41"]), 2)


if __name__ == "__main__":
    unittest.main()
