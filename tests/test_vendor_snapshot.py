"""Validate integrity of bundled TermuxManager v1.0.126 snapshot."""
import hashlib
import json
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class VendorSnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.archive = ROOT / 'vendor/TermuxManager-v1.0.126.zip'
        cls.digest = (ROOT / 'vendor/SHA256SUMS').read_text().split()[0]

    def test_archive_sha256(self):
        self.assertEqual(hashlib.sha256(self.archive.read_bytes()).hexdigest(), self.digest)

    def test_manifest_hashes_and_version(self):
        with zipfile.ZipFile(self.archive) as z:
            self.assertIsNone(z.testzip())
            self.assertIn('MANIFEST.json', z.namelist())
            manifest = json.loads(z.read('MANIFEST.json'))
            self.assertEqual(manifest['version'], '1.0.126')
            self.assertGreaterEqual(len(manifest['files']), 138)
            all_files = {name for name in z.namelist() if not name.endswith('/')}
            self.assertEqual(all_files, set(manifest['files']) | {'MANIFEST.json'})
            for name, digest in manifest['files'].items():
                self.assertNotIn('..', Path(name).parts)
                self.assertEqual(hashlib.sha256(z.read(name)).hexdigest(), digest)


if __name__ == '__main__':
    unittest.main(verbosity=2)
