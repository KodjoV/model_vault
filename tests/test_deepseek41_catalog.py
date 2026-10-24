"""P0 DeepSeek-V4.1 selected-shard smoke checks (offline, stdlib)."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
BACKBONE = "DeepSeek-V4.1-Flash-1017-GSQ-RCO-IQ2_XS"
ENGRAM = "DeepSeek-V4.1-Flash-Engram-IQ4_NL.gguf"
DRAFTER = "dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf"


class DeepSeek41CatalogTests(unittest.TestCase):
    def test_single_isolated_ds41_tier(self):
        catalog = json.loads((ROOT / "models.json").read_text(encoding="utf-8"))
        all_models = catalog["models"]
        selected = [m for m in all_models if m.get("tier") == "DS41"]
        self.assertEqual(len(selected), 2)
        by_repo = {m["repo"]: m for m in selected}
        self.assertEqual(len(by_repo), 2)
        self.assertEqual(set(by_repo), {
            "ISTA-DASLab/DeepSeek-V4.1-Flash-1017-GSQ-RCO-GGUF",
            "unsloth/DeepSeek-V4.1-Flash-1017-GGUF",
        })
        self.assertTrue(all(m["enabled"] for m in selected))
        for model in selected:
            self.assertTrue(set(model["required_patterns"]).issubset(
                set(model["allow_patterns"])
            ))
            self.assertNotIn("*", model["allow_patterns"])
        self.assertEqual(len([m for m in all_models if m.get("tier") == "ABL"]), 6)

    def test_ista_exact_four_shards_and_engram(self):
        catalog = json.loads((ROOT / "models.json").read_text(encoding="utf-8"))
        model = next(m for m in catalog["models"] if m["repo"].startswith("ISTA-DASLab/DeepSeek"))
        expected = {
            f"{BACKBONE}-{i:05d}-of-00004.gguf"
            for i in range(1, 5)
        }
        expected.add(ENGRAM)
        expected.add("tensor-allocation/DeepSeek-V4.1-Flash-1017-GSQ-RCO-IQ2_XS.rco-allocation.txt")
        self.assertEqual(set(model["required_patterns"]), expected)
        self.assertFalse(any("IQ1_M" in p or "IQ2_XXS" in p for p in model["allow_patterns"]))

    def test_unsloth_downloads_only_drafter_not_weights(self):
        catalog = json.loads((ROOT / "models.json").read_text(encoding="utf-8"))
        model = next(m for m in catalog["models"] if m["repo"].startswith("unsloth/DeepSeek"))
        self.assertEqual(model["required_patterns"], [DRAFTER])
        self.assertFalse(any("UD-" in p or "BF16.gguf" in p for p in model["allow_patterns"]))


if __name__ == "__main__":
    unittest.main()
