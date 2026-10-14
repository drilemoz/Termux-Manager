#!/usr/bin/env python3
"""Guard the SDK bootstrap regression observed in GitHub Actions run #1."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / '.github/workflows/build-personal-apk.yml'


class WorkflowRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding='utf-8')

    def test_deprecated_android_sdk_tools_are_not_requested(self):
        self.assertIn('uses: android-actions/setup-android@v4', self.workflow)
        self.assertRegex(self.workflow, r'uses: android-actions/setup-android@v4\s+with:\s+packages: platform-tools')
        self.assertNotIn('android-actions/setup-android@v3', self.workflow)
        self.assertNotRegex(self.workflow, r'(?m)^\s*packages:\s*["\']?tools(?:\s|["\']|$)')

    def test_apk_only_published_after_success(self):
        self.assertRegex(self.workflow, r'(?s)- name: Publicar APK compilado\s+if: success\(\)')
        self.assertIn('if-no-files-found: error', self.workflow)
        self.assertRegex(self.workflow, r'(?s)- name: Publicar apenas diagn[oó]stico quando falhar\s+if: failure\(\)')

    def test_local_tests_run_before_gradle(self):
        self.assertLess(self.workflow.index('test_java_bundle.py'), self.workflow.index(':app:assembleDebug'))
        self.assertIn("sdkmanager --install 'ndk;29.0.14206865' 'platforms;android-36' 'build-tools;36.0.0'", self.workflow)

    def test_version_sync(self):
        self.assertEqual((ROOT/'BUILD_NUMBER').read_text().strip(),'2')
        self.assertIn('0.1.0-alpha.2', (ROOT/'README.md').read_text())
        self.assertIn('0.1.0-alpha.2', (ROOT/'CHANGELOG.md').read_text())

    def test_yaml_parses_and_has_required_steps(self):
        try:
            import yaml
        except ImportError:
            self.skipTest('PyYAML unavailable')
        data = yaml.safe_load(self.workflow)
        steps = data['jobs']['build']['steps']
        names = [s['name'] for s in steps]
        self.assertEqual(len(names), len(set(names)))
        self.assertIn('Preparar Android SDK', names)
        self.assertIn('Compilar APK Android', names)
        self.assertIn('Publicar APK compilado', names)


if __name__ == '__main__':
    unittest.main(verbosity=2)
