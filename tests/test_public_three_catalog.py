import json
from pathlib import Path
import unittest

class TestPublicThree(unittest.TestCase):
    def test_catalog(self):
        data = json.loads((Path(__file__).resolve().parents[1] / "models.json").read_text())
        selected = [m for m in data["models"] if m.get("tier") == "OPEN3"]
        self.assertEqual(len(selected), 3)
        self.assertEqual(len({m["repo"] for m in selected}), 3)
        for m in selected:
            self.assertTrue(m["enabled"])
            self.assertTrue(set(m["required_patterns"]).issubset(m["allow_patterns"]))
            self.assertNotIn("*", m["allow_patterns"])
        d = {m["repo"]: m for m in selected}
        self.assertEqual(len(d["huihui-ai/Huihui-GLM-5.3-Flash-abliterated-GGUF"]["required_patterns"]),5)
        self.assertEqual(len(d["ggml-org/GLM-5.3-Flash-GGUF"]["required_patterns"]),4)
        self.assertEqual(d["audreyt/DeepSeek-V4.1-Flash-Abliterated-GGUF"]["required_patterns"],
                         ["DeepSeek-V4.1-Flash-1017-Maya-XS-Abliterated.gguf"])
if __name__ == "__main__":
    unittest.main()
