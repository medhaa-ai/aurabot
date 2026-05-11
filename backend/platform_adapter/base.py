"""Abstract platform adapter interface."""

import abc


class PlatformAdapter(abc.ABC):
    """Defines the platform-specific operations AuraBot may need."""

    @abc.abstractmethod
    def open_url(self, url: str) -> None:
        """Open a URL in the system's default browser."""

    @abc.abstractmethod
    def notify(self, title: str, message: str) -> None:
        """Show a system notification."""

    @abc.abstractmethod
    def get_data_dir(self) -> str:
        """Return the path to the user-level AuraBot data directory."""
