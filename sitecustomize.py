"""Project-local Python startup customizations.

On Windows, Python's ``platform.uname()`` may query WMI before returning
``platform.machine()``. If WMI/CIM is unhealthy, importing packages that call
``platform.machine()`` during startup, notably pandas, can hang before the app
reaches its own runtime code.
"""

from __future__ import annotations

import os
import platform


def _prime_windows_platform_uname_cache() -> None:
    if os.name != "nt":
        return
    if getattr(platform, "_uname_cache", None) is not None:
        return
    uname_result = getattr(platform, "uname_result", None)
    if uname_result is None:
        return

    machine = (
        os.environ.get("PROCESSOR_ARCHITEW6432")
        or os.environ.get("PROCESSOR_ARCHITECTURE")
        or "AMD64"
    )
    node = os.environ.get("COMPUTERNAME", "")
    platform._uname_cache = uname_result("Windows", node, "", "", machine)


_prime_windows_platform_uname_cache()
