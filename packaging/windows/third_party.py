"""Write THIRD_PARTY_NOTICES.txt and LICENSE.txt into the frozen Windows bundle.

The Windows app ships Python packages and native libraries (FFmpeg and its
codecs, from the PyAV wheel) under their own licenses. This module collects
those license texts, lists the exact upstream sources with SHA-256 hashes, and
adds a written offer of corresponding source, so the installer and the
Microsoft Store package carry the notices their licenses require.

The native list is checked against the DLLs actually present in the bundle, so a
PyAV update that adds or drops a library cannot silently leave the notices
wrong. Set PARROTIA_STRICT_NOTICES=1 (release builds) to make that check fatal.
"""

from __future__ import annotations

import importlib.metadata as metadata
import json
import os
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
COMPONENTS_FILE = HERE / "native-components.json"
LICENSE_DIR = HERE / "licenses"
SNAP_LICENSES = ROOT / "snap" / "licenses"
REPOSITORY = "https://github.com/igorbispo99/ParrotIA"
LICENSE_NAME = re.compile(r"(?i)^(licen[sc]e|copying|notice|copyright)([._-].*)?$")
HASH_SUFFIX = re.compile(r"-[0-9a-f]{32}$")
# Wheels that omit license files; texts retained from upstream (see snap/licenses/SOURCES.md).
SUPPLEMENTAL = {
    "ctranslate2": "ctranslate2-LICENSE.txt",
    "flatbuffers": "flatbuffers-LICENSE.txt",
    "tokenizers": "tokenizers-LICENSE.txt",
}
EMBEDDED_ASSETS = [
    ("Roboto fonts (embedded in CustomTkinter)", "Roboto-APACHE-2.0.txt"),
    ("Silero VAD model (embedded in faster-whisper)", "Silero-VAD-MIT.txt"),
]
RULE = "=" * 78


def normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def python_distributions(root: str = "parrotia") -> list[metadata.Distribution]:
    """Installed distributions the app needs at run time (its requirement closure)."""
    from packaging.requirements import Requirement

    found: dict[str, metadata.Distribution] = {}
    pending = [root]
    while pending:
        name = normalize(pending.pop())
        if name in found:
            continue
        try:
            dist = metadata.distribution(name)
        except metadata.PackageNotFoundError:
            continue  # an optional dependency that is not installed
        found[name] = dist
        for line in dist.requires or []:
            requirement = Requirement(line)
            if requirement.marker and not requirement.marker.evaluate({"extra": ""}):
                continue
            pending.append(requirement.name)
    found.pop(normalize(root), None)
    return sorted(found.values(), key=lambda d: normalize(d.metadata["Name"]))


def distribution_licenses(dist: metadata.Distribution) -> list[tuple[str, str]]:
    """License texts shipped in a distribution's metadata folder, deduplicated."""
    texts: dict[str, str] = {}
    for item in dist.files or []:
        if not item.parts or not item.parts[0].endswith(".dist-info"):
            continue
        if not (LICENSE_NAME.match(item.name) or "licenses" in item.parts[1:-1]):
            continue
        try:
            text = item.locate().read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if text.strip() and text.strip() not in {t.strip() for t in texts.values()}:
            texts[item.name] = text
    if not texts:
        supplement = SUPPLEMENTAL.get(normalize(dist.metadata["Name"]))
        if supplement and (SNAP_LICENSES / supplement).is_file():
            texts[supplement] = (SNAP_LICENSES / supplement).read_text(encoding="utf-8")
    return list(texts.items())


def license_summary(dist: metadata.Distribution) -> str:
    meta = dist.metadata
    expression = meta.get("License-Expression")
    if expression:
        return expression
    legacy = (meta.get("License") or "").strip()
    if legacy and len(legacy) < 80 and "\n" not in legacy:
        return legacy
    classifiers = [
        c.split("::")[-1].strip()
        for c in meta.get_all("Classifier") or []
        if c.startswith("License ::")
    ]
    return ", ".join(classifiers) or "see the license text below"


def section(title: str) -> str:
    return f"\n{RULE}\n{title}\n{RULE}\n\n"


def native_dll_names(data: dict) -> set[str]:
    names = {dll for c in data["components"] for dll in c["dlls"]}
    names |= {entry["dll"] for entry in data["toolchain_runtime"]["libraries"]}
    return names


def check_native_libs(bundle: Path, data: dict, strict: bool) -> list[str]:
    """Compare the DLLs in the bundle's av.libs folder with the documented list."""
    problems = []
    libs = [d for d in bundle.rglob("av.libs") if d.is_dir()]
    if not libs:
        problems.append("no av.libs folder in the bundle; the native list cannot be verified")
    actual = {HASH_SUFFIX.sub("", p.stem) for d in libs for p in d.glob("*.dll")}
    listed = native_dll_names(data)
    if actual - listed:
        problems.append(f"native libraries missing from native-components.json: {sorted(actual - listed)}")
    if listed - actual and actual:
        problems.append(f"documented libraries not in the bundle: {sorted(listed - actual)}")
    try:
        installed = metadata.version("av")
    except metadata.PackageNotFoundError:
        installed = None
    if installed and installed != data["pyav_version"]:
        problems.append(f"bundle uses av {installed} but native-components.json describes av {data['pyav_version']}")
    for problem in problems:
        print(f"third-party notices: {problem}", file=sys.stderr)
    if problems and strict:
        raise SystemExit("Update packaging/windows/native-components.json for the bundled PyAV, then rebuild.")
    return problems


