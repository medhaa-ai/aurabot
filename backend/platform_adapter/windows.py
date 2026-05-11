"""Windows platform adapter."""

import os
import subprocess
import webbrowser
from pathlib import Path

from backend.platform_adapter.base import PlatformAdapter


class WindowsAdapter(PlatformAdapter):

    def open_url(self, url: str) -> None:
        webbrowser.open(url)

    def notify(self, title: str, message: str) -> None:
        # Electron handles notifications on Windows via the IPC bridge.
        # This is a no-op stub kept for parity with the interface.
        pass

    def get_data_dir(self) -> str:
        return str(Path.home() / ".aurabot")
