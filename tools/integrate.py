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

ROOT = Path(__file__).resolve().parent.parent
OLD_REPO = "adriedsonlemoz/TermuxManager"
NEW_REPO = "drilemoz/TermuxManager"
APP_JAVA = Path("app/src/main/java/com/termux/app")
INSTALLER = APP_JAVA / "TermuxInstaller.java"
ASSET = Path("app/src/main/assets/termux-manager.bundle.zip")


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
        if sha256(p) != digest.lower():
            raise RuntimeError("Manager manifest SHA-256 mismatch: " + relative)
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
    return staged, manifest["version"]


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
    for file in [installer_path, gradle_path, strings_path]:
        if not file.is_file():
            raise RuntimeError("Not a compatible termux-app checkout: " + str(file))
    with tempfile.TemporaryDirectory(prefix="tm-integration-") as td:
        prepared, version = prepare_manager(manager, Path(td))
        make_zip(prepared, upstream / ASSET)

    destination = upstream / APP_JAVA / "TermuxManagerBundle.java"
    if destination.exists():
        raise RuntimeError("TermuxManagerBundle.java already exists; refusing duplicate patch")
    shutil.copyfile(ROOT / "integration/TermuxManagerBundle.java", destination)

    content = installer_path.read_text(encoding="utf-8")
    # Install from the background bootstrap installer, after $PREFIX is committed.
    anchor = "                    TermuxShellEnvironment.writeEnvironmentToFile(activity);"
    addition = anchor + "\n\n                    // Install the optional offline TermuxManager bundle.\n" \
        "                    TermuxManagerBundle.install(activity);"
    content = replace_exact(content, anchor, addition, "bootstrap callback")
    installer_path.write_text(content, encoding="utf-8")

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
    gradle_path.write_text(gradle, encoding="utf-8")

    strings = strings_path.read_text(encoding="utf-8")
    new_strings, count = re.subn(
        r'(<string\s+name="application_name">).*?(</string>)',
        r'\g<1>Termux Manager\2', strings, count=1)
    if count != 1:
        raise RuntimeError("Could not find application_name string")
    strings_path.write_text(new_strings, encoding="utf-8")
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
