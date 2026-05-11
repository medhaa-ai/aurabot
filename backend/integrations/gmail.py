"""Backward-compat shim — real implementation in gmail_client.py."""

from backend.integrations.gmail_client import *  # noqa: F401, F403
from backend.integrations.gmail_client import _client_config, _get_credentials  # noqa: F401
