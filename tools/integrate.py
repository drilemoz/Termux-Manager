#!/usr/bin/env python3
"""Integrate a bundled TermuxManager into a pinned checkout of termux-app.

The output is an Android source tree, not a replacement bootstrap. It preserves
package id com.termux, which also preserves Termux's hardcoded filesystem paths.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from manager_overlays import apply_manager_overlays

ROOT = Path(__file__).resolve().parent.parent
OLD_REPO = "adriedsonlemoz/TermuxManager"
NEW_REPO = "drilemoz/TermuxManager"
APP_JAVA = Path("app/src/main/java/com/termux/app")
INSTALLER = APP_JAVA / "TermuxInstaller.java"
ASSET = Path("app/src/main/assets/termux-manager.bundle.zip")
INDEX_ASSET = Path("app/src/main/assets/termux-manager.bundle-index.tsv")
LEGACY_INDEX_ASSET = Path("app/src/main/assets/termux-manager.legacy-index-1.0.126.tsv")


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def validate_manager(manager: Path) -> dict:
    manifest_path = manager / "MANIFEST.json"
    m = json.loads(manifest_path.read_text(encoding="utf-8"))
    version = re.search(r'^MANAGER_VERSION="([^"]+)"',
        (manager / "manager.sh").read_text(encoding="utf-8"), re.M)
    if not version or m.get("version") != version.group(1):
        raise RuntimeError("Manager version does not match MANIFEST.json")
    entries = m.get("files")
    if not isinstance(entries, dict) or not entries:
        raise RuntimeError("Manager manifest has no file hashes")
    for relative, digest in entries.items():
        p = manager / relative
        if Path(relative).is_absolute() or ".." in Path(relative).parts or not p.is_file():
            raise RuntimeError("Manager manifest has invalid or missing file: " + relative)
        if p.is_symlink() or not re.fullmatch(r"[0-9a-fA-F]{64}", digest):
            raise RuntimeError("Invalid file type or digest: " + relative)
        if sha256(p) != digest.lower():
            raise RuntimeError("Manager manifest SHA-256 mismatch: " + relative)
    for required in ("manager.sh", "modules/core.sh", "install.sh"):
        if required not in entries:
            raise RuntimeError("Required Manager file missing from manifest: " + required)
    for p in (manager / "modules").rglob("*.sh"):
        if p.relative_to(manager).as_posix() not in entries:
            raise RuntimeError("Unlisted Manager module: " + str(p))
    return m


def prepare_manager(manager: Path, work: Path) -> tuple[Path, str]:
    # Do not copy .git data or host-specific cache files into the APK.
    staged = work / "manager"
    shutil.copytree(manager, staged, ignore=shutil.ignore_patterns(
        ".git", "__pycache__", "*.pyc", ".DS_Store"))
    manifest = validate_manager(staged)
    replaced = []
    for p in staged.rglob("*"):
        if not p.is_file() or p.name == "MANIFEST.json":
            continue
        if p.suffix not in (".sh", ".md", ".json", ".txt", ".yml", ".yaml"):
            continue
        s = p.read_text(encoding="utf-8")
        if OLD_REPO in s:
            p.write_text(s.replace(OLD_REPO, NEW_REPO), encoding="utf-8")
            replaced.append(p.relative_to(staged).as_posix())
    # Recalculate official-format hash list after fixing obsolete repository URLs.
    for rel in manifest["files"]:
        manifest["files"][rel] = sha256(staged / rel)
    (staged / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if OLD_REPO in (staged / "manager.sh").read_text(encoding="utf-8"):
        raise RuntimeError("Manager origin update failed")
    print(f"Manager {manifest['version']}: {len(manifest['files'])} verified manifest entries; "
          f"updated origin in {len(replaced)} files")
    if (staged/'modules/termux_setup.sh').is_file():
        apply_manager_overlays(staged)
    elif manifest['version'] != '1.0.106':
        raise RuntimeError('Required Manager overlays cannot be applied to this snapshot')
    # Stage only signed-manifest files and MANIFEST.json; all other material is excluded.
    packaged = work / "packaged"
    for rel in [*manifest["files"], "MANIFEST.json"]:
        destination = packaged / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(staged / rel, destination)
    return packaged, manifest["version"]


def make_zip(src: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in sorted(src.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(src).as_posix())
    with zipfile.ZipFile(target) as z:
        for name in z.namelist():
            if name.startswith("/") or ".." in Path(name).parts or "\\" in name:
                raise RuntimeError("Unsafe zip entry: " + name)
        assert "manager.sh" in z.namelist()
        assert "MANIFEST.json" in z.namelist()


def create_index(packaged: Path) -> str:
    files = sorted(p for p in packaged.rglob("*") if p.is_file())
    return "".join(f"{p.relative_to(packaged).as_posix()}\t{sha256(p)}\n" for p in files)


def signing_gradle() -> str:
    return """
