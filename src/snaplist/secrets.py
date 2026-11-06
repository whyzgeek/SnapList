import os

import keyring


class SecretStore:
    """Store encrypted tokens in the OS keyring, with an env fallback.

    Tokens never leave the machine unless the user publishes. Nothing here is
    logged or written to the database.
    """

    def __init__(self, key_name: str) -> None:
        self.key_name = key_name

    def _env_key(self) -> str:
        return f"SNAPLIST_{self.key_name.upper()}"

    def set(self, value: str) -> None:
        try:
            keyring.set_password(self.key_name, self.key_name, value)
            return
        except Exception:
            pass
        os.environ[self._env_key()] = value

    def get(self) -> str | None:
        val = os.environ.get(self._env_key())
        if val:
            return val
        try:
            return keyring.get_password(self.key_name, self.key_name)
        except Exception:
            return None
