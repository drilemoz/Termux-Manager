#!/usr/bin/env python3
"""Offline smoke tests for source patching and bundle safety."""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import integrate

ROOT = Path(__file__).resolve().parent.parent


class IntegrationTests(unittest.TestCase):
    def make_fixture(self, directory: Path):
        app = directory / "upstream"
        java = app / integrate.INSTALLER
        java.parent.mkdir(parents=True, exist_ok=True)
        java.write_text('''package com.termux.app;
class TermuxInstaller {
  void extracted() {
    if (FileUtils.directoryFileExists(TERMUX_PREFIX_DIR_PATH, true)) {
      if (TermuxFileUtils.isTermuxPrefixDirectoryEmpty()) {} else {
        whenDone.run();
        return;
      }
    }
    TermuxShellEnvironment.writeEnvironmentToFile(activity);
    activity.runOnUiThread(whenDone);
  }
}
''')
        gradle = app / "app/build.gradle"
        gradle.write_text('''android {
    defaultConfig {
        versionCode 118
        versionName "0.118.0"
    }
}
''')
        string_file = app / "app/src/main/res/values/strings.xml"
        string_file.parent.mkdir(parents=True, exist_ok=True)
        string_file.write_text('<resources><string name="application_name">Termux</string></resources>')
        m = directory / "manager"
        (m / "modules").mkdir(parents=True)
        (m / "manager.sh").write_text('MANAGER_VERSION="1.0.106"\nMANAGER_REPOSITORY="https://github.com/adriedsonlemoz/TermuxManager"\n')
        (m / "modules/core.sh").write_text('MANAGER_GITHUB_RAW_BASE="https://raw.githubusercontent.com/adriedsonlemoz/TermuxManager/main"\n')
        (m / "README.md").write_text('Use adriedsonlemoz/TermuxManager')
        (m / "install.sh").write_text('#!/bin/bash\n')
        files = {p.relative_to(m).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in m.rglob('*') if p.is_file()}
        (m / "MANIFEST.json").write_text(json.dumps({'version':'1.0.106','files':files}))
        return app, m

    def test_integration_and_origin_patch(self):
        with tempfile.TemporaryDirectory() as temp:
            app, manager = self.make_fixture(Path(temp))
            integrate.integrate(app, manager, 3)
            installer = (app / integrate.INSTALLER).read_text()
            self.assertIn('TermuxManagerBundle.install(activity);', installer)
            self.assertEqual(installer.count('TermuxManagerBundle.install(activity);'), 2)
            self.assertIn('tm-manager-existing-prefix', installer)
            gradle = (app / 'app/build.gradle').read_text()
            self.assertIn('versionCode 118003', gradle)
            self.assertIn('versionName "0.118.0+tm.3"', gradle)
            self.assertIn('Termux Manager', (app/'app/src/main/res/values/strings.xml').read_text())
            self.assertIn('TM_KEYSTORE_FILE', gradle)
            index = (app / integrate.INDEX_ASSET).read_text().splitlines()
            expected = dict(line.split('\t') for line in index)
            with zipfile.ZipFile(app / integrate.ASSET) as z:
                self.assertEqual(set(z.namelist()), set(expected))
                for name, digest in expected.items():
                    self.assertEqual(hashlib.sha256(z.read(name)).hexdigest(), digest)
                self.assertIn('manager.sh', z.namelist())
                self.assertIn('modules/core.sh', z.namelist())
                self.assertNotIn(b'adriedsonlemoz/TermuxManager',z.read('manager.sh'))
                m=json.loads(z.read('MANIFEST.json'))
                for n, digest in m['files'].items():
                    self.assertEqual(hashlib.sha256(z.read(n)).hexdigest(),digest)
            with self.assertRaises(RuntimeError):
                integrate.integrate(app, manager, 3)  # refuse double patch

    def test_mismatch_aborts_and_preserves_upstream(self):
        with tempfile.TemporaryDirectory() as temp:
            app, manager = self.make_fixture(Path(temp))
            (manager/'modules/core.sh').write_text('tampered\n')
            before=(app/integrate.INSTALLER).read_bytes()
            with self.assertRaisesRegex(RuntimeError,'SHA-256 mismatch'):
                integrate.integrate(app, manager, 1)
            self.assertEqual((app/integrate.INSTALLER).read_bytes(),before)
            self.assertFalse((app/integrate.ASSET).exists())

    def test_unlisted_file_is_not_packed(self):
        with tempfile.TemporaryDirectory() as temp:
            app, manager = self.make_fixture(Path(temp))
            (manager / 'nao_listado.sh').write_text('echo warning')
            integrate.integrate(app, manager, 3)
            with zipfile.ZipFile(app / integrate.ASSET) as z:
                self.assertNotIn('nao_listado.sh', z.namelist())

    def test_incompatible_version_leaves_upstream_intact(self):
        with tempfile.TemporaryDirectory() as temp:
            app, manager = self.make_fixture(Path(temp))
            gradle = app / 'app/build.gradle'
            gradle.write_text(gradle.read_text().replace('"0.118.0"', '"bad-version"'))
            original = (app / integrate.INSTALLER).read_bytes()
            with self.assertRaisesRegex(RuntimeError, 'versionName'):
                integrate.integrate(app, manager, 3)
            self.assertEqual((app / integrate.INSTALLER).read_bytes(), original)
            self.assertFalse((app / integrate.ASSET).exists())
            self.assertFalse((app / integrate.INDEX_ASSET).exists())
            self.assertFalse((app / integrate.APP_JAVA / 'TermuxManagerBundle.java').exists())

    def test_syntax_check(self):
        subprocess.run(['python3','-m','py_compile',str(ROOT/'tools/integrate.py'),str(ROOT/'tools/validate_sources.py')],check=True)


if __name__ == '__main__':
    unittest.main(verbosity=2)
