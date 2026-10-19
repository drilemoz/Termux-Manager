"""Test modified bundled file list without mutating the upstream snapshot."""
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
import integrate

class ManagerOverlayTests(unittest.TestCase):
    def test_fish_first_run_and_progress_in_real_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            t=Path(tmp)
            with zipfile.ZipFile(ROOT/'vendor/TermuxManager-v1.0.133.zip') as z:
                z.extractall(t/'manager')
            packaged, v=integrate.prepare_manager(t/'manager',t/'work')
            self.assertEqual(v,'1.0.133')
            content=(packaged/'modules/termux_setup.sh').read_text()
            self.assertIn('Ativar Fish automaticamente nas novas sessões?',content)
            self.assertIn('fish=skipped',content)
            self.assertIn('first_run_mark_stage fish',content)
            self.assertIn('command -v fish',content)
            ui=(packaged/'modules/termux_packages_ui.sh').read_text()
            monitor=(packaged/'modules/termux_packages_monitor.sh').read_text()
            self.assertIn('pct" = "-1"',ui)
            self.assertIn('progresso variável',ui)
            self.assertIn('tela_operacao_termux "$titulo" -1',monitor)
            self.assertNotIn('pct=$((pct + 1))',monitor)
            manifest=json.loads((packaged/'MANIFEST.json').read_text())
            for filename, digest in manifest['files'].items():
                self.assertEqual(hashlib.sha256((packaged/filename).read_bytes()).hexdigest(),digest)
            self.assertFalse((packaged/'debug_unlisted.sh').exists())

if __name__=='__main__':unittest.main()
