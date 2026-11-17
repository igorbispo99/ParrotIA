"""Release pages contain one version's changes and actual download targets."""

import runpy
from pathlib import Path

import pytest

module = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "packaging/release_notes.py")
)
render = module["render_release_notes"]
extract = module["version_changes"]

CHANGELOG = """# Changelog

## [2.0.0] - 2026-11-16

### Added
- New macOS app.

## [1.0.0] - 2026-06-05

### Added
- Old feature.

[1.0.0]: https://example.com/old
"""


def test_only_requested_version_and_downloads_first():
    body = render(
        CHANGELOG, "v2.0.0", ["ParrotIA-2.0.0-macos-arm64.dmg", "parrotia.rb"]
    )
    assert body.startswith("## Downloads")
    assert body.index("macOS · Apple Silicon") < body.index("What's changed")
    assert "/v2.0.0/ParrotIA-2.0.0-macos-arm64.dmg" in body
    assert "New macOS app." in body and "Old feature." not in body
    assert "Windows" not in body and "parrotia.rb" not in body


def test_oldest_section_does_not_include_reference_definitions():
    assert extract(CHANGELOG, "1.0.0") == "### Added\n- Old feature."


def test_missing_version_fails_instead_of_publishing_history():
    with pytest.raises(ValueError, match="No changelog entry"):
        render(CHANGELOG, "v9.0.0", ["package.whl"])


def test_no_installer_links_are_invented():
    body = render(CHANGELOG, "1.0.0", ["parrotia-1.0.0-py3-none-any.whl"])
    assert "Python package" in body
    assert "macOS" not in body and "Windows" not in body


def test_empty_artifacts_fail():
    with pytest.raises(ValueError, match="No downloadable"):
        render(CHANGELOG, "v2.0.0", [])
