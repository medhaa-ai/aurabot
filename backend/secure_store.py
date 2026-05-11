"""Encrypted key/secret storage using Fernet + OS keyring.

Architecture:
  - A random Fernet key is generated once and stored in the OS keyring
    (Windows Credential Manager on Windows, Keychain on macOS).
  - Encrypted secrets are stored in ~/.aurabot/secrets.enc as a JSON dict
    of {key: base64_fernet_token}.
  - Plain settings (theme, name, timezone) stay in settings.json unencrypted.
  - Sensitive keys (API keys, OAuth secrets) always go through this module.
"""

import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)

SECRETS_PATH    = Path.home() / ".aurabot" / "secrets.enc"
KEYRING_SERVICE = "AuraBot"
KEYRING_USER    = "fernet_master_key"

SENSITIVE_KEYS = frozenset({
    "anthropic_key",
    "serpapi_key",
    "google_client_id",
    "google_client_secret",
})


# ── Key management ─────────────────────────────────────────────────────────

def _get_or_create_fernet_key() -> bytes:
    """Load master Fernet key from OS keyring, creating one if absent."""
    # Try OS keyring first (Windows Credential Manager / macOS Keychain)
    try:
        import keyring
        stored = keyring.get_password(KEYRING_SERVICE, KEYRING_USER)
        if stored:
            return stored.encode()

        from cryptography.fernet import Fernet
        new_key = Fernet.generate_key().decode()
        keyring.set_password(KEYRING_SERVICE, KEYRING_USER, new_key)
        log.info("Generated new Fernet key, stored in system keyring")
        return new_key.encode()

    except Exception as exc:
        log.warning("System keyring unavailable (%s) — using local key file fallback", exc)
        return _local_key_fallback()


def _local_key_fallback() -> bytes:
    """Store key in ~/.aurabot/.key when keyring is unavailable.
    Less secure than keyring but functional. File is chmod 600.
    """
    key_path = Path.home() / ".aurabot" / ".key"
    if key_path.exists():
        try:
            return key_path.read_bytes().strip()
        except Exception:
            pass

    from cryptography.fernet import Fernet
    new_key = Fernet.generate_key()
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_bytes(new_key + b"\n")
    try:
        import stat
        key_path.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 0o600
    except Exception:
        pass  # Windows doesn't support Unix perms — acceptable
    log.info("Fernet key stored at local fallback path %s", key_path)
    return new_key


def _get_fernet():
    from cryptography.fernet import Fernet
    return Fernet(_get_or_create_fernet_key())


# ── Low-level read/write ───────────────────────────────────────────────────

def _load_encrypted_store() -> dict:
    if not SECRETS_PATH.exists():
        return {}
    try:
        return json.loads(SECRETS_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        log.error("Could not read secrets store: %s", exc)
        return {}


def _save_encrypted_store(data: dict) -> None:
    SECRETS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SECRETS_PATH.write_text(json.dumps(data), encoding="utf-8")


# ── Public API ─────────────────────────────────────────────────────────────

def set_secret(key: str, value: str) -> None:
    """Encrypt and persist a secret. Does nothing if value is empty."""
    if not value or not value.strip():
        return
    try:
        encrypted = _get_fernet().encrypt(value.encode()).decode()
        store = _load_encrypted_store()
        store[key] = encrypted
        _save_encrypted_store(store)
        log.info("Encrypted secret saved: %s", key)
    except Exception as exc:
        log.error("Failed to save secret %s: %s", key, exc)
        raise RuntimeError(f"Could not save secret '{key}': {exc}") from exc


def get_secret(key: str, default: str = "") -> str:
    """Decrypt and return a secret. Returns default if key absent or decrypt fails."""
    store = _load_encrypted_store()
    if key not in store:
        return default
    try:
        return _get_fernet().decrypt(store[key].encode()).decode()
    except Exception as exc:
        log.error("Failed to decrypt secret %s: %s", key, exc)
        return default


def has_secret(key: str) -> bool:
    return key in _load_encrypted_store()


def delete_secret(key: str) -> None:
    store = _load_encrypted_store()
    if key in store:
        del store[key]
        _save_encrypted_store(store)
        log.info("Deleted secret: %s", key)


def list_secret_keys() -> list[str]:
    """Return list of keys that have stored (encrypted) values — not the values."""
    return list(_load_encrypted_store().keys())
