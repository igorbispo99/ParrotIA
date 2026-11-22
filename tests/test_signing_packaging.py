"""Signing must stay opt-in, tag-only, and complete when it is enabled."""

import re
import runpy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github/workflows"


def steps(workflow: str) -> list[str]:
    """Split a workflow into its step blocks (each starts with `      - `)."""
    text = (WORKFLOWS / workflow).read_text(encoding="utf-8")
    return re.split(r"(?m)^(?=      - )", text)[1:]


def test_macos_spec_signs_collected_binaries():
    # BUNDLE inherits its identity from COLLECT; EXE alone signs only the launcher.
    spec = (ROOT / "packaging/macos/ParrotIA.spec").read_text(encoding="utf-8")
    collect = spec[spec.index("coll = COLLECT(") : spec.index("app = BUNDLE(")]
    assert "codesign_identity=sign_identity" in collect
    assert "entitlements_file=entitlements" in collect


def test_windows_build_stages_are_exclusive(monkeypatch, capsys):
    build = runpy.run_path(str(ROOT / "packaging/windows/build.py"))
    monkeypatch.setattr(sys, "argv", ["build.py", "--bundle-only", "--installer-only"])
    with pytest.raises(SystemExit) as stopped:
        build["main"]()
    assert stopped.value.code == 2
    assert "not allowed with" in capsys.readouterr().err


def test_setup_executable_carries_signing_metadata():
    script = (ROOT / "packaging/windows/installer.iss").read_text(encoding="utf-8")
    assert "VersionInfoProductName=ParrotIA" in script
    assert "VersionInfoProductVersion={#AppVersion}" in script
    assert "VersionInfoVersion={#AppVersion}.0" in script


def test_release_passes_secrets_to_signing_jobs():
    release = (WORKFLOWS / "release.yml").read_text(encoding="utf-8")
    for job in ("windows", "macos"):
        block = release[release.index(f"  {job}:") :].split("\n\n", 1)[0]
        assert "secrets: inherit" in block, job


@pytest.mark.parametrize(
    ("workflow", "secret_names"),
    [
        ("windows.yml", ["SIGNPATH_API_TOKEN"]),
        (
            "macos.yml",
            [
                "APPLE_CERTIFICATE_P12",
                "APPLE_CERTIFICATE_PASSWORD",
                "APPLE_NOTARY_KEY",
                "APPLE_NOTARY_KEY_ID",
                "APPLE_NOTARY_ISSUER_ID",
            ],
        ),
    ],
)
def test_signing_secrets_are_only_used_by_gated_steps(workflow, secret_names):
    gate = None
    for step in steps(workflow):
        uses_secret = any(f"secrets.{name}" in step for name in secret_names)
        if "id: signing" in step:
            gate = step
            # The check only reads whether secrets exist; it never signs.
            assert "startsWith(github.ref, 'refs/tags/v')" in step
            assert "github.event_name != 'pull_request'" in step
        elif uses_secret:
            assert "steps.signing.outputs.enabled == 'true'" in step, step[:80]
    assert gate is not None, "missing signing gate step"


def test_signpath_requests_are_gated_and_use_github_artifacts():
    requests = [s for s in steps("windows.yml") if "submit-signing-request" in s]
    assert len(requests) == 2
    for step in requests:
        assert "steps.signing.outputs.enabled == 'true'" in step
        assert "github-artifact-id:" in step
        assert "wait-for-completion: true" in step