// Termux Manager: do not distribute an APK signed by the upstream public test key.
if (System.getenv('TM_KEYSTORE_FILE')) {
    android.signingConfigs {
        termuxManagerPrivate {
            storeFile file(System.getenv('TM_KEYSTORE_FILE'))
            storePassword System.getenv('KEYSTORE_PASSWORD')
            keyAlias System.getenv('KEY_ALIAS')
            keyPassword System.getenv('KEY_PASSWORD')
        }
    }
    android.buildTypes.debug.signingConfig = android.signingConfigs.termuxManagerPrivate
} else {
    throw new GradleException('Private signing not configured: TM_KEYSTORE_FILE missing')
}
"""


def replace_exact(contents: str, old: str, new: str, label: str) -> str:
    count = contents.count(old)
    if count != 1:
        raise RuntimeError(f"Expected exactly one {label} anchor, found {count}")
    return contents.replace(old, new)


def integrate(upstream: Path, manager: Path, build_number: int) -> None:
    if build_number < 1 or build_number > 999:
        raise RuntimeError("build_number must be in the range 1..999")
    installer_path = upstream / INSTALLER
    gradle_path = upstream / "app/build.gradle"
    strings_path = upstream / "app/src/main/res/values/strings.xml"
    layout_path = upstream / "app/src/main/res/layout/activity_termux.xml"
    for file in [installer_path, gradle_path, strings_path, layout_path]:
        if not file.is_file():
            raise RuntimeError("Not a compatible termux-app checkout: " + str(file))
    destination = upstream / APP_JAVA / "TermuxManagerBundle.java"
    if destination.exists() or (upstream / ASSET).exists():
        raise RuntimeError("TermuxManager already integrated: refusing duplicate patch")

    # Calculate all patches and validate source anchors before touching upstream.
    content = installer_path.read_text(encoding="utf-8")
    callback = 'activity.runOnUiThread(whenDone);'
    content = replace_exact(content, callback, 'TermuxManagerBundle.install(activity);\n                ' + callback, "fresh bootstrap callback")
    current_branch = re.compile(r'(?m)^([ \t]*)whenDone\.run\(\);[ \t]*\n[ \t]*return;')
    # This block must be inside the existing nonempty $PREFIX branch.
    branch_anchor = 'if (FileUtils.directoryFileExists(TERMUX_PREFIX_DIR_PATH, true))'
    if content.count(branch_anchor) != 1:
        raise RuntimeError("Could not locate existing-prefix branch")
    head, tail = content.split(branch_anchor, 1)
    found = current_branch.search(tail)
    if not found or found.start() > 1000:
        raise RuntimeError("Existing-prefix completion callback not found")
    old = found.group(0)
    new = (found.group(1) + 'new Thread(() -> {\n'
        + found.group(1) + '    TermuxManagerBundle.install(activity);\n'
        + found.group(1) + '    activity.runOnUiThread(whenDone);\n'
        + found.group(1) + '}, "tm-manager-existing-prefix").start();\n'
        + found.group(1) + 'return;')
    tail = tail[:found.start()] + new + tail[found.end():]
    content = head + branch_anchor + tail
    gradle = gradle_path.read_text(encoding="utf-8")
    m = re.search(r'(?m)^(\s*)versionCode\s+(\d+)\s*$', gradle)
    if not m or len(re.findall(r'(?m)^\s*versionCode\s+\d+\s*$', gradle)) != 1:
        raise RuntimeError("Could not locate stock Termux versionCode")
    base_code = int(m.group(2))
    version_code = base_code * 1000 + build_number
    gradle = gradle[:m.start()] + m.group(1) + f"versionCode {version_code}" + gradle[m.end():]
    m = re.search(r'(?m)^(\s*)versionName\s+"([0-9]+\.[0-9]+\.[0-9]+)"\s*$', gradle)
    if not m or len(re.findall(r'(?m)^\s*versionName\s+"', gradle)) != 1:
        raise RuntimeError("Could not locate stock Termux versionName")
    version_name = f"{m.group(2)}+tm.{build_number}"
    gradle = gradle[:m.start()] + m.group(1) + f'versionName "{version_name}"' + gradle[m.end():]
    gradle += signing_gradle()

    strings = strings_path.read_text(encoding="utf-8")
    new_strings, count = re.subn(
        r'(<string\s+name="application_name">).*?(</string>)',
        r'\g<1>Termux Manager\2', strings, count=1)
    if count != 1:
        raise RuntimeError("Could not find application_name string")
    localized_strings = {}
    for local in (upstream / "app/src/main/res").glob("values-*/strings.xml"):
        original_local = local.read_text(encoding="utf-8")
        translated, replacements = re.subn(
            r'(<string\s+name="application_name"[^>]*>).*?(</string>)',
            r'\g<1>Termux Manager\2', original_local, count=1)
        if replacements == 1:
            localized_strings[local] = translated
    if not (ROOT / "integration/TermuxManagerBundle.java").is_file():
        raise RuntimeError("Missing Java bundle source")
    brand = ROOT / "integration/branding"
    images = list(brand.glob('mipmap-*/*.png'))
    if len(images) < 10:
        raise RuntimeError("Missing launcher icon assets")

    # Android native extra-keys background: stock termux layout explicitly uses
    # @color/black. Match our terminal palette without changing Gboard/SwiftKey.
    layout = layout_path.read_text(encoding="utf-8")
    layout = replace_exact(layout, 'android:background="@color/black"',
                           'android:background="@color/termux_manager_toolbar_background"',
                           'Termux extra keys background')
    legacy_index = ROOT / "integration/legacy-index-1.0.126.tsv"
    if not legacy_index.is_file() or 'manager.sh\t' not in legacy_index.read_text():
        raise RuntimeError("Missing verified baseline index for Manager 1.0.126 migration")
    # Bundle generated into temp; do not patch upstream until validation completes.
    with tempfile.TemporaryDirectory(prefix="tm-integration-") as td:
        tmp = Path(td)
        prepared, version = prepare_manager(manager, tmp)
        bundle = tmp / 'manager.zip'
        make_zip(prepared, bundle)
        index = create_index(prepared)
        if not index or "manager.sh\t" not in index:
            raise RuntimeError("Invalid bundle index")
        edits = {
            installer_path: content,
            gradle_path: gradle,
            strings_path: new_strings,
            layout_path: layout,
            upstream / INDEX_ASSET: index,
            **localized_strings,
        }
        copies = {destination: ROOT / 'integration/TermuxManagerBundle.java',
                  upstream / ASSET: bundle,
                  upstream / LEGACY_INDEX_ASSET: legacy_index}
        for icon_file in images:
            copies[upstream / 'app/src/main/res' / icon_file.relative_to(brand)] = icon_file
        for xml_file in brand.rglob('*.xml'):
            copies[upstream / 'app/src/main/res' / xml_file.relative_to(brand)] = xml_file
        # Keep pristine originals for rollback on filesystem errors.
        targets = [*edits, *copies]
        original = {p: p.read_bytes() if p.is_file() else None for p in targets}
        try:
            for p, text in edits.items():
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(text, encoding='utf-8')
            for p, source in copies.items():
                p.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, p)
        except Exception:
            for p, before in original.items():
                if before is None:
                    p.unlink(missing_ok=True)
                else:
                    p.write_bytes(before)
            raise
    print(f"Integrated TermuxManager {version} into Termux app: "
          f"versionName={version_name}, versionCode={version_code}")
    print("Custom apk package id is com.termux; stock/debug signatures are not interchangeable")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--termux", type=Path, required=True, help="termux/termux-app checkout")
    parser.add_argument("--manager", type=Path, required=True, help="drilemoz/TermuxManager checkout")
    parser.add_argument("--build-number", type=int, default=1)
    args = parser.parse_args()
    try:
        integrate(args.termux.resolve(), args.manager.resolve(), args.build_number)
    except Exception as e:
        print("INTEGRATION ERROR:", str(e), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