def render_notices(version: str, dists: list, data: dict, runtime_texts: list[tuple[str, str]]) -> str:
    """Build the notices text. `dists` holds (name, version, summary, [(file, text)]) tuples."""
    out = [
        f"THIRD-PARTY NOTICES - ParrotIA {version}\n",
        "ParrotIA is free software under the GNU Affero General Public License,\n"
        f"version 3 or later (see LICENSE.txt). Its source code is at {REPOSITORY}.\n\n"
        "This installation also contains the third-party software listed below, each\n"
        "under its own license. Whisper model files are not included; they are\n"
        "downloaded from Hugging Face the first time you use a model.\n",
        section("OFFER OF CORRESPONDING SOURCE"),
        "Some bundled native libraries (FFmpeg, LAME, x264, x265) are licensed under\n"
        "the GNU LGPL or GPL. Their exact upstream source archives, with SHA-256\n"
        "hashes and the licenses they carry, are listed in section 2. On request,\n"
        "the ParrotIA maintainer will provide a copy of the corresponding source for\n"
        "these libraries, for no more than the cost of performing the distribution.\n"
        "This offer is valid for at least three years after the release that\n"
        "included this file and for anyone who received this software from us or\n"
        "through the Microsoft Store. To request source, open an issue at\n"
        f"{REPOSITORY}/issues .\n",
        section("1. PYTHON PACKAGES"),
    ]
    for name, dist_version, summary, texts in dists:
        out.append(f"* {name} {dist_version} - {summary}\n")
    for name, dist_version, _summary, texts in dists:
        for filename, text in texts:
            out.append(f"\n--- {name} {dist_version}: {filename} ---\n\n{text.rstrip()}\n")
    out.append(section("2. NATIVE LIBRARIES (FFmpeg and codecs, from the PyAV Windows wheel)"))
    out.append(
        f"PyAV {data['pyav_version']} bundles these libraries. They were built by the\n"
        f"pyav-ffmpeg recipe at {data['build_recipe']}\n"
        "with these FFmpeg options: " + " ".join(data["ffmpeg_configuration_flags"]) + "\n\n"
    )
    for c in data["components"]:
        location = f"statically linked into {c['static_in']}" if c.get("static_in") else ", ".join(c["dlls"])
        out.append(
            f"* {c['name']} {c['version']}\n"
            f"    License: {c['license']}\n"
            f"    Library: {location}\n"
            f"    Source:  {c['source']}\n"
            f"    SHA-256: {c['sha256']}\n"
        )
    for c in data["components"]:
        for filename in c["license_files"]:
            text = (LICENSE_DIR / c["directory"] / filename).read_text(encoding="utf-8", errors="replace")
            out.append(f"\n--- {c['name']} {c['version']}: {filename} ---\n\n{text.rstrip()}\n")
    out.append(section("3. MINGW-W64 RUNTIME LIBRARIES"))
    out.append(data["toolchain_runtime"]["note"] + "\n\n")
    for entry in data["toolchain_runtime"]["libraries"]:
        out.append(f"* {entry['dll']}: {entry['license']}\n")
    out.append(section("4. PYTHON AND TCL/TK RUNTIME"))
    for filename, text in runtime_texts:
        out.append(f"--- {filename} ---\n\n{text.rstrip()}\n\n")
    if not runtime_texts:
        out.append("Python is licensed under the Python Software Foundation License,\nhttps://docs.python.org/3/license.html . Tcl/Tk is licensed under the\nTcl/Tk license, https://www.tcl-lang.org/software/tcltk/license.html .\n")
    out.append(section("5. EMBEDDED ASSETS"))
    for title, filename in EMBEDDED_ASSETS:
        text = (SNAP_LICENSES / filename).read_text(encoding="utf-8")
        out.append(f"--- {title}: {filename} ---\n\n{text.rstrip()}\n\n")
    return "".join(out)


def runtime_license_texts() -> list[tuple[str, str]]:
    """Best effort: the license files of the Python and Tcl/Tk installation being frozen."""
    texts = []
    base = Path(sys.base_prefix)
    candidates = [("Python LICENSE.txt", base / "LICENSE.txt")]
    candidates += [(f"Tcl/Tk {p.parent.name}/{p.name}", p) for p in sorted(base.glob("tcl/*/license.terms"))]
    for label, path in candidates:
        if path.is_file():
            texts.append((label, path.read_text(encoding="utf-8", errors="replace")))
    return texts


def write_notices(bundle: Path, strict: bool | None = None) -> Path:
    if strict is None:
        strict = os.environ.get("PARROTIA_STRICT_NOTICES") == "1"
    data = json.loads(COMPONENTS_FILE.read_text(encoding="utf-8"))
    check_native_libs(bundle, data, strict)
    sys.path.insert(0, str(ROOT / "src"))
    from parrotia import __version__

    dists = [
        (d.metadata["Name"], d.version, license_summary(d), distribution_licenses(d))
        for d in python_distributions()
    ]
    text = render_notices(__version__, dists, data, runtime_license_texts())
    target = bundle / "THIRD_PARTY_NOTICES.txt"
    target.write_text(text, encoding="utf-8")
    shutil.copyfile(ROOT / "LICENSE", bundle / "LICENSE.txt")
    print(f"Notices: {target} ({len(text) // 1024} KiB, {len(dists)} Python packages)")
    return target


if __name__ == "__main__":
    write_notices(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "dist" / "ParrotIA")
