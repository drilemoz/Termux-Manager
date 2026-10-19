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
        layout = app / "app/src/main/res/layout/activity_termux.xml"
        layout.parent.mkdir(parents=True, exist_ok=True)
        layout.write_text('<LinearLayout android:background="@color/black"/>')
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
            integrate.integrate(app, manager, 5)
            installer = (app / integrate.INSTALLER).read_text()
            self.assertIn('TermuxManagerBundle.install(activity);', installer)
            self.assertEqual(installer.count('TermuxManagerBundle.install(activity);'), 2)
            self.assertIn('tm-manager-existing-prefix', installer)
            gradle = (app / 'app/build.gradle').read_text()
            self.assertIn('versionCode 118005', gradle)
            self.assertIn('versionName "0.118.0+tm.5"', gradle)
            self.assertIn('Termux Manager', (app/'app/src/main/res/values/strings.xml').read_text())
            self.assertIn('TM_KEYSTORE_FILE', gradle)
            self.assertIn('termux_manager_toolbar_background', (app/'app/src/main/res/layout/activity_termux.xml').read_text())
            self.assertTrue((app / integrate.LEGACY_INDEX_ASSET).is_file())
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
                integrate.integrate(app, manager, 5)  # refuse double patch

    def test_real_133_bundle_integration_preserves_visual_and_features(self):
        # Exercises the actual verified release, not only the synthetic 1.0.106 fixture.
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp)
            app, _ = self.make_fixture(work)
            manager = work / "real_manager"
            with zipfile.ZipFile(ROOT / "vendor/TermuxManager-v1.0.133.zip") as archive:
                self.assertIsNone(archive.testzip())
                self.assertTrue(all(not Path(name).is_absolute() and ".." not in Path(name).parts
                                    for name in archive.namelist()))
                archive.extractall(manager)
            integrate.integrate(app, manager, 5)
            self.assertIn('termux_manager_toolbar_background',
                          (app / 'app/src/main/res/layout/activity_termux.xml').read_text())
            index = dict(line.split('\t') for line in (app / integrate.INDEX_ASSET).read_text().splitlines())
            with zipfile.ZipFile(app / integrate.ASSET) as bundled:
                self.assertEqual(set(index), set(bundled.namelist()))
                release = json.loads(bundled.read('MANIFEST.json'))
                self.assertEqual(release['version'], '1.0.133')
                self.assertEqual(len(release['files']), 147)
                self.assertIn('modules/runtime_processes.sh', bundled.namelist())
                self.assertIn('modules/import_wizard.sh', bundled.namelist())
                self.assertIn('tools/test-iniciar-tudo-133.sh', bundled.namelist())
                self.assertIn(b'Ativar Fish automaticamente nas novas sess',
                              bundled.read('modules/termux_setup.sh'))
                for name, digest in index.items():
                    self.assertEqual(hashlib.sha256(bundled.read(name)).hexdigest(), digest)

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
            integrate.integrate(app, manager, 5)
            with zipfile.ZipFile(app / integrate.ASSET) as z:
                self.assertNotIn('nao_listado.sh', z.namelist())

    def test_incompatible_version_leaves_upstream_intact(self):
        with tempfile.TemporaryDirectory() as temp:
            app, manager = self.make_fixture(Path(temp))
            gradle = app / 'app/build.gradle'
            gradle.write_text(gradle.read_text().replace('"0.118.0"', '"bad-version"'))
            original = (app / integrate.INSTALLER).read_bytes()
            with self.assertRaisesRegex(RuntimeError, 'versionName'):
                integrate.integrate(app, manager, 5)
            self.assertEqual((app / integrate.INSTALLER).read_bytes(), original)
            self.assertFalse((app / integrate.ASSET).exists())
            self.assertFalse((app / integrate.INDEX_ASSET).exists())
            self.assertFalse((app / integrate.APP_JAVA / 'TermuxManagerBundle.java').exists())

    def test_syntax_check(self):
        subprocess.run(['python3','-m','py_compile',str(ROOT/'tools/integrate.py'),str(ROOT/'tools/validate_sources.py')],check=True)


if __name__ == '__main__':
    unittest.main(verbosity=2)
