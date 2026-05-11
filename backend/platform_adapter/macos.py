"""macOS platform adapter."""

import subprocess
import webbrowser
from pathlib import Path

from backend.platform_adapter.base import PlatformAdapter


class MacOSAdapter(PlatformAdapter):

    def open_url(self, url: str) -> None:
        subprocess.run(["open", url], check=False)

    def notify(self, title: str, message: str) -> None:
        script = f'display notification "{message}" with title "{title}"'
        subprocess.run(["osascript", "-e", script], check=False)

    def get_data_dir(self) -> str:
        return str(Path.home() / ".aurabot")
