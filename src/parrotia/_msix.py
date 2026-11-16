"""Behavior specific to the MSIX (Microsoft Store) package on Windows.

MSIX runs the same frozen executable as the Inno Setup installer, so the
differences are decided at runtime from the process's package identity.

Packaged data goes to the package's own ``LocalCache`` folder, which Windows
always deletes on uninstall (Store policy 10.2.7: clean removal). AppData
write virtualization is not relied on: Windows does not redirect writes into a
folder that already exists outside the package, such as the
``%LOCALAPPDATA%\\ParrotIA`` folder the Inno Setup build creates.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import MutableMapping, Optional

_ERROR_INSUFFICIENT_BUFFER = 122


def _package_string(function_name: str) -> Optional[str]:
    """Call a ``GetCurrentPackage*`` API; None when the process is unpackaged."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        function = getattr(ctypes.windll.kernel32, function_name)
    except (AttributeError, ImportError, OSError):
        return None  # Windows 7 and older lack the API, and package identity.
    function.argtypes = [ctypes.POINTER(wintypes.UINT), wintypes.LPWSTR]
    function.restype = wintypes.LONG
    length = wintypes.UINT(0)
    # Unpackaged processes get APPMODEL_ERROR_NO_PACKAGE (15700) instead.
    if function(ctypes.byref(length), None) != _ERROR_INSUFFICIENT_BUFFER:
        return None
    buffer = ctypes.create_unicode_buffer(length.value)
    if function(ctypes.byref(length), buffer) != 0:
        return None
    return buffer.value or None


def package_family_name() -> Optional[str]:
    """The package family name, e.g. ``Publisher.App_8wekyb3d8bbwe``."""
    return _package_string("GetCurrentPackageFamilyName")


def is_packaged() -> bool:
    """Return True when this process runs with MSIX package identity."""
    return package_family_name() is not None


def _environ(
    environ: Optional[MutableMapping[str, str]],
) -> MutableMapping[str, str]:
    return os.environ if environ is None else environ


def package_data_dir(
    family: Optional[str], environ: Optional[MutableMapping[str, str]] = None
) -> Optional[Path]:
    """The package's ``LocalCache`` folder, or None when unpackaged."""
    base = _environ(environ).get("LOCALAPPDATA")
    if not family or not base:
        return None
    return Path(base, "Packages", family, "LocalCache")


def local_data_dir(environ: Optional[MutableMapping[str, str]] = None) -> Path:
    """Per-user working data (e.g. the Explorer queue) for this build."""
    environ = _environ(environ)
    packaged = package_data_dir(package_family_name(), environ)
    if packaged is not None:
        return packaged
    return Path(environ["LOCALAPPDATA"]) / "ParrotIA"


def packaged_model_cache(
    family: Optional[str], environ: Optional[MutableMapping[str, str]] = None
) -> Optional[Path]:
    """Model cache for the Store package; an explicit HF setting always wins."""
    environ = _environ(environ)
    if environ.get("HF_HOME") or environ.get("HF_HUB_CACHE"):
        return None
    data = package_data_dir(family, environ)
    return data / "huggingface" if data is not None else None


def configure_packaged_environment(
    environ: Optional[MutableMapping[str, str]] = None,
) -> bool:
    """Apply package-only defaults; call before huggingface_hub is imported.

    Returns whether the process is packaged.
    """
    environ = _environ(environ)
    family = package_family_name()
    cache = packaged_model_cache(family, environ)
    if cache is not None:
        environ["HF_HOME"] = str(cache)
    return family is not None
