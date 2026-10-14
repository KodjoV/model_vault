import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest

os.environ['UI_PASSWORD'] = 'unit-test-password'
root = tempfile.TemporaryDirectory()
os.environ['VAULT_ROOT'] = root.name
os.environ['VAULT_CONFIG'] = str(Path(__file__).resolve().parents[1] / 'models.json')
loader = importlib.util.spec_from_file_location('vault', Path(__file__).resolve().parents[1] / 'vault.py')
vault = importlib.util.module_from_spec(loader)
loader.loader.exec_module(vault)

DATA = b'model-vault-demo-bytes:' * 3000
HASH = hashlib.sha256(DATA).hexdigest()

class ByteRangeHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != '/weights':
            self.send_error(404)
            return
        raw = self.headers.get('Range', '')
        if raw:
            start = int(raw.removeprefix('bytes=').removesuffix('-'))
            self.send_response(206)
            self.send_header('Content-Range', f'bytes {start}-{len(DATA)-1}/{len(DATA)}')
        else:
            start = 0
            self.send_response(200)
        self.send_header('Content-Length', str(len(DATA)-start))
        self.end_headers()
        self.wfile.write(DATA[start:])
    def log_message(self, *args):
        pass

class VaultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        vault.DOT.mkdir(parents=True, exist_ok=True)
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), ByteRangeHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.old_url = vault.hf_url
        vault.hf_url = lambda repo, sha, name: f'http://127.0.0.1:{cls.server.server_port}/weights'

    @classmethod
    def tearDownClass(cls):
        vault.hf_url = cls.old_url
        cls.server.shutdown()
        cls.server.server_close()
        root.cleanup()

    def setUp(self):
        vault.PLAN = {'created_at': vault.now(), 'models': {}}
        vault.RUNTIME = {'active': {}, 'phase': 'starting', 'last_error': None}
        vault.STOP.clear()
        vault.PAUSE_FILE.unlink(missing_ok=True)

    def test_resume_and_sha256_and_status(self):
        repo = 'offline/test-repo'
        name = 'nested/model.bin'
        path = vault.local_path(repo, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        part = path.with_name(path.name + '.part')
        part.write_bytes(DATA[:7333])  # simulate interrupted download
        record = {'repo': repo, 'sha':'0'*40, 'tier':'P0', 'note':'test',
                  'files':[{'path':name, 'size':len(DATA), 'lfs_sha256':HASH}],
                  'verified':{}, 'state':'downloading', 'error':''}
        vault.PLAN['models'][repo] = record
        old_get_config = vault.get_config
        vault.get_config = lambda:[{'repo':repo,'tier':'P0'}]
        try:
            before = vault.collect_status()
            self.assertEqual(before['downloaded_bytes'], 7333)
            self.assertEqual(before['expected_bytes'], len(DATA))
            vault.download_file(repo, '0'*40, record['files'][0], record)
            self.assertEqual(path.read_bytes(), DATA)
            self.assertFalse(part.exists())
            self.assertEqual(record['verified'][name]['sha256'], HASH)
            vault.finish_model(repo, record)
            after = vault.collect_status()
            self.assertEqual(after['percent'], 100.0)
            self.assertEqual(after['complete_models'], 1)
            self.assertTrue(after['verified_complete'])
            manifest = json.loads((path.parents[1] / 'MODEL_VAULT_MANIFEST.json').read_text())
            self.assertEqual(manifest['revision'], '0'*40)
        finally:
            vault.get_config = old_get_config

    def test_config_and_path_safety(self):
        self.assertFalse(vault.is_safe_path('../etc/passwd'))
        self.assertFalse(vault.is_safe_path('/etc/passwd'))
        self.assertTrue(vault.is_safe_path('nested/model.safetensors'))
        self.assertTrue(vault.wanted('f/foo-Q5_K.gguf', ['*Q5_K.gguf']))

if __name__ == '__main__':
    unittest.main()
