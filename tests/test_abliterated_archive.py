"""ABL catalog and read-only archive audit tests (stdlib only)."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

BASE = Path(__file__).resolve().parents[1]
SCRIPT = BASE / "tools" / "verify-abliterated.py"
LOADER = importlib.util.spec_from_file_location("verify_abliterated", SCRIPT)
MODULE = importlib.util.module_from_spec(LOADER)
LOADER.loader.exec_module(MODULE)


class AbliteratedArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = "sample/model"
        self.filename = "folder/main.gguf"
        self.model = {
            "repo": self.repo,
            "tier": "ABL",
            "required_patterns": [self.filename],
        }
        directory = self.root / "models" / self.repo
        (directory / "folder").mkdir(parents=True)
        data = b"fake weights for an offline test"
        (directory / self.filename).write_bytes(data)
        self.manifest_path = directory / "MODEL_VAULT_MANIFEST.json"
        self.record = {
            "path": self.filename,
            "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "lfs_sha256": hashlib.sha256(data).hexdigest(),
        }
        self._write_manifest()

    def _write_manifest(self):
        manifest = {
            "repo": self.repo,
            "revision": "a" * 40,
            "files": [self.record],
        }
        self.manifest_path.write_text(json.dumps(manifest))

    def test_all_six_configured_in_isolated_tier(self):
        models = json.loads((BASE / "models.json").read_text())["models"]
        self.assertEqual(len(models), len({m["repo"] for m in models}))
        selected = [m for m in models if m.get("tier") == "ABL"]
        self.assertEqual(len(selected), 6)
        for model in selected:
            self.assertTrue(model["enabled"])
            self.assertTrue(model["required_patterns"])
            self.assertTrue(set(model["required_patterns"]).issubset(
                set(model["allow_patterns"])
            ))
            self.assertTrue(all(p.endswith((".gguf", ".txt"))
                                for p in model["required_patterns"]))
        self.assertIn("m-a-p/YuE2-3B", {m["repo"] for m in models})
        self.assertIn("openai/whisper-large-v3", {m["repo"] for m in models})

    def test_offline_sha256_success(self):
        self.assertEqual(MODULE.verify_one(self.root, self.model)[0], 1)

    def test_tamper_detected(self):
        p = self.root / "models" / self.repo / self.filename
        p.write_bytes(b"x" * len(p.read_bytes()))
        with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
            MODULE.verify_one(self.root, self.model)

    def test_missing_required_file_rejected(self):
        self.model["required_patterns"] = ["not-there.gguf"]
        with self.assertRaisesRegex(ValueError, "missing required"):
            MODULE.verify_one(self.root, self.model)

    def test_rejects_path_traversal_and_invalid_revision(self):
        for value in ("../oops", "/tmp/weights", "x/../z", "a\\b"):
            with self.assertRaises(ValueError):
                MODULE.safe_rel(value)
        manifest = json.loads(self.manifest_path.read_text())
        manifest["revision"] = "main"
        self.manifest_path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "non-commit revision"):
            MODULE.verify_one(self.root, self.model)


if __name__ == "__main__":
    unittest.main()
