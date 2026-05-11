"""Platform adapter package — returns the right adapter for the current OS."""

import sys


def get_adapter():
    """Return a PlatformAdapter instance for the current platform."""
    if sys.platform == "win32":
        from backend.platform_adapter.windows import WindowsAdapter
        return WindowsAdapter()
    elif sys.platform == "darwin":
        from backend.platform_adapter.macos import MacOSAdapter
        return MacOSAdapter()
    else:
        from backend.platform_adapter.windows import WindowsAdapter
        return WindowsAdapter()
