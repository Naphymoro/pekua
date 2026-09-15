"""Credential vault ports and a local encrypted provider.

Production deployments should bind ``ExternalSecretVault`` to a managed KMS/secret
manager. Plaintext secrets are never returned by connector configuration APIs.
"""

from __future__ import annotations

import base64
import json
import os
import secrets
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


@dataclass(frozen=True)
class SecretContext:
    tenant_id: str
    connector_id: str
    version: int

    def aad(self) -> bytes:
        return json.dumps(self.__dict__, sort_keys=True, separators=(",", ":")).encode()


class SecretVault(ABC):
    @abstractmethod
    def put(self, context: SecretContext, plaintext: bytes) -> str: ...

    @abstractmethod
    def get(self, context: SecretContext, reference: str) -> bytes: ...

    @abstractmethod
    def revoke(self, reference: str) -> None: ...


class ExternalSecretVault(SecretVault):
    """Production port for Vault, AWS/GCP/Azure secret managers, or equivalent."""

    @abstractmethod
    def healthcheck(self) -> bool: ...


class EnvEncryptedVault(SecretVault):
    """Local/dev encrypted vault. Requires a base64 32-byte key in the environment."""

    def __init__(self, directory: Path, key_env: str = "PEKUA_DEV_VAULT_KEY") -> None:
        encoded = os.environ.get(key_env)
        if not encoded:
            raise RuntimeError(f"{key_env} must be configured; plaintext fallback is forbidden")
        try:
            key = base64.urlsafe_b64decode(encoded)
        except Exception as exc:
            raise RuntimeError(f"{key_env} is not valid URL-safe base64") from exc
        if len(key) != 32:
            raise RuntimeError(f"{key_env} must decode to exactly 32 bytes")
        self._cipher = AESGCM(key)
        self._directory = directory
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)

    def _path(self, reference: str) -> Path:
        token = reference.removeprefix("secret://")
        if not token or any(char not in "0123456789abcdef" for char in token):
            raise ValueError("Invalid secret reference")
        return self._directory / f"{token}.json"

    def put(self, context: SecretContext, plaintext: bytes) -> str:
        nonce = secrets.token_bytes(12)
        payload = self._cipher.encrypt(nonce, plaintext, context.aad())
        reference = f"secret://{secrets.token_hex(24)}"
        path = self._path(reference)
        path.write_text(
            json.dumps(
                {
                    "v": 1,
                    "nonce": base64.b64encode(nonce).decode(),
                    "ciphertext": base64.b64encode(payload).decode(),
                }
            )
        )
        path.chmod(0o600)
        return reference

    def get(self, context: SecretContext, reference: str) -> bytes:
        path = self._path(reference)
        if not path.exists():
            raise KeyError("Secret is unavailable or revoked")
        envelope = json.loads(path.read_text())
        if envelope.get("v") != 1:
            raise ValueError("Unsupported secret envelope")
        return self._cipher.decrypt(
            base64.b64decode(envelope["nonce"]),
            base64.b64decode(envelope["ciphertext"]),
            context.aad(),
        )

    def revoke(self, reference: str) -> None:
        self._path(reference).unlink(missing_ok=True)
