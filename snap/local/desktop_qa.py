"""Host-side isolated portal for installed-Snap desktop integration QA.

Run under dbus-run-session and Xvfb with system Python's dbus/gi packages.
Arguments: REVIEW_DIRECTORY CLIENT_COMMAND [CLIENT_ARGUMENTS...]
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib


def main() -> None:
    expected = os.environ.get("PARROTIA_DESKTOP_QA_BUS")
    if expected is None:
        # A filesystem socket under /tmp would be hidden by Snap's private /tmp.
        # Use a private abstract session socket, never the real desktop's bus.
        address = "unix:abstract=/tmp/dbus-parrotia-qa-" + uuid.uuid4().hex
        config = Path("/usr/share/dbus-1/session.conf").read_text()
        config, count = re.subn(
            r"<listen>.*?</listen>", f"<listen>{address}</listen>", config
        )
        if count != 1:
            raise SystemExit("Expected one session-bus listener in the test config")
        with tempfile.TemporaryDirectory(prefix="parrotia-desktop-bus-") as temporary:
            path = Path(temporary) / "session.conf"
            path.write_text(config)
            result = subprocess.run(
                [
                    "dbus-run-session",
                    "--config-file",
                    str(path),
                    "--",
                    sys.executable,
                    __file__,
                    *sys.argv[1:],
                ],
                env={**os.environ, "PARROTIA_DESKTOP_QA_BUS": address},
                check=False,
            )
        raise SystemExit(result.returncode)
    address = os.environ.get("DBUS_SESSION_BUS_ADDRESS", "")
    if (
        not expected.startswith("unix:abstract=/tmp/dbus-parrotia-qa-")
        or address.split(",")[0] != expected
    ):
        raise SystemExit("This QA requires its own private test bus.")
    directory = Path(sys.argv[1]).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    mode = directory / "mode"
    mode.write_text("1")
    DBusGMainLoop(set_as_default=True)
    bus = dbus.SessionBus()
    name = dbus.service.BusName(
        "org.freedesktop.portal.Desktop", bus=bus, do_not_queue=True
    )

    class Settings(dbus.service.Object):
        @dbus.service.method(
            "org.freedesktop.portal.Settings", in_signature="ss", out_signature="v"
        )
        def ReadOne(self, namespace, key):
            assert (namespace, key) == ("org.freedesktop.appearance", "color-scheme")
            return dbus.UInt32(int(mode.read_text()), variant_level=1)

        @dbus.service.method(
            "org.freedesktop.portal.Settings", in_signature="ss", out_signature="v"
        )
        def Read(self, namespace, key):
            return self.ReadOne(namespace, key)

    portal = Settings(name, "/org/freedesktop/portal/desktop")
    loop = GLib.MainLoop()
    deadline = time.monotonic() + 120
    with (
        (directory / "desktop.json").open("w") as report,
        (directory / "desktop.log").open("w") as log,
    ):
        command = sys.argv[2:]
        environment = dict(os.environ)
        if command == ["parrotia.check"]:
            # Let snap run perform its normal cgroup tracking before switching
            # the test client to our isolated portal bus inside confinement.
            environment.pop("DBUS_SESSION_BUS_ADDRESS", None)
            command = [
                "snap",
                "run",
                "--shell",
                "parrotia.check",
                "-c",
                'export DBUS_SESSION_BUS_ADDRESS="$PARROTIA_DESKTOP_QA_BUS"; '
                'exec "$SNAP/bin/parrotia-env" "$SNAP/bin/python3" '
                '"$SNAP/share/parrotia/check.py" "$@"',
                "desktop-qa",
            ]
        process = subprocess.Popen(
            [*command, "--exercise-desktop", str(mode)],
            stdout=report,
            stderr=log,
            env=environment,
        )

        def finished():
            if process.poll() is not None or time.monotonic() >= deadline:
                loop.quit()
                return False
            return True

        GLib.timeout_add(50, finished)
        try:
            loop.run()
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            portal.remove_from_connection()
    if process.returncode:
        raise SystemExit((directory / "desktop.log").read_text())
    result = json.loads((directory / "desktop.json").read_text())
    assert result["desktop"]["appearance_transitions"] == ["Dark", "Light", "Dark"]
    print(json.dumps(result["desktop"], indent=2))


if __name__ == "__main__":
    main()
