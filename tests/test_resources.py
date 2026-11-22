"""In-app legal links must point at files that exist, and notices must be found."""

import subprocess
import sys
from pathlib import Path

from parrotia import resources

ROOT = Path(__file__).resolve().parents[1]


def repo_path(url: str) -> Path:
    prefix = f"{resources.PROJECT_URL}/blob/main/"
    assert url.startswith(prefix), url
    return ROOT / url.removeprefix(prefix)


def test_privacy_and_license_links_point_at_tracked_files():
    assert repo_path(resources.PRIVACY_URL).is_file()
    assert repo_path(resources.LICENSE_URL).is_file()


def test_notices_are_found_only_beside_a_frozen_executable(tmp_path, monkeypatch):
    assert resources.bundled_notices() is None  # running from source
    exe = tmp_path / "parrotia-gui.exe"
    exe.write_bytes(b"MZ")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    assert resources.bundled_notices() is None  # no file shipped
    (tmp_path / resources.NOTICES_NAME).write_text("notices", encoding="utf-8")
    assert resources.bundled_notices() == tmp_path / resources.NOTICES_NAME


def test_hugging_face_usage_telemetry_is_off_unless_the_user_overrides(tmp_path):
    code = (
        "import os, parrotia.transcriber; print(os.environ['HF_HUB_DISABLE_TELEMETRY'])"
    )
    run = lambda env: subprocess.run(  # noqa: E731
        [sys.executable, "-c", code], capture_output=True, text=True, env=env, cwd=ROOT
    )
    import os

    base = {k: v for k, v in os.environ.items() if k != "HF_HUB_DISABLE_TELEMETRY"}
    base["PYTHONPATH"] = str(ROOT / "src")
    assert run(base).stdout.strip() == "1"
    assert run({**base, "HF_HUB_DISABLE_TELEMETRY": "0"}).stdout.strip() == "0"
